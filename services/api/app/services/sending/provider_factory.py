from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ProviderName, ProviderType
from app.models.provider_credential import ProviderCredential
from app.services.provider_credentials.service import (
    _as_str,
    decrypt_provider_config,
    get_active_credential,
)
from app.services.sending.base import EmailSender
from app.services.sending.external_providers import (
    MailgunEmailSender,
    ResendEmailSender,
    SendGridEmailSender,
    SmtpEmailSender,
)
from app.services.sending.mock_provider import MockEmailSender


def _sender_from_credential(credential: ProviderCredential | None) -> EmailSender:
    if credential is None or ProviderName(_as_str(credential.provider_name)) == ProviderName.MOCK:
        return MockEmailSender()

    config = decrypt_provider_config(credential)
    provider_name = ProviderName(_as_str(credential.provider_name))
    from_email = str(config.get("from_email", ""))
    from_name = str(config.get("from_name") or "") or None

    if provider_name == ProviderName.SMTP:
        return SmtpEmailSender(
            host=str(config.get("host", "")),
            port=int(config.get("port", 587)),
            username=str(config.get("username", "")),
            password=str(config.get("password", "")),
            from_email=from_email,
            from_name=from_name,
            use_tls=bool(config.get("use_tls", True)),
        )
    if provider_name == ProviderName.RESEND:
        return ResendEmailSender(str(config.get("api_key", "")), from_email, from_name)
    if provider_name == ProviderName.SENDGRID:
        return SendGridEmailSender(str(config.get("api_key", "")), from_email, from_name)
    if provider_name == ProviderName.MAILGUN:
        return MailgunEmailSender(
            api_key=str(config.get("api_key", "")),
            domain=str(config.get("domain", "")),
            from_email=from_email,
            from_name=from_name,
        )
    return MockEmailSender()


def resolve_sending_credential(
    db: Session,
    workspace_id: int,
    credential_id: int | None = None,
) -> ProviderCredential | None:
    """The campaign's chosen credential (if any and still valid), else the active one."""
    if credential_id is not None:
        credential = db.scalar(
            select(ProviderCredential).where(
                ProviderCredential.id == credential_id,
                ProviderCredential.workspace_id == workspace_id,
                ProviderCredential.provider_type == ProviderType.EMAIL,
            ),
        )
        if credential is not None:
            return credential
    return get_active_credential(db, workspace_id, ProviderType.EMAIL)


def resolve_sender(
    db: Session,
    workspace_id: int,
    credential_id: int | None = None,
) -> tuple[EmailSender, ProviderCredential | None]:
    credential = resolve_sending_credential(db, workspace_id, credential_id)
    return _sender_from_credential(credential), credential


def get_email_sender_for_workspace(db: Session, workspace_id: int) -> EmailSender:
    return resolve_sender(db, workspace_id)[0]


def is_mock_email_provider_active(db: Session, workspace_id: int) -> bool:
    credential = get_active_credential(db, workspace_id, ProviderType.EMAIL)
    return (
        credential is None or ProviderName(_as_str(credential.provider_name)) == ProviderName.MOCK
    )
