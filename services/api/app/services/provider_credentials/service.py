import json
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.core.security import (
    decrypt_secret_payload,
    encrypt_secret_payload,
    mask_secret_value,
)
from app.models.audit_log import AuditLog
from app.models.enums import ProviderCredentialStatus, ProviderName, ProviderType
from app.models.provider_credential import ProviderCredential

DISPLAY_NAMES: dict[ProviderName, str] = {
    ProviderName.MOCK: "Mock (local testing)",
    ProviderName.GOOGLE_CSE: "Google Custom Search",
    ProviderName.BING: "Bing Web Search",
    ProviderName.SERPAPI: "SerpAPI",
    ProviderName.SMTP: "SMTP",
    ProviderName.RESEND: "Resend",
    ProviderName.SENDGRID: "SendGrid",
    ProviderName.MAILGUN: "Mailgun",
    ProviderName.HUNTER: "Hunter.io",
    ProviderName.IMAP: "IMAP inbox",
    ProviderName.GROQ: "Groq",
    ProviderName.OPENAI: "OpenAI",
    ProviderName.GEMINI: "Google Gemini",
    ProviderName.GMAIL: "Gmail / Google Workspace",
    ProviderName.OUTLOOK: "Microsoft 365 / Outlook",
    ProviderName.ZEROBOUNCE: "ZeroBounce",
    ProviderName.NEVERBOUNCE: "NeverBounce",
}

SEARCH_PROVIDERS = {
    ProviderName.MOCK,
    ProviderName.GOOGLE_CSE,
    ProviderName.BING,
    ProviderName.SERPAPI,
}
EMAIL_PROVIDERS = {
    ProviderName.MOCK,
    ProviderName.SMTP,
    ProviderName.RESEND,
    ProviderName.SENDGRID,
    ProviderName.MAILGUN,
}

EMAIL_DISCOVERY_PROVIDERS = {
    ProviderName.HUNTER,
}

INBOX_PROVIDERS = {ProviderName.IMAP}
VERIFICATION_PROVIDERS = {ProviderName.ZEROBOUNCE, ProviderName.NEVERBOUNCE}
LLM_PROVIDERS = {ProviderName.GROQ, ProviderName.OPENAI, ProviderName.GEMINI}

ALLOWED_PROVIDERS: dict[ProviderType, set[ProviderName]] = {
    ProviderType.SEARCH: SEARCH_PROVIDERS,
    ProviderType.EMAIL: EMAIL_PROVIDERS,
    ProviderType.EMAIL_DISCOVERY: EMAIL_DISCOVERY_PROVIDERS,
    ProviderType.INBOX: INBOX_PROVIDERS,
    ProviderType.LLM: {*LLM_PROVIDERS, ProviderName.MOCK},
    ProviderType.EMAIL_VERIFICATION: {*VERIFICATION_PROVIDERS, ProviderName.MOCK},
}

# Config fields holding webhook verification material, per sending provider.
WEBHOOK_SECRET_FIELDS = {
    ProviderName.RESEND: "webhook_secret",
    ProviderName.SENDGRID: "event_public_key",
    ProviderName.MAILGUN: "webhook_signing_key",
}

SECRET_FIELDS = {
    "api_key",
    "password",
    "search_engine_id",
}


def _as_str(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _log_audit(
    db: Session,
    actor_id: int | None,
    action: str,
    entity_id: int,
    metadata: dict | None = None,
    *,
    workspace_id: int | None = None,
) -> None:
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_id=actor_id,
            action=action,
            entity_type="provider_credential",
            entity_id=entity_id,
            metadata_=metadata,
        ),
    )


