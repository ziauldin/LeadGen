"use client";

export type CampaignStepInput = {
  step_number: number;
  delay_days: number;
  subject_template: string;
  body_template: string;
};

export function CampaignStepEditor({
  step,
  onChange,
}: {
  step: CampaignStepInput;
  onChange: (step: CampaignStepInput) => void;
}) {
  const labelClass = "block text-[13px] font-semibold mb-1.5";
  const inputClass = "w-full px-3 py-2 border rounded text-[13px] outline-none transition-colors";
  const inputStyle = {
    borderColor: "var(--outline-variant)",
    color: "var(--on-surface)",
    background: "var(--surface-container-lowest)",
  };

  const handleFocus = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    e.target.style.borderColor = "var(--primary)";
    e.target.style.boxShadow = "0 0 0 1px var(--primary)";
  };

  const handleBlur = (e: React.FocusEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    e.target.style.borderColor = "var(--outline-variant)";
    e.target.style.boxShadow = "none";
  };

  return (
    <div
      className="space-y-4 rounded-lg border p-5 bg-white"
      style={{ borderColor: "var(--outline-variant)" }}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className={labelClass} style={{ color: "var(--on-surface)" }}>
            Step Number
          </label>
          <input
            type="number"
            min={1}
            value={step.step_number}
            onChange={(e) =>
              onChange({ ...step, step_number: Number(e.target.value) || 1 })
            }
            className={inputClass}
            style={inputStyle}
            onFocus={handleFocus}
            onBlur={handleBlur}
          />
        </div>
        <div>
          <label className={labelClass} style={{ color: "var(--on-surface)" }}>
            Delay (days)
          </label>
          <input
            type="number"
            min={0}
            value={step.delay_days}
            onChange={(e) =>
              onChange({ ...step, delay_days: Number(e.target.value) || 0 })
            }
            className={inputClass}
            style={inputStyle}
            onFocus={handleFocus}
            onBlur={handleBlur}
          />
        </div>
      </div>

      <div>
        <label className={labelClass} style={{ color: "var(--on-surface)" }}>
          Subject Template
        </label>
        <input
          type="text"
          value={step.subject_template}
          onChange={(e) => onChange({ ...step, subject_template: e.target.value })}
          className={inputClass}
          style={inputStyle}
          onFocus={handleFocus}
          onBlur={handleBlur}
          placeholder="e.g. Quick question regarding {{company}}"
        />
      </div>

      <div>
        <label className={labelClass} style={{ color: "var(--on-surface)" }}>
          Body Template
        </label>
        <textarea
          rows={10}
          value={step.body_template}
          onChange={(e) => onChange({ ...step, body_template: e.target.value })}
          className="w-full px-3 py-2 border rounded text-[13px] outline-none transition-colors font-mono"
          style={inputStyle}
          onFocus={handleFocus}
          onBlur={handleBlur}
          placeholder="Hi {{first_name}},\n\n..."
        />
        <div
          className="mt-2 p-2.5 rounded text-[11px] leading-[16px]"
          style={{ background: "var(--surface-container-low)", color: "var(--on-surface-variant)" }}
        >
          <strong>Available placeholders:</strong>{" "}
          <code className="bg-white px-1 py-0.5 rounded border">{"{{first_name}}"}</code>,{" "}
          <code className="bg-white px-1 py-0.5 rounded border">{"{{company}}"}</code>,{" "}
          <code className="bg-white px-1 py-0.5 rounded border">{"{{pain_point}}"}</code>,{" "}
          <code className="bg-white px-1 py-0.5 rounded border">{"{{sender_name}}"}</code>,{" "}
          <code className="bg-white px-1 py-0.5 rounded border">{"{{unsubscribe_link}}"}</code>
        </div>
      </div>
    </div>
  );
}
