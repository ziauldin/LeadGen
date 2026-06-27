import { type ReactNode } from "react";
import { cn } from "@/lib/utils";

interface KpiCardProps {
  label: string;
  value: string | number;
  dot?: "green" | "red" | "amber" | "blue" | "none";
  highlight?: boolean;
  trend?: ReactNode;
  className?: string;
}

const dotColors: Record<string, string> = {
  green: "#10b981",
  red: "#f43f5e",
  amber: "#f59e0b",
  blue: "#4f46e5",
};

export function KpiCard({ label, value, dot, highlight, trend, className }: KpiCardProps) {
  return (
    <div
      className={cn(
        "bg-white border rounded-lg p-4 shadow-sm flex flex-col justify-between",
        className,
      )}
      style={{ borderColor: "var(--outline-variant)", minHeight: "96px" }}
    >
      <div className="flex justify-between items-start">
        <p
          className="text-[13px] font-medium leading-[18px] truncate"
          style={{ color: "var(--on-surface-variant)" }}
        >
          {label}
        </p>
        {dot && dot !== "none" && (
          <span
            className="w-2 h-2 rounded-full mt-1 shrink-0"
            style={{ background: dotColors[dot] }}
          />
        )}
      </div>
      <p
        className="text-[20px] font-semibold leading-[28px] tracking-[-0.01em] mt-2"
        style={{ color: highlight ? "var(--primary)" : "var(--on-surface)" }}
      >
        {typeof value === "number" ? value.toLocaleString() : value}
      </p>
      {trend && <div className="mt-1">{trend}</div>}
    </div>
  );
}
