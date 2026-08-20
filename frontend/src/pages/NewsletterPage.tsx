import { useEffect, useRef, useState } from "react";
import { CheckCircle2, ChevronDown, Loader2, Mail, MailMinus, MailPlus } from "lucide-react";
import { getConfig } from "../api/config";
import { Header } from "../components/layout/Header";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";

// ─── константы ───────────────────────────────────────────────────────────────

const API_BASE = "";

const FILTER_TYPE_OPTIONS = [
  { label: "Тендеры для Россетей", value: "Тендеры для Россетей" },
  { label: "Тендеры для OEM", value: "Тендеры для OEM" },
  { label: "Тендеры для ITM", value: "Тендеры для ITM" },
];

const DISTRICT_OPTIONS = [
  "Центральный федеральный округ",
  "Северо-Западный федеральный округ",
  "Южный федеральный округ",
  "Северо-Кавказский федеральный округ",
  "Приволжский федеральный округ",
  "Уральский федеральный округ",
  "Сибирский федеральный округ",
  "Дальневосточный федеральный округ",
].map((d) => ({ label: d, value: d }));


const REGIONS_OPTIONS = [
  // Общие категории (были в образце)
  { label: "77 - Московская область", value: "77" },

  // Филиалы ПАО "Россети Центр и Приволжье"
  { label: "12 - Республика Марий Эл", value: "12" },
  { label: "52 - Нижегородская область", value: "52" },
  { label: "43 - Кировская область", value: "43" },
  { label: "18 - Удмуртская Республика", value: "18" },
  { label: "33 - Владимирская область", value: "33" },
  { label: "37 - Ивановская область", value: "37" },
  { label: "62 - Рязанская область", value: "62" },
  { label: "71 - Тульская область", value: "71" },
  { label: "40 - Калужская область", value: "40" },

  // Филиалы ПАО "Россети Волга"
  { label: "56 - Оренбургская область", value: "56" },
  { label: "63 - Самарская область", value: "63" },
  { label: "64 - Саратовская область", value: "64" },

  // Филиалы ПАО "Россети Центр"
  { label: "36 - Воронежская область", value: "36" },
  { label: "31 - Белгородская область", value: "31" },
  { label: "57 - Орловская область", value: "57" },
  { label: "44 - Костромская область", value: "44" },
  { label: "76 - Ярославская область", value: "76" },
  { label: "69 - Тверская область", value: "69" },
  { label: "67 - Смоленская область", value: "67" },
  { label: "32 - Брянская область", value: "32" },
  { label: "46 - Курская область", value: "46" },
  { label: "48 - Липецкая область", value: "48" },
  { label: "68 - Тамбовская область", value: "68" },
];

const RESEND_COOLDOWN = 60; // секунд

function needsDistrict(filterType: string) {
  return filterType === "Тендеры для OEM" || filterType === "Тендеры для ITM";
}

function needsRegion(filterType: string) {
  return filterType === "Тендеры для Россетей";
}

// ─── утилиты ─────────────────────────────────────────────────────────────────

async function apiPost<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  let data: Record<string, unknown> = {};
  try {
    data = await res.json();
  } catch {}
  if (!res.ok) {
    throw new Error(String(data.detail || data.message || `HTTP ${res.status}`));
  }
  return data as T;
}

// ─── шаги формы ──────────────────────────────────────────────────────────────

type Step = "form" | "code" | "done";
type Mode = "subscribe" | "unsubscribe";

// ─── компонент формы ─────────────────────────────────────────────────────────

