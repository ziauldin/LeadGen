import {
  apiFetch,
  apiUpload,
  downloadAuthenticatedFile,
  queryString,
} from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import type {
  AddLeadsResult,
  ApprovalItem,
  ApprovalQueue,
  BillingSummary,
  BulkResult,
  Campaign,
  CampaignCreate,
  CampaignMessage,
  CampaignMetrics,
  CampaignUpdate,
  Company,
  CompanyUpdate,
  DashboardSummary,
  DeliverabilityReport,
  EmailMessage,
  EmailPreview,
  EmailTemplate,
  Enrollment,
  GenerationMode,
  Invitation,
  InvitationPreview,
  Lead,
  LeadBulkRequest,
  LeadImportResult,
  LeadStats,
  LeadUpdate,
  ListParams,
  LoginResponse,
  Member,
  Niche,
  NicheCreate,
  Onboarding,
  Paginated,
  ProviderCredential,
  ProviderName,
  ProviderType,
  Reply,
  ReplyDetail,
  SearchQuery,
  Suppression,
  TemplateCreate,
  TemplateUpdate,
  User,
  UserSettings,
  UserSettingsUpdate,
  Workspace,
  WorkspaceDetail,
  WorkspaceRole,
} from "@/lib/api/types";

const json = (data: unknown) => JSON.stringify(data);

export const authApi = {
  register: (data: { name: string; email: string; password: string }) =>
    apiFetch<User>("/auth/register", { method: "POST", body: json(data), skipAuthRetry: true }),
  login: (data: { email: string; password: string }) =>
    apiFetch<LoginResponse>("/auth/login", {
      method: "POST",
      body: json(data),
      skipAuthRetry: true,
    }),
  logout: () => apiFetch<{ message: string }>("/auth/logout", { method: "POST", skipAuthRetry: true }),
  logoutAll: () => apiFetch<{ message: string }>("/auth/logout-all", { method: "POST" }),
  me: () => apiFetch<User>("/auth/me"),
  verifyEmail: (token: string) =>
    apiFetch<User>("/auth/verify-email", { method: "POST", body: json({ token }), skipAuthRetry: true }),
  resendVerification: () =>
    apiFetch<{ message: string }>("/auth/resend-verification", { method: "POST" }),
  forgotPassword: (email: string) =>
    apiFetch<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: json({ email }),
      skipAuthRetry: true,
    }),
  resetPassword: (token: string, password: string) =>
    apiFetch<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: json({ token, password }),
      skipAuthRetry: true,
    }),
};

export const workspacesApi = {
  list: () =>
    apiFetch<{ items: Workspace[]; current_workspace_id: number | null }>("/workspaces"),
  create: (data: { name: string; timezone?: string }) =>
    apiFetch<WorkspaceDetail>("/workspaces", { method: "POST", body: json(data) }),
  current: () => apiFetch<WorkspaceDetail>("/workspaces/current"),
  update: (data: { name?: string; timezone?: string }) =>
    apiFetch<WorkspaceDetail>("/workspaces/current", { method: "PATCH", body: json(data) }),
  switch: (id: number) =>
    apiFetch<WorkspaceDetail>(`/workspaces/${id}/switch`, { method: "POST" }),
  members: () => apiFetch<Member[]>("/workspaces/current/members"),
  updateMember: (userId: number, role: WorkspaceRole) =>
    apiFetch<Member>(`/workspaces/current/members/${userId}`, {
      method: "PATCH",
      body: json({ role }),
    }),
  removeMember: (userId: number) =>
    apiFetch<void>(`/workspaces/current/members/${userId}`, { method: "DELETE" }),
  invitations: () => apiFetch<Invitation[]>("/workspaces/current/invitations"),
  invite: (email: string, role: WorkspaceRole) =>
    apiFetch<Invitation>("/workspaces/current/invitations", {
      method: "POST",
      body: json({ email, role }),
    }),
  revokeInvitation: (id: number) =>
    apiFetch<void>(`/workspaces/current/invitations/${id}`, { method: "DELETE" }),
  onboarding: () => apiFetch<Onboarding>("/workspaces/current/onboarding"),
  leave: () => apiFetch<void>("/workspaces/current/leave", { method: "POST" }),
  previewInvitation: (token: string) => apiFetch<InvitationPreview>(`/invitations/${token}`),
  acceptInvitation: (token: string) =>
    apiFetch<WorkspaceDetail>(`/invitations/${token}/accept`, { method: "POST" }),
};

