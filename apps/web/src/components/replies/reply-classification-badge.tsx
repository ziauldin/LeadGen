import type { ReplyClassification } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";

const styles: Record<ReplyClassification, "default" | "secondary" | "destructive" | "outline"> = {
  positive: "default",
  neutral: "secondary",
  objection: "outline",
  unsubscribe: "destructive",
  bounce: "destructive",
  out_of_office: "secondary",
  auto_reply: "secondary",
  wrong_person: "outline",
  unknown: "outline",
};

export function ReplyClassificationBadge({
  classification,
}: {
  classification: ReplyClassification;
}) {
  return (
    <Badge variant={styles[classification]}>
      {classification.replaceAll("_", " ")}
    </Badge>
  );
}
