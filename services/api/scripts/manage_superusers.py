"""Grant, revoke or list platform superusers (admin back office access).

    python -m scripts.manage_superusers list
    python -m scripts.manage_superusers grant ops@example.com
    python -m scripts.manage_superusers revoke ops@example.com

Superusers are only ever granted here, never through the API.
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.user import User


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("action", choices=["list", "grant", "revoke"])
    parser.add_argument("email", nargs="?")
    args = parser.parse_args(argv)

    db = SessionLocal()
    db.info["tenant_bypass"] = True
    try:
        if args.action == "list":
            for user in db.scalars(
                select(User).where(User.is_superuser.is_(True)).order_by(User.email)
            ):
                print(
                    f"{user.email}\t2FA={'on' if user.mfa_enabled else 'OFF'}\tactive={user.is_active}"
                )
            return 0
        if not args.email:
            parser.error("email is required for grant and revoke")
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            print(f"No user with email {args.email}", file=sys.stderr)
            return 1
        user.is_superuser = args.action == "grant"
        user.token_version += 1  # outstanding access tokens are replaced on the next refresh
        db.add(
            AuditLog(
                workspace_id=None,
                actor_id=None,
                action=f"admin.superuser_{'granted' if user.is_superuser else 'revoked'}",
                entity_type="user",
                entity_id=user.id,
                metadata_={"email": user.email, "via": "cli"},
            )
        )
        db.commit()
        print(f"{user.email} is {'now' if user.is_superuser else 'no longer'} a superuser")
        if user.is_superuser and not user.mfa_enabled:
            print("Note: they must turn on two-factor authentication before the admin area opens.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
