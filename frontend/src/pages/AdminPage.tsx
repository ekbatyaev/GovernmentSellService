import { Header } from "../components/layout/Header";
import { Card } from "../components/ui/Card";

export function AdminPage() {
  return (
    <>
      <Header title="Админка" subtitle="Ручной запуск задач и обслуживание базы" />

      <div className="p-6">
        <Card>
          <div className="font-semibold">Раздел в разработке</div>
          <p className="mt-2 text-sm text-slate-500">
            На следующем этапе перенесём запуск backfill, обработку дня и удаление
            просроченных закупок.
          </p>
        </Card>
      </div>
    </>
  );
}