import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  ExternalLink,
  FileText,
  Maximize2,
  Pencil,
  RefreshCw,
  Trash2,
  Save,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { getConfig } from "../api/config";
import { deletePurchase, getAllPurchases, updatePurchase } from "../api/purchases";
import { Header } from "../components/layout/Header";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Input } from "../components/ui/Input";
import { Select } from "../components/ui/Select";
import { formatDate, formatMoney } from "../lib/format";
import {
  buildPurchaseRequestMeta,
  FEDERAL_DISTRICT_OPTIONS,
  getDocumentDisplayMeta,
  getDocumentDisplayName,
  isOemOrItm,
  REGION_OPTIONS,
} from "../lib/purchases";
import type { Purchase, PurchaseFilters } from "../types/purchase";


type RequestPurchaseFilters = PurchaseFilters & {
  filter_type_name?: string;
  region_numbers?: string[];
};

const REGION_CODES_BY_FEDERAL_DISTRICT: Record<string, string[]> = {
  "Центральный федеральный округ": [
    "31", "32", "33", "36", "37", "40", "44", "46", "48", "50",
    "57", "62", "67", "68", "69", "71", "76", "77",
  ],
  "Северо-Западный федеральный округ": [
    "10", "11", "29", "35", "39", "47", "51", "53", "60", "78", "83",
  ],
  "Южный федеральный округ": [
    "01", "08", "23", "30", "34", "61", "82", "92",
  ],
  "Северо-Кавказский федеральный округ": [
    "05", "06", "07", "09", "15", "20", "26", "95",
  ],
  "Приволжский федеральный округ": [
    "02", "12", "13", "16", "18", "21", "43", "52", "56", "58",
    "59", "63", "64", "73", "81",
  ],
  "Уральский федеральный округ": [
    "45", "66", "72", "74", "86", "89",
  ],
  "Сибирский федеральный округ": [
    "04", "17", "19", "22", "24", "38", "42", "54", "55", "70", "85",
  ],
  "Дальневосточный федеральный округ": [
    "03", "14", "25", "27", "28", "41", "49", "65", "75", "79", "80", "87",
  ],
};

function getRegionNumbers(filters: UiFilters): string[] | undefined {
  if (filters.regionNumber) {
    return [filters.regionNumber];
  }

  if (filters.districtName) {
    return REGION_CODES_BY_FEDERAL_DISTRICT[filters.districtName];
  }

  return undefined;
}

type UiFilters = {
  filterTypeName: string;
  districtName: string;
  regionNumber: string;
  name: string;
  initialSumFrom: string;
  initialSumTo: string;
  publicationDateFrom: string;
  publicationDateTo: string;
  sourceFile: string;
};

const defaultFilters: UiFilters = {
  filterTypeName: "",
  districtName: "",
  regionNumber: "",
  name: "",
  initialSumFrom: "",
  initialSumTo: "",
  publicationDateFrom: "",
  publicationDateTo: "",
  sourceFile: "",
};

function toNumber(value: string): number | undefined {
  if (!value.trim()) {
    return undefined;
  }

  const number = Number(value.replace(",", "."));
  return Number.isFinite(number) ? number : undefined;
}

function buildFilters(token: string, filters: UiFilters): RequestPurchaseFilters {
  const requestMeta = buildPurchaseRequestMeta({
    filterTypeName: filters.filterTypeName,
    districtName: filters.districtName,
    regionNumber: filters.regionNumber,
  });
  const regionNumbers = getRegionNumbers(filters);

  const payload: RequestPurchaseFilters = {
    token,
    name: filters.name.trim() || undefined,
    initial_sum_from: toNumber(filters.initialSumFrom),
    initial_sum_to: toNumber(filters.initialSumTo),
    publication_datetime_from: filters.publicationDateFrom || undefined,
    publication_datetime_to: filters.publicationDateTo || undefined,
    source_file: filters.sourceFile.trim() || undefined,
    ...requestMeta,
    filter_type_name: filters.filterTypeName || undefined,
    region_numbers: regionNumbers,
  };

  return payload;
}

function getRecordValue(record: Record<string, unknown> | null, key: string): string {
  if (!record) {
    return "—";
  }

  const value = record[key];
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  return String(value);
}

