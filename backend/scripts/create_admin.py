"""Create or update an admin user.

Usage::

    cd backend
    python -m scripts.create_admin --email admin@example.com --password 'Passw0rd!'

If a user with that email already exists, the password and role are
overwritten in place. Run after `alembic upgrade head` so the `users`
table exists.
"""
from __future__ import annotations

import argparse
import sys

from db.session import get_sessionmaker, reset_engine
from db.models.role import ROLE_ADMIN, ROLES
from repositories import user_repo
from services.password_service import hash_password


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create or update an admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--display-name", default="Administrator")
    parser.add_argument("--role", default=ROLE_ADMIN, choices=ROLES)
    args = parser.parse_args(argv)

    reset_engine()
    SessionLocal = get_sessionmaker()
    session = SessionLocal()
    try:
        existing = user_repo.get_user_by_email(session, email=args.email)
        if existing is None:
            user = user_repo.create_user(
                session,
                email=args.email,
                password_hash=hash_password(args.password),
                role=args.role,
                display_name=args.display_name,
            )
            session.commit()
            print(f"created user id={user.id} email={user.email} role={user.role}")
        else:
            existing.password_hash = hash_password(args.password)
            existing.role = args.role
            existing.display_name = args.display_name
            existing.is_active = True
            session.commit()
            print(
                f"updated user id={existing.id} email={existing.email} role={existing.role}"
            )
    finally:
        session.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
