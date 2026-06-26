from sqlalchemy.orm import Session

from app.models.enums import ProviderName, ProviderType
from app.services.provider_credentials.service import _as_str, decrypt_provider_config, get_active_credential
from app.services.sending.external_providers import (
    MailgunEmailSender,
    ResendEmailSender,
    SendGridEmailSender,
    SmtpEmailSender,
)
from app.services.sending.mock_provider import MockEmailSender


def get_email_sender_for_user(db: Session, user_id: int):
    credential = get_active_credential(db, user_id, ProviderType.EMAIL)
    if credential is None or ProviderName(_as_str(credential.provider_name)) == ProviderName.MOCK:
        return MockEmailSender()

    config = decrypt_provider_config(credential)
    provider_name = ProviderName(_as_str(credential.provider_name))

    if provider_name == ProviderName.SMTP:
        return SmtpEmailSender(
            host=str(config.get("host", "")),
            port=int(config.get("port", 587)),
            username=str(config.get("username", "")),
            password=str(config.get("password", "")),
            from_email=str(config.get("from_email", "")),
            from_name=str(config.get("from_name") or "") or None,
            use_tls=bool(config.get("use_tls", True)),
        )
    if provider_name == ProviderName.RESEND:
        return ResendEmailSender(
            api_key=str(config.get("api_key", "")),
            from_email=str(config.get("from_email", "")),
            from_name=str(config.get("from_name") or "") or None,
        )
    if provider_name == ProviderName.SENDGRID:
        return SendGridEmailSender(
            api_key=str(config.get("api_key", "")),
            from_email=str(config.get("from_email", "")),
            from_name=str(config.get("from_name") or "") or None,
        )
    if provider_name == ProviderName.MAILGUN:
        return MailgunEmailSender(
            api_key=str(config.get("api_key", "")),
            domain=str(config.get("domain", "")),
            from_email=str(config.get("from_email", "")),
            from_name=str(config.get("from_name") or "") or None,
        )

    return MockEmailSender()


def is_mock_email_provider_active(db: Session, user_id: int) -> bool:
    credential = get_active_credential(db, user_id, ProviderType.EMAIL)
    return credential is None or ProviderName(_as_str(credential.provider_name)) == ProviderName.MOCK
