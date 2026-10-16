import {
  apiFetch,
  apiUpload,
  downloadAuthenticatedFile,
  queryString,
} from "@/lib/api/client";
import type { components } from "@/lib/api/schema";

type S = components["schemas"];
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
  register: (data: { name: string; email: string; password: string; captcha_token?: string | null }) =>
    apiFetch<User>("/auth/register", { method: "POST", body: json(data), skipAuthRetry: true }),
  login: (data: { email: string; password: string; captcha_token?: string | null }) =>
    apiFetch<LoginResponse>("/auth/login", {
      method: "POST",
      body: json(data),
      skipAuthRetry: true,
    }),
  loginTwoFactor: (mfaToken: string, code: string) =>
    apiFetch<LoginResponse>("/auth/login/2fa", {
      method: "POST",
      body: json({ mfa_token: mfaToken, code }),
      skipAuthRetry: true,
    }),
  changePassword: (currentPassword: string, newPassword: string) =>
    apiFetch<LoginResponse>("/auth/change-password", {
      method: "POST",
      body: json({ current_password: currentPassword, new_password: newPassword }),
    }),
  twoFactorStatus: () => apiFetch<S["TwoFactorStatus"]>("/auth/2fa"),
  twoFactorSetup: () => apiFetch<S["TwoFactorSetup"]>("/auth/2fa/setup", { method: "POST" }),
  twoFactorEnable: (code: string) =>
    apiFetch<S["RecoveryCodes"]>("/auth/2fa/enable", { method: "POST", body: json({ code }) }),
  twoFactorDisable: (password: string, code: string) =>
    apiFetch<{ message: string }>("/auth/2fa/disable", {
      method: "POST",
      body: json({ password, code }),
    }),
  regenerateRecoveryCodes: (code: string) =>
    apiFetch<S["RecoveryCodes"]>("/auth/2fa/recovery-codes", {
      method: "POST",
      body: json({ code }),
    }),
  sessions: () => apiFetch<S["SessionRead"][]>("/auth/sessions"),
  revokeSession: (id: string) =>
    apiFetch<void>(`/auth/sessions/${encodeURIComponent(id)}`, { method: "DELETE" }),
  deleteAccount: (password: string, code?: string) =>
    apiFetch<void>("/auth/account", {
      method: "DELETE",
      body: json({ password, code: code || null }),
    }),
  logout: () => apiFetch<{ message: string }>("/auth/logout", { method: "POST", skipAuthRetry: true }),
  logoutAll: () => apiFetch<{ message: string }>("/auth/logout-all", { method: "POST" }),
  me: () => apiFetch<User>("/auth/me"),
  verifyEmail: (token: string) =>
    apiFetch<User>("/auth/verify-email", { method: "POST", body: json({ token }), skipAuthRetry: true }),
  resendVerification: () =>
    apiFetch<{ message: string }>("/auth/resend-verification", { method: "POST" }),
  forgotPassword: (email: string, captchaToken?: string | null) =>
    apiFetch<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: json({ email, captcha_token: captchaToken ?? null }),
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
  update: (data: { name?: string; timezone?: string; require_2fa?: boolean }) =>
    apiFetch<WorkspaceDetail>("/workspaces/current", { method: "PATCH", body: json(data) }),
  switch: (id: number) =>
    apiFetch<WorkspaceDetail>(`/workspaces/${id}/switch`, { method: "POST" }),
  members: () => apiFetch<Member[]>("/workspaces/current/members"),
  /** Change the built-in role and/or the custom role (null clears it). */
  updateMember: (userId: number, data: { role?: WorkspaceRole; custom_role_id?: number | null }) =>
    apiFetch<Member>(`/workspaces/current/members/${userId}`, {
      method: "PATCH",
      body: json(data),
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

export const ssoApi = {
  providers: () => apiFetch<S["ProvidersRead"]>("/auth/providers", { skipAuthRetry: true }),
  discover: (email: string) =>
    apiFetch<S["DiscoverRead"]>("/auth/sso/discover", {
      method: "POST",
      body: json({ email }),
      skipAuthRetry: true,
    }),
  identities: () => apiFetch<S["IdentityRead"][]>("/auth/identities"),
  linkProvider: (provider: "google" | "microsoft") =>
    apiFetch<S["UrlRead"]>(`/auth/oidc/${provider}/link`, { method: "POST" }),
  unlinkIdentity: (id: number) => apiFetch<void>(`/auth/identities/${id}`, { method: "DELETE" }),
  domains: () => apiFetch<S["DomainRead"][]>("/sso/domains"),
  addDomain: (domain: string) =>
    apiFetch<S["DomainRead"]>("/sso/domains", { method: "POST", body: json({ domain }) }),
  verifyDomain: (id: number) =>
    apiFetch<S["DomainRead"]>(`/sso/domains/${id}/verify`, { method: "POST" }),
  deleteDomain: (id: number) => apiFetch<void>(`/sso/domains/${id}`, { method: "DELETE" }),
  connections: () => apiFetch<S["ConnectionRead"][]>("/sso/connections"),
  createConnection: (data: S["ConnectionWrite"]) =>
    apiFetch<S["ConnectionRead"]>("/sso/connections", { method: "POST", body: json(data) }),
  updateConnection: (id: number, data: S["ConnectionWrite"]) =>
    apiFetch<S["ConnectionRead"]>(`/sso/connections/${id}`, { method: "PATCH", body: json(data) }),
  deleteConnection: (id: number) =>
    apiFetch<void>(`/sso/connections/${id}`, { method: "DELETE" }),
};

export const rolesApi = {
  mine: () => apiFetch<S["MyPermissions"]>("/workspaces/current/permissions"),
  permissions: () => apiFetch<S["PermissionInfo"][]>("/roles/permissions"),
  list: () => apiFetch<S["RoleRead"][]>("/roles"),
  create: (data: S["RoleWrite"]) =>
    apiFetch<S["RoleRead"]>("/roles", { method: "POST", body: json(data) }),
  update: (id: number, data: S["RoleWrite"]) =>
    apiFetch<S["RoleRead"]>(`/roles/${id}`, { method: "PATCH", body: json(data) }),
  remove: (id: number) => apiFetch<void>(`/roles/${id}`, { method: "DELETE" }),
};

export const auditApi = {
  list: (params: ListParams = {}) => apiFetch<S["AuditPage"]>(`/audit-logs${queryString(params)}`),
  exportCsv: (params: ListParams = {}) =>
    downloadAuthenticatedFile(`/audit-logs/export${queryString(params)}`, "audit-log.csv"),
};

export const privacyApi = {
  requests: (params: ListParams = {}) =>
    apiFetch<S["DataRequestPage"]>(`/privacy/requests${queryString(params)}`),
  createRequest: (data: S["DataRequestCreate"]) =>
    apiFetch<S["DataRequestRead"]>("/privacy/requests", { method: "POST", body: json(data) }),
  downloadLink: (id: number) =>
    apiFetch<S["DownloadRead"]>(`/privacy/requests/${id}/download`, { method: "POST" }),
  retry: (id: number) =>
    apiFetch<S["DataRequestRead"]>(`/privacy/requests/${id}/retry`, { method: "POST" }),
  settings: () => apiFetch<S["GovernanceSettings"]>("/privacy/settings"),
  updateSettings: (data: S["GovernanceSettings"]) =>
    apiFetch<S["GovernanceSettings"]>("/privacy/settings", { method: "PUT", body: json(data) }),
};

export const developerApi = {
  options: () => apiFetch<S["DeveloperOptions"]>("/developer/options"),
  keys: () => apiFetch<S["ApiKeyRead"][]>("/api-keys"),
  createKey: (data: S["ApiKeyCreate"]) =>
    apiFetch<S["ApiKeyCreated"]>("/api-keys", { method: "POST", body: json(data) }),
  revokeKey: (id: number) => apiFetch<void>(`/api-keys/${id}`, { method: "DELETE" }),
  endpoints: () => apiFetch<S["EndpointRead"][]>("/webhook-endpoints"),
  createEndpoint: (data: S["EndpointWrite"]) =>
    apiFetch<S["EndpointCreated"]>("/webhook-endpoints", { method: "POST", body: json(data) }),
  updateEndpoint: (id: number, data: S["EndpointWrite"]) =>
    apiFetch<S["EndpointRead"]>(`/webhook-endpoints/${id}`, { method: "PATCH", body: json(data) }),
  deleteEndpoint: (id: number) => apiFetch<void>(`/webhook-endpoints/${id}`, { method: "DELETE" }),
  rotateSecret: (id: number) =>
    apiFetch<S["SecretRead"]>(`/webhook-endpoints/${id}/rotate-secret`, { method: "POST" }),
  testEndpoint: (id: number) =>
    apiFetch<S["DeliveryRead"]>(`/webhook-endpoints/${id}/test`, { method: "POST" }),
  deliveries: (id: number) =>
    apiFetch<S["DeliveryPage"]>(`/webhook-endpoints/${id}/deliveries`),
  replay: (deliveryId: number) =>
    apiFetch<S["DeliveryRead"]>(`/webhook-deliveries/${deliveryId}/replay`, { method: "POST" }),
};

export type AdminOverview = {
  users: number;
  new_users_7d: number;
  workspaces: number;
  workspaces_by_plan: Record<string, number>;
  active_workspaces_7d: number;
  suspended_workspaces: number;
  emails_sent_24h: number;
  emails_sent_7d: number;
  replies_7d: number;
};
export type AdminHealth = {
  checks: Record<string, { ok: boolean; detail: string | null }>;
  failed_emails_24h: number;
  queued_emails: number;
  provider_errors: number;
  webhooks_pending: number;
  webhooks_failed_24h: number;
  data_requests_open: number;
};
export type AdminAbuse = {
  sending: {
    workspace_id: number;
    name: string;
    plan: string;
    sent_7d: number;
    bounced_7d: number;
    complained_7d: number;
    suspended: boolean;
    reasons: string[];
  }[];
  signups: { user_id: number; email: string; name: string; created_at: string; is_active: boolean; reasons: string[] }[];
};
export type AdminFlags = { flags: { key: string; description: string; default: boolean }[]; plans: string[] };

export const adminApi = {
  overview: () => apiFetch<AdminOverview>("/admin/overview"),
  health: () => apiFetch<AdminHealth>("/admin/health"),
  abuse: () => apiFetch<AdminAbuse>("/admin/abuse"),
  flags: () => apiFetch<AdminFlags>("/admin/flags"),
  workspaces: (params: ListParams = {}) =>
    apiFetch<S["WorkspacePage"]>(`/admin/workspaces${queryString(params)}`),
  workspace: (id: number) => apiFetch<S["WorkspaceDetail"]>(`/admin/workspaces/${id}`),
  updateWorkspace: (id: number, data: S["WorkspacePatch"]) =>
    apiFetch<S["WorkspaceDetail"]>(`/admin/workspaces/${id}`, { method: "PATCH", body: json(data) }),
  suspend: (id: number, reason: string) =>
    apiFetch<S["WorkspaceDetail"]>(`/admin/workspaces/${id}/suspend`, { method: "POST", body: json({ reason }) }),
  unsuspend: (id: number) =>
    apiFetch<S["WorkspaceDetail"]>(`/admin/workspaces/${id}/unsuspend`, { method: "POST" }),
  impersonate: (id: number, data: S["ImpersonateRequest"]) =>
    apiFetch<S["ImpersonationToken"]>(`/admin/workspaces/${id}/impersonate`, {
      method: "POST",
      body: json(data),
    }),
  users: (params: ListParams = {}) => apiFetch<S["UserPage"]>(`/admin/users${queryString(params)}`),
  setUserActive: (id: number, active: boolean) =>
    apiFetch<{ is_active: boolean }>(`/admin/users/${id}/${active ? "enable" : "disable"}`, { method: "POST" }),
  suppressions: (search?: string) =>
    apiFetch<Suppression[]>(`/admin/suppressions${queryString({ search })}`),
  addSuppression: (data: S["GlobalSuppressionCreate"]) =>
    apiFetch<Suppression>("/admin/suppressions", { method: "POST", body: json(data) }),
  removeSuppression: (id: number) => apiFetch<void>(`/admin/suppressions/${id}`, { method: "DELETE" }),
  auditLogs: () => apiFetch<S["AdminAuditRow"][]>("/admin/audit-logs"),
};

export const notificationsApi = {
  list: (unreadOnly = false) =>
    apiFetch<S["NotificationList"]>(`/notifications${queryString({ unread_only: unreadOnly || undefined })}`),
  markRead: (payload: { ids?: number[]; all?: boolean }) =>
    apiFetch<{ message: string }>("/notifications/read", { method: "POST", body: json(payload) }),
  preferences: () => apiFetch<S["PreferenceKind"][]>("/notifications/preferences"),
  savePreferences: (settings: Record<string, Record<string, boolean>>) =>
    apiFetch<S["PreferenceKind"][]>("/notifications/preferences", {
      method: "PUT",
      body: json({ settings }),
    }),
  slack: () => apiFetch<S["SlackSettings"]>("/workspaces/current/slack"),
  updateSlack: (data: S["SlackUpdate"]) =>
    apiFetch<S["SlackSettings"]>("/workspaces/current/slack", { method: "PUT", body: json(data) }),
  testSlack: () => apiFetch<{ message: string }>("/workspaces/current/slack/test", { method: "POST" }),
};

export const mailboxesApi = {
  providers: () => apiFetch<S["MailboxProvider"][]>("/mailboxes/providers"),
  connect: (provider: string) =>
    apiFetch<S["ConnectResponse"]>(`/mailboxes/${provider}/connect`, { method: "POST" }),
  accounts: () => apiFetch<S["SenderAccount"][]>("/sending-accounts"),
  updateAccount: (id: number, data: S["MailboxUpdate"]) =>
    apiFetch<S["SenderAccount"]>(`/sending-accounts/${id}`, { method: "PATCH", body: json(data) }),
  campaignSenders: (campaignId: number) =>
    apiFetch<S["SenderAccount"][]>(`/campaigns/${campaignId}/senders`),
  setCampaignSenders: (campaignId: number, credentialIds: number[]) =>
    apiFetch<S["SenderAccount"][]>(`/campaigns/${campaignId}/senders`, {
      method: "PUT",
      body: json({ credential_ids: credentialIds }),
    }),
};

export const inboxApi = {
  list: (params: ListParams = {}) =>
    apiFetch<S["ConversationPage"]>(`/inbox/conversations${queryString(params)}`),
  get: (id: number) => apiFetch<S["ConversationDetail"]>(`/inbox/conversations/${id}`),
  update: (id: number, data: S["ConversationUpdate"]) =>
    apiFetch<S["ConversationDetail"]>(`/inbox/conversations/${id}`, { method: "PATCH", body: json(data) }),
  reply: (id: number, body: string) =>
    apiFetch<S["SentReply"]>(`/inbox/conversations/${id}/reply`, { method: "POST", body: json({ body }) }),
  suggest: (id: number) =>
    apiFetch<S["Suggestion"]>(`/inbox/conversations/${id}/suggest`, { method: "POST" }),
};

export const crmApi = {
  flags: () => apiFetch<Record<string, boolean>>("/workspaces/current/flags"),
  board: () => apiFetch<S["Board"]>("/deals/board"),
  createDeal: (data: S["DealWrite"]) => apiFetch<S["DealRead"]>("/deals", { method: "POST", body: json(data) }),
  updateDeal: (id: number, data: S["DealWrite"]) =>
    apiFetch<S["DealRead"]>(`/deals/${id}`, { method: "PATCH", body: json(data) }),
  deleteDeal: (id: number) => apiFetch<void>(`/deals/${id}`, { method: "DELETE" }),
  addStage: (data: S["StageWrite"]) =>
    apiFetch<S["StageRead"]>("/deals/stages", { method: "POST", body: json(data) }),
  tasks: (params: ListParams = {}) => apiFetch<S["TaskRead"][]>(`/tasks${queryString(params)}`),
  createTask: (data: S["TaskWrite"]) => apiFetch<S["TaskRead"]>("/tasks", { method: "POST", body: json(data) }),
  updateTask: (id: number, data: S["TaskWrite"]) =>
    apiFetch<S["TaskRead"]>(`/tasks/${id}`, { method: "PATCH", body: json(data) }),
  deleteTask: (id: number) => apiFetch<void>(`/tasks/${id}`, { method: "DELETE" }),
  notes: (leadId: number) => apiFetch<S["NoteRead"][]>(`/leads/${leadId}/notes`),
  addNote: (leadId: number, body: string) =>
    apiFetch<S["NoteRead"]>(`/leads/${leadId}/notes`, { method: "POST", body: json({ body }) }),
  deleteNote: (id: number) => apiFetch<void>(`/notes/${id}`, { method: "DELETE" }),
  timeline: (leadId: number) => apiFetch<S["TimelineItem"][]>(`/leads/${leadId}/timeline`),
};

/** Where the browser goes to start "Continue with Google/Microsoft". */
export function socialSignInUrl(provider: "google" | "microsoft", next?: string | null) {
  const query = next ? `?next=${encodeURIComponent(next)}` : "";
  return `/api/auth/oidc/${provider}/start${query}`;
}

export const analyticsApi = {
  overview: (params: { days?: number; campaign_id?: number } = {}) =>
    apiFetch<S["Overview"]>(`/analytics/overview${queryString(params)}`),
  exportCsv: (days: number) =>
    downloadAuthenticatedFile(`/analytics/export${queryString({ days })}`, `leadsgen-analytics-${days}d.csv`),
  variants: (campaignId: number) => apiFetch<S["StepVariants"][]>(`/campaigns/${campaignId}/variants`),
};

export const billingApi = {
  summary: () => apiFetch<BillingSummary>("/billing"),
  checkout: (plan: string, interval: "month" | "year") =>
    apiFetch<{ url: string }>("/billing/checkout", { method: "POST", body: json({ plan, interval }) }),
  portal: () => apiFetch<{ url: string }>("/billing/portal", { method: "POST" }),
  invoices: () => apiFetch<S["Invoice"][]>("/billing/invoices"),
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
