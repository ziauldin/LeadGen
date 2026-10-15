/** Small display helpers shared by the campaign pages. */

const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
const dateOnly = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateTime.format(date);
}

export function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : dateOnly.format(date);
}

/** 0.0523 -> "5.2%"; small non-zero rates keep two decimals so 0.08% doesn't read as 0%. */
export function formatRate(rate: number | null | undefined): string {
  if (!rate) return "0%";
  const percent = rate * 100;
  const digits = percent < 1 ? 2 : 1;
  return `${percent.toFixed(digits).replace(/\.?0+$/, "")}%`;
}

/** "pending_approval" -> "Pending approval". */
export function humanize(value: string | null | undefined): string {
  if (!value) return "—";
  const text = value.replace(/_/g, " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export const WEEKDAYS = [
  { value: 0, short: "Mon", long: "Monday" },
  { value: 1, short: "Tue", long: "Tuesday" },
  { value: 2, short: "Wed", long: "Wednesday" },
  { value: 3, short: "Thu", long: "Thursday" },
  { value: 4, short: "Fri", long: "Friday" },
  { value: 5, short: "Sat", long: "Saturday" },
  { value: 6, short: "Sun", long: "Sunday" },
] as const;

export function formatSendingDays(days: number[] | null | undefined): string {
  if (!days || days.length === 0 || days.length === 7) return "Every day";
  const sorted = [...days].sort();
  if (sorted.join(",") === "0,1,2,3,4") return "Weekdays (Mon–Fri)";
  return sorted.map((day) => WEEKDAYS[day]?.short ?? day).join(", ");
}

/** Rates the system watches: above "danger" it pauses the campaign automatically. */
export const RATE_THRESHOLDS = {
  bounce: { warn: 0.02, danger: 0.05 },
  complaint: { warn: 0.0005, danger: 0.001 },
} as const;

export type RateLevel = "ok" | "warn" | "danger";

export function rateLevel(rate: number, kind: keyof typeof RATE_THRESHOLDS): RateLevel {
  const limits = RATE_THRESHOLDS[kind];
  if (rate > limits.danger) return "danger";
  if (rate > limits.warn) return "warn";
  return "ok";
}
