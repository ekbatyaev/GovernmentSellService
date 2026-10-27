import { useState } from "react";
import { CheckCircle2, Loader2, UserCheck } from "lucide-react";
import { approveUser, type UserRole } from "../api/users";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Select } from "../components/ui/Select";
import { errorMessage } from "../lib/errors";

const ROLE_OPTIONS = [
  { label: "Пользователь", value: "user" },
  { label: "Администратор", value: "admin" },
];

/** Открывается по ссылке из письма администратору: /approve/{guid}. */
export function ApprovePage({ guid, onExit }: { guid: string; onExit: () => void }) {
  const [role, setRole] = useState<UserRole>("user");
  const [loading, setLoading] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleApprove() {
    try {
      setLoading(true);
      setError(null);
      await approveUser(guid, role);
      setDone(true);
    } catch (e) {
      setError(errorMessage(e, "Не удалось подтвердить пользователя"));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="se-shell-gradient flex min-h-screen items-center justify-center px-4 py-10 text-[color:var(--se-text)]">
      <Card className="w-full max-w-md space-y-5">
        {done ? (
          <div className="flex flex-col items-center gap-4 py-4 text-center">
            <CheckCircle2 size={48} className="text-[color:var(--se-techno-green)]" />
            <div className="text-lg font-bold">Пользователь подтверждён</div>
            <p className="text-sm text-[color:var(--se-muted)]">
              Пользователю отправлено письмо — теперь он может войти в систему.
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-start gap-4">
              <div className="rounded-2xl bg-emerald-50 p-3 text-[color:var(--se-techno-green)] shrink-0">
                <UserCheck size={22} />
              </div>
              <div>
                <div className="font-semibold">Подтверждение регистрации</div>
                <p className="mt-1 text-xs leading-5 text-[color:var(--se-muted)]">
                  Выберите роль для нового пользователя. Подтверждать регистрацию может только администратор.
                </p>
              </div>
            </div>

            <Select
              label="Роль"
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              options={ROLE_OPTIONS}
            />

            {error && (
              <div className="rounded-xl bg-rose-50 px-4 py-2.5 text-sm font-semibold text-rose-700">{error}</div>
            )}

            <Button onClick={handleApprove} disabled={loading} className="w-full">
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 size={16} className="animate-spin" /> Подтверждаем...
                </span>
              ) : (
                "Подтвердить"
              )}
            </Button>
          </>
        )}

        <Button variant="secondary" onClick={onExit} className="w-full">
          Перейти в приложение
        </Button>
      </Card>
    </div>
  );
}
