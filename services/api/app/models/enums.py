from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    OPERATOR = "operator"


class LeadStatus(StrEnum):
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


class SearchStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SearchProvider(StrEnum):
    MOCK = "mock"
    GOOGLE_CSE = "google_cse"
    BING = "bing"
    SERPAPI = "serpapi"
    MANUAL = "manual"


class EnrichmentStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class EmailType(StrEnum):
    GENERIC = "generic"
    ROLE_BASED = "role_based"
    PERSONAL = "personal"
    NAMED = "named"


class CampaignStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class EmailMessageStatus(StrEnum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    QUEUED = "queued"
    SENDING = "sending"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"
    COMPLAINED = "complained"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class ReplyStatus(StrEnum):
    NONE = "none"
    RECEIVED = "received"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class BounceStatus(StrEnum):
    NONE = "none"
    HARD = "hard"
    SOFT = "soft"


class ReplyClassification(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    OBJECTION = "objection"
    UNSUBSCRIBE = "unsubscribe"
    BOUNCE = "bounce"
    OUT_OF_OFFICE = "out_of_office"
    AUTO_REPLY = "auto_reply"
    WRONG_PERSON = "wrong_person"
    UNKNOWN = "unknown"


class ProviderType(StrEnum):
    SEARCH = "search"
    EMAIL = "email"
    EMAIL_DISCOVERY = "email_discovery"
    INBOX = "inbox"
    LLM = "llm"


class ProviderName(StrEnum):
    MOCK = "mock"
    GOOGLE_CSE = "google_cse"
    BING = "bing"
    SERPAPI = "serpapi"
    SMTP = "smtp"
    RESEND = "resend"
    SENDGRID = "sendgrid"
    MAILGUN = "mailgun"
    HUNTER = "hunter"
    IMAP = "imap"
    GROQ = "groq"
    OPENAI = "openai"
    GEMINI = "gemini"


class ProviderCredentialStatus(StrEnum):
    NOT_CONFIGURED = "not_configured"
    CONFIGURED = "configured"
    ERROR = "error"
