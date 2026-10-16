/**
 * API client.
 *
 * - Requests go to `/api/*`, which Next.js rewrites to the API (see next.config.ts), so the
 *   refresh cookie is first-party and httpOnly.
 * - The access token lives in memory only. On a 401 we make one shared refresh call, then retry.
 * - The current workspace is sent as `X-Workspace-Id`.
 */

export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE ?? "/api").replace(/\/$/, "");
const WORKSPACE_KEY = "lg_workspace";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let accessToken: string | null = null;
let refreshing: Promise<string | null> | null = null;
let onSessionExpired: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

/** Called once when a refresh fails, so the app can send the user to the login page. */
export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler;
}

/**
 * Impersonation: a platform admin viewing the app as a customer, in one browser tab.
 * The short-lived token lives in this tab's sessionStorage and never touches the refresh
 * cookie, so the admin's own session (and other tabs) are unaffected.
 */
const IMPERSONATION_KEY = "lg_impersonation";

export type Impersonation = {
  token: string;
  workspaceId: number;
  workspaceName: string;
  userName: string;
  userEmail: string;
  readOnly: boolean;
  expiresAt: string;
};

export function getImpersonation(): Impersonation | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.sessionStorage.getItem(IMPERSONATION_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Impersonation;
    if (new Date(value.expiresAt).getTime() <= Date.now()) {
      window.sessionStorage.removeItem(IMPERSONATION_KEY);
      return null;
    }
    return value;
  } catch {
    return null;
  }
}

export function startImpersonation(value: Impersonation): void {
  window.sessionStorage.setItem(IMPERSONATION_KEY, JSON.stringify(value));
  accessToken = value.token;
}

export function endImpersonation(): void {
  try {
    window.sessionStorage.removeItem(IMPERSONATION_KEY);
  } catch {
    // Nothing stored.
  }
  accessToken = null;
}

export function getWorkspaceId(): string | null {
  if (typeof window === "undefined") return null;
  const impersonation = getImpersonation();
  if (impersonation) return String(impersonation.workspaceId);
  try {
    return window.localStorage.getItem(WORKSPACE_KEY);
  } catch {
    return null;
  }
}

export function setWorkspaceId(id: number | null): void {
  if (typeof window === "undefined" || getImpersonation()) return;
  try {
    if (id === null) window.localStorage.removeItem(WORKSPACE_KEY);
    else window.localStorage.setItem(WORKSPACE_KEY, String(id));
  } catch {
    // Storage can be unavailable (private mode); the API falls back to the last workspace.
  }
}

/** Swap the refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshAccessToken(): Promise<string | null> {
  if (typeof window !== "undefined" && window.sessionStorage?.getItem(IMPERSONATION_KEY)) {
    // Impersonation sessions can't be renewed: they end when the token expires.
    const impersonation = getImpersonation();
    accessToken = impersonation?.token ?? null;
    return Promise.resolve(accessToken);
  }
  if (!refreshing) {
    refreshing = fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
      headers: { "X-Requested-With": "fetch" },
    })
      .then(async (response) => {
        if (!response.ok) return null;
        const body = (await response.json()) as { access_token?: string };
        return body.access_token ?? null;
      })
      .catch(() => null)
      .then((token) => {
        accessToken = token;
        return token;
      })
      .finally(() => {
        refreshing = null;
      });
  }
  return refreshing;
}

async function parseError(response: Response): Promise<ApiError> {
  let detail: unknown;
  const text = await response.text();
  try {
    detail = text ? JSON.parse(text) : undefined;
  } catch {
    detail = text;
  }
  return new ApiError(errorMessage(detail, response.status), response.status, detail);
}

type FetchOptions = RequestInit & { skipAuthRetry?: boolean };

async function rawFetch(path: string, options: FetchOptions, token: string | null) {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const workspaceId = getWorkspaceId();
  if (workspaceId && !headers.has("X-Workspace-Id")) headers.set("X-Workspace-Id", workspaceId);
  return fetch(`${API_BASE}${path}`, { ...options, headers, credentials: "include" });
}

async function request(path: string, options: FetchOptions = {}): Promise<Response> {
  let response = await rawFetch(path, options, accessToken);
  if (response.status === 401 && !options.skipAuthRetry) {
    const token = await refreshAccessToken();
    if (token) {
      response = await rawFetch(path, options, token);
    } else {
      onSessionExpired?.();
    }
  }
  if (!response.ok) throw await parseError(response);
  return response;
}

export async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const response = await request(path, options);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function apiUpload<T>(path: string, formData: FormData): Promise<T> {
  return apiFetch<T>(path, { method: "POST", body: formData });
}

export async function downloadAuthenticatedFile(path: string, filename: string): Promise<void> {
  const response = await request(path);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function queryString(params?: Record<string, unknown>): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : "";
}

/** A readable message for any API error body (FastAPI 422 lists, AppError details, text). */
export function errorMessage(detail: unknown, status?: number): string {
  if (detail && typeof detail === "object" && "detail" in detail) {
    const inner = (detail as { detail: unknown }).detail;
    if (typeof inner === "string") return inner;
    if (Array.isArray(inner) && inner.length) {
      return inner
        .map((item) => {
          const entry = item as { loc?: unknown[]; msg?: string };
          const field = entry.loc?.filter((part) => part !== "body").join(".");
          const msg = (entry.msg ?? "Invalid value").replace(/^Value error, /, "");
          return field ? `${field}: ${msg}` : msg;
        })
        .join("; ");
    }
  }
  if (typeof detail === "string" && detail.trim() && detail.length < 300) return detail;
  switch (status) {
    case 401:
      return "Your session has expired. Please sign in again.";
    case 402:
      return "You've reached your plan's limit for this. It resets at the start of the period.";
    case 403:
      return "You don't have permission to do that.";
    case 404:
      return "Not found.";
    case 429:
      return "Too many requests. Please wait a moment and try again.";
    case 503:
      return "The service is temporarily unavailable. Please try again shortly.";
    default:
      return "Something went wrong. Please try again.";
  }
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof TypeError) return "Can't reach the server. Check your connection.";
  if (error instanceof Error && error.message) return error.message;
  return "Something went wrong. Please try again.";
}

export const api = {
  health: () => apiFetch<{ status: string; environment: string }>("/health"),
  healthReady: () =>
    apiFetch<{
      status: string;
      environment: string;
      dependencies: Array<{ name: string; status: string; detail?: string | null }>;
    }>("/health/ready"),
};
