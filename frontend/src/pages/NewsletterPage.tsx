import { Header } from "../components/layout/Header";
import { Card } from "../components/ui/Card";

export function NewsletterPage() {
  return (
    <>
      <Header
        title="Рассылка"
        subtitle="Подписка на уведомления по новым закупкам"
      />

      <div className="p-6">
        <Card>
          <div className="font-semibold">Раздел в разработке</div>
          <p className="mt-2 text-sm text-slate-500">
            На следующем этапе перенесём подтверждение email, подписку и отписку.
          </p>
        </Card>
      </div>
    </>
  );
}