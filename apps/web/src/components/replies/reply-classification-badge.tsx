import type { ReplyClassification } from "@/lib/api/types";
import { Badge } from "@/components/ui/badge";

const styles: Record<ReplyClassification, "default" | "secondary" | "destructive" | "outline"> = {
  positive: "default",
  neutral: "secondary",
  objection: "outline",
  unsubscribe: "destructive",
  bounce: "destructive",
  unknown: "outline",
};

export function ReplyClassificationBadge({
  classification,
}: {
  classification: ReplyClassification;
}) {
  return (
    <Badge variant={styles[classification]}>
      {classification.replace("_", " ")}
    </Badge>
  );
}
