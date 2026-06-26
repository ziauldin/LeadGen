import { apiFetch, apiUpload, downloadAuthenticatedFile } from "@/lib/api/client";
import type {
  Campaign,
  Company,
  DashboardSummary,
  EmailPreview,
  Lead,
  Niche,
  Paginated,
  ProviderCredential,
  ProviderName,
  ProviderType,
  Reply,
  SearchQuery,
  TokenResponse,
  User,
  UserSettings,
} from "@/lib/api/types";

export const authApi = {
  register: (data: { name: string; email: string; password: string }) =>
    apiFetch<User>("/auth/register", { method: "POST", body: JSON.stringify(data) }),
  login: (data: { email: string; password: string }) =>
    apiFetch<TokenResponse>("/auth/login", { method: "POST", body: JSON.stringify(data) }),
  me: () => apiFetch<User>("/auth/me"),
};

export const dashboardApi = {
  summary: () => apiFetch<DashboardSummary>("/dashboard/summary"),
};

export const nichesApi = {
  list: () => apiFetch<Paginated<Niche>>("/niches"),
  get: (id: number) => apiFetch<Niche>(`/niches/${id}`),
  create: (data: Omit<Niche, "id" | "user_id" | "created_at">) =>
    apiFetch<Niche>("/niches", { method: "POST", body: JSON.stringify(data) }),
  update: (id: number, data: Partial<Niche>) =>
    apiFetch<Niche>(`/niches/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
};

export const leadsApi = {
  list: (params?: { niche_id?: number; status?: string }) => {
    const search = new URLSearchParams();
    if (params?.niche_id) search.set("niche_id", String(params.niche_id));
    if (params?.status) search.set("status", params.status);
    const qs = search.toString();
    return apiFetch<Paginated<Lead>>(`/leads${qs ? `?${qs}` : ""}`);
  },
  get: (id: number) => apiFetch<Lead>(`/leads/${id}`),
  outreachReadiness: (id: number) =>
    apiFetch<{ ready: boolean; issues: string[] }>(`/leads/${id}/outreach-readiness`),
  importCsv: (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    return apiUpload<{ created: number; updated: number; skipped: number; errors: string[] }>(
      "/leads/import-csv",
      formData,
    );
  },
  exportCsv: (nicheId?: number) => {
    const qs = nicheId ? `?niche_id=${nicheId}` : "";
    return downloadAuthenticatedFile(`/leads/export-csv${qs}`, "leads.csv");
  },
  recalculateScores: (nicheId?: number) =>
    apiFetch<{ updated: number }>("/scoring/recalculate", {
      method: "POST",
      body: JSON.stringify(nicheId ? { niche_id: nicheId } : {}),
    }),
};

export const companiesApi = {
  list: () => apiFetch<Paginated<Company>>("/companies"),
  enrich: (id: number, sync = false) =>
    apiFetch<Company>(`/companies/${id}/enrich?sync=${sync}`, { method: "POST" }),
};

export const searchesApi = {
  generateQueries: (nicheId: number) =>
    apiFetch<{ queries: string[] }>("/searches/generate-queries", {
      method: "POST",
      body: JSON.stringify({ niche_id: nicheId }),
    }),
  run: (nicheId: number, queryText: string) =>
    apiFetch<SearchQuery>("/searches/run", {
      method: "POST",
      body: JSON.stringify({ niche_id: nicheId, query_text: queryText }),
    }),
  get: (id: number) => apiFetch<SearchQuery>(`/searches/${id}`),
  saveResults: (id: number, resultIndexes: number[]) =>
    apiFetch<{ created: number }>(`/searches/${id}/save-results`, {
      method: "POST",
      body: JSON.stringify({ result_indexes: resultIndexes }),
    }),
};

export const emailsApi = {
  preview: (leadId: number, templateId = "wellpredict") =>
    apiFetch<EmailPreview>("/emails/preview", {
      method: "POST",
      body: JSON.stringify({ lead_id: leadId, template_id: templateId }),
    }),
  generate: (leadId: number, campaignId?: number, templateId = "wellpredict") =>
    apiFetch<{ message: { id: number; status: string }; compliance_errors: string[] }>(
      "/emails/generate",
      {
        method: "POST",
        body: JSON.stringify({
          lead_id: leadId,
          template_id: templateId,
          campaign_id: campaignId ?? null,
        }),
      },
    ),
  approve: (emailMessageId: number) =>
    apiFetch<{ message: { id: number; status: string } }>("/emails/approve", {
      method: "POST",
      body: JSON.stringify({ email_message_id: emailMessageId }),
    }),
};

export const campaignsApi = {
  list: (nicheId?: number) => {
    const qs = nicheId ? `?niche_id=${nicheId}` : "";
    return apiFetch<Paginated<Campaign>>(`/campaigns${qs}`);
  },
  get: (id: number) => apiFetch<Campaign>(`/campaigns/${id}`),
  create: (data: {
    niche_id: number;
    name: string;
    daily_send_limit?: number;
    sending_window_start?: string;
    sending_window_end?: string;
    steps: Array<{
      step_number: number;
      delay_days: number;
      subject_template: string;
      body_template: string;
    }>;
  }) => apiFetch<Campaign>("/campaigns", { method: "POST", body: JSON.stringify(data) }),
  addLeads: (id: number, leadIds: number[]) =>
    apiFetch<{ created: number; message_ids: number[] }>(`/campaigns/${id}/add-leads`, {
      method: "POST",
      body: JSON.stringify({ lead_ids: leadIds }),
    }),
  start: (id: number) =>
    apiFetch<{ campaign: Campaign }>(`/campaigns/${id}/start`, { method: "POST" }),
  pause: (id: number) =>
    apiFetch<{ campaign: Campaign }>(`/campaigns/${id}/pause`, { method: "POST" }),
  processSends: (id: number) =>
    apiFetch<{ sent: number; blocked: number }>(`/campaigns/${id}/process-sends`, {
      method: "POST",
    }),
};

export const repliesApi = {
  list: (classification?: string) => {
    const qs = classification ? `?classification=${classification}` : "";
    return apiFetch<Paginated<Reply>>(`/replies${qs}`);
  },
  sync: () => apiFetch<{ synced: number; message: string }>("/replies/sync", { method: "POST" }),
  exportCsv: () => downloadAuthenticatedFile("/replies/export-csv", "replies.csv"),
  update: (
    id: number,
    data: { classification?: string; mark_meeting_booked?: boolean; notes?: string },
  ) => apiFetch<Reply>(`/replies/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
};

export const settingsApi = {
  get: () => apiFetch<UserSettings>("/settings"),
  update: (data: UserSettings) =>
    apiFetch<UserSettings>("/settings", { method: "PATCH", body: JSON.stringify(data) }),
  listSuppressions: () =>
    apiFetch<
      Paginated<{ id: number; email: string | null; domain: string | null; reason: string | null }>
    >("/suppressions"),
  createSuppression: (data: { email?: string; domain?: string; reason?: string }) =>
    apiFetch<{ id: number }>("/suppressions", {
      method: "POST",
      body: JSON.stringify({ ...data, source: "manual" }),
    }),
  deleteSuppression: (id: number) =>
    apiFetch<void>(`/suppressions/${id}`, { method: "DELETE" }),
};

export const providerSettingsApi = {
  list: () => apiFetch<{ items: ProviderCredential[] }>("/provider-settings"),
  upsert: (data: {
    provider_type: ProviderType;
    provider_name: ProviderName;
    config: Record<string, string | number | boolean | null>;
  }) =>
    apiFetch<ProviderCredential>("/provider-settings", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  activate: (id: number) =>
    apiFetch<ProviderCredential>(`/provider-settings/${id}/activate`, { method: "PATCH" }),
  test: (id: number) =>
    apiFetch<{ success: boolean; message: string; tested_at: string }>(
      `/provider-settings/${id}/test`,
      { method: "POST" },
    ),
  delete: (id: number) => apiFetch<void>(`/provider-settings/${id}`, { method: "DELETE" }),
};