function NewsletterForm({
  mode,
  token,
  onDone,
}: {
  mode: Mode;
  token: string;
  onDone: (email: string) => void;
}) {
  const [step, setStep] = useState<Step>("form");
  const [email, setEmail] = useState("");
  const [filterType, setFilterType] = useState("Тендеры для Россетей");
  const [districtName, setDistrictName] = useState("");
  const [code, setCode] = useState("");
  const [status, setStatus] = useState<{ text: string; error: boolean } | null>(null);
  const [loading, setLoading] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  function startCooldown() {
    setCooldown(RESEND_COOLDOWN);
    timerRef.current = setInterval(() => {
      setCooldown((prev) => {
        if (prev <= 1) {
          clearInterval(timerRef.current!);
          return 0;
        }
        return prev - 1;
      });
    }, 1_000);
  }

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  async function handleSendCode() {
    if (!email) { setStatus({ text: "Введите email", error: true }); return; }
    if (!token) { setStatus({ text: "Токен не загружен, попробуйте позже", error: true }); return; }
    if (needsDistrict(filterType) && !districtName) {
      setStatus({ text: "Выберите федеральный округ", error: true });
      return;
    }

    if (needsRegion(filterType) && !districtName) {
      setStatus({ text: "Выберите регион", error: true });
      return;
    }

    try {
      setLoading(true);
      setStatus(null);
      await apiPost(`${API_BASE}/send_auth_code`, { email, token });
      setStatus({ text: "Код отправлен на указанный email", error: false });
      setStep("code");
      startCooldown();
    } catch (e) {
      setStatus({ text: e instanceof Error ? e.message : "Ошибка", error: true });
    } finally {
      setLoading(false);
    }
  }

  async function handleResendCode() {
    if (cooldown > 0) return;
    try {
      setLoading(true);
      setStatus(null);
      await apiPost(`${API_BASE}/send_auth_code`, { email, token });
      setStatus({ text: "Код отправлен повторно", error: false });
      startCooldown();
    } catch (e) {
      setStatus({ text: e instanceof Error ? e.message : "Ошибка", error: true });
    } finally {
      setLoading(false);
    }
  }

  async function handleVerify() {
    if (!code) { setStatus({ text: "Введите код", error: true }); return; }

    try {
      setLoading(true);
      setStatus(null);

      await apiPost(`${API_BASE}/verify_code`, { email, code: String(code), token });

      const newsletterPayload = {
        email,
        token,
        filter_type_name: filterType,
        district_name: (needsDistrict(filterType) || needsRegion(filterType)) ? districtName : "",
      };

      if (mode === "subscribe") {
        await apiPost(`${API_BASE}/put_newsletter`, newsletterPayload);
      } else {
        await apiPost(`${API_BASE}/delete_newsletter`, newsletterPayload);
      }

      setStep("done");
      onDone(email);
    } catch (e) {
      setStatus({ text: e instanceof Error ? e.message : "Ошибка", error: true });
    } finally {
      setLoading(false);
    }
  }

  if (step === "done") {
    return (
      <div className="flex flex-col items-center gap-4 py-8 text-center">
        <CheckCircle2 size={48} className="text-[color:var(--se-techno-green)]" />
        <div className="text-xl font-bold text-[color:var(--se-text)]">
          {mode === "subscribe" ? "Подписка оформлена!" : "Вы отписались"}
        </div>
        <p className="max-w-sm text-sm text-[color:var(--se-muted)]">
          {mode === "subscribe"
            ? `На ${email} будут приходить уведомления о новых закупках типа «${filterType}».`
            : `Email ${email} удалён из рассылки «${filterType}».`}
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Шаг 1: email + фильтр */}
      <div className="space-y-3">
        <div>
          <label className="mb-1.5 block text-sm font-semibold text-[color:var(--se-text)]">
            Email
          </label>
          <Input
            type="email"
            placeholder="you@example.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            disabled={step === "code"}
          />
        </div>

        <div>
          <label className="mb-1.5 block text-sm font-semibold text-[color:var(--se-text)]">
            Тип заявок
          </label>
          <Select
            value={filterType}
            onChange={(e) => {
              setFilterType(e.target.value);
              setDistrictName("");
            }}
            disabled={step === "code"}
            options={FILTER_TYPE_OPTIONS}
          />
        </div>

        {needsDistrict(filterType) && (
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-[color:var(--se-text)]">
              Федеральный округ
            </label>
            <Select
              value={districtName}
              onChange={(e) => setDistrictName(e.target.value)}
              disabled={step === "code"}
              options={[{ label: "Выберите округ", value: "" }, ...DISTRICT_OPTIONS]}
            />
            <p className="mt-1 text-xs text-[color:var(--se-muted)]">
              Округ необходимых заявок
            </p>
          </div>
        )}

        {needsRegion(filterType) && (
          <div>
            <label className="mb-1.5 block text-sm font-semibold text-[color:var(--se-text)]">
              Регион заявок
            </label>
            <Select
              value={districtName}
              onChange={(e) => setDistrictName(e.target.value)}
              disabled={step === "code"}
              options={[{ label: "Выберите регион", value: "" }, ...REGIONS_OPTIONS]}
            />
            <p className="mt-1 text-xs text-[color:var(--se-muted)]">
              Регион необходимых заявок
            </p>
          </div>
        )}

      </div>

      {/* Шаг 2: код подтверждения */}
      {step === "code" && (
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4 space-y-3">
          <p className="text-sm text-[color:var(--se-muted)]">
            Код отправлен на <span className="font-semibold text-[color:var(--se-text)]">{email}</span>.
            Введите его ниже для подтверждения.
          </p>
          <Input
            placeholder="Код из письма"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          <button
            type="button"
            onClick={handleResendCode}
            disabled={cooldown > 0 || loading}
            className="text-xs font-semibold text-[color:var(--se-techno-green)] disabled:text-[color:var(--se-muted)] hover:underline"
          >
            {cooldown > 0 ? `Отправить повторно через ${cooldown} с.` : "Отправить код повторно"}
          </button>
        </div>
      )}

      {/* Статус */}
      {status && (
        <div
          className={`rounded-xl px-4 py-2.5 text-sm font-semibold ${
            status.error
              ? "bg-rose-50 text-rose-700"
              : "bg-emerald-50 text-[color:var(--se-techno-green)]"
          }`}
        >
          {status.text}
        </div>
      )}

      {/* Кнопки */}
      <div>
        {step === "form" ? (
          <Button onClick={handleSendCode} disabled={loading} className="w-full">
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={16} className="animate-spin" /> Отправляем...
              </span>
            ) : (
              "Получить код"
            )}
          </Button>
        ) : (
          <Button onClick={handleVerify} disabled={loading} className="w-full">
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <Loader2 size={16} className="animate-spin" /> Проверяем...
              </span>
            ) : mode === "subscribe" ? (
              "Подтвердить и подписаться"
            ) : (
              "Подтвердить и отписаться"
            )}
          </Button>
        )}
      </div>
    </div>
  );
}

