from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.enums import ProviderType
from app.services.provider_credentials.service import get_active_credential, decrypt_provider_config
from .hunter_provider import HunterEmailDiscoveryProvider


def get_email_discovery_provider(db: Session, user_id: int | None = None):
    # 1. Try DB if user_id provided
    if user_id is not None:
        credential = get_active_credential(db, user_id, ProviderType.EMAIL_DISCOVERY)
        if credential and credential.provider_name.value == "hunter":
            config = decrypt_provider_config(credential)
            api_key = config.get("api_key")
            if api_key:
                return HunterEmailDiscoveryProvider(api_key=str(api_key))

    # 2. Try ENV fallback
    if not getattr(settings, "hunter_enabled", False):
        return None
        
    if getattr(settings, "email_discovery_provider", "") != "hunter":
        return None

    api_key = getattr(settings, "hunter_api_key", "")
    if not api_key:
        return None

    return HunterEmailDiscoveryProvider(api_key=api_key)
