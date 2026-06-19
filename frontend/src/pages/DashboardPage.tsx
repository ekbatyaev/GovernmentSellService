import { useEffect, useState } from "react";
import {
  Activity,
  Clock3,
  Database,
  Mail,
  RefreshCw,
  ServerCrash,
  CheckCircle2,
  Wifi,
  WifiOff,
  XCircle,
} from "lucide-react";
import { getStats, type Stats } from "../api/stats";
import { Card } from "../components/ui/Card";
import { Header } from "../components/layout/Header";
// ─── утилиты ──────────────────────────────────────────────────────────────────

function ago(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60_000);
  if (mins < 1) return "только что";
  if (mins < 60) return `${mins} мин. назад`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours} ч. назад`;
  return `${Math.floor(hours / 24)} дн. назад`;
}

// МОСКОВСКОЕ ВРЕМЯ: форматирование ISO-строки в московском часовом поясе
function formatMoscowTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return date.toLocaleString('ru-RU', {
    timeZone: 'Europe/Moscow',
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

// ─── типы ────────────────────────────────────────────────────────────────────

type ServiceItem = {
  label: string;
  value: string;
  ok: boolean | null; // null = нейтральный
};

// ─── компоненты ──────────────────────────────────────────────────────────────

function StatusDot({ ok }: { ok: boolean | null }) {
  if (ok === null) return <span className="h-2 w-2 rounded-full bg-slate-300 inline-block" />;
  return ok ? (
    <span className="h-2 w-2 rounded-full bg-emerald-500 inline-block animate-pulse" />
  ) : (
    <span className="h-2 w-2 rounded-full bg-rose-500 inline-block" />
  );
}

function ServiceRow({ label, value, ok }: ServiceItem) {
  return (
    <div className="flex items-center justify-between gap-4 py-3 border-b last:border-0 border-[color:var(--se-border)]">
      <div className="flex items-center gap-2 text-sm text-[color:var(--se-muted)]">
        <StatusDot ok={ok} />
        {label}
      </div>
      <div className="text-sm font-semibold text-[color:var(--se-text)]">{value}</div>
    </div>
  );
}

function BigStat({
  label,
  value,
  sub,
  icon: Icon,
  tone = "green",
}: {
  label: string;
  value: string | number;
  sub?: string;
  icon: typeof Database;
  tone?: "green" | "blue" | "amber" | "rose";
}) {
  const colors: Record<string, string> = {
    green: "bg-emerald-50 text-[color:var(--se-techno-green)]",
    blue: "bg-sky-50 text-sky-600",
    amber: "bg-amber-50 text-amber-600",
    rose: "bg-rose-50 text-rose-600",
  };

  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-xs font-semibold uppercase tracking-wide text-[color:var(--se-muted)]">
            {label}
          </div>
          <div className="mt-2 text-3xl font-bold tracking-tight text-[color:var(--se-text)]">
            {value}
          </div>
          {sub && (
            <div className="mt-1.5 text-xs text-[color:var(--se-muted)]">{sub}</div>
          )}
        </div>
        <div className={`rounded-2xl p-3 ${colors[tone]}`}>
          <Icon size={22} />
        </div>
      </div>
    </Card>
  );
}

// ─── главная страница ─────────────────────────────────────────────────────────

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

  const apiOk = !error && stats !== null;

  const statsData = stats as Record<string, unknown> | null;

  const serviceItems: ServiceItem[] = [
    {
      label: "API backend",
      value: isLoading ? "Проверяем..." : apiOk ? "Отвечает" : "Недоступен",
      ok: isLoading ? null : apiOk,
    },
    {
      label: "База данных",
      ok: isLoading ? null : apiOk ? true : false,
      value: isLoading ? "Проверяем..." : apiOk ? "Подключена" : "Нет данных",
    },
    {
      label: "Закупок в базе",
      value: statsData?.purchases_count != null ? String(statsData.purchases_count) : "—",
      ok: null,
    },
    {
      label: "Подписчиков рассылки",
      value: statsData?.newsletter_count != null ? String(statsData.newsletter_count) : "—",
      ok: null,
    },
    {
      label: "Последняя обработка даты",
      value: statsData?.last_process_day_at
        ? formatMoscowTime(String(statsData.last_process_day_at))
        : "—",
      ok: null,
    }
  ];

  return (
    <>
      <Header
        title="Дашборд"
        subtitle="Состояние сервиса: API, база, рассылки, задачи парсинга"
        onRefresh={loadStats}
      />

      <div className="space-y-6 p-6">
        {/* Ошибка */}
        {error && (
          <Card className="border-rose-200 bg-rose-50 text-rose-700 flex items-center gap-3">
            <XCircle size={18} className="shrink-0" />
            {error}
          </Card>
        )}

        {/* Hero-блок */}
        <section className="overflow-hidden rounded-[2rem] border border-[color:var(--se-border)] bg-white shadow-sm">
          <div className="grid gap-0 lg:grid-cols-[1.3fr_0.7fr]">
            <div className="p-7">
              <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold uppercase tracking-wide text-[color:var(--se-techno-green)]">
                {apiOk ? <Wifi size={14} /> : <WifiOff size={14} />}
                {apiOk ? "Сервис работает" : "Нет связи с API"}
              </div>
              <h2 className="mt-5 max-w-3xl text-3xl font-bold tracking-tight text-[color:var(--se-text)]">
                Мониторинг госзакупок — панель оператора
              </h2>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-[color:var(--se-muted)]">
                Здесь отображается актуальное состояние базы, статус рассылки и
                когда последний раз запускались задачи получения документов.
                Для ручного запуска парсинга закупок — перейдите в раздел «Админ-панель».
              </p>
            </div>

            <div className="flex flex-col justify-center gap-3 border-t border-[color:var(--se-border)] bg-emerald-50/70 p-7 lg:border-l lg:border-t-0">
              <div className="text-sm font-semibold text-[color:var(--se-muted)]">
                Данные получены
              </div>
              <div className="text-2xl font-bold text-[color:var(--se-text)]">
                {/* МОСКОВСКОЕ ВРЕМЯ: заменили formatDate на formatMoscowTime */}
                {formatMoscowTime(stats?.timestamp)}
              </div>
              <div className="text-xs text-[color:var(--se-muted)]">
                {ago(stats?.timestamp)} {/* относительное время оставляем */}
              </div>
              <div className="mt-2 flex items-center gap-2 text-sm font-semibold text-[color:var(--se-techno-green)]">
                {isLoading
                  ? <RefreshCw className="animate-spin" size={16} />
                  : apiOk
                    ? <CheckCircle2 size={16} />
                    : <ServerCrash size={16} className="text-rose-500" />
                }
                {isLoading ? "Обновляем..." : apiOk ? "API отвечает" : "Ошибка соединения"}
              </div>
            </div>
          </div>
        </section>

        {/* KPI-карточки */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <BigStat
            label="Закупок в базе"
            value={stats?.purchases_count ?? "—"}
            sub="Доступны для поиска и фильтрации"
            icon={Database}
            tone="green"
          />
          <BigStat
            label="Статус API"
            value={isLoading ? "Проверка" : apiOk ? "Работает" : "Ошибка"}
            sub={apiOk ? "Эндпоинт /stats отвечает" : error ?? "Нет ответа"}
            icon={apiOk ? Activity : ServerCrash}
            tone={isLoading ? "blue" : apiOk ? "green" : "rose"}
          />
          <BigStat
            label="Подписчиков"
            value={
              statsData?.newsletter_count != null
                ? String(statsData.newsletter_count)
                : "—"
            }
            sub="Получают email при новых закупках"
            icon={Mail}
            tone="blue"
          />
          <BigStat
            label="Последнее обновление"
            value={ago(stats?.timestamp)} // относительное время
            // МОСКОВСКОЕ ВРЕМЯ: абсолютное время в подсказке
            sub={formatMoscowTime(stats?.timestamp)}
            icon={Clock3}
            tone="amber"
          />
        </div>

        {/* Детальный статус сервиса */}
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <div className="mb-1 font-semibold text-[color:var(--se-text)]">
              Состояние компонентов
            </div>
            <p className="mb-4 text-xs text-[color:var(--se-muted)]">
              Актуальные данные из эндпоинта /stats
            </p>
            {isLoading ? (
              <div className="flex items-center gap-2 text-sm text-[color:var(--se-muted)]">
                <RefreshCw size={14} className="animate-spin" /> Загрузка...
              </div>
            ) : (
              serviceItems.map((item) => (
                <ServiceRow key={item.label} {...item} />
              ))
            )}
          </Card>

          <Card>
            <div className="mb-1 font-semibold text-[color:var(--se-text)]">
              Как пользоваться сервисом
            </div>
            <ul className="mt-4 space-y-4 text-sm text-[color:var(--se-muted)]">
              <li className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-bold text-[color:var(--se-techno-green)]">
                  1
                </span>
                <span>
                  <span className="font-semibold text-[color:var(--se-text)]">Закупки</span> — поиск и просмотр
                  заявок с автоматической фильтрацией по типу, региону, сумме и дате.
                </span>
              </li>
              <li className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-bold text-[color:var(--se-techno-green)]">
                  2
                </span>
                <span>
                  <span className="font-semibold text-[color:var(--se-text)]">Рассылка</span> — подпишите email
                  на уведомления о новых закупках выбранного типа и региона.
                </span>
              </li>
              <li className="flex gap-3">
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-xs font-bold text-[color:var(--se-techno-green)]">
                  3
                </span>
                <span>
                  <span className="font-semibold text-[color:var(--se-text)]">Админ-панель</span> — ручной запуск
                  backfill за диапазон дат или просмотр закупок за конкретный день.
                </span>
              </li>
            </ul>
          </Card>
        </div>
      </div>
    </>
  );
}