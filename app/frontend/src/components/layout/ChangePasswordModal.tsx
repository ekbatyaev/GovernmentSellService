import { useEffect, useState, type FormEvent } from "react";
import { CheckCircle2, Loader2, X } from "lucide-react";
import { changePassword } from "../../api/users";
import { errorMessage } from "../../lib/errors";
import { Button } from "../ui/Button";
import { Input } from "../ui/Input";

type Status = { text: string; error: boolean } | null;

export function ChangePasswordModal({ onClose }: { onClose: () => void }) {
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [passwordRepeat, setPasswordRepeat] = useState("");
  const [status, setStatus] = useState<Status>(null);
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!currentPassword) {
      setStatus({ text: "Введите текущий пароль", error: true });
      return;
    }
    if (password.length < 8 || password.length > 128) {
      setStatus({ text: "Пароль должен быть от 8 до 128 символов", error: true });
      return;
    }
    if (password !== passwordRepeat) {
      setStatus({ text: "Пароли не совпадают", error: true });
      return;
    }

    try {
      setLoading(true);
      setStatus(null);
      await changePassword(currentPassword, password);
      setDone(true);
    } catch (e) {
      setStatus({ text: errorMessage(e, "Не удалось сменить пароль"), error: true });
    } finally {
      setLoading(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="change-password-title"
        className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-5 flex items-center justify-between gap-4">
          <div id="change-password-title" className="text-lg font-bold text-[color:var(--se-text)]">
            Смена пароля
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="rounded-xl p-1.5 text-[color:var(--se-muted)] transition hover:bg-slate-100 hover:text-[color:var(--se-text)]"
          >
            <X size={20} />
          </button>
        </div>

        {done ? (
          <div className="flex flex-col items-center gap-4 py-4 text-center">
            <CheckCircle2 size={48} className="text-[color:var(--se-techno-green)]" />
            <div className="text-lg font-bold text-[color:var(--se-text)]">Пароль изменён</div>
            <Button type="button" onClick={onClose} className="w-full">
              Готово
            </Button>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={handleSubmit}>
            <Input
              label="Текущий пароль"
              type="password"
              autoComplete="current-password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
            <Input
              label="Новый пароль (от 8 символов)"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <Input
              label="Повторите новый пароль"
              type="password"
              autoComplete="new-password"
              value={passwordRepeat}
              onChange={(e) => setPasswordRepeat(e.target.value)}
            />
            {status && (
              <div
                className={`rounded-xl px-4 py-2.5 text-sm font-semibold ${
                  status.error ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-[color:var(--se-techno-green)]"
                }`}
              >
                {status.text}
              </div>
            )}
            <Button type="submit" disabled={loading} className="w-full">
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 size={16} className="animate-spin" /> Сохраняем...
                </span>
              ) : (
                "Сменить пароль"
              )}
            </Button>
          </form>
        )}
      </div>
    </div>
  );
}
