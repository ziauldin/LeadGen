"use client";

import { useSyncExternalStore } from "react";

/**
 * Cookie consent. Essential cookies (session, CSRF, preferences) need no consent; analytics
 * only load after the visitor chooses "all". Stored in localStorage on this device.
 */
export type Consent = "all" | "essential";
const KEY = "lg_cookie_consent";
const EVENT = "lg-consent-change";

export function getConsent(): Consent | null {
  if (typeof window === "undefined") return null;
  try {
    const value = window.localStorage.getItem(KEY);
    return value === "all" || value === "essential" ? value : null;
  } catch {
    return null;
  }
}

export function setConsent(value: Consent): void {
  try {
    window.localStorage.setItem(KEY, value);
  } catch {
    // Storage blocked: the choice lasts for this page view only.
  }
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

/** `undefined` while rendering on the server, `null` until the visitor chooses. */
export function useConsent(): Consent | null | undefined {
  return useSyncExternalStore(subscribe, getConsent, () => undefined);
}
