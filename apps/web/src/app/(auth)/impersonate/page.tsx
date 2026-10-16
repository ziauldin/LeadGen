"use client";

import { useEffect, useState } from "react";
import { startImpersonation, type Impersonation } from "@/lib/api/client";

/** Opened in a new tab by the admin area with the session in the URL fragment (never sent to a server). */
export default function ImpersonatePage() {
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    try {
      const encoded = window.location.hash.slice(1);
      const session = JSON.parse(decodeURIComponent(encoded)) as Impersonation;
      if (!session.token || !session.workspaceId) throw new Error("missing");
      startImpersonation(session);
      // Drop the token from the address bar and history.
      window.location.replace("/dashboard");
    } catch {
      setError("This impersonation link is invalid or has expired. Start a new session from the admin area.");
    }
  }, []);

  return (
    <div className="flex min-h-screen items-center justify-center p-4 text-[14px]" role="status">
      {error ?? "Opening the customer's workspace…"}
    </div>
  );
}