def build_masked_summary(provider_name: ProviderName, config: dict) -> str:
    if provider_name == ProviderName.MOCK:
        return "No credentials required"

    parts: list[str] = []
    if provider_name == ProviderName.GOOGLE_CSE:
        if config.get("api_key"):
            parts.append(f"API key {mask_secret_value(str(config['api_key']))}")
        if config.get("search_engine_id"):
            parts.append(f"CX {mask_secret_value(str(config['search_engine_id']))}")
    elif provider_name == ProviderName.BING:
        if config.get("api_key"):
            parts.append(f"API key {mask_secret_value(str(config['api_key']))}")
        endpoint = config.get("endpoint") or "https://api.bing.microsoft.com/v7.0/search"
        parts.append(f"Endpoint {endpoint}")
    elif provider_name == ProviderName.SERPAPI:
        if config.get("api_key"):
            parts.append(f"API key {mask_secret_value(str(config['api_key']))}")
    elif provider_name == ProviderName.SMTP:
        parts.append(f"Host {config.get('host', '')}")
        parts.append(f"Port {config.get('port', 587)}")
        if config.get("username"):
            parts.append(f"User {config.get('username')}")
        if config.get("password"):
            parts.append(f"Password {mask_secret_value(str(config['password']))}")
        if config.get("from_email"):
            parts.append(f"From {config.get('from_email')}")
    elif provider_name in {ProviderName.RESEND, ProviderName.SENDGRID}:
        if config.get("api_key"):
            parts.append(f"API key {mask_secret_value(str(config['api_key']))}")
        if config.get("from_email"):
            parts.append(f"From {config.get('from_email')}")
    elif provider_name in {ProviderName.HUNTER, *LLM_PROVIDERS}:
        if config.get("api_key"):
            parts.append(f"API key {mask_secret_value(str(config['api_key']))}")
        if config.get("model"):
            parts.append(f"Model {config.get('model')}")
    elif provider_name == ProviderName.IMAP:
        parts.append(f"Host {config.get('host', '')}")
        if config.get("username"):
            parts.append(f"User {config.get('username')}")
        parts.append(f"Folder {config.get('folder') or 'INBOX'}")
    elif provider_name == ProviderName.MAILGUN:
        if config.get("api_key"):
            parts.append(f"API key {mask_secret_value(str(config['api_key']))}")
        if config.get("domain"):
            parts.append(f"Domain {config.get('domain')}")
        if config.get("from_email"):
            parts.append(f"From {config.get('from_email')}")

    return " · ".join(part for part in parts if part)


def _validate_provider_type_name(provider_type: ProviderType, provider_name: ProviderName) -> None:
    allowed = ALLOWED_PROVIDERS.get(provider_type, set())
    if provider_name not in allowed:
        raise ValueError(f"Provider {provider_name.value} is not valid for {provider_type.value}")


def _required_fields(provider_name: ProviderName) -> list[str]:
    if provider_name == ProviderName.MOCK:
        return []
    if provider_name == ProviderName.GOOGLE_CSE:
        return ["api_key", "search_engine_id"]
    if provider_name == ProviderName.BING:
        return ["api_key"]
    if provider_name == ProviderName.SERPAPI:
        return ["api_key"]
    if provider_name == ProviderName.SMTP:
        return ["host", "port", "username", "password", "from_email"]
    if provider_name in {ProviderName.RESEND, ProviderName.SENDGRID}:
        return ["api_key", "from_email"]
    if provider_name == ProviderName.MAILGUN:
        return ["api_key", "domain", "from_email"]
    if (
        provider_name == ProviderName.HUNTER
        or provider_name in LLM_PROVIDERS | VERIFICATION_PROVIDERS
    ):
        return ["api_key"]
    if provider_name == ProviderName.IMAP:
        return ["host", "username", "password"]
    return []


def _normalize_config(provider_name: ProviderName, config: dict) -> dict:
    normalized = {key: value for key, value in config.items() if value not in (None, "")}
    if provider_name == ProviderName.BING and "endpoint" not in normalized:
        normalized["endpoint"] = "https://api.bing.microsoft.com/v7.0/search"
    if provider_name == ProviderName.SMTP:
        if "port" in normalized:
            normalized["port"] = int(normalized["port"])
        if "use_tls" not in normalized:
            normalized["use_tls"] = True
    if provider_name == ProviderName.IMAP:
        normalized["port"] = int(normalized.get("port") or 993)
        normalized.setdefault("use_ssl", True)
        normalized.setdefault("folder", "INBOX")
    return normalized


def decrypt_provider_config(credential: ProviderCredential) -> dict:
    if not credential.encrypted_config_json:
        return {}
    return json.loads(decrypt_secret_payload(credential.encrypted_config_json))


def get_credential(
    db: Session,
    workspace_id: int,
    credential_id: int,
) -> ProviderCredential | None:
    return db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.id == credential_id,
            ProviderCredential.workspace_id == workspace_id,
        ),
    )


