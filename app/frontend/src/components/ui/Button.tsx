import type { ButtonHTMLAttributes, PropsWithChildren } from "react";

type ButtonProps = PropsWithChildren<ButtonHTMLAttributes<HTMLButtonElement>> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
};

export function Button({
  children,
  variant = "primary",
  className = "",
  ...props
}: ButtonProps) {
  const base =
    "inline-flex h-10 items-center justify-center rounded-xl px-4 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50";

  const variants = {
    primary:
      "bg-[color:var(--se-techno-green)] text-white hover:brightness-95 shadow-sm shadow-emerald-900/10",
    secondary:
      "border border-[color:var(--se-border)] bg-white text-[color:var(--se-text)] hover:bg-emerald-50",
    ghost:
      "bg-transparent text-[color:var(--se-muted)] hover:bg-emerald-50 hover:text-[color:var(--se-techno-green)]",
    danger:
      "bg-[color:var(--se-coral-pink)] text-white hover:brightness-95",
  };

  return (
    <button className={`${base} ${variants[variant]} ${className}`} {...props}>
      {children}
    </button>
  );
}