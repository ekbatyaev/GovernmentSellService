import { RefreshCw } from "lucide-react";
import { Button } from "../ui/Button";

type HeaderProps = {
  title: string;
  subtitle?: string;
  onRefresh?: () => void;
};

export function Header({ title, subtitle, onRefresh }: HeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white px-6 py-5">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-950">
            {title}
          </h1>
          {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
        </div>

        {onRefresh && (
          <Button variant="secondary" onClick={onRefresh}>
            <RefreshCw className="mr-2" size={16} />
            Обновить
          </Button>
        )}
      </div>
    </header>
  );
}