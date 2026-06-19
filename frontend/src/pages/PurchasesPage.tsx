import { useCallback, useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  ChevronUp,
  Download,
  ExternalLink,
  FileJson,
  FileSpreadsheet,
  FileText,
  Loader2,
  Maximize2,
  Pencil,
  RefreshCw,
  Save,
  Search,
  SlidersHorizontal,
  Trash2,
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
  isOemOrItm,
  REGION_OPTIONS,
  FLAG_OPTIONS_OEM
} from "../lib/purchases";
import type { Purchase, PurchaseFilters } from "../types/purchase";
import ExcelJS from "exceljs";

// ─── типы ─────────────────────────────────────────────────────────────────────

type RequestPurchaseFilters = PurchaseFilters & {
  filter_type_name?: string;
  region_numbers?: string[];
  oem_flag?: string;
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

// Карта код→название региона (для экспорта)
const REGION_NAMES_BY_CODE: Record<string, string> = {
  "01": "Республика Адыгея", "02": "Республика Башкортостан", "03": "Республика Бурятия",
  "04": "Республика Алтай", "05": "Республика Дагестан", "06": "Республика Ингушетия",
  "07": "Кабардино-Балкарская Республика", "08": "Республика Калмыкия",
  "09": "Карачаево-Черкесская Республика", "10": "Республика Карелия",
  "11": "Республика Коми", "12": "Республика Марий Эл", "13": "Республика Мордовия",
  "14": "Республика Саха (Якутия)", "15": "Республика Северная Осетия — Алания",
  "16": "Республика Татарстан", "17": "Республика Тыва", "18": "Удмуртская Республика",
  "19": "Республика Хакасия", "20": "Чеченская Республика (старый код)",
  "21": "Чувашская Республика", "22": "Алтайский край", "23": "Краснодарский край",
  "24": "Красноярский край", "25": "Приморский край", "26": "Ставропольский край",
  "27": "Хабаровский край", "28": "Амурская область", "29": "Архангельская область",
  "30": "Астраханская область", "31": "Белгородская область", "32": "Брянская область",
  "33": "Владимирская область", "34": "Волгоградская область", "35": "Вологодская область",
  "36": "Воронежская область", "37": "Ивановская область", "38": "Иркутская область",
  "39": "Калининградская область", "40": "Калужская область", "41": "Камчатский край",
  "42": "Кемеровская область — Кузбасс", "43": "Кировская область", "44": "Костромская область",
  "45": "Курганская область", "46": "Курская область", "47": "Ленинградская область",
  "48": "Липецкая область", "49": "Магаданская область", "50": "Московская область",
  "51": "Мурманская область", "52": "Нижегородская область", "53": "Новгородская область",
  "54": "Новосибирская область", "55": "Омская область", "56": "Оренбургская область",
  "57": "Орловская область", "58": "Пензенская область", "59": "Пермский край",
  "60": "Псковская область", "61": "Ростовская область", "62": "Рязанская область",
  "63": "Самарская область", "64": "Саратовская область", "65": "Сахалинская область",
  "66": "Свердловская область", "67": "Смоленская область", "68": "Тамбовская область",
  "69": "Тверская область", "70": "Томская область", "71": "Тульская область",
  "72": "Тюменская область", "73": "Ульяновская область", "74": "Челябинская область",
  "75": "Забайкальский край", "76": "Ярославская область", "77": "Москва",
  "78": "Санкт-Петербург", "79": "Еврейская автономная область", "82": "Республика Крым",
  "83": "Ненецкий автономный округ", "86": "Ханты-Мансийский АО — Югра",
  "87": "Чукотский автономный округ", "89": "Ямало-Ненецкий автономный округ",
  "92": "Севастополь", "95": "Чеченская Республика",
};

const ROSSETI_REGIONS_OPTIONS = [
  // Общие категории (были в образце)
  { label: "Все регионы", value: "" },
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


function getRegionNumbers(filters: UiFilters): string[] | undefined {
  if (filters.regionNumber) return [filters.regionNumber];
  if (filters.districtName) return REGION_CODES_BY_FEDERAL_DISTRICT[filters.districtName];
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
  submissionStartFrom: string;
  submissionStartTo: string;
  submissionCloseFrom: string;
  submissionCloseTo: string;
  oem_flag: string;
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
  submissionStartFrom: "",
  submissionStartTo: "",
  submissionCloseFrom: "",
  submissionCloseTo: "",
  oem_flag: ""
};

function dateToIsoStart(dateStr: string): string | undefined {
  if (!dateStr) return undefined;
  return `${dateStr}T00:00:00`;
}

function dateToIsoEnd(dateStr: string): string | undefined {
  if (!dateStr) return undefined;
  return `${dateStr}T23:59:59.999`;
}

function toNumber(value: string): number | undefined {
  if (!value.trim()) return undefined;
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

  return {
    token,
    name: filters.name.trim() || undefined,
    initial_sum_from: toNumber(filters.initialSumFrom),
    initial_sum_to: toNumber(filters.initialSumTo),
    publication_datetime_from: dateToIsoStart(filters.publicationDateFrom),
    publication_datetime_to: dateToIsoEnd(filters.publicationDateTo),
    submission_start_datetime_from: dateToIsoStart(filters.submissionStartFrom),
    submission_start_datetime_to: dateToIsoEnd(filters.submissionStartTo),
    submission_close_datetime_from: dateToIsoStart(filters.submissionCloseFrom),
    submission_close_datetime_to: dateToIsoEnd(filters.submissionCloseTo),
    ...requestMeta,
    filter_type_name: filters.filterTypeName || undefined,
    region_numbers: regionNumbers,
    oem_flag: filters.oem_flag || undefined
  };
}

function getRecordValue(record: Record<string, unknown> | null, key: string): string {
  if (!record) return "—";
  const value = record[key];
  if (value === null || value === undefined || value === "") return "—";
  return String(value);
}

// ─── экспорт ──────────────────────────────────────────────────────────────────

function buildGosRegistryUrl(registrationNumber?: string | null): string {
  const value = String(registrationNumber || "").trim();
  if (!value) return "";
  return `https://zakupki.gov.ru/epz/order/notice/notice223/common-info.html?regNumber=${encodeURIComponent(value)}`;
}

function safeExportValue(v: unknown): string {
  return v != null ? String(v) : "";
}

function formatExportDate(value: string | null | undefined): Date | "" {
  if (!value) return "";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? "" : d;
}

function buildExportRows(purchases: Purchase[], filterTypeName: string): Record<string, unknown>[] {
  const isOem = filterTypeName === "Тендеры для OEM";
  const isItm = filterTypeName === "Тендеры для ITM";

  if (isOem || isItm) {
    return purchases.map((p) => {
      const customer = (p as Record<string, unknown>).customer as Record<string, unknown> | null ?? null;
      const resultInfo = (p as Record<string, unknown>).result_info as Record<string, unknown> | null ?? null;
      const contact = (p as Record<string, unknown>).contact as Record<string, unknown> | null ?? null;

      const base: Record<string, unknown> = {
        "Реестровый номер": safeExportValue(p.registration_number),
        "Название закупки": safeExportValue(p.name),
        "Сумма закупки": Number(p.initial_sum) || 0,
        "Дата начала подачи заявок": formatExportDate(p.submission_start_datetime),
        "Дата окончания подачи заявок": formatExportDate(p.submission_close_datetime),
        "Дата публикации": formatExportDate(p.publication_datetime),
        "Заказчик название": safeExportValue(customer?.full_name),
        "Регион заявки": safeExportValue(REGION_NAMES_BY_CODE[p.region_number ?? ""] ?? p.region_number),
        "Ссылка на заявку в госреестре": buildGosRegistryUrl(p.registration_number),
      };

      if (isItm && resultInfo) {
        base["Победитель"] = safeExportValue(resultInfo["Победитель"]);
        base["ИНН"] = safeExportValue(resultInfo["ИНН"]);
        base["Итоговая цена контракта"] = safeExportValue(resultInfo["Итоговая цена контракта"]);
        base["Другие участники"] = safeExportValue(resultInfo["Другие участники"]);
      }

      const contactFullName = contact
      ? [contact.last_name, contact.first_name, contact.middle_name]
          .filter(Boolean)
          .join(' ')
      : '';

      const contactPhone = contact?.phone ? String(contact.phone) : 'Отсутствует';
      const contactEmail = contact?.email ? String(contact.email) : 'Отсутствует';

      if (isOem && resultInfo) {
        base["Контактное лицо"] = safeExportValue(contactFullName)
        base["Телефон"] = safeExportValue(contactPhone)
        base["Email"] = safeExportValue(contactEmail)
        base["Победитель"] = safeExportValue(resultInfo["Победитель"]);
        base["Итоговая цена контракта"] = safeExportValue(resultInfo["Итоговая цена контракта"]);
        base["Слова маячки в тз"] = safeExportValue(resultInfo["Слова маячки в тз"]);
      }

      return base;
    });
  }

  // Россети — развёртка по лотам
  const rows: Record<string, unknown>[] = [];
  for (const p of purchases) {
    const customer = (p as Record<string, unknown>).customer as Record<string, unknown> | null ?? null;
    const resultInfo = (p as Record<string, unknown>).result_info as Record<string, unknown> | null ?? null;
    const lots = Array.isArray((p as Record<string, unknown>).lots)
      ? ((p as Record<string, unknown>).lots as Record<string, unknown>[])
      : [{}];

    for (const lot of lots) {
      rows.push({
        "Реестровый номер закупки": safeExportValue(p.registration_number),
        "Наименование лота": safeExportValue(lot.subject ?? p.name),
        "Начальная (максимальная) цена контракта": Number(p.initial_sum) || 0,
        "Валюта": safeExportValue(lot.currency ?? "RUB"),
        "Наименование Заказчика": safeExportValue(customer?.full_name),
        "Регион заявки": safeExportValue(REGION_NAMES_BY_CODE[p.region_number ?? ""] ?? p.region_number),
        "Организация, осуществляющая размещение": safeExportValue(customer?.placement_organization ?? customer?.full_name),
        "Дата размещения": formatExportDate(p.submission_start_datetime),
        "Дата обновления": formatExportDate(p.publication_datetime),
        "Дата начала подачи заявок": formatExportDate(p.submission_start_datetime),
        "Дата окончания подачи заявок": formatExportDate(p.submission_close_datetime),
        "Победитель": safeExportValue(resultInfo?.["Победитель"]),
        "Другие участники": safeExportValue(resultInfo?.["Другие участники"]),
        "Ячейки": safeExportValue(resultInfo?.["Ячейки"]),
        "Кол-во ячеек": safeExportValue(resultInfo?.["Кол-во ячеек"]),
        "Типовой проект": safeExportValue(resultInfo?.["Типовой проект"]),
        "Проектировщик": safeExportValue(resultInfo?.["Проектировщик"]),
        "Дата исполнения договора": safeExportValue(resultInfo?.["Дата исполнения договора"]),
        "Филиал/РЭС": safeExportValue(resultInfo?.["Филиал/РЭС"]),
        "Ссылка на заявку в госреестре": buildGosRegistryUrl(p.registration_number),
      });
    }
  }
  return rows;
}

function buildExportFileName(ext: string, filterTypeName: string, districtName: string): string {
  const now = new Date();
  const day = String(now.getDate()).padStart(2, '0');
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const dateStr = `${day}.${month}`;

  if (filterTypeName === "Тендеры для OEM") {
    const d = districtName || "Все округа";
    return `oem_purchases_${d.toLowerCase().replace(/\s+/g, "_")}_${dateStr}.${ext}`;
  }
  if (filterTypeName === "Тендеры для ITM") {
    const d = districtName || "Все округа";
    return `itm_purchases_${d.toLowerCase().replace(/\s+/g, "_")}_${dateStr}.${ext}`;
  }
  if (filterTypeName === "Тендеры для Россетей") {
    const d = districtName || "Все округа";
    return `rosseti_purchases_${d.toLowerCase().replace(/\s+/g, "_")}_${dateStr}.${ext}`;
  }
  return `purchases_${dateStr}.${ext}`;
}

function downloadJson(purchases: Purchase[], filters: UiFilters) {
  const rows = buildExportRows(purchases, filters.filterTypeName).map((row) => {
    const normalized = { ...row };
    for (const key of Object.keys(normalized)) {
      if (normalized[key] instanceof Date) {
        normalized[key] = (normalized[key] as Date).toISOString();
      }
    }
    return normalized;
  });

  const blob = new Blob([JSON.stringify(rows, null, 2)], { type: "application/json;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = buildExportFileName("json", filters.filterTypeName, filters.districtName);
  a.click();
  URL.revokeObjectURL(a.href);
}

async function downloadXlsx(
  purchases: Purchase[],
  filters: UiFilters,
) {
  const workbook = new ExcelJS.Workbook();
  const worksheet = workbook.addWorksheet("Закупки");

  const rows = buildExportRows(
    purchases,
    filters.filterTypeName,
  );

  worksheet.columns = getExportColumns(
    filters.filterTypeName,
  );

  worksheet.addRows(rows);

  const thinBorder = {
    top: { style: "thin" },
    left: { style: "thin" },
    bottom: { style: "thin" },
    right: { style: "thin" },
  } as const;

  const yellowHeaderCols = new Set([
    "Победитель",
    "Другие участники",
    "ИНН",
    "Итоговая цена контракта",
    "Слова маячки в тз",
    "Ячейки",
    "Кол-во ячеек",
    "Типовой проект",
    "Проектировщик",
    "Дата исполнения договора",
    "Филиал/РЭС",
  ]);

  worksheet.getRow(1).height = 67.5;

  worksheet.getRow(1).eachCell((cell: ExcelJS.Cell) => {
    cell.font = {
      name: "Calibri",
      size: 11,
      bold: true,
    };

    cell.alignment = {
      horizontal: "center",
      vertical: "middle",
      wrapText: true,
    };

    cell.border = thinBorder;

    if (yellowHeaderCols.has(String(cell.value))) {
      cell.fill = {
        type: "pattern",
        pattern: "solid",
        fgColor: { argb: "FFFFFF00" },
      };
    }
  });

  for (
    let rowNumber = 2;
    rowNumber <= worksheet.rowCount;
    rowNumber++
  ) {
    const row = worksheet.getRow(rowNumber);

    row.eachCell((cell: ExcelJS.Cell, colNumber: number) => {
      cell.font = {
        name: "Calibri",
        size: 11,
      };

      cell.alignment = {
        wrapText: true,
        vertical: "middle",
      };

      cell.border = thinBorder;

      if (colNumber === 1) {
        cell.alignment = {
          ...cell.alignment,
          horizontal: "left",
        };
      }

      if (colNumber === 2) {
        cell.alignment = {
          ...cell.alignment,
          horizontal: "center",
        };
      }

      if (cell.value instanceof Date) {
        cell.numFmt = "dd.mm.yyyy";
      }

      if (typeof cell.value === "number") {
        cell.numFmt = "#,##0.00";
      }
    });
  }

  const buffer = await workbook.xlsx.writeBuffer();

  const blob = new Blob(
    [buffer],
    {
      type:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    },
  );

  const url = URL.createObjectURL(blob);

  const a = document.createElement("a");

  a.href = url;

  a.download = buildExportFileName(
    "xlsx",
    filters.filterTypeName,
    filters.districtName,
  );

  a.click();

  URL.revokeObjectURL(url);
}

function getExportColumns(filterTypeName: string) {
  if (filterTypeName === "Тендеры для OEM") {
    return [
      { header: "Реестровый номер", key: "Реестровый номер", width: 18 },
      { header: "Название закупки", key: "Название закупки", width: 60 },
      { header: "Сумма закупки", key: "Сумма закупки", width: 18 },
      { header: "Дата начала подачи заявок", key: "Дата начала подачи заявок", width: 18 },
      { header: "Дата окончания подачи заявок", key: "Дата окончания подачи заявок", width: 18 },
      { header: "Дата публикации", key: "Дата публикации", width: 18 },
      { header: "Заказчик название", key: "Заказчик название", width: 36 },
      { header: "Контактное лицо", key: "Контактное лицо", width: 16 },
      { header: "Телефон", key: "Телефон", width: 14 },
      { header: "Email", key: "Email", width: 14 },
      { header: "Победитель", key: "Победитель", width: 14 },
      { header: "Итоговая цена контракта", key: "Итоговая цена контракта", width: 13 },
      { header: "Слова маячки в тз", key: "Слова маячки в тз", width: 9 },
      { header: "Регион заявки", key: "Регион заявки", width: 36 },
      { header: "Ссылка на заявку в госреестре", key: "Ссылка на заявку в госреестре", width: 72 },
    ];
  }

  if (filterTypeName === "Тендеры для ITM") {
    return [
      { header: "Реестровый номер", key: "Реестровый номер", width: 18 },
      { header: "Название закупки", key: "Название закупки", width: 60 },
      { header: "Сумма закупки", key: "Сумма закупки", width: 18 },
      { header: "Дата начала подачи заявок", key: "Дата начала подачи заявок", width: 18 },
      { header: "Дата окончания подачи заявок", key: "Дата окончания подачи заявок", width: 18 },
      { header: "Дата публикации", key: "Дата публикации", width: 18 },
      { header: "Заказчик название", key: "Заказчик название", width: 36 },
      { header: "Регион заявки", key: "Регион заявки", width: 36 },
      { header: "Победитель", key: "Победитель", width: 14 },
      { header: "ИНН", key: "ИНН", width: 9 },
      { header: "Итоговая цена контракта", key: "Итоговая цена контракта", width: 13 },
      { header: "Другие участники", key: "Другие участники", width: 15 },
      { header: "Ссылка на заявку в госреестре", key: "Ссылка на заявку в госреестре", width: 72 },
    ];
  }

  return [
    { header: "Реестровый номер закупки", key: "Реестровый номер закупки", width: 16 },
    { header: "Наименование лота", key: "Наименование лота", width: 55 },
    { header: "Начальная (максимальная) цена контракта", key: "Начальная (максимальная) цена контракта", width: 16 },
    { header: "Валюта", key: "Валюта", width: 9 },
    { header: "Наименование Заказчика", key: "Наименование Заказчика", width: 28 },
    { header: "Регион заявки", key: "Регион заявки", width: 36 },
    { header: "Организация, осуществляющая размещение", key: "Организация, осуществляющая размещение", width: 21 },
    { header: "Дата размещения", key: "Дата размещения", width: 13 },
    { header: "Дата обновления", key: "Дата обновления", width: 13 },
    { header: "Дата начала подачи заявок", key: "Дата начала подачи заявок", width: 11 },
    { header: "Дата окончания подачи заявок", key: "Дата окончания подачи заявок", width: 13 },
    { header: "Победитель", key: "Победитель", width: 14 },
    { header: "Другие участники", key: "Другие участники", width: 15 },
    { header: "Ячейки", key: "Ячейки", width: 9 },
    { header: "Кол-во ячеек", key: "Кол-во ячеек", width: 13 },
    { header: "Типовой проект", key: "Типовой проект", width: 15 },
    { header: "Проектировщик", key: "Проектировщик", width: 29 },
    { header: "Дата исполнения договора", key: "Дата исполнения договора", width: 13 },
    { header: "Филиал/РЭС", key: "Филиал/РЭС", width: 14 },
    { header: "Ссылка на заявку в госреестре", key: "Ссылка на заявку в госреестре", width: 72 },
  ];
}

// ─── компонент "Экспорт" ──────────────────────────────────────────────────────

function ExportPanel({
  purchases,
  filters,
}: {
  purchases: Purchase[];
  filters: UiFilters;
}) {
  const [xlsxLoading, setXlsxLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleXlsx() {
    try {
      setXlsxLoading(true);
      setError(null);
      await downloadXlsx(purchases, filters);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка экспорта XLSX");
    } finally {
      setXlsxLoading(false);
    }
  }

  function handleJson() {
    try {
      setError(null);
      downloadJson(purchases, filters);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка экспорта JSON");
    }
  }

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 font-semibold text-[color:var(--se-text)]">
          <Download size={18} />
          Экспорт ({purchases.length} заявок)
        </div>

        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={handleJson} type="button">
            <FileJson size={16} className="mr-2" />
            JSON
          </Button>
          <Button variant="secondary" onClick={handleXlsx} disabled={xlsxLoading} type="button">
            {xlsxLoading
              ? <Loader2 size={16} className="mr-2 animate-spin" />
              : <FileSpreadsheet size={16} className="mr-2" />
            }
            XLSX
          </Button>
        </div>
      </div>

      {error && (
        <div className="mt-3 rounded-xl bg-rose-50 px-4 py-2.5 text-sm text-rose-700">
          {error}
        </div>
      )}
    </Card>
  );
}

// ─── документы заявки ────────────────────────────────────────────────────────
// ИСПРАВЛЕНО: раньше компонент принимал documents_list как `unknown[]`, но
// getDocumentDisplayName/Meta ожидают правильно типизированный объект.
// Добавлена явная нормализация элементов перед передачей в утилиты.

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
          onClick={() => setIsOpen((v) => !v)}
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
            {documents.map((document, index) => (
              <div key={`${String(document)}-${index}`} className="px-4 py-3">
                <div className="text-sm font-semibold text-[color:var(--se-text)]">
                  {String(document)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    );
}

// ─── фильтры ─────────────────────────────────────────────────────────────────

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
        onClick={() => setIsOpen((v) => !v)}
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
            label="Тип фильтра"
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
        onClick={() => setIsOpen((v) => !v)}
        type="button"
      >
        <div className="flex items-center gap-2 font-semibold">
          <SlidersHorizontal size={18} />
          Обычные фильтры
        </div>
        {isOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
      </button>

      {isOpen && (
        <div className="mt-5 space-y-5">
          {/* Название закупки — на всю ширину */}
          <Input
            label="Название закупки"
            placeholder="Например: выключатель"
            value={filters.name}
            onChange={(event) => onChange({ name: event.target.value })}
          />

          {/* Пара: Федеральный округ + Регион */}
          {(filters.filterTypeName === "Тендеры для OEM" || filters.filterTypeName === "Тендеры для ITM") && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
          </div>
          )}

          {filters.filterTypeName === "Тендеры для Россетей" && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Select
              label="Регион"
              value={filters.regionNumber}
              onChange={(event) => onChange({ regionNumber: event.target.value })}
              options={ROSSETI_REGIONS_OPTIONS}
            />
          </div>
          )}

          {/* Пара: Начало подачи от/до */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input
              label="Начало подачи от"
              type="date"
              value={filters.submissionStartFrom}
              onChange={(e) => onChange({ submissionStartFrom: e.target.value })}
            />
            <Input
              label="Начало подачи до"
              type="date"
              value={filters.submissionStartTo}
              onChange={(e) => onChange({ submissionStartTo: e.target.value })}
            />
          </div>

          {/* Пара: Окончание подачи от/до */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input
              label="Окончание подачи от"
              type="date"
              value={filters.submissionCloseFrom}
              onChange={(e) => onChange({ submissionCloseFrom: e.target.value })}
            />
            <Input
              label="Окончание подачи до"
              type="date"
              value={filters.submissionCloseTo}
              onChange={(e) => onChange({ submissionCloseTo: e.target.value })}
            />
          </div>

          {/* Пара: Публикация от/до */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input
              label="Публикация от"
              type="date"
              value={filters.publicationDateFrom}
              onChange={(event) => onChange({ publicationDateFrom: event.target.value })}
            />
            <Input
              label="Публикация до"
              type="date"
              value={filters.publicationDateTo}
              onChange={(event) => onChange({ publicationDateTo: event.target.value })}
            />
          </div>

          {/* Пара: Сумма от/до */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
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
          </div>

          {(filters.filterTypeName === "Тендеры для OEM") && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Select
              label="Слова маячки в тз"
              value={filters.oem_flag}
              onChange={(event) => onChange({ oem_flag: event.target.value })}
              options={FLAG_OPTIONS_OEM}
            />
          </div>
          )}


          {/* Кнопка сброса — справа */}
          <div className="flex justify-end">
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

// ─── статус дедлайна ─────────────────────────────────────────────────────────

type DeadlineStatus = {
  key: "active" | "soon" | "expired";
  label: string;
  tone: "success" | "warning" | "danger";
};

function getDeadlineStatus(purchase: Purchase): DeadlineStatus {
  const value = purchase.submission_close_datetime;
  if (!value) return { key: "active", label: "Без дедлайна", tone: "success" };

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return { key: "active", label: "Дедлайн", tone: "success" };

  const now = new Date();
  if (date.getTime() < now.getTime()) return { key: "expired", label: "Просрочена", tone: "danger" };

  const diffHours = (date.getTime() - now.getTime()) / 1000 / 60 / 60;
  if (diffHours <= 48) return { key: "soon", label: `Скоро (${Math.ceil(diffHours)}ч)`, tone: "warning" };

  return { key: "active", label: "Активна", tone: "success" };
}

function getRegionLabel(regionNumber?: string | null): string {
  if (!regionNumber) return "—";
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

// ─── вспомогательные компоненты детальной карточки ───────────────────────────

function InfoTile({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="rounded-2xl bg-slate-50 p-4">
      <div className="text-xs font-semibold uppercase tracking-wide text-[color:var(--se-muted)]">
        {label}
      </div>
      <div className={`mt-2 text-sm font-semibold text-[color:var(--se-text)] ${mono ? "font-mono" : ""}`}>
        {value}
      </div>
    </div>
  );
}

// ─── форма редактирования ─────────────────────────────────────────────────────

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
  if (!value) return null;
  return new Date(`${value}T00:00:00`).toISOString();
}

function PurchaseEditForm({
  draft,
  onChange,
}: {
  draft: PurchaseDraft;
  onChange: (draft: PurchaseDraft) => void;
}) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Input
        label="Название закупки"
        value={draft.name}
        onChange={(event) => onChange({ ...draft, name: event.target.value })}
        className="md:col-span-2"
      />
      <Input
        label="Регистрационный номер"
        value={draft.registrationNumber}
        onChange={(event) => onChange({ ...draft, registrationNumber: event.target.value })}
      />
      <Input
        label="Сумма"
        type="number"
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
        onChange={(event) => onChange({ ...draft, submissionStart: event.target.value })}
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

// ─── детали заявки ───────────────────────────────────────────────────────────

function PurchaseDetails({ purchase }: { purchase: Purchase }) {
  const registryUrl = buildGosRegistryUrl(purchase.registration_number);
  const contact = purchase.contact;

  const contactFullName = contact
  ? [contact.last_name, contact.first_name, contact.middle_name]
      .filter(Boolean)
      .join(' ')
  : '';

  const contactPhone = contact?.phone ? String(contact.phone) : 'Отсутствует';
  const contactEmail = contact?.email ? String(contact.email) : 'Отсутствует';

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
        <InfoTile label="Регистрационный номер" value={purchase.registration_number || "—"} mono />
        <InfoTile label="Заказчик" value={getCustomerName(purchase.customer)} />
        <InfoTile label="Контактное лицо" value={contactFullName || 'Отсутствует'} />
        <InfoTile label="Телефон" value={contactPhone} />
        <InfoTile label="Email" value={contactEmail} />
        <InfoTile label="Регион подачи заявки" value={getRegionLabel(purchase.region_number)} />
        <InfoTile label="Начало подачи заявки" value={formatDate(purchase.submission_start_datetime)} />
        <InfoTile label="Окончание подачи заявки" value={formatDate(purchase.submission_close_datetime)} />
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

      {/* ИСПРАВЛЕНО: documents_list может быть null/undefined — защита перед передачей */}
      <DocumentsList
        documents={Array.isArray(purchase.documents_list) ? purchase.documents_list : []}
      />
    </div>
  );
}

// ─── модальное окно заявки ───────────────────────────────────────────────────

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

  useEffect(() => { setDraft(buildPurchaseDraft(purchase)); }, [purchase]);

  async function handleSave() {
    if (!token || !purchase.guid) { setError("Нет токена или GUID заявки"); return; }

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
        customer: { ...(purchase.customer || {}), full_name: draft.customerName || undefined },
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
    if (!token || !purchase.guid) { setError("Нет токена или GUID заявки"); return; }

    const ok = window.confirm(`Удалить заявку ${purchase.registration_number || purchase.name}?`);
    if (!ok) return;

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
                <Button variant="ghost" onClick={() => setIsEditing(false)} disabled={isSaving} type="button">
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
              <DocumentsList
                documents={Array.isArray(purchase.documents_list) ? purchase.documents_list : []}
              />
            </div>
          ) : (
            <PurchaseDetails purchase={purchase} />
          )}

          {error && (
            <div className="mt-5 rounded-2xl bg-rose-50 p-3 text-sm text-rose-700">{error}</div>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── карточка заявки в списке ────────────────────────────────────────────────

type PurchaseCardProps = {
  purchase: Purchase;
  token: string;
  onSaved: (purchase: Purchase) => void;
  onDeleted: (guid: string) => void;
};

function PurchaseCard({ purchase, token, onSaved, onDeleted }: PurchaseCardProps) {
  const [isOpen, setIsOpen] = useState(false);
  const status = getDeadlineStatus(purchase);
  const documentsCount = Array.isArray(purchase.documents_list) ? purchase.documents_list.length : 0;

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
  const [sortOption, setSortOption] = useState<string>("submission_start_desc");
  const [refreshKey, setRefreshKey] = useState(0);

  // Пагинация: по 25 заявок на страницу
  const [currentPage, setCurrentPage] = useState(1);
  const ITEMS_PER_PAGE = 25;

  const requestFilters = useMemo(() => buildFilters(token, filters), [filters, token]);

  const totalAmount = useMemo(
    () => purchases.reduce((sum, p) => sum + (p.initial_sum || 0), 0),
    [purchases],
  );

  const sortedPurchases = useMemo(() => {
      const list = [...purchases];
      const safeDate = (date?: string | null) => {
        const d = new Date(date || 0);
        return isNaN(d.getTime()) ? 0 : d.getTime();
      };

      switch (sortOption) {
        case "sum_desc":
          return list.sort((a, b) => (b.initial_sum || 0) - (a.initial_sum || 0));
        case "sum_asc":
          return list.sort((a, b) => (a.initial_sum || 0) - (b.initial_sum || 0));
        case "name_asc":
          return list.sort((a, b) => (a.name || "").localeCompare(b.name || "", "ru"));
        case "submission_start_asc":
          return list.sort((a, b) => safeDate(a.submission_start_datetime) - safeDate(b.submission_start_datetime));
        case "submission_start_desc":
          return list.sort((a, b) => safeDate(b.submission_start_datetime) - safeDate(a.submission_start_datetime));
        case "submission_close_asc":
          return list.sort((a, b) => safeDate(a.submission_close_datetime) - safeDate(b.submission_close_datetime));
        case "submission_close_desc":
          return list.sort((a, b) => safeDate(b.submission_close_datetime) - safeDate(a.submission_close_datetime));
        case "pub_asc":
          return list.sort((a, b) => safeDate(a.publication_datetime) - safeDate(b.publication_datetime));
        case "pub_desc":
          return list.sort((a, b) => safeDate(b.publication_datetime) - safeDate(a.publication_datetime));
        default:
          return list;
      }
    }, [purchases, sortOption]);

  // Вычисляем общее количество страниц
  const totalPages = Math.ceil(sortedPurchases.length / ITEMS_PER_PAGE);
  // Текущие заявки (срез)
  const currentPurchases = useMemo(() => {
    const start = (currentPage - 1) * ITEMS_PER_PAGE;
    const end = start + ITEMS_PER_PAGE;
    return sortedPurchases.slice(start, end);
  }, [sortedPurchases, currentPage]);

  // Сброс страницы при изменении фильтров, сортировки или обновлении данных
  useEffect(() => {
    setCurrentPage(1);
  }, [filters, sortOption, refreshKey, purchases.length]);

  const filterTypeOptions = [
      { label: "Все типы", value: "" },
  { label: "Тендеры для Россетей", value: "Тендеры для Россетей" },
  { label: "Тендеры для OEM", value: "Тендеры для OEM" },
  { label: "Тендеры для ITM", value: "Тендеры для ITM" }
    ];

  useEffect(() => {
    let ignore = false;
    getConfig()
      .then((response) => { if (!ignore) setToken(response.data.system_token || ""); })
      .catch((err: unknown) => { if (!ignore) setError(err instanceof Error ? err.message : "Не удалось получить токен"); });
    return () => { ignore = true; };
  }, []);

  useEffect(() => {
    if (!token) return undefined;

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
            setError(err instanceof Error ? err.message : "Не удалось загрузить закупки");
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setIsLoading(false);
        });
    }, 350);

    return () => {
      controller.abort();
      window.clearTimeout(timeoutId);
    };
  }, [requestFilters, token, refreshKey]);

  function updateFilters(patch: Partial<UiFilters>) {
    setFilters((current) => ({ ...current, ...patch }));
  }

  const handleRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
  }, []);

  function handlePurchaseSaved(nextPurchase: Purchase) {
    setPurchases((current) =>
      current.map((p) => (p.guid === nextPurchase.guid ? nextPurchase : p)),
    );
  }

  function handlePurchaseDeleted(guid: string) {
    setPurchases((current) => current.filter((p) => p.guid !== guid));
  }

  // Функция для рендера кружочков пагинации
  const renderPagination = () => {
    if (totalPages <= 1) return null;

    // Показываем максимум 7 кружочков, чтобы не перегружать экран
    const maxVisible = 7;
    let pages: number[] = [];
    if (totalPages <= maxVisible) {
      pages = Array.from({ length: totalPages }, (_, i) => i + 1);
    } else {
      const left = Math.max(1, currentPage - 3);
      const right = Math.min(totalPages, currentPage + 3);
      if (left > 1) pages.push(1, -1); // -1 означает пропуск (троеточие)
      for (let i = left; i <= right; i++) pages.push(i);
      if (right < totalPages) pages.push(-1, totalPages);
    }

    return (
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {/* Кнопка "Назад" */}
        <Button
          variant="ghost"
          className="rounded-full w-10 h-10 p-0"
          onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
          disabled={currentPage === 1}
        >
          ←
        </Button>

        {pages.map((p, idx) =>
          p === -1 ? (
            <span key={`dots-${idx}`} className="w-10 h-10 flex items-center justify-center text-muted">
              …
            </span>
          ) : (
            <Button
              key={p}
              variant={currentPage === p ? "primary" : "secondary"}
              className="rounded-full w-10 h-10 p-0"
              onClick={() => setCurrentPage(p)}
            >
              {p}
            </Button>
          )
        )}

        {/* Кнопка "Вперёд" */}
        <Button
          variant="ghost"
          className="rounded-full w-10 h-10 p-0"
          onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
          disabled={currentPage === totalPages}
        >
          →
        </Button>
      </div>
    );
  };

  return (
    <>
      <Header
        title="Закупки"
        subtitle="Автоматический поиск: запрос уходит при каждом изменении фильтров"
        onRefresh={handleRefresh}
      />

      <div className="space-y-5 p-6">
        <PurposeFilterCard
          filters={filters}
          filterTypeOptions={filterTypeOptions}
          onChange={updateFilters}
        />

        <FiltersPanel
          filters={filters}
          onChange={updateFilters}
          onReset={() => setFilters(defaultFilters)}
        />

        {/* Статистика */}
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
          <Card className="border-rose-200 bg-rose-50 text-rose-700">{error}</Card>
        )}

        {/* Экспорт */}
        {purchases.length > 0 && (
          <ExportPanel purchases={purchases} filters={filters} />
        )}

        {/* Сортировка */}
        <div className="flex items-center gap-4">
          <Select
            label="Сортировка"
            value={sortOption}
            onChange={(e) => setSortOption(e.target.value)}
            options={[
              { label: "По дате начала (новые)", value: "submission_start_desc" },
              { label: "По дате начала (старые)", value: "submission_start_asc" },
              { label: "По дате окончания (скоро)", value: "submission_close_asc" },
              { label: "По дате окончания (позже)", value: "submission_close_desc" },
              { label: "По сумме (убывание)", value: "sum_desc" },
              { label: "По сумме (возрастание)", value: "sum_asc" },
              { label: "По названию", value: "name_asc" },
              { label: "По дате публикации (новые)", value: "pub_desc" },
              { label: "По дате публикации (старые)", value: "pub_asc" },
            ]}
          />
        </div>

        {/* Список заявок (только текущая страница) */}
        <div className="space-y-4">
          {currentPurchases.length === 0 && !isLoading ? (
            <Card>
              <div className="font-semibold">Заявки не найдены</div>
              <p className="mt-2 text-sm text-[color:var(--se-muted)]">
                Измени тип фильтра, регион, федеральный округ или обычные фильтры —
                поиск запустится автоматически.
              </p>
            </Card>
          ) : (
            currentPurchases.map((purchase) => (
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
        {renderPagination()}
      </div>
    </>
  );
}