def list_credentials(db: Session, workspace_id: int) -> list[ProviderCredential]:
    return list(
        db.scalars(
            select(ProviderCredential)
            .where(ProviderCredential.workspace_id == workspace_id)
            .order_by(ProviderCredential.provider_type, ProviderCredential.provider_name),
        ).all(),
    )


def get_active_credential(
    db: Session,
    workspace_id: int,
    provider_type: ProviderType,
) -> ProviderCredential | None:
    return db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider_type == provider_type,
            ProviderCredential.is_active.is_(True),
        ),
    )


def upsert_credential(
    db: Session,
    workspace_id: int,
    actor_id: int,
    provider_type: ProviderType,
    provider_name: ProviderName,
    config: dict,
) -> ProviderCredential:
    _validate_provider_type_name(provider_type, provider_name)

    existing = db.scalar(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider_type == provider_type,
            ProviderCredential.provider_name == provider_name,
        ),
    )

    merged_config: dict = {}
    if existing:
        merged_config = decrypt_provider_config(existing)

    incoming = _normalize_config(provider_name, config)
    for key, value in incoming.items():
        if isinstance(value, str) and not value.strip():
            continue
        merged_config[key] = value

    if provider_name == ProviderName.MOCK:
        merged_config = {}

    required = _required_fields(provider_name)
    missing = [field for field in required if not merged_config.get(field)]
    if missing and provider_name != ProviderName.MOCK:
        raise ValueError(f"Missing required fields: {', '.join(missing)}")

    encrypted = encrypt_secret_payload(json.dumps(merged_config))
    masked = build_masked_summary(provider_name, merged_config)
    status = (
        ProviderCredentialStatus.CONFIGURED
        if provider_name == ProviderName.MOCK or merged_config
        else ProviderCredentialStatus.NOT_CONFIGURED
    )

    webhook_field = WEBHOOK_SECRET_FIELDS.get(provider_name)
    if webhook_field and merged_config.get(webhook_field):
        masked = f"{masked} · Webhook verification set" if masked else "Webhook verification set"

    if existing:
        if provider_type == ProviderType.EMAIL and provider_name != ProviderName.MOCK:
            existing.webhook_token = existing.webhook_token or secrets.token_urlsafe(24)
        existing.encrypted_config_json = encrypted
        existing.masked_summary = masked
        existing.status = status
        existing.display_name = DISPLAY_NAMES[provider_name]
        credential = existing
        action = "provider_credential_updated"
    else:
        credential = ProviderCredential(
            workspace_id=workspace_id,
            user_id=actor_id,
            provider_type=provider_type,
            provider_name=provider_name,
            display_name=DISPLAY_NAMES[provider_name],
            encrypted_config_json=encrypted,
            masked_summary=masked,
            is_active=False,
            status=status,
            webhook_token=(
                secrets.token_urlsafe(24)
                if provider_type == ProviderType.EMAIL and provider_name != ProviderName.MOCK
                else None
            ),
        )
        db.add(credential)
        action = "provider_credential_created"

    db.flush()
    _log_audit(
        db,
        actor_id,
        action,
        credential.id,
        {
            "provider_type": _as_str(provider_type),
            "provider_name": _as_str(provider_name),
            "masked_summary": masked,
        },
        workspace_id=workspace_id,
    )
    db.commit()
    db.refresh(credential)
    return credential


def activate_credential(
    db: Session,
    workspace_id: int,
    actor_id: int,
    credential_id: int,
) -> ProviderCredential:
    credential = get_credential(db, workspace_id, credential_id)
    if credential is None:
        raise NotFoundError("Provider credential not found")
    if (
        _as_str(credential.status)
        not in {
            ProviderCredentialStatus.CONFIGURED.value,
            ProviderCredentialStatus.ERROR.value,
        }
        and ProviderName(_as_str(credential.provider_name)) != ProviderName.MOCK
    ):
        raise ValueError("Provider must be configured before activation")

    others = db.scalars(
        select(ProviderCredential).where(
            ProviderCredential.workspace_id == workspace_id,
            ProviderCredential.provider_type == credential.provider_type,
            ProviderCredential.id != credential.id,
        ),
    ).all()
    for other in others:
        other.is_active = False

    credential.is_active = True
    if credential.status == ProviderCredentialStatus.ERROR:
        credential.status = ProviderCredentialStatus.CONFIGURED

    _log_audit(
        db,
        actor_id,
        "provider_credential_activated",
        credential.id,
        {
            "provider_type": _as_str(credential.provider_type),
            "provider_name": _as_str(credential.provider_name),
        },
        workspace_id=workspace_id,
    )
    db.commit()
    db.refresh(credential)
    return credential


