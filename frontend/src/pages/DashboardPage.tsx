import { useEffect, useState } from "react";
import { getStats, type Stats } from "../api/stats";
import { Card } from "../components/ui/Card";
import { Header } from "../components/layout/Header";
import { formatDate } from "../lib/format";

export function DashboardPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function loadStats() {
    try {
      setError(null);
      const response = await getStats();
      setStats(response.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Ошибка загрузки статистики");
    }
  }

  useEffect(() => {
    loadStats();
  }, []);

  return (
    <>
      <Header
        title="Дашборд"
        subtitle="Обзор состояния базы госзакупок"
        onRefresh={loadStats}
      />

      <div className="p-6">
        {error && (
          <Card className="mb-6 border-rose-200 bg-rose-50 text-rose-700">
            {error}
          </Card>
        )}

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <div className="text-sm text-slate-500">Закупок в базе</div>
            <div className="mt-3 text-3xl font-semibold">
              {stats?.purchases_count ?? "—"}
            </div>
          </Card>

          <Card>
            <div className="text-sm text-slate-500">Последнее обновление</div>
            <div className="mt-3 text-lg font-semibold">
              {formatDate(stats?.timestamp)}
            </div>
          </Card>

          <Card>
            <div className="text-sm text-slate-500">Статус API</div>
            <div className="mt-3 text-lg font-semibold text-emerald-600">
              {stats ? "Работает" : "Проверяется"}
            </div>
          </Card>
        </div>
      </div>
    </>
  );
}