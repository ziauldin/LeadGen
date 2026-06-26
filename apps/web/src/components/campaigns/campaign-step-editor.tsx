import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

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
  return (
    <div className="space-y-4 rounded-lg border p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-2">
          <label className="text-sm font-medium">Step number</label>
          <Input
            type="number"
            min={1}
            value={step.step_number}
            onChange={(e) =>
              onChange({ ...step, step_number: Number(e.target.value) || 1 })
            }
          />
        </div>
        <div className="space-y-2">
          <label className="text-sm font-medium">Delay (days)</label>
          <Input
            type="number"
            min={0}
            value={step.delay_days}
            onChange={(e) => onChange({ ...step, delay_days: Number(e.target.value) || 0 })}
          />
        </div>
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium">Subject template</label>
        <Input
          value={step.subject_template}
          onChange={(e) => onChange({ ...step, subject_template: e.target.value })}
        />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium">Body template</label>
        <Textarea
          rows={12}
          value={step.body_template}
          onChange={(e) => onChange({ ...step, body_template: e.target.value })}
        />
        <p className="text-xs text-muted-foreground">
          Variables: {"{{first_name}}"}, {"{{company}}"}, {"{{pain_point}}"}, {"{{sender_name}}"},
          {" {{unsubscribe_link}}"}
        </p>
      </div>
    </div>
  );
}
