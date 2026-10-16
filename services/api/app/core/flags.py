"""Feature flags: a global default from settings (FEATURE_*) with per-workspace overrides.

Platform admins can switch a flag on or off for one workspace (Admin > Workspaces) without
changing the global setting, e.g. to pilot the public API with a few customers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings

if TYPE_CHECKING:
    from app.models.workspace import Workspace

FLAGS: dict[str, str] = {
    "ai_emails": "AI drafting and reply labelling",
    "imap": "IMAP inbox polling",
    "inbound_webhooks": "Provider webhooks for bounces and replies",
    "sso": "Single sign-on",
    "public_api": "Public API and outbound webhooks",
}


def feature_enabled(name: str, workspace: Workspace | None = None) -> bool:
    if name not in FLAGS:
        raise ValueError(f"Unknown feature flag {name}")
    if workspace is not None:
        override = (workspace.feature_flags or {}).get(name)
        if override is not None:
            return bool(override)
    return bool(getattr(settings, f"feature_{name}"))
