from __future__ import annotations

from urllib.parse import quote

from app.core.config import settings
from app.services.platform_email.mailer import TransactionalEmail


def _link(path: str, token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}{path}?token={quote(token)}"


def verification_email(to: str, name: str, token: str) -> TransactionalEmail:
    link = _link("/verify-email", token)
    return TransactionalEmail(
        to=to,
        subject=f"Confirm your {settings.app_name} email",
        text=(
            f"Hi {name},\n\n"
            f"Please confirm your email address to finish setting up {settings.app_name}:\n\n"
            f"{link}\n\n"
            "This link expires in 48 hours. If you didn't sign up, you can ignore this email.\n"
        ),
        tags={"kind": "verify"},
    )


def password_reset_email(to: str, name: str, token: str) -> TransactionalEmail:
    link = _link("/reset-password", token)
    return TransactionalEmail(
        to=to,
        subject=f"Reset your {settings.app_name} password",
        text=(
            f"Hi {name},\n\n"
            "We received a request to reset your password. Use this link to choose a new one:\n\n"
            f"{link}\n\n"
            "This link expires in 1 hour. If you didn't ask for this, you can ignore this email; "
            "your password stays the same.\n"
        ),
        tags={"kind": "reset"},
    )


def invitation_email(to: str, inviter: str, workspace: str, token: str) -> TransactionalEmail:
    link = f"{settings.frontend_url.rstrip('/')}/invite/{quote(token)}"
    return TransactionalEmail(
        to=to,
        subject=f"{inviter} invited you to {workspace} on {settings.app_name}",
        text=(
            f"{inviter} has invited you to join the {workspace} workspace on "
            f"{settings.app_name}.\n\n"
            f"Accept the invitation here:\n\n{link}\n\n"
            "This invitation expires in 7 days.\n"
        ),
        tags={"kind": "invite"},
    )
