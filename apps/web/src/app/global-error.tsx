"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

/** Last-resort error page when the root layout itself fails. */
export default function GlobalError({ error }: { error: Error & { digest?: string } }) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", padding: 40, textAlign: "center" }}>
        <h1>Something went wrong</h1>
        <p>Please reload the page. If it keeps happening, contact support
          {error.digest ? ` (reference ${error.digest})` : ""}.</p>
      </body>
    </html>
  );
}
