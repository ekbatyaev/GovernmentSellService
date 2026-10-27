import { useEffect, useRef, useState, type FormEvent } from "react";
import { CheckCircle2, Loader2 } from "lucide-react";
import eSymbolUrl from "../assets/e-symbol.svg";
import { ApiError } from "../api/client";
import { getStats } from "../api/stats";
import { login, register, requestRegisterCode } from "../api/users";
import { useAuth } from "../auth/AuthContext";
import { clearToken, setToken } from "../auth/session";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { errorMessage } from "../lib/errors";

// Бэк выдаёт новый код не чаще раза в 5 минут (send_auth_code)
const RESEND_COOLDOWN = 300;

type Tab = "login" | "register";
type Status = { text: string; error: boolean } | null;

function StatusBox({ status }: { status: Status }) {
  if (!status) return null;
  return (
    <div
      className={`rounded-xl px-4 py-2.5 text-sm font-semibold ${
        status.error ? "bg-rose-50 text-rose-700" : "bg-emerald-50 text-[color:var(--se-techno-green)]"
      }`}
    >
      {status.text}
    </div>
  );
}

function Spinner({ text }: { text: string }) {
  return (
    <span className="flex items-center justify-center gap-2">
      <Loader2 size={16} className="animate-spin" /> {text}
    </span>
  );
}

// ─── вход ────────────────────────────────────────────────────────────────────

function LoginForm() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState<Status>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!email || !password) {
      setStatus({ text: "Введите email и пароль", error: true });
      return;
    }

    try {
      setLoading(true);
      setStatus(null);
      const { data } = await login(email, password);

      // Логин выдаёт токен и неподтверждённому пользователю (роль guest),
      // но все защищённые маршруты отвечают ему 401. Проверяем доступ до входа в приложение.
      setToken(data.access_token);
      try {
        await getStats();
      } catch (e) {
        clearToken();
        if (e instanceof ApiError && e.status === 401) {
          setStatus({ text: "Аккаунт ожидает подтверждения администратором", error: true });
          return;
        }
        throw e;
      }
      auth.login(data.access_token);
    } catch (e) {
      setStatus({ text: errorMessage(e, "Не удалось войти"), error: true });
    } finally {
      setLoading(false);
    }
  }

  return (
    <form className="space-y-4" onSubmit={handleSubmit}>
      <Input
        label="Email"
        type="email"
        autoComplete="username"
        placeholder="you@example.com"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />
      <Input
        label="Пароль"
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <StatusBox status={status} />
      <Button type="submit" disabled={loading} className="w-full">
        {loading ? <Spinner text="Входим..." /> : "Войти"}
      </Button>
    </form>
  );
}

// ─── регистрация ─────────────────────────────────────────────────────────────

