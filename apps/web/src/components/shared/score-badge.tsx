import { cn } from "@/lib/utils";

interface ScoreBadgeProps {
  score: number;
  className?: string;
}

function getScoreStyle(score: number): { bg: string; text: string; border: string } {
  if (score >= 80)
    return {
      bg: "var(--secondary-container)",
      text: "var(--on-secondary-container)",
      border: "rgba(0,108,73,0.2)",
    };
  if (score >= 60)
    return {
      bg: "var(--primary-container)",
      text: "var(--on-primary-container)",
      border: "rgba(53,37,205,0.2)",
    };
  if (score >= 40)
    return {
      bg: "var(--tertiary-fixed)",
      text: "var(--on-tertiary-fixed)",
      border: "rgba(104,64,0,0.2)",
    };
  return {
    bg: "var(--surface-variant)",
    text: "var(--on-surface-variant)",
    border: "var(--outline-variant)",
  };
}

export function ScoreBadge({ score, className }: ScoreBadgeProps) {
  const style = getScoreStyle(score);
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center px-2 py-1 rounded-full text-[12px] font-semibold leading-[16px] tracking-[0.05em] border min-w-[36px]",
        className,
      )}
      style={{
        background: style.bg,
        color: style.text,
        borderColor: style.border,
      }}
      title={`Score: ${score}`}
    >
      {score}
    </span>
  );
}
