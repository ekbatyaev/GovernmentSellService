import { useRef, useState } from "react";
import {
  CalendarDays,
  CalendarRange,
  Loader2,
  Settings2,
  Trash2
} from "lucide-react";
import { api, ApiError } from "../api/client";
import { errorMessage } from "../lib/errors";
import { Header } from "../components/layout/Header";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";

// ─── константы ───────────────────────────────────────────────────────────────

const FILTER_TYPE_OPTIONS = [
  { label: "Все типы", value: "0" },
  { label: "Тендеры для Россетей", value: "1"},
  { label: "Тендеры для OEM", value: "2" },
  { label: "Тендеры для ITM", value: "3" },
];

// ─── утилиты ─────────────────────────────────────────────────────────────────

type JobStatus = {
  name: string | null;
  status: "idle" | "running" | "done" | "error";
  message: string | null;
};

function todayIso() {
  return new Date().toISOString().split("T")[0];
}

async function waitJob(): Promise<string> {
  while (true) {
    await new Promise((r) => setTimeout(r, 5000));
    let job: JobStatus | undefined;
    try {
      job = (await api.get<JobStatus>("/services/stats/job_status")).data;
    } catch (e) {
      // Сессия истекла — клиент уже вывел на экран входа, опрос прекращаем
      if (e instanceof ApiError && e.status === 401) throw e;
      continue; // прокси/сервер моргнул — спросим ещё раз
    }
    if (job?.status === "done") return job.message || "Готово";
    if (job?.status === "error") throw new Error(job.message || "Ошибка в задаче");
    if (job?.status === "idle") throw new Error("Задача прервана — сервер перезапускался");
  }
}

// ─── тип лога ────────────────────────────────────────────────────────────────

type LogEntry = {
  id: number;
  ts: string;
  text: string;
  ok: boolean;
};

// ─── блок задачи ─────────────────────────────────────────────────────────────

function TaskBlock({
  title,
  description,
  icon: Icon,
  children,
}: {
  title: string;
  description: string;
  icon: typeof CalendarRange;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <div className="flex items-start gap-4 mb-5">
        <div className="rounded-2xl bg-emerald-50 p-3 text-[color:var(--se-techno-green)] shrink-0">
          <Icon size={22} />
        </div>
        <div>
          <div className="font-semibold text-[color:var(--se-text)]">{title}</div>
          <p className="mt-1 text-xs text-[color:var(--se-muted)] leading-5">{description}</p>
        </div>
      </div>
      {children}
    </Card>
  );
}

// ─── главная страница ─────────────────────────────────────────────────────────

