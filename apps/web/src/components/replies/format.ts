export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: date.getFullYear() === new Date().getFullYear() ? undefined : "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function formatRelative(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  const diff = Date.now() - date.getTime();
  if (Number.isNaN(diff)) return "—";
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  const days = Math.round(hours / 24);
  if (days < 7) return `${days} d ago`;
  return formatDateTime(value);
}

export function emailDomain(email: string | null | undefined): string {
  if (!email || !email.includes("@")) return "";
  return email.split("@").pop()!.trim().toLowerCase();
}

/** How a reply was tied to one of our sent emails, in plain words. */
export const MATCH_METHODS: Record<string, { label: string; detail: string; low?: boolean }> = {
  in_reply_to: {
    label: "Email thread headers",
    detail: "The reply referenced our message ID, so the match is certain.",
  },
  reply_token: {
    label: "Reply address token",
    detail: "The reply was sent to the unique reply address on our email.",
  },
  provider: {
    label: "Sending provider",
    detail: "The email provider told us which message this reply belongs to.",
  },
  sender_fallback: {
    label: "Sender address (low confidence)",
    detail:
      "Matched only because it came from an address we emailed. Check the conversation is right.",
    low: true,
  },
  sender: {
    label: "Sender address (low confidence)",
    detail:
      "Matched only because it came from an address we emailed. Check the conversation is right.",
    low: true,
  },
  manual: {
    label: "Linked by hand",
    detail: "Someone on your team linked this reply to a sent email.",
  },
  unmatched: {
    label: "Not matched",
    detail: "We couldn't tell which sent email this answers.",
    low: true,
  },
};
