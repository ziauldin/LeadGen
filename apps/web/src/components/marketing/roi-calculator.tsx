"use client";

import { useId, useState } from "react";

type Field = {
  key: "prospects" | "replyRate" | "meetingRate" | "closeRate" | "dealValue";
  label: string;
  min: number;
  max: number;
  step: number;
  format: (value: number) => string;
};

const FIELDS: Field[] = [
  { key: "prospects", label: "New prospects emailed a month", min: 100, max: 10_000, step: 100, format: (v) => v.toLocaleString() },
  { key: "replyRate", label: "Reply rate", min: 1, max: 20, step: 0.5, format: (v) => `${v}%` },
  { key: "meetingRate", label: "Replies that become meetings", min: 5, max: 60, step: 5, format: (v) => `${v}%` },
  { key: "closeRate", label: "Meetings that become customers", min: 5, max: 50, step: 5, format: (v) => `${v}%` },
  { key: "dealValue", label: "Average first-year deal value", min: 500, max: 50_000, step: 500, format: (v) => `$${v.toLocaleString()}` },
];

const DEFAULTS = { prospects: 1_000, replyRate: 5, meetingRate: 30, closeRate: 20, dealValue: 6_000 };

/** "What could this be worth?" An estimate from the visitor's own numbers; nothing is stored. */
export function RoiCalculator() {
  const id = useId();
  const [values, setValues] = useState(DEFAULTS);
  const replies = (values.prospects * values.replyRate) / 100;
  const meetings = (replies * values.meetingRate) / 100;
  const customers = (meetings * values.closeRate) / 100;
  const pipeline = customers * values.dealValue;
  const round = (value: number) => (value >= 10 ? Math.round(value) : Math.round(value * 10) / 10);

  return (
    <div className="mk-card grid gap-8 p-6 sm:p-8 lg:grid-cols-[1.1fr_0.9fr]">
      <form className="space-y-6" onSubmit={(event) => event.preventDefault()} aria-label="Outreach estimate inputs">
        {FIELDS.map((field) => (
          <div key={field.key}>
            <div className="flex items-baseline justify-between gap-3">
              <label htmlFor={`${id}-${field.key}`} className="text-[14px] font-medium text-white">
                {field.label}
              </label>
              <output htmlFor={`${id}-${field.key}`} className="text-[14px] font-semibold tabular-nums text-[#cfc7ff]">
                {field.format(values[field.key])}
              </output>
            </div>
            <input
              id={`${id}-${field.key}`}
              type="range"
              min={field.min}
              max={field.max}
              step={field.step}
              value={values[field.key]}
              onChange={(event) => setValues((current) => ({ ...current, [field.key]: Number(event.target.value) }))}
              className="mt-3 w-full cursor-pointer accent-[#8f7cff]"
            />
          </div>
        ))}
      </form>
      <div className="flex flex-col justify-between rounded-2xl bg-gradient-to-br from-[#5b4bff]/25 via-[#7b3fe4]/15 to-[#f472b6]/10 p-6 ring-1 ring-white/10">
        <div aria-live="polite">
          <p className="text-[13px] font-semibold uppercase tracking-wider text-[#cfc7ff]">Every month, roughly</p>
          <dl className="mt-5 grid grid-cols-3 gap-3">
            {[
              ["Replies", round(replies)],
              ["Meetings", round(meetings)],
              ["Customers", round(customers)],
            ].map(([label, value]) => (
              <div key={label} className="rounded-xl bg-black/20 p-3 text-center">
                <dt className="text-[12px] text-[var(--mk-muted)]">{label}</dt>
                <dd className="mt-1 text-[22px] font-bold tabular-nums text-white">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-6 text-[13px] text-[var(--mk-muted)]">New first-year revenue</p>
          <p className="mk-gradient-text text-[44px] font-bold leading-tight tabular-nums">
            ${Math.round(pipeline).toLocaleString()}
          </p>
        </div>
        <p className="mt-6 text-[12px] leading-5 text-[var(--mk-muted)]">
          An estimate from the numbers you choose, not a promise. Results depend on your list, offer and follow-up.
        </p>
      </div>
    </div>
  );
}