export const billingApi = {
  summary: () => apiFetch<BillingSummary>("/billing"),
};

export const dashboardApi = {
  summary: () => apiFetch<DashboardSummary>("/dashboard/summary"),
};

export const nichesApi = {
  list: (params?: ListParams) => apiFetch<Paginated<Niche>>(`/niches${queryString(params)}`),
  get: (id: number) => apiFetch<Niche>(`/niches/${id}`),
  create: (data: NicheCreate) => apiFetch<Niche>("/niches", { method: "POST", body: json(data) }),
  update: (id: number, data: Partial<NicheCreate>) =>
    apiFetch<Niche>(`/niches/${id}`, { method: "PATCH", body: json(data) }),
  delete: (id: number) => apiFetch<void>(`/niches/${id}`, { method: "DELETE" }),
};

export const leadsApi = {
  list: (params?: ListParams) => apiFetch<Paginated<Lead>>(`/leads${queryString(params)}`),
  stats: (nicheId?: number) => apiFetch<LeadStats>(`/leads/stats${queryString({ niche_id: nicheId })}`),
  get: (id: number) => apiFetch<Lead>(`/leads/${id}`),
  create: (data: components["schemas"]["LeadCreate"]) =>
    apiFetch<Lead>("/leads", { method: "POST", body: json(data) }),
  update: (id: number, data: LeadUpdate) =>
    apiFetch<Lead>(`/leads/${id}`, { method: "PATCH", body: json(data) }),
  delete: (id: number) => apiFetch<void>(`/leads/${id}`, { method: "DELETE" }),
  bulk: (data: LeadBulkRequest) =>
    apiFetch<BulkResult>("/leads/bulk", { method: "POST", body: json(data) }),
  outreachReadiness: (id: number) =>
    apiFetch<components["schemas"]["OutreachReadiness"]>(`/leads/${id}/outreach-readiness`),
  importCsv: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiUpload<LeadImportResult>("/leads/import-csv", formData);
  },
  exportCsv: (nicheId?: number) =>
    downloadAuthenticatedFile(`/leads/export-csv${queryString({ niche_id: nicheId })}`, "leads.csv"),
  recalculateScores: (nicheId?: number) =>
    apiFetch<{ updated: number }>("/scoring/recalculate", {
      method: "POST",
      body: json(nicheId ? { niche_id: nicheId } : {}),
    }),
};

export const companiesApi = {
  list: (params?: ListParams) =>
    apiFetch<Paginated<Company>>(`/companies${queryString(params)}`),
  get: (id: number) => apiFetch<Company>(`/companies/${id}`),
  update: (id: number, data: CompanyUpdate) =>
    apiFetch<Company>(`/companies/${id}`, { method: "PATCH", body: json(data) }),
  enrich: (id: number, sync = false) =>
    apiFetch<{ company_id: number; status: string; message: string }>(
      `/companies/${id}/enrich?sync=${sync}`,
      { method: "POST" },
    ),
  bulkEnrich: (ids: number[]) =>
    apiFetch<BulkResult>("/companies/bulk-enrich", { method: "POST", body: json({ ids }) }),
};

export const searchesApi = {
  generateQueries: (nicheId: number) =>
    apiFetch<{ queries: string[] }>("/searches/generate-queries", {
      method: "POST",
      body: json({ niche_id: nicheId }),
    }),
  run: (nicheId: number, queryText: string, provider?: string) =>
    apiFetch<SearchQuery>("/searches/run", {
      method: "POST",
      body: json({ niche_id: nicheId, query: queryText, ...(provider ? { provider } : {}) }),
    }),
  get: (id: number) => apiFetch<SearchQuery>(`/searches/${id}`),
  /** Save the chosen results (by URL) as leads and companies. */
  saveResults: (id: number, selectedUrls: string[]) =>
    apiFetch<{ created: number; skipped: number }>(`/searches/${id}/save-results`, {
      method: "POST",
      body: json({ selected_urls: selectedUrls }),
    }),
};

