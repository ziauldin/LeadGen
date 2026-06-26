import { CheckCircle2, Circle, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { Lead } from "@/lib/api/types";

type CheckItem = {
  label: string;
  passed: boolean;
};

function buildChecks(lead: Lead, issues: string[] = []): CheckItem[] {
  const suppressed = issues.some((issue) => issue.toLowerCase().includes("suppression"));
  return [
    { label: "Email contact on file", passed: Boolean(lead.primary_email) },
    { label: "Not opted out", passed: lead.status !== "opted_out" },
    { label: "Source URL recorded", passed: Boolean(lead.source_url) },
    { label: "Compliance / source note", passed: Boolean(lead.compliance_source_note) },
    { label: "Not on suppression list", passed: !suppressed },
  ];
}

export function OutreachChecklist({
  lead,
  issues = [],
}: {
  lead: Lead;
  issues?: string[];
}) {
  const checks = buildChecks(lead, issues);
  const ready = checks.every((check) => check.passed) && issues.length === 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Outreach readiness</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <ul className="space-y-2 text-sm">
          {checks.map((check) => (
            <li key={check.label} className="flex items-center gap-2">
              {check.passed ? (
                <CheckCircle2 className="size-4 text-green-600" />
              ) : (
                <XCircle className="size-4 text-destructive" />
              )}
              <span>{check.label}</span>
            </li>
          ))}
        </ul>
        {issues.length > 0 ? (
          <ul className="space-y-1 border-t pt-3 text-sm text-destructive">
            {issues.map((issue) => (
              <li key={issue} className="flex items-start gap-2">
                <Circle className="mt-1 size-3 shrink-0" />
                <span>{issue}</span>
              </li>
            ))}
          </ul>
        ) : null}
        <p className="text-sm text-muted-foreground">
          {ready
            ? "This lead passes client-side outreach checks. Approval and campaign gates still apply before sending."
            : "Resolve the items above before generating or approving outreach."}
        </p>
      </CardContent>
    </Card>
  );
}
