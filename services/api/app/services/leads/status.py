"""Rules for status changes requested by users (as opposed to system events)."""

from app.core.errors import ValidationFailedError
from app.models.enums import LeadStatus

# Only the suppression/unsubscribe pipeline may opt a lead out, and nobody may opt them back in.
SYSTEM_ONLY_STATUSES = {LeadStatus.OPTED_OUT}


def validate_user_status_change(current: LeadStatus | str, requested: LeadStatus) -> LeadStatus:
    current_status = LeadStatus(str(current))
    if current_status == requested:
        return requested
    if current_status == LeadStatus.OPTED_OUT:
        raise ValidationFailedError(
            "This lead opted out. Their status can't be changed and they can't be contacted.",
        )
    if requested in SYSTEM_ONLY_STATUSES:
        raise ValidationFailedError(
            "Opt-outs are recorded through the suppression list, not by editing the lead.",
        )
    return requested
