import os
import secrets

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import settings


def _build_database_url() -> str:
    """
    Pick the DATABASE_URL.

    Priority:
    1. Explicit DATABASE_URL env var (used by the HA add-on for SQLite mode).
    2. Postgres URL assembled from the Settings fields (self-host default).
    """
    env_url = os.environ.get("DATABASE_URL", "").strip()
    if env_url:
        return env_url
    return (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


DATABASE_URL = _build_database_url()
IS_SQLITE = DATABASE_URL.startswith("sqlite")

_connect_args: dict = {}
if IS_SQLITE:
    _connect_args["check_same_thread"] = False

engine = create_async_engine(DATABASE_URL, echo=False, connect_args=_connect_args)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
AsyncSessionLocal = SessionLocal  # alias used by addon_manager


class Base(DeclarativeBase):
    pass


async def get_db():
    async with SessionLocal() as session:
        yield session


# ── SQL dialect helpers ──────────────────────────────────────────────────────
# Postgres-specific statements (TIMESTAMPTZ, NOW(), ALTER … SET DEFAULT NOW())
# are gated; SQLite needs softer equivalents. Both engines accept the
# `CREATE TABLE IF NOT EXISTS` and `ALTER TABLE … ADD COLUMN IF NOT EXISTS`
# clauses our migrations rely on (SQLite >= 3.35, Postgres >= 9.6).

def _now_default_clause() -> str:
    return "CURRENT_TIMESTAMP" if IS_SQLITE else "NOW()"


def _timestamptz() -> str:
    return "TIMESTAMP" if IS_SQLITE else "TIMESTAMPTZ"


async def init_db():
    now_default = _now_default_clause()
    ts_type = _timestamptz()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Lightweight in-place schema patches for tables that already exist
        # (create_all does NOT add new columns). Each statement is idempotent.
        await conn.execute(text(
            "ALTER TABLE favorites ADD COLUMN IF NOT EXISTS address VARCHAR(300) NOT NULL DEFAULT ''"
        ))
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        # SQLite cannot add a UNIQUE column via ALTER TABLE — add the column
        # plain, then create a UNIQUE INDEX. Postgres accepts both.
        if IS_SQLITE:
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS gps_push_token VARCHAR(64)"
            ))
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_gps_push_token "
                "ON users(gps_push_token) WHERE gps_push_token IS NOT NULL"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255)"
            ))
            await conn.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_google_id "
                "ON users(google_id) WHERE google_id IS NOT NULL"
            ))
        else:
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS gps_push_token VARCHAR(64) UNIQUE"
            ))
            await conn.execute(text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS google_id VARCHAR(255) UNIQUE"
            ))
        await conn.execute(text(
            "ALTER TABLE favorites ADD COLUMN IF NOT EXISTS show_chip BOOLEAN NOT NULL DEFAULT TRUE"
        ))
        await conn.execute(text(
            "ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS fuel_type VARCHAR(20)"
        ))
        await conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS user_addons (
                user_id VARCHAR(36) REFERENCES users(id) ON DELETE CASCADE,
                addon_id VARCHAR(100) NOT NULL,
                installed_at {ts_type} DEFAULT {now_default},
                license_key VARCHAR(255),
                license_status VARCHAR(20) NOT NULL DEFAULT 'free',
                PRIMARY KEY (user_id, addon_id)
            )
        """))
        # `ALTER COLUMN … SET DEFAULT` is Postgres-only. For SQLite the
        # default set in CREATE TABLE above is already correct (and SQLite
        # cannot alter column defaults retroactively).
        if not IS_SQLITE:
            await conn.execute(text("""
                ALTER TABLE user_addons
                ALTER COLUMN installed_at SET DEFAULT NOW()
            """))
        # Backfill: jeder existierende User ohne Token bekommt einen.
        rows = (await conn.execute(text(
            "SELECT id FROM users WHERE gps_push_token IS NULL OR gps_push_token = ''"
        ))).fetchall()
        for row in rows:
            await conn.execute(
                text("UPDATE users SET gps_push_token = :t WHERE id = :id"),
                {"t": secrets.token_urlsafe(24), "id": row.id},
            )
        # Bootstrap-Admins aus ADMIN_EMAILS env var (komma-getrennt).
        emails = [e.strip().lower() for e in settings.admin_emails.split(",") if e.strip()]
        if emails:
            placeholders = ", ".join(f":e{i}" for i in range(len(emails)))
            params = {f"e{i}": e for i, e in enumerate(emails)}
            await conn.execute(
                text(f"UPDATE users SET is_admin = TRUE WHERE LOWER(email) IN ({placeholders})"),
                params,
            )
