import type { PropsWithChildren } from "react";
import { Sidebar } from "./Sidebar";

type AppShellProps = PropsWithChildren<{
  activePage: string;
  onChangePage: (page: string) => void;
}>;

export function AppShell({ activePage, onChangePage, children }: AppShellProps) {
  return (
    <div className="se-shell-gradient min-h-screen text-[color:var(--se-text)]">
      <div className="flex min-h-screen">
        <Sidebar activePage={activePage} onChangePage={onChangePage} />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </div>
  );
}