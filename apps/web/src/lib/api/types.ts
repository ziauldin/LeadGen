export type LeadStatus =
  | "new"
  | "enriched"
  | "qualified"
  | "ready_for_outreach"
  | "contacted"
  | "replied"
  | "meeting_booked"
  | "client"
  | "disqualified"
  | "opted_out";

export type ReplyClassification =
  | "positive"
  | "neutral"
  | "objection"
  | "unsubscribe"
  | "bounce"
  | "unknown";

export type CampaignStatus = "draft" | "active" | "paused" | "completed";

export type User = {
  id: number;
  name: string;
  email: string;
  role: string;
  created_at: string;
};

export type Niche = {
  id: number;
  user_id: number;
  name: string;
  country: string;
  industry: string;
  target_roles: string[];
  keywords: string[];
  exclusion_keywords: string[];
  company_size_min: number | null;
  company_size_max: number | null;
  created_at: string;
};

export type CompanySummary = {
  id: number;
  name: string;
  website: string | null;
  domain: string | null;
  enrichment_status?: string;
};

export type EmailContact = {
  id: number;
  email: string;
  source_provider: string | null;
  opted_out: boolean;
  created_at: string;
};

export type Lead = {
  id: number;
  niche_id: number;
  full_name: string;
  job_title: string | null;
  linkedin_url: string | null;
  source_url: string | null;
  source_provider: string | null;
  company_id: number | null;
  status: LeadStatus;
  score: number;
  qualification_notes: string | null;
  compliance_source_note: string | null;
  created_at: string;
  updated_at: string;
  company: CompanySummary | null;
  primary_email: string | null;
  email_contacts: EmailContact[];
};

export type Company = {
  id: number;
  name: string;
  website: string | null;
  domain: string | null;
  industry: string | null;
  country: string | null;
  size_estimate: number | null;
  enrichment_status: string;
  enrichment_message: string | null;
  created_at: string;
  updated_at: string;
  email_contacts: EmailContact[];
};

export type Campaign = {
  id: number;
  niche_id: number;
  name: string;
  status: CampaignStatus;
  daily_send_limit: number;
  sending_window_start: string | null;
  sending_window_end: string | null;
  created_at: string;
  steps: CampaignStep[];
};

export type CampaignStep = {
  id: number;
  campaign_id: number;
  step_number: number;
  delay_days: number;
  subject_template: string;
  body_template: string;
};

export type Reply = {
  id: number;
  email_message_id: number;
  from_email: string;
  body: string;
  classification: ReplyClassification;
  received_at: string;
  lead_id: number | null;
  lead_name: string | null;
  campaign_id: number | null;
  notes: string | null;
};

export type DashboardSummary = {
  total_leads: number;
  qualified_leads: number;
  contacted_leads: number;
  replied_leads: number;
  active_campaigns: number;
  pending_replies: number;
  positive_replies: number;
  lead_status_counts: Record<string, number>;
};

export type UserSettings = {
  sender_name: string | null;
  sender_company: string | null;
  business_address: string | null;
};

export type ProviderCredentialStatus = "not_configured" | "configured" | "error";
export type ProviderType = "search" | "email" | "email_discovery";
export type ProviderName =
  | "mock"
  | "google_cse"
  | "bing"
  | "serpapi"
  | "smtp"
  | "resend"
  | "sendgrid"
  | "mailgun"
  | "hunter";

export type ProviderCredential = {
  id: number;
  provider_type: ProviderType;
  provider_name: ProviderName;
  display_name: string;
  masked_summary: string | null;
  is_active: boolean;
  status: ProviderCredentialStatus;
  last_tested_at: string | null;
  last_test_status: string | null;
  last_test_message: string | null;
  created_at: string;
  updated_at: string;
};

export type Paginated<T> = {
  items: T[];
  total: number;
  skip: number;
  limit: number;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
};

export type EmailPreview = {
  lead_id?: number;
  template_id?: string;
  subject: string;
  body: string;
  recipient_email: string;
  has_opt_out_line?: boolean;
  compliance_errors?: string[];
  can_send?: boolean;
  compliance_ok?: boolean;
  compliance_issues?: string[];
  variables?: Record<string, string>;
};

export type SearchQuery = {
  id: number;
  niche_id: number;
  query_text: string;
  provider: string;
  status: string;
  results: unknown[] | null;
  created_at: string;
};