export function AdminPage() {
  // Backfill по диапазону дат
  const [backfillFrom, setBackfillFrom] = useState("");
  const [backfillTo, setBackfillTo] = useState(todayIso());
  const [backfillFilterType, setBackfillFilterType] = useState<number>(0);

  // Process day
  const [processDay, setProcessDay] = useState(todayIso());
  const [processDayFilterType, setProcessDayFilterType] = useState<number>(0);

  const [loadingTask, setLoadingTask] = useState<string | null>(null);
  const [log, setLog] = useState<LogEntry[]>([]);
  const logIdRef = useRef(0);

  function addLog(text: string, ok: boolean) {
    const entry: LogEntry = {
      id: ++logIdRef.current,
      ts: new Date().toLocaleTimeString("ru-RU"),
      text,
      ok,
    };
    setLog((prev) => [entry, ...prev].slice(0, 20));
  }

  async function runTask(taskName: string, url: string, body: unknown) {
    try {
      setLoadingTask(taskName);
      addLog(`Запуск: ${taskName}...`, true);
      await api.post(url, body); // 409, если уже идёт другая задача — текст покажем в логе
      addLog("⏳ Задача запущена", true);
      const message = await waitJob();
      addLog(`✅ ${message}`, true);
    } catch (e) {
      addLog(`❌ ${errorMessage(e)}`, false);
    } finally {
      setLoadingTask(null);
    }
  }

  // ─── Backfill по диапазону ─────────────────────────────────────────────────

  function handleBackfill() {
    if (!backfillFrom) { addLog("Укажите дату начала", false); return; }
    if (!backfillTo) { addLog("Укажите дату окончания", false); return; }
    if (backfillFrom > backfillTo) { addLog("Дата начала не может быть позже даты конца", false); return; }

    runTask(
      "run_process_period",
      "/services/run/process_period",
      {
        date_from: `${backfillFrom}T00:00:00`,
        date_to: `${backfillTo}T23:59:59`,
        filter_number: backfillFilterType,
      },
    );
  }

  // ─── Process day ──────────────────────────────────────────────────────────

  function handleProcessDay() {
    if (!processDay) { addLog("Выберите дату", false); return; }
    if (processDay > todayIso()) { addLog("Дата не может быть в будущем", false); return; }

    runTask(
      "run_process_day",
      "/services/run/process_day",
      {
        date: `${processDay}T00:00:00`,
        filter_number: processDayFilterType,
      },
    );
  }

  const isLoading = loadingTask !== null;

  return (
    <>
      <Header title="Админ-панель" subtitle="Ручной запуск парсинга закупок" />

      <div className="space-y-6 p-6">
        {/* Задачи */}
        <div className="grid gap-4 lg:grid-cols-2">

          {/* ── Backfill по диапазону ─────────────────────────────────────── */}
          <TaskBlock
            title="Сбор закупок за период"
            description="Запускает backfill за указанный диапазон дат."
            icon={CalendarRange}
          >
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[color:var(--se-muted)]">
                    С даты
                  </label>
                  <Input
                    type="date"
                    value={backfillFrom}
                    max={todayIso()}
                    onChange={(e) => setBackfillFrom(e.target.value)}
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[color:var(--se-muted)]">
                    По дату
                  </label>
                  <Input
                    type="date"
                    value={backfillTo}
                    max={todayIso()}
                    onChange={(e) => setBackfillTo(e.target.value)}
                  />
                </div>
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[color:var(--se-muted)]">
                  Тип заявок
                </label>
                <Select
                  value={backfillFilterType}
                  onChange={(e) => setBackfillFilterType(Number(e.target.value))}
                  options={FILTER_TYPE_OPTIONS}
                />
              </div>

              <Button
                onClick={handleBackfill}
                disabled={isLoading}
                className="w-full"
              >
                {loadingTask === "run_backfill" ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 size={16} className="animate-spin" /> Выполняется...
                  </span>
                ) : (
                  "Запустить сбор"
                )}
              </Button>
            </div>
          </TaskBlock>

          {/* ── Process day ───────────────────────────────────────────────── */}
          <TaskBlock
            title="Просмотр закупок за день"
            description="Запускает обработку заявок для конкретной даты."
            icon={CalendarDays}
          >
            <div className="space-y-3">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[color:var(--se-muted)]">
                  Дата
                </label>
                <Input
                  type="date"
                  value={processDay}
                  max={todayIso()}
                  onChange={(e) => setProcessDay(e.target.value)}
                />
              </div>

              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[color:var(--se-muted)]">
                  Тип заявок
                </label>
                <Select
                  value={processDayFilterType}
                  onChange={(e) => setProcessDayFilterType(Number(e.target.value))}
                  options={FILTER_TYPE_OPTIONS}
                />
              </div>

              <Button
                onClick={handleProcessDay}
                disabled={isLoading}
                className="w-full"
              >
                {loadingTask === "run_process_day" ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 size={16} className="animate-spin" /> Выполняется...
                  </span>
                ) : (
                  "Запустить обработку"
                )}
              </Button>
            </div>
          </TaskBlock>
        </div>

        {/* Лог выполнения */}
        {log.length > 0 && (
          <Card>
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-2 font-semibold text-[color:var(--se-text)]">
                <Settings2 size={18} />
                Лог задач
              </div>
              <button
                type="button"
                onClick={() => setLog([])}
                className="flex items-center gap-1 text-xs text-[color:var(--se-muted)] hover:text-rose-500"
              >
                <Trash2 size={14} /> Очистить
              </button>
            </div>
            <div className="space-y-1.5 font-mono text-xs">
              {log.map((entry) => (
                <div
                  key={entry.id}
                  className={`flex gap-3 rounded-xl px-3 py-2 ${
                    entry.ok ? "bg-emerald-50 text-emerald-800" : "bg-rose-50 text-rose-700"
                  }`}
                >
                  <span className="shrink-0 text-[color:var(--se-muted)]">{entry.ts}</span>
                  <span>{entry.text}</span>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </>
  );
}
