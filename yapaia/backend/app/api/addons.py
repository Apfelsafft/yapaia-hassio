"""Generic addon API: per-user install/uninstall, settings CRUD, marketplace proxy."""
import io
import logging
import tarfile
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.addons import manager as addon_manager
from app.auth import get_current_user
from app.config import settings as app_settings
from app.db import get_db
from app.models import AddonUserSettings, User, UserAddon

router = APIRouter(prefix="/api/addons", tags=["addons"])
logger = logging.getLogger(__name__)

MARKETPLACE_URL = "https://marketplace.yapaia.cloud"  # overridden by config if set


def _marketplace_url() -> str:
    return getattr(app_settings, "marketplace_url", MARKETPLACE_URL)


def _marketplace_enabled() -> bool:
    """
    Returns False if the marketplace is intentionally disabled (empty URL).
    In that mode every catalog/install endpoint short-circuits with a clear
    503; the bundled add-ons still work via the local fallback path.
    """
    return bool((_marketplace_url() or "").strip())


# ── Per-user installed list ───────────────────────────────────────────────────

@router.get("/installed")
async def list_installed(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return manifests for add-ons the current user has installed."""
    rows = (await db.execute(
        select(UserAddon).where(UserAddon.user_id == current_user.id)
    )).scalars().all()

    result = []
    for row in rows:
        manifest = addon_manager.manifest_for(row.addon_id)
        if manifest is None:
            # Code not present on server yet — return minimal stub
            manifest = {"id": row.addon_id, "name": row.addon_id,
                        "version": "?", "description": "", "icon": "📦",
                        "author": "", "category": "", "capabilities": [],
                        "settings_schema": [], "code_missing": True}
        manifest = dict(manifest)
        manifest["license_status"] = row.license_status
        result.append(manifest)
    return result


@router.get("/server/available")
async def list_server_available(_: User = Depends(get_current_user)):
    """Add-ons whose code is loaded on this server (installable by any user)."""
    return addon_manager.list_manifests()


# ── Install / Uninstall ───────────────────────────────────────────────────────

class InstallRequest(BaseModel):
    license_key: str | None = None


@router.post("/marketplace/install/{addon_id}")
async def install_from_marketplace(
    addon_id: str,
    body: InstallRequest = InstallRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Install an add-on for the current user.

    If the add-on code is not yet present on this server it is downloaded
    from the marketplace first (any authenticated user may trigger this).
    """
    # 1. Check if user already has it
    existing = (await db.execute(
        select(UserAddon).where(
            UserAddon.user_id == current_user.id,
            UserAddon.addon_id == addon_id,
        )
    )).scalar_one_or_none()
    if existing:
        return {"ok": True, "message": "Bereits installiert"}

    # 2. Validate license key if provided
    license_status = "free"
    if body.license_key:
        license_status = await _validate_license(addon_id, body.license_key)
        if license_status == "invalid":
            raise HTTPException(400, "Ungültiger Lizenzschlüssel")

    # 3. Ensure code is loaded — prefer on-disk bundled code over marketplace download
    if not addon_manager.is_loaded(addon_id):
        from app.db import AsyncSessionLocal
        addon_dir = addon_manager.ADDONS_DIR / addon_id
        if addon_dir.exists() and (addon_dir / "manifest.json").exists():
            # Code already on disk (bundled addon) — just load it
            ok = await addon_manager.reload_addon(addon_id, AsyncSessionLocal)
        else:
            # Download from marketplace then load
            await _download_addon(addon_id)
            ok = await addon_manager.reload_addon(addon_id, AsyncSessionLocal)
        if not ok:
            raise HTTPException(500, "Add-on konnte nicht geladen werden")

    # 4. Register user → addon
    db.add(UserAddon(
        user_id=current_user.id,
        addon_id=addon_id,
        license_key=body.license_key,
        license_status=license_status,
    ))
    await db.commit()
    addon_manager.register_user_addon(current_user.id, addon_id)

    return {"ok": True, "message": f"Add-on '{addon_id}' installiert"}


@router.delete("/{addon_id}")
async def uninstall_addon(
    addon_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove an add-on from the current user's installed list."""
    row = (await db.execute(
        select(UserAddon).where(
            UserAddon.user_id == current_user.id,
            UserAddon.addon_id == addon_id,
        )
    )).scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Add-on nicht installiert")

    await db.delete(row)
    await db.commit()
    addon_manager.unregister_user_addon(current_user.id, addon_id)
    return {"ok": True}


@router.delete("/admin/{addon_id}/purge")
async def admin_purge_addon(
    addon_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Admin: unload add-on code from server and remove from disk."""
    if not current_user.is_admin:
        raise HTTPException(403, "Admin-Rechte erforderlich")

    await addon_manager.unload_addon(addon_id)

    target_dir = addon_manager.ADDONS_DIR / addon_id
    if target_dir.exists():
        import shutil
        shutil.rmtree(target_dir)

    return {"ok": True, "message": f"Add-on '{addon_id}' vom Server entfernt"}


# ── License validation ────────────────────────────────────────────────────────

@router.post("/{addon_id}/validate-license")
async def validate_license_endpoint(
    addon_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    body = await request.json()
    key = body.get("license_key", "")
    if not key:
        raise HTTPException(400, "Kein Lizenzschlüssel angegeben")

    status = await _validate_license(addon_id, key)
    if status in ("valid", "free"):
        row = (await db.execute(
            select(UserAddon).where(
                UserAddon.user_id == current_user.id,
                UserAddon.addon_id == addon_id,
            )
        )).scalar_one_or_none()
        if row:
            row.license_key = key
            row.license_status = status
            await db.commit()

    return {"status": status}


async def _validate_license(addon_id: str, key: str) -> str:
    """Returns 'valid', 'free', 'expired', 'invalid', or 'unverified'."""
    if not _marketplace_enabled():
        # No marketplace configured (HA add-on mode): bundled add-ons are
        # implicitly free; licensed add-ons cannot be activated without a
        # marketplace and will be rejected by the caller via status != valid/free.
        return "free"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{_marketplace_url()}/licenses/validate",
                json={"addon_id": addon_id, "license_key": key},
            )
            if resp.status_code == 200:
                return resp.json().get("status", "invalid")
    except Exception:
        logger.warning("License validation request failed for %s", addon_id)
    # If marketplace unreachable, return unverified — caller decides.
    return "unverified"


# ── Marketplace catalog ───────────────────────────────────────────────────────

@router.get("/marketplace/catalog")
async def marketplace_catalog(_: User = Depends(get_current_user)):
    """Proxy the marketplace catalog so the frontend only needs one CORS origin."""
    if not _marketplace_enabled():
        # In the HA-Add-on context the marketplace is intentionally disabled.
        # Returning an empty catalog (200) keeps the UI usable; the
        # "Marketplace" tab will just show "keine externen Add-ons verfügbar".
        return []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{_marketplace_url()}/catalog")
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(503, f"Marketplace nicht erreichbar: {exc}") from exc


# ── Per-user addon settings ───────────────────────────────────────────────────

@router.get("/{addon_id}/settings")
async def get_addon_settings(
    addon_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AddonUserSettings).where(
            AddonUserSettings.user_id == current_user.id,
            AddonUserSettings.addon_id == addon_id,
        )
    )
    row = result.scalar_one_or_none()
    return row.settings if row else {}


@router.put("/{addon_id}/settings")
async def update_addon_settings(
    addon_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not addon_manager.is_loaded(addon_id):
        raise HTTPException(404, f"Addon '{addon_id}' nicht gefunden")

    body = await request.json()
    result = await db.execute(
        select(AddonUserSettings).where(
            AddonUserSettings.user_id == current_user.id,
            AddonUserSettings.addon_id == addon_id,
        )
    )
    row = result.scalar_one_or_none()
    if row:
        row.settings = body
    else:
        db.add(AddonUserSettings(
            user_id=current_user.id,
            addon_id=addon_id,
            settings=body,
        ))
    await db.commit()
    return {"ok": True}


# ── Generic addon request proxy ───────────────────────────────────────────────
# IMPORTANT: this route must come LAST so the specific routes above take priority.

@router.api_route(
    "/{addon_id}/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
)
async def addon_proxy(
    addon_id: str,
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    addon = addon_manager.get(addon_id)
    if addon is None:
        raise HTTPException(404, f"Addon '{addon_id}' nicht gefunden oder nicht aktiv")

    if not addon_manager.user_has_addon(current_user.id, addon_id):
        raise HTTPException(403, f"Add-on '{addon_id}' ist nicht installiert")

    result = await db.execute(
        select(AddonUserSettings).where(
            AddonUserSettings.user_id == current_user.id,
            AddonUserSettings.addon_id == addon_id,
        )
    )
    row = result.scalar_one_or_none()
    addon_settings = row.settings if row else {}

    return await addon.handle_request(path, request, current_user, db, addon_settings)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _download_addon(addon_id: str) -> None:
    """Download add-on tarball from marketplace and extract to ADDONS_DIR."""
    target_dir = addon_manager.ADDONS_DIR / addon_id
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.get(f"{_marketplace_url()}/addons/{addon_id}/download")
            if resp.status_code == 404:
                raise HTTPException(404, f"Add-on '{addon_id}' im Marketplace nicht gefunden")
            resp.raise_for_status()

        target_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
            tar.extractall(target_dir, filter="data")

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Download of addon %s failed", addon_id)
        raise HTTPException(500, f"Download fehlgeschlagen: {exc}") from exc
