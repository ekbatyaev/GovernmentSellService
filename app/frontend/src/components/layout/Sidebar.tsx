import { useEffect, useState } from "react";
import { Bell, Database, KeyRound, LayoutDashboard, LogOut, Settings, X } from "lucide-react";
import eSymbolUrl from "../../assets/e-symbol.svg";
import { useAuth } from "../../auth/AuthContext";
import { ChangePasswordModal } from "./ChangePasswordModal";

type SidebarProps = {
  activePage: string;
  onChangePage: (page: string) => void;
  /** Открыт ли сайдбар как выезжающая панель на узких экранах (< lg); на десктопе не влияет. */
  open: boolean;
  onClose: () => void;
};

const items = [
  { id: "dashboard", label: "Дашборд", icon: LayoutDashboard },
  { id: "purchases", label: "Закупки", icon: Database },
  { id: "newsletter", label: "Рассылка", icon: Bell },
  { id: "admin", label: "Админ-панель", icon: Settings },
];

export function Sidebar({ activePage, onChangePage, open, onClose }: SidebarProps) {
  const { logout } = useAuth();
  const [passwordOpen, setPasswordOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [open, onClose]);

  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        id="app-sidebar"
        className={`fixed inset-y-0 left-0 z-40 w-72 overflow-y-auto border-r border-[color:var(--se-border)] bg-white px-4 py-6 transition-transform duration-200 lg:static lg:z-auto lg:translate-x-0 lg:overflow-visible lg:bg-white/90 lg:shadow-none lg:backdrop-blur ${
          open ? "translate-x-0 shadow-xl" : "-translate-x-full"
        }`}
      >
        <div className="mb-8 px-2">
          <div className="flex items-center gap-3">
            <div className="flex size-12 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-[color:var(--se-border)]">
              <img
                src={eSymbolUrl}
                alt="Systeme Electric"
                className="h-8 w-8 object-contain"
              />
            </div>

            <div className="flex-1">
              <div className="font-bold text-[color:var(--se-techno-green)]">
                Systeme Electric
              </div>
              <div className="text-xs text-[color:var(--se-muted)]">
                Мониторинг закупок
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              aria-label="Закрыть меню"
              className="rounded-xl p-1.5 text-[color:var(--se-muted)] transition hover:bg-slate-100 hover:text-[color:var(--se-text)] lg:hidden"
            >
              <X size={20} />
            </button>
          </div>
        </div>

        <nav className="space-y-1">
          {items.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.id;

            return (
              <button
                key={item.id}
                onClick={() => {
                  onChangePage(item.id);
                  onClose();
                }}
                className={`flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-semibold transition ${
                  isActive
                    ? "bg-[color:var(--se-techno-green)] text-white shadow-sm shadow-emerald-900/10"
                    : "text-[color:var(--se-muted)] hover:bg-emerald-50 hover:text-[color:var(--se-techno-green)]"
                }`}
              >
                <Icon size={18} />
                {item.label}
              </button>
            );
          })}
        </nav>

        <button
          type="button"
          onClick={() => {
            setPasswordOpen(true);
            onClose();
          }}
          className="mt-6 flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-semibold text-[color:var(--se-muted)] transition hover:bg-emerald-50 hover:text-[color:var(--se-techno-green)]"
        >
          <KeyRound size={18} />
          Сменить пароль
        </button>

        <button
          type="button"
          onClick={logout}
          className="mt-1 flex w-full items-center gap-3 rounded-2xl px-3 py-2.5 text-sm font-semibold text-[color:var(--se-muted)] transition hover:bg-rose-50 hover:text-rose-600"
        >
          <LogOut size={18} />
          Выйти
        </button>
      </aside>

      {passwordOpen && <ChangePasswordModal onClose={() => setPasswordOpen(false)} />}
    </>
  );
}
