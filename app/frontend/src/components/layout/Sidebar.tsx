import { Bell, Database, LayoutDashboard, Settings } from "lucide-react";
import eSymbolUrl from "../../assets/e-symbol.svg";

type SidebarProps = {
  activePage: string;
  onChangePage: (page: string) => void;
};

const items = [
  { id: "dashboard", label: "Дашборд", icon: LayoutDashboard },
  { id: "purchases", label: "Закупки", icon: Database },
  { id: "newsletter", label: "Рассылка", icon: Bell },
  { id: "admin", label: "Админ-панель", icon: Settings },
];

export function Sidebar({ activePage, onChangePage }: SidebarProps) {
  return (
    <aside className="hidden w-72 border-r border-[color:var(--se-border)] bg-white/90 px-4 py-6 backdrop-blur lg:block">
      <div className="mb-8 px-2">
        <div className="flex items-center gap-3">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-[color:var(--se-border)]">
            <img
              src={eSymbolUrl}
              alt="Systeme Electric"
              className="h-8 w-8 object-contain"
            />
          </div>

          <div>
            <div className="font-bold text-[color:var(--se-techno-green)]">
              Systeme Electric
            </div>
            <div className="text-xs text-[color:var(--se-muted)]">
              Мониторинг закупок
            </div>
          </div>
        </div>
      </div>

      <nav className="space-y-1">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = activePage === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onChangePage(item.id)}
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
    </aside>
  );
}