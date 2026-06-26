import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, XCircle } from "lucide-react";

export type EmailPreviewData = {
  recipient_email: string;
  subject: string;
  body: string;
  has_opt_out_line?: boolean;
  compliance_errors?: string[];
  can_send?: boolean;
  compliance_ok?: boolean;
  compliance_issues?: string[];
};

export function EmailPreview({ preview }: { preview: EmailPreviewData }) {
  const errors = preview.compliance_errors ?? preview.compliance_issues ?? [];
  const canSend =
    preview.can_send ?? (errors.length === 0 && (preview.has_opt_out_line ?? preview.compliance_ok));

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-base">Email preview</CardTitle>
        <Badge variant={canSend ? "default" : "destructive"}>
          {canSend ? "Ready for approval" : "Blocked"}
        </Badge>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">To: {preview.recipient_email}</p>
        <p className="font-medium">{preview.subject}</p>
        <pre className="whitespace-pre-wrap rounded-lg border bg-muted/30 p-4 text-sm">
          {preview.body}
        </pre>
        {canSend ? (
          <Alert>
            <CheckCircle2 className="size-4" />
            <AlertTitle>Compliance checks passed</AlertTitle>
            <AlertDescription>Opt-out line present and required fields are set.</AlertDescription>
          </Alert>
        ) : (
          <Alert variant="destructive">
            <XCircle className="size-4" />
            <AlertTitle>Cannot approve yet</AlertTitle>
            <AlertDescription>
              <ul className="mt-1 list-disc pl-4">
                {errors.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
                {!preview.has_opt_out_line && errors.length === 0 ? (
                  <li>Missing opt-out line in template</li>
                ) : null}
              </ul>
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
