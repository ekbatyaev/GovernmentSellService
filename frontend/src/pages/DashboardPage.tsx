import { useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  CheckCircle2,
  Clock3,
  Database,
  RefreshCw,
  Search,
} from "lucide-react";
import { getStats, type Stats } from "../api/stats";
import { Card } from "../components/ui/Card";
import { Header } from "../components/layout/Header";
import { formatDate } from "../lib/format";

function StatCard({
  title,
  value,
  description,
  icon: Icon,
}: {
  title: string;
  value: string | number;
  description: string;
  icon: typeof Database;
}) {
  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm text-[color:var(--se-muted)]">{title}</div>
          <div className="mt-3 text-3xl font-bold tracking-tight">{value}</div>
          <div className="mt-2 text-xs text-[color:var(--se-muted)]">
            {description}
          </div>
        </div>
        <div className="rounded-2xl bg-emerald-50 p-3 text-[color:var(--se-techno-green)]">
          <Icon size={24} />
        </div>
      </div>
    </Card>
  );
}

export function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function loadStats() {
    try {
      setIsLoading(true);
      setError(null);
      const response = await getStats();
      setStats(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки статистики");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadStats();
  }, []);

  return (
    <>
      <Header
        title="Дашборд"
        subtitle="Информативный обзор базы, API и готовности сервиса к поиску закупок"
        onRefresh={loadStats}
      />

      <div className="space-y-6 p-6">
        {error && (
          <Card className="border-rose-200 bg-rose-50 text-rose-700">
            {error}
          </Card>
        )}

        <section className="overflow-hidden rounded-[2rem] border border-[color:var(--se-border)] bg-white shadow-sm">
          <div className="grid gap-0 lg:grid-cols-[1.3fr_0.7fr]">
            <div className="p-7">
              <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold uppercase tracking-wide text-[color:var(--se-techno-green)]">
                <Activity size={14} />
                Мониторинг активен
              </div>
              <h2 className="mt-5 max-w-3xl text-3xl font-bold tracking-tight text-[color:var(--se-text)]">
                Единая панель для контроля закупок и быстрого перехода к заявкам
              </h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[color:var(--se-muted)]">
                Здесь видно количество закупок в базе, актуальность данных и состояние
                API. Раздел «Закупки» теперь обновляется автоматически при изменении
                фильтров, поэтому ручная кнопка поиска не нужна.
              </p>
            </div>

            <div className="border-t border-[color:var(--se-border)] bg-emerald-50/70 p-7 lg:border-l lg:border-t-0">
              <div className="text-sm font-semibold text-[color:var(--se-muted)]">
                Последняя проверка
              </div>
              <div className="mt-3 text-2xl font-bold">
                {formatDate(stats?.timestamp)}
              </div>
              <div className="mt-5 flex items-center gap-2 text-sm font-semibold text-[color:var(--se-techno-green)]">
                {isLoading ? <RefreshCw className="animate-spin" size={18} /> : <CheckCircle2 size={18} />}
                {isLoading ? "Обновляем статистику" : stats ? "API отвечает" : "Ожидаем ответ API"}
              </div>
            </div>
          </div>
        </section>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <StatCard
            title="Закупок в базе"
            value={stats?.purchases_count ?? "—"}
            description="Общее количество записей, доступных для поиска"
            icon={Database}
          />
          <StatCard
            title="Статус API"
            value={stats ? "Работает" : "Проверяется"}
            description="Показывает доступность backend-эндпоинта /stats"
            icon={CheckCircle2}
          />
          <StatCard
            title="Автопоиск"
            value="Включён"
            description="Запросы к get_all_purchases запускаются при смене фильтров"
            icon={Search}
          />
          <StatCard
            title="Обновление"
            value={isLoading ? "Идёт" : "Готово"}
            description="Ручное обновление доступно в верхней панели"
            icon={Clock3}
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <div className="flex items-center gap-2 font-semibold">
              <BarChart3 size={18} />
              Состояние сервиса
            </div>
            <div className="mt-5 grid gap-3 md:grid-cols-3">
              <div className="rounded-2xl bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  База данных
                </div>
                <div className="mt-2 font-bold text-[color:var(--se-text)]">
                  {stats ? "Подключена" : "Нет данных"}
                </div>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  Интерфейс
                </div>
                <div className="mt-2 font-bold text-[color:var(--se-text)]">
                  React + TypeScript
                </div>
              </div>
              <div className="rounded-2xl bg-slate-50 p-4">
                <div className="text-xs uppercase tracking-wide text-slate-400">
                  Фильтры
                </div>
                <div className="mt-2 font-bold text-[color:var(--se-text)]">
                  Автоматические
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <div className="font-semibold">Что улучшено</div>
            <ul className="mt-4 space-y-3 text-sm text-[color:var(--se-muted)]">
              <li>• Тип фильтра вынесен в отдельный заметный блок.</li>
              <li>• Список документов раскрывается только по кнопке.</li>
              <li>• Карточки заявок можно редактировать прямо на странице.</li>
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}
