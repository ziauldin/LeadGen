import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}

export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn("flex flex-col md:flex-row md:items-center justify-between gap-4 mb-6", className)}>
      <div>
        <h2
          className="text-[36px] font-bold leading-[44px] tracking-[-0.02em]"
          style={{ color: "var(--on-surface)" }}
        >
          {title}
        </h2>
        {description && (
          <p
            className="text-[14px] leading-[20px] mt-1"
            style={{ color: "var(--on-surface-variant)" }}
          >
            {description}
          </p>
        )}
      </div>
      {actions && (
        <div className="flex flex-wrap items-center gap-3 shrink-0">{actions}</div>
      )}
    </div>
  );
}