function RegisterForm() {
  const [step, setStep] = useState<"email" | "code" | "done">("email");
  const [email, setEmail] = useState("");
  const [codeGuid, setCodeGuid] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [passwordRepeat, setPasswordRepeat] = useState("");
  const [status, setStatus] = useState<Status>(null);
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  function startCooldown() {
    if (timerRef.current) clearInterval(timerRef.current);
    setCooldown(RESEND_COOLDOWN);
    timerRef.current = setInterval(() => {
      setCooldown((prev) => {
        if (prev <= 1) {
          if (timerRef.current) clearInterval(timerRef.current);
          return 0;
        }
        return prev - 1;
      });
    }, 1_000);
  }

  async function sendCode() {
    if (!email) {
      setStatus({ text: "Введите email", error: true });
      return;
    }
    try {
      setLoading(true);
      setStatus(null);
      const { data } = await requestRegisterCode(email);
      setCodeGuid(data.guid);
      setStep("code");
      setStatus({ text: "Код отправлен на указанный email", error: false });
      startCooldown();
    } catch (e) {
      setStatus({ text: errorMessage(e, "Не удалось отправить код"), error: true });
    } finally {
      setLoading(false);
    }
  }

  async function handleRegister(event: FormEvent) {
    event.preventDefault();
    if (!codeGuid) return;
    if (!/^\d{6}$/.test(code.trim())) {
      setStatus({ text: "Код состоит из 6 цифр", error: true });
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
      await register(codeGuid, email, password, Number(code.trim()));
      setStep("done");
    } catch (e) {
      setStatus({ text: errorMessage(e, "Не удалось зарегистрироваться"), error: true });
    } finally {
      setLoading(false);
    }
  }

  if (step === "done") {
    return (
      <div className="flex flex-col items-center gap-4 py-6 text-center">
        <CheckCircle2 size={48} className="text-[color:var(--se-techno-green)]" />
        <div className="text-lg font-bold text-[color:var(--se-text)]">Регистрация завершена</div>
        <p className="max-w-sm text-sm text-[color:var(--se-muted)]">
          Администратор получил запрос на подтверждение. Когда аккаунт будет подтверждён, на {email} придёт
          письмо — после этого можно войти.
        </p>
      </div>
    );
  }

  if (step === "email") {
    return (
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          void sendCode();
        }}
      >
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <StatusBox status={status} />
        <Button type="submit" disabled={loading} className="w-full">
          {loading ? <Spinner text="Отправляем..." /> : "Получить код"}
        </Button>
      </form>
    );
  }

  return (
    <form className="space-y-4" onSubmit={handleRegister}>
      <div className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4 space-y-3">
        <p className="text-sm text-[color:var(--se-muted)]">
          Код отправлен на <span className="font-semibold text-[color:var(--se-text)]">{email}</span>.
          Проверить его можно через 20 секунд после отправки.
        </p>
        <Input
          placeholder="Код из письма"
          inputMode="numeric"
          autoComplete="one-time-code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
        <button
          type="button"
          onClick={() => void sendCode()}
          disabled={cooldown > 0 || loading}
          className="text-xs font-semibold text-[color:var(--se-techno-green)] disabled:text-[color:var(--se-muted)] hover:underline"
        >
          {cooldown > 0 ? `Отправить повторно через ${cooldown} с.` : "Отправить код повторно"}
        </button>
      </div>
      <Input
        label="Пароль (от 8 символов)"
        type="password"
        autoComplete="new-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <Input
        label="Повторите пароль"
        type="password"
        autoComplete="new-password"
        value={passwordRepeat}
        onChange={(e) => setPasswordRepeat(e.target.value)}
      />
      <StatusBox status={status} />
      <Button type="submit" disabled={loading} className="w-full">
        {loading ? <Spinner text="Регистрируем..." /> : "Зарегистрироваться"}
      </Button>
    </form>
  );
}

// ─── страница ────────────────────────────────────────────────────────────────

export function AuthPage() {
  const [tab, setTab] = useState<Tab>("login");

  return (
    <div className="se-shell-gradient flex min-h-screen items-center justify-center px-4 py-10 text-[color:var(--se-text)]">
      <div className="w-full max-w-md space-y-6">
        <div className="flex items-center justify-center gap-3">
          <div className="flex size-12 items-center justify-center rounded-2xl bg-white shadow-sm ring-1 ring-[color:var(--se-border)]">
            <img src={eSymbolUrl} alt="Systeme Electric" className="h-8 w-8 object-contain" />
          </div>
          <div>
            <div className="font-bold text-[color:var(--se-techno-green)]">Systeme Electric</div>
            <div className="text-xs text-[color:var(--se-muted)]">Мониторинг закупок</div>
          </div>
        </div>

        <Card>
          <div className="mb-5 grid grid-cols-2 gap-1 rounded-2xl bg-slate-100 p-1">
            {(
              [
                ["login", "Вход"],
                ["register", "Регистрация"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setTab(id)}
                className={`rounded-xl py-2 text-sm font-semibold transition ${
                  tab === id
                    ? "bg-white text-[color:var(--se-techno-green)] shadow-sm"
                    : "text-[color:var(--se-muted)] hover:text-[color:var(--se-text)]"
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          {tab === "login" ? <LoginForm /> : <RegisterForm />}
        </Card>
      </div>
    </div>
  );
}
