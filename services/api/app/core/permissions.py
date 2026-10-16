"""What people may do in a workspace.

Built-in roles map to fixed permission sets. Enterprise workspaces can also define custom
roles with any subset of permissions. Owners always have every permission.
"""

from __future__ import annotations

from enum import StrEnum


class Permission(StrEnum):
    LEADS_WRITE = "leads.write"  # add, import, edit, enrich and search for leads and companies
    LEADS_DELETE = "leads.delete"
    CAMPAIGNS_MANAGE = "campaigns.manage"  # campaigns, sequences, templates, drafts
    CAMPAIGNS_SEND = "campaigns.send"  # start and pause campaigns
    CAMPAIGNS_SEND_NOW = "campaigns.send_now"  # push due emails out immediately
    APPROVALS_APPROVE = "approvals.approve"  # approve or reject emails
    REPLIES_MANAGE = "replies.manage"
    DATA_EXPORT = "data.export"
    PRIVACY_MANAGE = "privacy.manage"  # data subject requests, retention, lawful-basis policy
    PROVIDERS_MANAGE = "providers.manage"
    SETTINGS_MANAGE = "settings.manage"  # workspace profile, AI, suppressions, policies
    MEMBERS_MANAGE = "members.manage"
    SSO_MANAGE = "sso.manage"
    API_KEYS_MANAGE = "api_keys.manage"
    AUDIT_VIEW = "audit.view"
    BILLING_MANAGE = "billing.manage"


ALL_PERMISSIONS: frozenset[str] = frozenset(p.value for p in Permission)

DESCRIPTIONS: dict[str, str] = {
    Permission.LEADS_WRITE: "Add, import, edit and enrich leads and companies",
    Permission.LEADS_DELETE: "Delete leads",
    Permission.CAMPAIGNS_MANAGE: "Create and edit campaigns, templates and drafts",
    Permission.CAMPAIGNS_SEND: "Start and pause campaigns",
    Permission.CAMPAIGNS_SEND_NOW: "Send due emails immediately",
    Permission.APPROVALS_APPROVE: "Approve and reject emails",
    Permission.REPLIES_MANAGE: "Label replies and add notes",
    Permission.DATA_EXPORT: "Export data (CSV and workspace exports)",
    Permission.PRIVACY_MANAGE: "Handle data requests (export or erase a person) and retention",
    Permission.PROVIDERS_MANAGE: "Connect sending, inbox, search and AI providers",
    Permission.SETTINGS_MANAGE: "Change workspace settings and suppressions",
    Permission.MEMBERS_MANAGE: "Invite people and change roles",
    Permission.SSO_MANAGE: "Set up single sign-on",
    Permission.API_KEYS_MANAGE: "Create API keys and webhooks",
    Permission.AUDIT_VIEW: "View the audit log",
    Permission.BILLING_MANAGE: "Manage the plan and billing",
}

MEMBER_PERMISSIONS: frozenset[str] = frozenset(
    {
        Permission.LEADS_WRITE,
        Permission.LEADS_DELETE,
        Permission.CAMPAIGNS_MANAGE,
        Permission.CAMPAIGNS_SEND,
        Permission.APPROVALS_APPROVE,
        Permission.REPLIES_MANAGE,
        Permission.DATA_EXPORT,
    }
)
ADMIN_PERMISSIONS: frozenset[str] = ALL_PERMISSIONS - {Permission.BILLING_MANAGE}

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "owner": ALL_PERMISSIONS,
    "admin": ADMIN_PERMISSIONS,
    "member": MEMBER_PERMISSIONS,
}


def permissions_for(role: str, custom_permissions: list[str] | None = None) -> frozenset[str]:
    if role == "owner":
        return ALL_PERMISSIONS
    if custom_permissions is not None and role == "member":
        return frozenset(p for p in custom_permissions if p in ALL_PERMISSIONS)
    return ROLE_PERMISSIONS.get(role, frozenset())


def validate_permissions(values: list[str]) -> list[str]:
    unknown = sorted(set(values) - ALL_PERMISSIONS)
    if unknown:
        from app.core.errors import ValidationFailedError

        raise ValidationFailedError(f"Unknown permissions: {', '.join(unknown)}")
    return sorted(set(values))
