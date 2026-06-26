import { Badge } from "@/components/ui/badge";

export function ScoreBadge({ score }: { score: number }) {
  const variant = score >= 80 ? "default" : score >= 60 ? "secondary" : "outline";
  return <Badge variant={variant}>{Math.round(score)}</Badge>;
}
