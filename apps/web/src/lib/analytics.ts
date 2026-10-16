"use client";

/**
 * Product analytics (PostHog). Off unless NEXT_PUBLIC_POSTHOG_KEY is set AND the visitor chose
 * "Accept all" in the cookie banner. Never sends email addresses or names: users are identified
 * by their numeric id only, and impersonation sessions are never tracked.
 */
import { getConsent } from "@/lib/consent";

const KEY = process.env.NEXT_PUBLIC_POSTHOG_KEY;
const HOST = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://eu.i.posthog.com";

/** Funnel events. Keep names stable: dashboards depend on them. */
export type AnalyticsEvent =
  | "signed_up"
  | "email_verified"
  | "provider_connected"
  | "campaign_created"
  | "emails_approved"
  | "first_send"
  | "checkout_started"
  | "feedback_sent";

type PostHog = typeof import("posthog-js").default;
let client: PostHog | null = null;
let loading: Promise<PostHog | null> | null = null;

export function analyticsConfigured(): boolean {
  return Boolean(KEY);
}

async function load(): Promise<PostHog | null> {
  if (!KEY || typeof window === "undefined" || getConsent() !== "all") return null;
  if (window.sessionStorage?.getItem("lg_impersonation")) return null;
  if (client) return client;
  loading ??= import("posthog-js").then(({ default: posthog }) => {
    posthog.init(KEY, {
      api_host: HOST,
      capture_pageview: "history_change",
      persistence: "localStorage+cookie",
      autocapture: false,
      disable_session_recording: true,
      mask_all_text: true,
    });
    client = posthog;
    return posthog;
  });
  return loading;
}

/** Start analytics if allowed (call after consent changes). */
export function initAnalytics(): void {
  void load();
}

export function track(event: AnalyticsEvent, properties: Record<string, string | number | boolean> = {}): void {
  void load().then((posthog) => posthog?.capture(event, properties));
}

export function identify(userId: number, workspaceId?: number | null, plan?: string): void {
  void load().then((posthog) => {
    if (!posthog) return;
    posthog.identify(String(userId));
    if (workspaceId) posthog.group("workspace", String(workspaceId), plan ? { plan } : undefined);
  });
}

export function resetAnalytics(): void {
  client?.reset();
}

export function optOut(): void {
  client?.opt_out_capturing();
}
