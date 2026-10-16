import type { ErrorEvent } from "@sentry/nextjs";

const SENSITIVE = /password|token|secret|authorization|cookie|api[_-]?key|email|body|subject/i;

function scrub(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(scrub);
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([key, item]) => [
        key,
        SENSITIVE.test(key) ? "[redacted]" : scrub(item),
      ]),
    );
  }
  return value;
}

/** Never send request bodies, cookies or contact details to Sentry. */
export function beforeSend(event: ErrorEvent): ErrorEvent {
  if (event.request) {
    delete event.request.data;
    delete event.request.cookies;
    if (event.request.headers) event.request.headers = scrub(event.request.headers) as Record<string, string>;
  }
  if (event.extra) event.extra = scrub(event.extra) as Record<string, unknown>;
  return event;
}

export const sentryOptions = {
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN,
  enabled: Boolean(process.env.NEXT_PUBLIC_SENTRY_DSN),
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT ?? process.env.NODE_ENV,
  release: process.env.NEXT_PUBLIC_RELEASE || undefined,
  tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? 0),
  sendDefaultPii: false,
  beforeSend,
};
