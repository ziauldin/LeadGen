import enum


class UserRole(str, enum.Enum):
    ADMIN = "admin"
    OPERATOR = "operator"


class LeadStatus(str, enum.Enum):
    NEW = "new"
    ENRICHED = "enriched"
    QUALIFIED = "qualified"
    READY_FOR_OUTREACH = "ready_for_outreach"
    CONTACTED = "contacted"
    REPLIED = "replied"
    MEETING_BOOKED = "meeting_booked"
    CLIENT = "client"
    DISQUALIFIED = "disqualified"
    OPTED_OUT = "opted_out"


class SearchStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SearchProvider(str, enum.Enum):
    MOCK = "mock"
    GOOGLE_CSE = "google_cse"
    BING = "bing"
    SERPAPI = "serpapi"
    MANUAL = "manual"


class EnrichmentStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class EmailType(str, enum.Enum):
    GENERIC = "generic"
    ROLE_BASED = "role_based"
    PERSONAL = "personal"
    NAMED = "named"


class CampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class EmailMessageStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"


class ReplyStatus(str, enum.Enum):
    NONE = "none"
    RECEIVED = "received"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class BounceStatus(str, enum.Enum):
    NONE = "none"
    HARD = "hard"
    SOFT = "soft"


class ReplyClassification(str, enum.Enum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    OBJECTION = "objection"
    UNSUBSCRIBE = "unsubscribe"
    BOUNCE = "bounce"
    UNKNOWN = "unknown"


class ProviderType(str, enum.Enum):
    SEARCH = "search"
    EMAIL = "email"
    EMAIL_DISCOVERY = "email_discovery"


class ProviderName(str, enum.Enum):
    MOCK = "mock"
    GOOGLE_CSE = "google_cse"
    BING = "bing"
    SERPAPI = "serpapi"
    SMTP = "smtp"
    RESEND = "resend"
    SENDGRID = "sendgrid"
    MAILGUN = "mailgun"
    HUNTER = "hunter"


class ProviderCredentialStatus(str, enum.Enum):
    NOT_CONFIGURED = "not_configured"
    CONFIGURED = "configured"
    ERROR = "error"
