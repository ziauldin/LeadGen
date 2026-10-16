"use client";

import { useEffect } from "react";
import { useAuth } from "@/hooks/use-auth";
import { useWorkspace } from "@/hooks/use-workspace";
import { identify, initAnalytics, optOut } from "@/lib/analytics";
import { useConsent } from "@/lib/consent";

/** Starts analytics once the visitor consents, and ties events to the signed-in user (by id). */
export function AnalyticsBridge() {
  const consent = useConsent();
  const { user } = useAuth();
  const { current } = useWorkspace();

  useEffect(() => {
    if (consent === "all") initAnalytics();
    if (consent === "essential") optOut();
  }, [consent]);

  useEffect(() => {
    if (consent === "all" && user && !user.impersonation) identify(user.id, current?.id, current?.plan);
  }, [consent, user, current?.id, current?.plan]);

  return null;
}
