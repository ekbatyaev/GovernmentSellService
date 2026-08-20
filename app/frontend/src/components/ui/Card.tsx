import type { PropsWithChildren } from "react";

type CardProps = PropsWithChildren<{
  className?: string;
}>;

export function Card({ children, className = "" }: CardProps) {
  return (
    <div className={`se-card rounded-3xl p-5 ${className}`}>
      {children}
    </div>
  );
}