export const templatesApi = {
  list: (includeArchived = false) =>
    apiFetch<EmailTemplate[]>(`/templates${includeArchived ? "?include_archived=true" : ""}`),
  get: (id: string) => apiFetch<EmailTemplate>(`/templates/${encodeURIComponent(id)}`),
  variables: () => apiFetch<{ variables: string[]; required: string[] }>("/templates/variables"),
  create: (data: TemplateCreate) =>
    apiFetch<EmailTemplate>("/templates", { method: "POST", body: json(data) }),
  update: (id: string, data: TemplateUpdate) =>
    apiFetch<EmailTemplate>(`/templates/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: json(data),
    }),
  archive: (id: string) =>
    apiFetch<void>(`/templates/${encodeURIComponent(id)}`, { method: "DELETE" }),
};

export type DraftOptions = {
  templateId?: string;
  mode?: GenerationMode;
  instructions?: string;
};

export const emailsApi = {
  preview: (leadId: number, options: DraftOptions = {}) =>
    apiFetch<EmailPreview>("/emails/preview", {
      method: "POST",
      body: json({
        lead_id: leadId,
        template_id: options.templateId ?? "system:intro",
        mode: options.mode ?? "template",
        instructions: options.instructions || null,
      }),
    }),
  generate: (leadId: number, campaignId?: number | null, options: DraftOptions = {}) =>
    apiFetch<{ message: EmailMessage; compliance_errors: string[] }>("/emails/generate", {
      method: "POST",
      body: json({
        lead_id: leadId,
        campaign_id: campaignId ?? null,
        template_id: options.templateId ?? "system:intro",
        mode: options.mode ?? "template",
        instructions: options.instructions || null,
      }),
    }),
  get: (id: number) => apiFetch<ApprovalItem>(`/emails/${id}`),
  edit: (id: number, data: { subject?: string; body?: string }) =>
    apiFetch<ApprovalItem>(`/emails/${id}`, { method: "PATCH", body: json(data) }),
  approve: (id: number) => apiFetch<ApprovalItem>(`/emails/${id}/approve`, { method: "POST" }),
  reject: (id: number, reason?: string) =>
    apiFetch<ApprovalItem>(`/emails/${id}/reject`, {
      method: "POST",
      body: json({ reason: reason || null }),
    }),
  regenerate: (id: number, options: DraftOptions = {}) =>
    apiFetch<EmailMessage>(`/emails/${id}/regenerate`, {
      method: "POST",
      body: json({
        mode: options.mode ?? "template",
        template_id: options.templateId ?? null,
        instructions: options.instructions || null,
      }),
    }),
};

export const approvalsApi = {
  list: (params?: ListParams & { campaign_id?: number; mode?: string }) =>
    apiFetch<ApprovalQueue>(`/approvals${queryString(params)}`),
  bulkApprove: (messageIds: number[]) =>
    apiFetch<BulkResult>("/approvals/bulk-approve", {
      method: "POST",
      body: json({ message_ids: messageIds }),
    }),
  bulkReject: (messageIds: number[], reason?: string) =>
    apiFetch<BulkResult>("/approvals/bulk-reject", {
      method: "POST",
      body: json({ message_ids: messageIds, reason: reason || null }),
    }),
};

export const campaignsApi = {
  list: (params?: ListParams & { niche_id?: number; status?: string }) =>
    apiFetch<Paginated<Campaign>>(`/campaigns${queryString(params)}`),
  get: (id: number) => apiFetch<Campaign>(`/campaigns/${id}`),
  create: (data: CampaignCreate) =>
    apiFetch<Campaign>("/campaigns", { method: "POST", body: json(data) }),
  update: (id: number, data: CampaignUpdate) =>
    apiFetch<Campaign>(`/campaigns/${id}`, { method: "PATCH", body: json(data) }),
  metrics: (id: number) => apiFetch<CampaignMetrics>(`/campaigns/${id}/metrics`),
  messages: (id: number, params?: ListParams & { status?: string; step_number?: number }) =>
    apiFetch<Paginated<CampaignMessage>>(`/campaigns/${id}/messages${queryString(params)}`),
  enrollments: (id: number, params?: ListParams & { status?: string }) =>
    apiFetch<Paginated<Enrollment>>(`/campaigns/${id}/enrollments${queryString(params)}`),
  stopEnrollment: (id: number, enrollmentId: number) =>
    apiFetch<Enrollment>(`/campaigns/${id}/enrollments/${enrollmentId}/stop`, { method: "POST" }),
  addLeads: (id: number, leadIds: number[]) =>
    apiFetch<AddLeadsResult>(`/campaigns/${id}/add-leads`, {
      method: "POST",
      body: json({ lead_ids: leadIds }),
    }),
  start: (id: number) => apiFetch<{ campaign: Campaign }>(`/campaigns/${id}/start`, { method: "POST" }),
  pause: (id: number) => apiFetch<{ campaign: Campaign }>(`/campaigns/${id}/pause`, { method: "POST" }),
  /** Admin only: queue this campaign's due emails now instead of waiting for the dispatcher. */
  processSends: (id: number) =>
    apiFetch<components["schemas"]["ProcessSendsResponse"]>(`/campaigns/${id}/process-sends`, {
      method: "POST",
    }),
};

export const repliesApi = {
  list: (params?: ListParams & { classification?: string; campaign_id?: number; search?: string }) =>
    apiFetch<Paginated<Reply>>(`/replies${queryString(params)}`),
  get: (id: number) => apiFetch<ReplyDetail>(`/replies/${id}`),
  update: (
    id: number,
    data: { classification?: string; mark_meeting_booked?: boolean; notes?: string },
  ) => apiFetch<Reply>(`/replies/${id}`, { method: "PATCH", body: json(data) }),
  link: (id: number, emailMessageId: number) =>
    apiFetch<Reply>(`/replies/${id}/link`, {
      method: "POST",
      body: json({ email_message_id: emailMessageId }),
    }),
  sync: () => apiFetch<{ synced: number; message: string }>("/replies/sync", { method: "POST" }),
  exportCsv: () => downloadAuthenticatedFile("/replies/export-csv", "replies.csv"),
};

export const settingsApi = {
  get: () => apiFetch<UserSettings>("/settings"),
  update: (data: UserSettingsUpdate) =>
    apiFetch<UserSettings>("/settings", { method: "PATCH", body: json(data) }),
  deliverability: (domain?: string) =>
    apiFetch<DeliverabilityReport>(`/settings/deliverability${queryString({ domain })}`),
  listSuppressions: (params?: ListParams & { search?: string }) =>
    apiFetch<Paginated<Suppression>>(`/suppressions${queryString(params)}`),
  createSuppression: (data: { email?: string; domain?: string; reason?: string }) =>
    apiFetch<Suppression>("/suppressions", {
      method: "POST",
      body: json({ ...data, source: "manual" }),
    }),
  deleteSuppression: (id: number) => apiFetch<void>(`/suppressions/${id}`, { method: "DELETE" }),
};

export const providerSettingsApi = {
  list: () => apiFetch<{ items: ProviderCredential[] }>("/provider-settings"),
  upsert: (data: {
    provider_type: ProviderType;
    provider_name: ProviderName;
    config: Record<string, string | number | boolean | null>;
  }) => apiFetch<ProviderCredential>("/provider-settings", { method: "POST", body: json(data) }),
  activate: (id: number) =>
    apiFetch<ProviderCredential>(`/provider-settings/${id}/activate`, { method: "PATCH" }),
  test: (id: number) =>
    apiFetch<{ success: boolean; message: string; tested_at: string }>(
      `/provider-settings/${id}/test`,
      { method: "POST" },
    ),
  warmup: (
    id: number,
    data: { enabled: boolean; start_volume?: number; daily_increment?: number; maximum?: number },
  ) =>
    apiFetch<ProviderCredential>(`/provider-settings/${id}/warmup`, {
      method: "PATCH",
      body: json(data),
    }),
  delete: (id: number) => apiFetch<void>(`/provider-settings/${id}`, { method: "DELETE" }),
};
