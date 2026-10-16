import * as Sentry from "@sentry/nextjs";

export async function register() {
  if (process.env.NEXT_RUNTIME === "nodejs" || process.env.NEXT_RUNTIME === "edge") {
    const { sentryOptions } = await import("@/lib/sentry-options");
    Sentry.init(sentryOptions);
  }
}

export const onRequestError = Sentry.captureRequestError;
