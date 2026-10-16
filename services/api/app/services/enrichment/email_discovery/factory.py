from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import ProviderName, ProviderType
from app.services.provider_credentials.service import (
    _as_str,
    decrypt_provider_config,
    get_active_credential,
)

from .hunter_provider import HunterEmailDiscoveryProvider


def resolve_email_discovery(
    db: Session,
    workspace_id: int | None = None,
) -> tuple[HunterEmailDiscoveryProvider | None, bool]:
    """The provider to use and whether its lookups count against the plan (platform key only)."""
    # 1. The workspace's own active Hunter credential: never metered.
    if workspace_id is not None:
        credential = get_active_credential(db, workspace_id, ProviderType.EMAIL_DISCOVERY)
        if credential and _as_str(credential.provider_name) == ProviderName.HUNTER.value:
            api_key = decrypt_provider_config(credential).get("api_key")
            if api_key:
                return HunterEmailDiscoveryProvider(api_key=str(api_key)), False

    # 2. Platform-level fallback from the environment: metered.
    if not settings.hunter_enabled or settings.email_discovery_provider != "hunter":
        return None, False
    if not settings.hunter_api_key:
        return None, False
    return HunterEmailDiscoveryProvider(api_key=settings.hunter_api_key), True


def get_email_discovery_provider(
    db: Session,
    workspace_id: int | None = None,
) -> HunterEmailDiscoveryProvider | None:
    return resolve_email_discovery(db, workspace_id)[0]
