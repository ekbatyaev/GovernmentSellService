import { useState, type PropsWithChildren } from "react";
import { Menu } from "lucide-react";
import eSymbolUrl from "../../assets/e-symbol.svg";
import { Sidebar } from "./Sidebar";

type AppShellProps = PropsWithChildren<{
  activePage: string;
  onChangePage: (page: string) => void;
}>;

export function AppShell({ activePage, onChangePage, children }: AppShellProps) {
  // Выезжающее меню на узких экранах (< lg); на десктопе сайдбар виден всегда
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="se-shell-gradient min-h-screen text-[color:var(--se-text)]">
      <div className="flex min-h-screen">
        <Sidebar
          activePage={activePage}
          onChangePage={onChangePage}
          open={menuOpen}
          onClose={() => setMenuOpen(false)}
        />
        <main className="min-w-0 flex-1">
          <div className="sticky top-0 z-20 flex items-center gap-3 border-b border-[color:var(--se-border)] bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
            <button
              type="button"
              onClick={() => setMenuOpen(true)}
              aria-label="Открыть меню"
              aria-expanded={menuOpen}
              aria-controls="app-sidebar"
              className="rounded-xl p-2 text-[color:var(--se-muted)] transition hover:bg-emerald-50 hover:text-[color:var(--se-techno-green)]"
            >
              <Menu size={22} />
            </button>
            <img src={eSymbolUrl} alt="" className="h-7 w-7 object-contain" />
            <div className="font-bold text-[color:var(--se-techno-green)]">Systeme Electric</div>
          </div>
          {children}
        </main>
      </div>
    </div>
  );
}
