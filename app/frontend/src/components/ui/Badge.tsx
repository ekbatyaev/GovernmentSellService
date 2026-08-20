import type { PropsWithChildren } from "react";

type BadgeProps = PropsWithChildren<{
  tone?: "default" | "success" | "warning" | "danger";
}>;

export function Badge({ children, tone = "default" }: BadgeProps) {
  const tones = {
    default: "bg-slate-100 text-slate-700",
    success: "bg-emerald-50 text-emerald-700",
    warning: "bg-amber-50 text-amber-700",
    danger: "bg-rose-50 text-rose-700",
  };

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${tones[tone]}`}
    >
      {children}
    </span>
  );
}