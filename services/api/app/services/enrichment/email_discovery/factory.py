from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import ProviderName, ProviderType
from app.services.provider_credentials.service import (
    _as_str,
    decrypt_provider_config,
    get_active_credential,
)

from .hunter_provider import HunterEmailDiscoveryProvider


def get_email_discovery_provider(
    db: Session,
    user_id: int | None = None,
) -> HunterEmailDiscoveryProvider | None:
    # 1. The account's own active Hunter credential.
    if user_id is not None:
        credential = get_active_credential(db, user_id, ProviderType.EMAIL_DISCOVERY)
        if credential and _as_str(credential.provider_name) == ProviderName.HUNTER.value:
            api_key = decrypt_provider_config(credential).get("api_key")
            if api_key:
                return HunterEmailDiscoveryProvider(api_key=str(api_key))

    # 2. Platform-level fallback from the environment.
    if not settings.hunter_enabled or settings.email_discovery_provider != "hunter":
        return None
    if not settings.hunter_api_key:
        return None
    return HunterEmailDiscoveryProvider(api_key=settings.hunter_api_key)