// ─── главная страница ─────────────────────────────────────────────────────────

export function NewsletterPage() {
  const [token, setToken] = useState("");
  const [tokenError, setTokenError] = useState<string | null>(null);
  // ИСПРАВЛЕНО: заменил тип с Mode | null на Mode | null, но изменил логику handleOpen.
  // Проблема была: при клике на "Подписаться" когда уже открыта "Отписаться",
  // оба раскрывались одновременно. Это происходило потому что клик на одну карточку
  // ставил activeMode = новый режим, но React рендерил обе карточки до ресета.
  // Теперь handleOpen явно переключает: если нажали на тот же режим — закрывает,
  // если нажали на другой — закрывает старый и открывает новый (один setState).
  const [activeMode, setActiveMode] = useState<Mode | null>(null);
  const [lastDoneEmail, setLastDoneEmail] = useState<string | null>(null);

  useEffect(() => {
    getConfig()
      .then((r) => setToken(r.data.system_token || ""))
      .catch((e: unknown) =>
        setTokenError(e instanceof Error ? e.message : "Не удалось загрузить конфиг")
      );
  }, []);

  function handleDone(email: string) {
    setLastDoneEmail(email);
  }

  function handleToggle(mode: Mode) {
    // Если кликнули на уже открытый режим — закрыть. Иначе — переключить.
    // Один setState гарантирует что никогда не будут активны оба одновременно.
    setActiveMode((current) => (current === mode ? null : mode));
    setLastDoneEmail(null);
  }

  return (
    <>
      <Header
        title="Рассылка"
        subtitle="Подписка и отписка от email-уведомлений о новых закупках"
      />

      <div className="space-y-6 p-6">
        {tokenError && (
          <Card className="border-rose-200 bg-rose-50 text-rose-700 text-sm">
            {tokenError}
          </Card>
        )}

        {/* Пояснение */}
        <Card className="bg-emerald-50/60 border-emerald-200">
          <div className="flex items-start gap-4">
            <div className="rounded-2xl bg-emerald-100 p-3 text-[color:var(--se-techno-green)] shrink-0">
              <Mail size={24} />
            </div>
            <div>
              <div className="font-semibold text-[color:var(--se-text)]">
                Как работает рассылка
              </div>
              <p className="mt-1.5 text-sm leading-6 text-[color:var(--se-muted)]">
                Сервис ежедневно собирает новые закупки и рассылает уведомления подписчикам.
                Подписка привязана к типу заявок и, при необходимости, к федеральному округу.
                Для подтверждения email потребуется ввести код из письма.
              </p>
            </div>
          </div>
        </Card>

        {/* Карточки действий */}
        <div className="grid gap-4 sm:grid-cols-2 items-start">
          {/* Карточка "Подписаться" */}
          <Card
              className={`flex-1 cursor-pointer transition-all hover:shadow-md ${
                activeMode === "subscribe" ? "ring-2 ring-[color:var(--se-techno-green)]" : ""
              }`}
            >
            <button
              className="flex w-full items-center justify-between gap-4 text-left"
              type="button"
              onClick={() => handleToggle("subscribe")}
            >
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-emerald-100 p-2.5 text-[color:var(--se-techno-green)]">
                  <MailPlus size={20} />
                </div>
                <div>
                  <div className="font-semibold text-[color:var(--se-text)]">Подписаться</div>
                  <div className="text-xs text-[color:var(--se-muted)]">
                    Получать уведомления о новых закупках
                  </div>
                </div>
              </div>
              <ChevronDown
                size={18}
                className={`text-[color:var(--se-muted)] transition-transform ${
                  activeMode === "subscribe" ? "rotate-180" : ""
                }`}
              />
            </button>

            {activeMode === "subscribe" && (
              <div className="mt-5 border-t border-[color:var(--se-border)] pt-5">
                <NewsletterForm
                  key="subscribe"
                  mode="subscribe"
                  token={token}
                  onDone={handleDone}
                />
              </div>
            )}
          </Card>

          {/* Карточка "Отписаться" */}
          <Card
              className={`flex-1 cursor-pointer transition-all hover:shadow-md ${
                activeMode === "unsubscribe" ? "ring-2 ring-rose-400" : ""
              }`}
            >
            <button
              className="flex w-full items-center justify-between gap-4 text-left"
              type="button"
              onClick={() => handleToggle("unsubscribe")}
            >
              <div className="flex items-center gap-3">
                <div className="rounded-xl bg-rose-50 p-2.5 text-rose-500">
                  <MailMinus size={20} />
                </div>
                <div>
                  <div className="font-semibold text-[color:var(--se-text)]">Отписаться</div>
                  <div className="text-xs text-[color:var(--se-muted)]">
                    Удалить email из рассылки
                  </div>
                </div>
              </div>
              <ChevronDown
                size={18}
                className={`text-[color:var(--se-muted)] transition-transform ${
                  activeMode === "unsubscribe" ? "rotate-180" : ""
                }`}
              />
            </button>

            {activeMode === "unsubscribe" && (
              <div className="mt-5 border-t border-[color:var(--se-border)] pt-5">
                <NewsletterForm
                  key="unsubscribe"
                  mode="unsubscribe"
                  token={token}
                  onDone={handleDone}
                />
              </div>
            )}
          </Card>
        </div>

        {/* Последнее действие */}
        {lastDoneEmail && (
          <Card className="border-emerald-200 bg-emerald-50/60 flex items-center gap-3 text-sm text-[color:var(--se-techno-green)]">
            <CheckCircle2 size={18} className="shrink-0" />
            Последнее действие выполнено для <span className="font-semibold">{lastDoneEmail}</span>
          </Card>
        )}
      </div>
    </>
  );
}