function DocumentsList({ documents }: { documents: unknown[] }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!Array.isArray(documents) || documents.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-[color:var(--se-border)] bg-slate-50/70 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold">
          <FileText size={18} />
          Обработанные документы
        </div>
        <p className="mt-2 text-sm text-[color:var(--se-muted)]">
          Обработанные документы не найдены.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-[color:var(--se-border)] bg-white p-4">
      <button
        className="flex w-full items-center justify-between gap-3 text-left"
        onClick={() => setIsOpen((value) => !value)}
        type="button"
      >
        <div>
          <div className="flex items-center gap-2 text-sm font-semibold">
            <FileText size={18} />
            Обработанные документы
          </div>
          <div className="mt-1 text-xs text-[color:var(--se-muted)]">
            Найдено: {documents.length}. Список появится после нажатия «Показать».
          </div>
        </div>

        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-[color:var(--se-techno-green)]">
          {isOpen ? "Скрыть" : "Показать"}
          {isOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </span>
      </button>

      {isOpen && (
        <div className="mt-4 divide-y divide-[color:var(--se-border)] rounded-2xl border border-[color:var(--se-border)] bg-white">
          {documents.map((document, index) => {
            const item = document as Record<string, unknown>;
            const name = getDocumentDisplayName(document, index);
            const meta = getDocumentDisplayMeta(document);
            const rawUrl = item.url || item.href || item.link;
            const url = rawUrl ? String(rawUrl) : "";

            return (
              <div
                key={`${name}-${index}`}
                className="flex flex-col gap-2 px-4 py-3 md:flex-row md:items-center md:justify-between"
              >
                <div>
                  <div className="text-sm font-semibold text-[color:var(--se-text)]">
                    {name}
                  </div>

                  {meta && (
                    <div className="mt-1 text-xs text-[color:var(--se-muted)]">
                      {meta}
                    </div>
                  )}
                </div>

                {url && (
                  <a
                    className="inline-flex items-center gap-2 text-sm font-semibold text-[color:var(--se-techno-green)] hover:underline"
                    href={String(url)}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Открыть
                    <ExternalLink size={14} />
                  </a>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function PurposeFilterCard({
  filters,
  filterTypeOptions,
  onChange,
}: {
  filters: UiFilters;
  filterTypeOptions: { label: string; value: string }[];
  onChange: (patch: Partial<UiFilters>) => void;
}) {
  const [isOpen, setIsOpen] = useState(true);
  const showDistrictHint = isOemOrItm(filters.filterTypeName);

  return (
    <Card className="border-2 border-[color:var(--se-techno-green)] bg-emerald-50/60">
      <button
        className="flex w-full items-start justify-between gap-4 text-left"
        onClick={() => setIsOpen((value) => !value)}
        type="button"
      >
        <div>
          <div className="inline-flex items-center gap-2 rounded-full bg-white px-3 py-1 text-xs font-bold uppercase tracking-wide text-[color:var(--se-techno-green)] shadow-sm">
            Обязательный выбор цели
          </div>
          <h2 className="mt-3 text-lg font-bold text-[color:var(--se-text)]">
            Для каких целей нужны заявки?
          </h2>
          <p className="mt-1 text-sm text-[color:var(--se-muted)]">
            Тип фильтра отделён от остальных параметров, потому что он определяет
            сценарий поиска и влияет на подбор регионов.
          </p>
        </div>

        <span className="rounded-full bg-white p-2 text-[color:var(--se-techno-green)] shadow-sm">
          {isOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </span>
      </button>

      {isOpen && (
        <div className="mt-5 grid gap-4">
          <Select
            label="Тип фильтра / цель"
            value={filters.filterTypeName}
            onChange={(event) => onChange({ filterTypeName: event.target.value })}
            options={filterTypeOptions}
            className="border-[color:var(--se-techno-green)] bg-white font-semibold"
          />

          <div className="rounded-2xl bg-white/80 p-4 text-sm text-[color:var(--se-muted)]">
            {filters.filterTypeName ? (
              <>
                Выбран сценарий: <b>{filters.filterTypeName}</b>.
                {showDistrictHint
                  ? " Федеральный округ автоматически раскрывается в список регионов, если конкретный регион не выбран вручную."
                  : " Федеральный округ можно использовать как общий фильтр, а конкретный регион уточняет поиск."}
              </>
            ) : (
              "Выберите тип фильтра, чтобы сразу запустить поиск с корректным назначением заявок."
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

function FiltersPanel({
  filters,
  onChange,
  onReset,
}: {
  filters: UiFilters;
  onChange: (patch: Partial<UiFilters>) => void;
  onReset: () => void;
}) {
  const [isOpen, setIsOpen] = useState(true);

  return (
    <Card>
      <button
        className="flex w-full items-center justify-between gap-3 text-left"
        onClick={() => setIsOpen((value) => !value)}
        type="button"
      >
        <div className="flex items-center gap-2 font-semibold">
          <SlidersHorizontal size={18} />
          Обычные фильтры
        </div>
        {isOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {isOpen && (
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <Input
            label="Название закупки"
            placeholder="Например: выключатель"
            value={filters.name}
            onChange={(event) => onChange({ name: event.target.value })}
          />

          <Input
            label="Файл-источник"
            placeholder="source_file"
            value={filters.sourceFile}
            onChange={(event) => onChange({ sourceFile: event.target.value })}
          />

          <Select
            label="Федеральный округ"
            value={filters.districtName}
            onChange={(event) =>
              onChange({ districtName: event.target.value, regionNumber: "" })
            }
            options={FEDERAL_DISTRICT_OPTIONS}
          />

          <Select
            label="Регион"
            value={filters.regionNumber}
            onChange={(event) => onChange({ regionNumber: event.target.value })}
            options={REGION_OPTIONS}
          />

          <Input
            label="Сумма от"
            type="number"
            min="0"
            value={filters.initialSumFrom}
            onChange={(event) => onChange({ initialSumFrom: event.target.value })}
          />

          <Input
            label="Сумма до"
            type="number"
            min="0"
            value={filters.initialSumTo}
            onChange={(event) => onChange({ initialSumTo: event.target.value })}
          />

          <Input
            label="Публикация от"
            type="date"
            value={filters.publicationDateFrom}
            onChange={(event) =>
              onChange({ publicationDateFrom: event.target.value })
            }
          />

          <Input
            label="Публикация до"
            type="date"
            value={filters.publicationDateTo}
            onChange={(event) => onChange({ publicationDateTo: event.target.value })}
          />

          <div className="flex items-end justify-end md:col-span-2 xl:col-span-4">
            <Button variant="secondary" onClick={onReset} type="button">
              <X className="mr-2" size={16} />
              Сбросить фильтры
            </Button>
          </div>
        </div>
      )}
    </Card>
  );
}

type DeadlineStatus = {
  key: "active" | "soon" | "expired";
  label: string;
  tone: "success" | "warning" | "danger";
};

function getDeadlineStatus(purchase: Purchase): DeadlineStatus {
  const value = purchase.submission_close_datetime;

  if (!value) {
    return { key: "active", label: "Без дедлайна", tone: "success" };
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return { key: "active", label: "Дедлайн", tone: "success" };
  }

  const now = new Date();

  if (date.getTime() < now.getTime()) {
    return { key: "expired", label: "Просрочена", tone: "danger" };
  }

  const diffHours = (date.getTime() - now.getTime()) / 1000 / 60 / 60;

  if (diffHours <= 48) {
    return { key: "soon", label: `Скоро (${Math.ceil(diffHours)}ч)`, tone: "warning" };
  }

  return { key: "active", label: "Активна", tone: "success" };
}

function getRegionLabel(regionNumber?: string | null): string {
  if (!regionNumber) {
    return "—";
  }

  const option = REGION_OPTIONS.find((item) => item.value === regionNumber);
  return option ? option.label.replace(`${regionNumber} — `, "") : regionNumber;
}

function getCustomerName(customer: Record<string, unknown> | null): string {
  return (
    getRecordValue(customer, "full_name") !== "—"
      ? getRecordValue(customer, "full_name")
      : getRecordValue(customer, "name")
  );
}

function buildRegistryUrl(registrationNumber?: string | null): string {
  const value = String(registrationNumber || "").trim();

  if (!value) {
    return "";
  }

  return `https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=${encodeURIComponent(value)}`;
}

type PurchaseCardProps = {
  purchase: Purchase;
  token: string;
  onSaved: (purchase: Purchase) => void;
  onDeleted: (guid: string) => void;
};

type PurchaseDraft = {
  name: string;
  registrationNumber: string;
  initialSum: string;
  regionNumber: string;
  customerName: string;
  submissionStart: string;
  submissionClose: string;
  publicationDate: string;
};

function buildPurchaseDraft(purchase: Purchase): PurchaseDraft {
  const customerName = getCustomerName(purchase.customer);

  return {
    name: purchase.name || "",
    registrationNumber: purchase.registration_number || "",
    initialSum: purchase.initial_sum?.toString() || "",
    regionNumber: purchase.region_number || "",
    customerName: customerName === "—" ? "" : customerName,
    submissionStart: purchase.submission_start_datetime?.slice(0, 10) || "",
    submissionClose: purchase.submission_close_datetime?.slice(0, 10) || "",
    publicationDate: purchase.publication_datetime?.slice(0, 10) || "",
  };
}

function dateToIso(value: string): string | null {
  if (!value) {
    return null;
  }

  return new Date(`${value}T00:00:00`).toISOString();
}

function InfoTile({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-2xl bg-slate-50 p-3">
      <div className="text-xs font-semibold uppercase tracking-wide text-[color:var(--se-muted)]">
        {label}
      </div>
      <div
        className={`mt-1 min-w-0 break-words text-sm font-semibold text-[color:var(--se-text)] ${
          mono ? "font-mono" : ""
        }`}
      >
        {value || "—"}
      </div>
    </div>
  );
}

function PurchaseEditForm({
  draft,
  onChange,
}: {
  draft: PurchaseDraft;
  onChange: (draft: PurchaseDraft) => void;
}) {
  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <Input
        label="Наименование"
        value={draft.name}
        onChange={(event) => onChange({ ...draft, name: event.target.value })}
        className="md:col-span-2 xl:col-span-4"
      />
      <Input
        label="Регистрационный номер"
        value={draft.registrationNumber}
        onChange={(event) =>
          onChange({ ...draft, registrationNumber: event.target.value })
        }
      />
      <Input
        label="Стоимость"
        type="number"
        min="0"
        value={draft.initialSum}
        onChange={(event) => onChange({ ...draft, initialSum: event.target.value })}
      />
      <Select
        label="Регион подачи заявки"
        value={draft.regionNumber}
        onChange={(event) => onChange({ ...draft, regionNumber: event.target.value })}
        options={REGION_OPTIONS}
      />
      <Input
        label="Заказчик"
        value={draft.customerName}
        onChange={(event) => onChange({ ...draft, customerName: event.target.value })}
      />
      <Input
        label="Начало подачи заявки"
        type="date"
        value={draft.submissionStart}
        onChange={(event) =>
          onChange({ ...draft, submissionStart: event.target.value })
        }
      />
      <Input
        label="Окончание подачи заявки"
        type="date"
        value={draft.submissionClose}
        onChange={(event) => onChange({ ...draft, submissionClose: event.target.value })}
      />
      <Input
        label="Дата публикации"
        type="date"
        value={draft.publicationDate}
        onChange={(event) => onChange({ ...draft, publicationDate: event.target.value })}
      />
    </div>
  );
}

function PurchaseDetails({ purchase }: { purchase: Purchase }) {
  const registryUrl = buildRegistryUrl(purchase.registration_number);

  return (
    <div className="space-y-5">
      <div>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={getDeadlineStatus(purchase).tone}>
            {getDeadlineStatus(purchase).label}
          </Badge>
          <Badge>{purchase.guid ? `GUID: ${purchase.guid.slice(0, 8)}…` : "GUID: —"}</Badge>
        </div>

        <h2 className="mt-4 text-2xl font-bold leading-tight text-[color:var(--se-text)]">
          {purchase.name || "—"}
        </h2>

        <div className="mt-3 text-4xl font-bold text-[color:var(--se-text)]">
          {formatMoney(purchase.initial_sum)}
        </div>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        <InfoTile
          label="Регистрационный номер"
          value={purchase.registration_number || "—"}
          mono
        />
        <InfoTile label="Заказчик" value={getCustomerName(purchase.customer)} />
        <InfoTile label="Регион подачи заявки" value={getRegionLabel(purchase.region_number)} />
        <InfoTile
          label="Начало подачи заявки"
          value={formatDate(purchase.submission_start_datetime)}
        />
        <InfoTile
          label="Окончание подачи заявки"
          value={formatDate(purchase.submission_close_datetime)}
        />
        <InfoTile label="Дата публикации" value={formatDate(purchase.publication_datetime)} />
      </div>

      {registryUrl && (
        <a
          className="inline-flex h-10 items-center justify-center rounded-xl border border-[color:var(--se-border)] bg-white px-4 text-sm font-semibold text-[color:var(--se-text)] transition hover:bg-emerald-50"
          href={registryUrl}
          target="_blank"
          rel="noreferrer"
        >
          <ExternalLink className="mr-2" size={16} />
          Открыть в госреестре
        </a>
      )}

      <DocumentsList documents={purchase.documents_list || []} />
    </div>
  );
}

function PurchaseFullScreenModal({
  purchase,
  token,
  onClose,
  onSaved,
  onDeleted,
}: {
  purchase: Purchase;
  token: string;
  onClose: () => void;
  onSaved: (purchase: Purchase) => void;
  onDeleted: (guid: string) => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState(() => buildPurchaseDraft(purchase));

  useEffect(() => {
    setDraft(buildPurchaseDraft(purchase));
  }, [purchase]);

  async function handleSave() {
    if (!token || !purchase.guid) {
      setError("Нет токена или GUID заявки");
      return;
    }

    try {
      setIsSaving(true);
      setError(null);

      const response = await updatePurchase({
        token,
        guid: purchase.guid,
        name: draft.name,
        registration_number: draft.registrationNumber,
        initial_sum: toNumber(draft.initialSum) ?? null,
        region_number: draft.regionNumber || null,
        customer: {
          ...(purchase.customer || {}),
          full_name: draft.customerName || undefined,
        },
        publication_datetime: dateToIso(draft.publicationDate),
        submission_start_datetime: dateToIso(draft.submissionStart),
        submission_close_datetime: dateToIso(draft.submissionClose),
      });

      onSaved(response.data);
      setIsEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось сохранить заявку");
    } finally {
      setIsSaving(false);
    }
  }

  async function handleDelete() {
    if (!token || !purchase.guid) {
      setError("Нет токена или GUID заявки");
      return;
    }

    const ok = window.confirm(`Удалить заявку ${purchase.registration_number || purchase.name}?`);

    if (!ok) {
      return;
    }

    try {
      setIsSaving(true);
      setError(null);
      await deletePurchase(token, purchase.guid);
      onDeleted(purchase.guid);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Не удалось удалить заявку");
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 bg-slate-950/60 p-3 backdrop-blur-sm md:p-6">
      <div className="mx-auto flex h-full max-w-6xl flex-col overflow-hidden rounded-3xl bg-white shadow-2xl">
        <div className="flex items-start justify-between gap-4 border-b border-[color:var(--se-border)] px-5 py-4 md:px-7">
          <div className="min-w-0">
            <div className="text-xs font-bold uppercase tracking-wide text-[color:var(--se-muted)]">
              Полная карточка закупки
            </div>
            <div className="mt-1 truncate text-lg font-bold text-[color:var(--se-text)]">
              {purchase.registration_number || purchase.name || "Закупка"}
            </div>
          </div>

          <div className="flex shrink-0 flex-wrap justify-end gap-2">
            {isEditing ? (
              <>
                <Button variant="primary" onClick={handleSave} disabled={isSaving} type="button">
                  <Save className="mr-2" size={16} />
                  Сохранить
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => setIsEditing(false)}
                  disabled={isSaving}
                  type="button"
                >
                  Отмена
                </Button>
              </>
            ) : (
              <Button variant="secondary" onClick={() => setIsEditing(true)} type="button">
                <Pencil className="mr-2" size={16} />
                Изменить
              </Button>
            )}
            <Button variant="danger" onClick={handleDelete} disabled={isSaving} type="button">
              <Trash2 className="mr-2" size={16} />
              Удалить
            </Button>
            <Button variant="ghost" onClick={onClose} disabled={isSaving} type="button">
              <X className="mr-2" size={16} />
              Закрыть
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-5 md:px-7">
          {isEditing ? (
            <div className="space-y-5">
              <PurchaseEditForm draft={draft} onChange={setDraft} />
              <DocumentsList documents={purchase.documents_list || []} />
            </div>
          ) : (
            <PurchaseDetails purchase={purchase} />
          )}

          {error && (
            <div className="mt-5 rounded-2xl bg-rose-50 p-3 text-sm text-rose-700">
              {error}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function PurchaseCard({ purchase, token, onSaved, onDeleted }: PurchaseCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const status = getDeadlineStatus(purchase);
  const documentsCount = Array.isArray(purchase.documents_list)
    ? purchase.documents_list.length
    : 0;

  return (
    <>
      <Card className="p-0 transition hover:-translate-y-0.5 hover:shadow-lg">
        <button
          className="grid w-full gap-4 p-4 text-left lg:grid-cols-[minmax(0,1.35fr)_0.9fr_0.75fr_0.75fr_auto] lg:items-center"
          onClick={() => setIsOpen(true)}
          type="button"
        >
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone={status.tone}>{status.label}</Badge>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-[color:var(--se-muted)]">
                Документов: {documentsCount}
              </span>
            </div>
            <div className="mt-2 truncate text-base font-bold text-[color:var(--se-text)]">
              {purchase.name || "—"}
            </div>
            <div className="mt-1 truncate font-mono text-xs text-[color:var(--se-muted)]">
              № {purchase.registration_number || "—"}
            </div>
          </div>

          <div className="min-w-0">
            <div className="text-xs font-semibold uppercase tracking-wide text-[color:var(--se-muted)]">
              Заказчик
            </div>
            <div className="mt-1 truncate text-sm font-semibold text-[color:var(--se-text)]">
              {getCustomerName(purchase.customer)}
            </div>
          </div>

          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-[color:var(--se-muted)]">
              Стоимость
            </div>
            <div className="mt-1 text-sm font-bold text-[color:var(--se-text)]">
              {formatMoney(purchase.initial_sum)}
            </div>
          </div>

          <div>
            <div className="text-xs font-semibold uppercase tracking-wide text-[color:var(--se-muted)]">
              Срок подачи
            </div>
            <div className="mt-1 text-sm font-semibold text-[color:var(--se-text)]">
              {formatDate(purchase.submission_close_datetime)}
            </div>
            <div className="mt-1 text-xs text-[color:var(--se-muted)]">
              Регион: {getRegionLabel(purchase.region_number)}
            </div>
          </div>

          <div className="flex items-center justify-end gap-2 text-sm font-semibold text-[color:var(--se-techno-green)]">
            Открыть
            <Maximize2 size={16} />
          </div>
        </button>
      </Card>

      {isOpen && (
        <PurchaseFullScreenModal
          purchase={purchase}
          token={token}
          onClose={() => setIsOpen(false)}
          onSaved={onSaved}
          onDeleted={onDeleted}
        />
      )}
    </>
  );
}

export function PurchasesPage() {
  const [token, setToken] = useState("");
  const [filters, setFilters] = useState<UiFilters>(defaultFilters);
  const [purchases, setPurchases] = useState<Purchase[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const requestFilters = useMemo(() => buildFilters(token, filters), [filters, token]);
  const totalAmount = useMemo(
    () => purchases.reduce((sum, purchase) => sum + (purchase.initial_sum || 0), 0),
    [purchases],
  );
  const filterTypeOptions = useMemo(() => {
    const names = Array.from(
      new Set(
        purchases
          .map((purchase) => (purchase as Record<string, unknown>).filter_type_name)
          .filter(
            (value): value is string =>
              typeof value === "string" && Boolean(value.trim()),
          ),
      ),
    ).sort((left, right) => left.localeCompare(right, "ru"));

    return [
      { label: "Все типы", value: "" },
      ...names.map((name) => ({ label: name, value: name })),
    ];
  }, [purchases]);

  useEffect(() => {
    let ignore = false;

    getConfig()
      .then((response) => {
        if (!ignore) {
          setToken(response.data.system_token || "");
        }
      })
      .catch((err: unknown) => {
        if (!ignore) {
          setError(err instanceof Error ? err.message : "Не удалось получить токен");
        }
      });

    return () => {
      ignore = true;
    };
  }, []);

  useEffect(() => {
    if (!token) {
      return undefined;
    }

    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => {
      setIsLoading(true);
      setError(null);

      getAllPurchases(requestFilters)
        .then((response) => {
          if (!controller.signal.aborted) {
            setPurchases(Array.isArray(response.data) ? response.data : []);
            setLastUpdated(new Date().toISOString());
          }
        })
        .catch((err: unknown) => {
          if (!controller.signal.aborted) {
            setError(
              err instanceof Error ? err.message : "Не удалось загрузить закупки",
            );
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) {
            setIsLoading(false);
          }
        });
    }, 350);

    return () => {
      controller.abort();
      window.clearTimeout(timeoutId);
    };
  }, [requestFilters, token]);

  function updateFilters(patch: Partial<UiFilters>) {
    setFilters((current) => ({ ...current, ...patch }));
  }

  function handlePurchaseSaved(nextPurchase: Purchase) {
    setPurchases((current) =>
      current.map((purchase) =>
        purchase.guid === nextPurchase.guid ? nextPurchase : purchase,
      ),
    );
  }

  function handlePurchaseDeleted(guid: string) {
    setPurchases((current) => current.filter((purchase) => purchase.guid !== guid));
  }

  return (
    <>
      <Header
        title="Закупки"
        subtitle="Автоматический поиск: запрос в get_all_purchases уходит при каждом изменении фильтров"
      />

      <div className="space-y-5 p-6">
        <PurposeFilterCard filters={filters} filterTypeOptions={filterTypeOptions} onChange={updateFilters} />

        <FiltersPanel
          filters={filters}
          onChange={updateFilters}
          onReset={() => setFilters(defaultFilters)}
        />

        <div className="grid gap-4 md:grid-cols-3">
          <Card>
            <div className="flex items-center justify-between gap-3">
              <div>
                <div className="text-sm text-[color:var(--se-muted)]">Найдено заявок</div>
                <div className="mt-2 text-3xl font-bold">{purchases.length}</div>
              </div>
              <Search className="text-[color:var(--se-techno-green)]" size={30} />
            </div>
          </Card>

          <Card>
            <div className="text-sm text-[color:var(--se-muted)]">Общая сумма</div>
            <div className="mt-2 text-2xl font-bold">{formatMoney(totalAmount)}</div>
          </Card>

          <Card>
            <div className="flex items-center gap-2 text-sm text-[color:var(--se-muted)]">
              <RefreshCw size={16} className={isLoading ? "animate-spin" : ""} />
              Статус поиска
            </div>
            <div className="mt-2 text-lg font-bold">
              {isLoading ? "Загружаем..." : "Автообновление включено"}
            </div>
            <div className="mt-1 text-xs text-[color:var(--se-muted)]">
              Последнее обновление: {formatDate(lastUpdated)}
            </div>
          </Card>
        </div>

        {error && (
          <Card className="border-rose-200 bg-rose-50 text-rose-700">
            {error}
          </Card>
        )}

        <div className="space-y-4">
          {purchases.length === 0 && !isLoading ? (
            <Card>
              <div className="font-semibold">Заявки не найдены</div>
              <p className="mt-2 text-sm text-[color:var(--se-muted)]">
                Измени тип фильтра, регион, федеральный округ или обычные фильтры —
                поиск запустится автоматически.
              </p>
            </Card>
          ) : (
            purchases.map((purchase) => (
              <PurchaseCard
                key={purchase.guid || purchase.registration_number || purchase.name}
                purchase={purchase}
                token={token}
                onSaved={handlePurchaseSaved}
                onDeleted={handlePurchaseDeleted}
              />
            ))
          )}
        </div>
      </div>
    </>
  );
}
