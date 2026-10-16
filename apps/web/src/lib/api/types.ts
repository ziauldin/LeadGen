/**
 * Friendly names for the API's types. Everything here comes from `schema.d.ts`, which is
 * generated from the backend's OpenAPI schema (`npm run gen:api`), so the two can't drift.
 */
import type { components } from "@/lib/api/schema";

type S = components["schemas"];

export type LeadStatus = S["LeadStatus"];
export type ReplyClassification = S["ReplyClassification"];
export type CampaignStatus = S["CampaignStatus"];
export type EmailMessageStatus = S["EmailMessageStatus"];
export type ProviderType = S["ProviderType"];
export type ProviderName = S["ProviderName"];
export type ProviderCredentialStatus = S["ProviderCredentialStatus"];
export type WorkspaceRole = S["WorkspaceRole"];

export type User = S["UserRead"];
export type LoginResponse = S["LoginResponse"];
export type TokenResponse = S["LoginResponse"];

export type Workspace = S["WorkspaceWithRole"];
export type WorkspaceDetail = S["WorkspaceRead"];
export type Member = S["MemberRead"];
export type Invitation = S["InvitationRead"];
export type InvitationPreview = S["InvitationPreview"];
export type Onboarding = S["OnboardingStatus"];
export type BillingSummary = S["BillingSummary"];

export type Niche = S["NicheRead"];
export type NicheCreate = S["NicheCreate"];
export type CompanySummary = S["CompanySummary"];
export type EmailContact = S["app__schemas__lead__EmailContactRead"];
export type Lead = S["LeadRead"];
export type LeadUpdate = S["LeadUpdate"];
export type LeadStats = S["LeadStats"];
export type LeadBulkRequest = S["LeadBulkRequest"];
export type LeadImportResult = S["LeadImportResult"];
export type Company = S["CompanyRead"];
export type CompanyUpdate = S["CompanyUpdate"];

export type Campaign = S["CampaignRead"];
export type CampaignCreate = S["CampaignCreate"];
export type CampaignUpdate = S["CampaignUpdate"];
export type CampaignStep = S["CampaignStepRead"];
export type CampaignStepInput = S["CampaignStepBase"];
export type CampaignMetrics = S["CampaignMetrics"];
export type CampaignMessage = S["CampaignMessageRead"];
export type Enrollment = S["EnrollmentRead"];
export type AddLeadsResult = S["AddLeadsResponse"];

export type EmailTemplate = S["TemplateRead"];
export type TemplateCreate = S["TemplateCreate"];
export type TemplateUpdate = S["TemplateUpdate"];
export type EmailPreview = S["EmailPreviewResponse"];
export type EmailMessage = S["EmailMessageRead"];
export type ApprovalItem = S["ApprovalItem"];
export type ApprovalQueue = S["ApprovalQueue"];
export type GenerationMode = "template" | "ai";

export type Reply = S["ReplyRead"];
export type ReplyDetail = S["ReplyDetail"];

export type DashboardSummary = S["DashboardSummary"];
export type UserSettings = S["UserSettingsRead"];
export type UserSettingsUpdate = S["UserSettingsUpdate"];
export type DeliverabilityReport = S["DeliverabilityReport"];
export type ProviderCredential = S["ProviderCredentialRead"];
export type Suppression = S["SuppressionRead"];
export type SearchQuery = S["SearchQueryRead"];

export type BulkResult = S["BulkResult"];
export type BulkItemResult = S["BulkItemResult"];

export type Paginated<T> = {
  items: T[];
  total: number;
  skip: number;
  limit: number;
};

/** Common list query: paging, an optional `sort` like "-score,full_name", and filters. */
export type ListParams = {
  skip?: number;
  limit?: number;
  sort?: string;
  [filter: string]: string | number | boolean | undefined | null;
};