def delete_credential(db: Session, workspace_id: int, actor_id: int, credential_id: int) -> None:
    credential = get_credential(db, workspace_id, credential_id)
    if credential is None:
        raise NotFoundError("Provider credential not found")

    metadata = {
        "provider_type": _as_str(credential.provider_type),
        "provider_name": _as_str(credential.provider_name),
    }
    db.delete(credential)
    db.flush()
    _log_audit(
        db,
        actor_id,
        "provider_credential_deleted",
        credential_id,
        metadata,
        workspace_id=workspace_id,
    )
    db.commit()


def record_test_result(
    db: Session,
    credential: ProviderCredential,
    *,
    success: bool,
    message: str,
    actor_id: int | None = None,
) -> ProviderCredential:
    credential.last_tested_at = datetime.now(UTC)
    credential.last_test_status = "success" if success else "error"
    credential.last_test_message = message
    credential.status = (
        ProviderCredentialStatus.CONFIGURED if success else ProviderCredentialStatus.ERROR
    )
    if actor_id is not None:
        _log_audit(
            db,
            actor_id,
            "provider_credential_tested",
            credential.id,
            {
                "provider_type": _as_str(credential.provider_type),
                "provider_name": _as_str(credential.provider_name),
                "success": success,
                "message": message,
            },
            workspace_id=credential.workspace_id,
        )
    db.commit()
    db.refresh(credential)
    return credential


def ensure_default_mock_credentials(db: Session, workspace_id: int, user_id: int) -> None:
    for provider_type, provider_name in (
        (ProviderType.SEARCH, ProviderName.MOCK),
        (ProviderType.EMAIL, ProviderName.MOCK),
    ):
        existing = db.scalar(
            select(ProviderCredential).where(
                ProviderCredential.workspace_id == workspace_id,
                ProviderCredential.provider_type == provider_type,
                ProviderCredential.provider_name == provider_name,
            ),
        )
        if existing:
            continue
        encrypted = encrypt_secret_payload("{}")
        credential = ProviderCredential(
            workspace_id=workspace_id,
            user_id=user_id,
            provider_type=provider_type,
            provider_name=provider_name,
            display_name=DISPLAY_NAMES[provider_name],
            encrypted_config_json=encrypted,
            masked_summary=build_masked_summary(provider_name, {}),
            is_active=True,
            status=ProviderCredentialStatus.CONFIGURED,
        )
        db.add(credential)
    db.flush()


def webhook_urls(credential: ProviderCredential) -> dict[str, str]:
    """URLs to paste into the provider's dashboard for this sending account."""
    from app.core.config import settings

    if not credential.webhook_token:
        return {}
    base = f"{settings.api_public_url.rstrip('/')}/webhooks"
    name = _as_str(credential.provider_name)
    token = credential.webhook_token
    if name == ProviderName.RESEND.value:
        return {"events_and_inbound": f"{base}/resend/{token}"}
    if name in {ProviderName.SENDGRID.value, ProviderName.MAILGUN.value}:
        return {
            "events": f"{base}/{name}/{token}/events",
            "inbound": f"{base}/{name}/{token}/inbound",
        }
    return {}


def configure_warmup(
    db: Session,
    workspace_id: int,
    actor_id: int,
    credential_id: int,
    *,
    enabled: bool,
    start_volume: int,
    daily_increment: int,
    maximum: int | None,
) -> ProviderCredential:
    from datetime import UTC, datetime

    credential = get_credential(db, workspace_id, credential_id)
    if credential is None or _as_str(credential.provider_type) != ProviderType.EMAIL.value:
        raise NotFoundError("Sending account not found")
    if enabled and not credential.warmup_enabled:
        credential.warmup_started_at = datetime.now(UTC)
    credential.warmup_enabled = enabled
    credential.warmup_start_volume = start_volume
    credential.warmup_daily_increment = daily_increment
    credential.warmup_max = maximum
    _log_audit(
        db,
        actor_id,
        "provider_credential_warmup",
        credential.id,
        {"enabled": enabled, "start": start_volume, "increment": daily_increment, "max": maximum},
        workspace_id=workspace_id,
    )
    db.commit()
    db.refresh(credential)
    return credential
