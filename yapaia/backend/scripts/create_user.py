"""Create or update a user from the command line.

Usage (inside the backend container):
    python -m scripts.create_user <email> <password> [display_name] [plan]

Examples:
    python -m scripts.create_user test@test.de test1234
    python -m scripts.create_user admin@navi.local admin1234 "Admin" premium
"""

import asyncio
import sys

from sqlalchemy import select

from app.auth import hash_password
from app.db import SessionLocal, init_db
from app.models import User


async def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    email = sys.argv[1].strip().lower()
    password = sys.argv[2]
    display_name = sys.argv[3] if len(sys.argv) > 3 else email.split("@")[0]
    plan = sys.argv[4] if len(sys.argv) > 4 else "premium"

    if plan not in ("free", "premium"):
        print(f"plan must be 'free' or 'premium', got: {plan}")
        sys.exit(1)

    await init_db()

    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if user:
            user.hashed_password = hash_password(password)
            user.display_name = display_name
            user.plan = plan
            user.is_active = True
            action = "updated"
        else:
            user = User(
                email=email,
                hashed_password=hash_password(password),
                display_name=display_name,
                plan=plan,
                is_active=True,
            )
            db.add(user)
            action = "created"

        await db.commit()

    print(f"User {action}:")
    print(f"  Email:    {email}")
    print(f"  Password: {password}")
    print(f"  Name:     {display_name}")
    print(f"  Plan:     {plan}")


if __name__ == "__main__":
    asyncio.run(main())
