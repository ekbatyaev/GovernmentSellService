export const FILTER_TYPE_OPTIONS = [
  { value: "", label: "Выберите цель поиска" },
  { value: "ОЭМ", label: "ОЭМ — закупки для производителей оборудования" },
  { value: "ИТМ", label: "ИТМ — инфраструктурные и технические материалы" },
  { value: "Поставка", label: "Поставка товаров" },
  { value: "Работы", label: "Выполнение работ" },
  { value: "Услуги", label: "Оказание услуг" },
];

export const DISPLAY_MODE_OPTIONS = [
  { value: "cards", label: "Карточки" },
  { value: "compact", label: "Компактно" },
];

export const REGION_CODES_BY_FEDERAL_DISTRICT: Record<string, string[]> = {
  "Центральный федеральный округ": [
    "31",
    "32",
    "33",
    "36",
    "37",
    "40",
    "44",
    "46",
    "48",
    "50",
    "57",
    "62",
    "67",
    "68",
    "69",
    "71",
    "76",
    "77",
  ],
  "Северо-Западный федеральный округ": [
    "10",
    "11",
    "29",
    "35",
    "39",
    "47",
    "51",
    "53",
    "60",
    "78",
    "83",
  ],
  "Южный федеральный округ": ["01", "08", "23", "30", "34", "61", "91", "92"],
  "Северо-Кавказский федеральный округ": ["05", "06", "07", "09", "15", "20", "26"],
  "Приволжский федеральный округ": [
    "02",
    "12",
    "13",
    "16",
    "18",
    "21",
    "43",
    "52",
    "56",
    "58",
    "59",
    "63",
    "64",
    "73",
  ],
  "Уральский федеральный округ": ["45", "66", "72", "74", "86", "89"],
  "Сибирский федеральный округ": ["04", "17", "19", "22", "24", "38", "42", "54", "55", "70"],
  "Дальневосточный федеральный округ": [
    "03",
    "14",
    "25",
    "27",
    "28",
    "41",
    "49",
    "65",
    "75",
    "79",
    "87",
  ],
};

export const FEDERAL_DISTRICT_OPTIONS = [
  { value: "", label: "Все федеральные округа" },
  ...Object.keys(REGION_CODES_BY_FEDERAL_DISTRICT).map((district) => ({
    value: district,
    label: district,
  })),
];

export const REGION_OPTIONS = [
  { value: "", label: "Все регионы" },
  { value: "01", label: "01 — Республика Адыгея" },
  { value: "02", label: "02 — Республика Башкортостан" },
  { value: "03", label: "03 — Республика Бурятия" },
  { value: "04", label: "04 — Республика Алтай" },
  { value: "05", label: "05 — Республика Дагестан" },
  { value: "06", label: "06 — Республика Ингушетия" },
  { value: "07", label: "07 — Кабардино-Балкарская Республика" },
  { value: "08", label: "08 — Республика Калмыкия" },
  { value: "09", label: "09 — Карачаево-Черкесская Республика" },
  { value: "10", label: "10 — Республика Карелия" },
  { value: "11", label: "11 — Республика Коми" },
  { value: "12", label: "12 — Республика Марий Эл" },
  { value: "13", label: "13 — Республика Мордовия" },
  { value: "14", label: "14 — Республика Саха (Якутия)" },
  { value: "15", label: "15 — Республика Северная Осетия — Алания" },
  { value: "16", label: "16 — Республика Татарстан" },
  { value: "17", label: "17 — Республика Тыва" },
  { value: "18", label: "18 — Удмуртская Республика" },
  { value: "19", label: "19 — Республика Хакасия" },
  { value: "20", label: "20 — Чеченская Республика" },
  { value: "21", label: "21 — Чувашская Республика" },
  { value: "22", label: "22 — Алтайский край" },
  { value: "23", label: "23 — Краснодарский край" },
  { value: "24", label: "24 — Красноярский край" },
  { value: "25", label: "25 — Приморский край" },
  { value: "26", label: "26 — Ставропольский край" },
  { value: "27", label: "27 — Хабаровский край" },
  { value: "28", label: "28 — Амурская область" },
  { value: "29", label: "29 — Архангельская область" },
  { value: "30", label: "30 — Астраханская область" },
  { value: "31", label: "31 — Белгородская область" },
  { value: "32", label: "32 — Брянская область" },
  { value: "33", label: "33 — Владимирская область" },
  { value: "34", label: "34 — Волгоградская область" },
  { value: "35", label: "35 — Вологодская область" },
  { value: "36", label: "36 — Воронежская область" },
  { value: "37", label: "37 — Ивановская область" },
  { value: "38", label: "38 — Иркутская область" },
  { value: "39", label: "39 — Калининградская область" },
  { value: "40", label: "40 — Калужская область" },
  { value: "41", label: "41 — Камчатский край" },
  { value: "42", label: "42 — Кемеровская область" },
  { value: "43", label: "43 — Кировская область" },
  { value: "44", label: "44 — Костромская область" },
  { value: "45", label: "45 — Курганская область" },
  { value: "46", label: "46 — Курская область" },
  { value: "47", label: "47 — Ленинградская область" },
  { value: "48", label: "48 — Липецкая область" },
  { value: "49", label: "49 — Магаданская область" },
  { value: "50", label: "50 — Московская область" },
  { value: "51", label: "51 — Мурманская область" },
  { value: "52", label: "52 — Нижегородская область" },
  { value: "53", label: "53 — Новгородская область" },
  { value: "54", label: "54 — Новосибирская область" },
  { value: "55", label: "55 — Омская область" },
  { value: "56", label: "56 — Оренбургская область" },
  { value: "57", label: "57 — Орловская область" },
  { value: "58", label: "58 — Пензенская область" },
  { value: "59", label: "59 — Пермский край" },
  { value: "60", label: "60 — Псковская область" },
  { value: "61", label: "61 — Ростовская область" },
  { value: "62", label: "62 — Рязанская область" },
  { value: "63", label: "63 — Самарская область" },
  { value: "64", label: "64 — Саратовская область" },
  { value: "65", label: "65 — Сахалинская область" },
  { value: "66", label: "66 — Свердловская область" },
  { value: "67", label: "67 — Смоленская область" },
  { value: "68", label: "68 — Тамбовская область" },
  { value: "69", label: "69 — Тверская область" },
  { value: "70", label: "70 — Томская область" },
  { value: "71", label: "71 — Тульская область" },
  { value: "72", label: "72 — Тюменская область" },
  { value: "73", label: "73 — Ульяновская область" },
  { value: "74", label: "74 — Челябинская область" },
  { value: "75", label: "75 — Забайкальский край" },
  { value: "76", label: "76 — Ярославская область" },
  { value: "77", label: "77 — Москва" },
  { value: "78", label: "78 — Санкт-Петербург" },
  { value: "79", label: "79 — Еврейская автономная область" },
  { value: "83", label: "83 — Ненецкий автономный округ" },
  { value: "86", label: "86 — Ханты-Мансийский автономный округ" },
  { value: "87", label: "87 — Чукотский автономный округ" },
  { value: "89", label: "89 — Ямало-Ненецкий автономный округ" },
  { value: "91", label: "91 — Республика Крым" },
  { value: "92", label: "92 — Севастополь" },
];

export const FLAG_OPTIONS_OEM = [
  { value: "", label: "Не выбрано" },
  { value: "Есть", label: "Есть" },
  { value: "Нету", label: "Нету" },
];



export function isOemOrItm(filterTypeName: string) {
  const normalized = filterTypeName.toLowerCase();

  return (
    normalized.includes("оэм") ||
    normalized.includes("oem") ||
    normalized.includes("итм") ||
    normalized.includes("itm")
  );
}

export function getRegionNumbersByDistrict(districtName: string) {
  return REGION_CODES_BY_FEDERAL_DISTRICT[districtName] || [];
}

export function buildPurchaseRequestMeta(filters: {
  filterTypeName: string;
  districtName: string;
  regionNumber: string;
}) {
  const shouldUseDistrict = isOemOrItm(filters.filterTypeName);

  if (filters.regionNumber) {
    return {
      filter_type_name: filters.filterTypeName || undefined,
      region_number: filters.regionNumber,
      region_numbers: [filters.regionNumber],
    };
  }

  if (shouldUseDistrict && filters.districtName) {
    const regionNumbers = getRegionNumbersByDistrict(filters.districtName);

    return {
      filter_type_name: filters.filterTypeName || undefined,
      region_numbers: regionNumbers.length ? regionNumbers : undefined,
    };
  }

  return {
    filter_type_name: filters.filterTypeName || undefined,
    region_numbers: undefined,
  };
}

export function getDocumentDisplayName(document: unknown, index: number): string {
  const item = document as Record<string, unknown>;

  const value =
    item.name ||
    item.file_name ||
    item.filename ||
    item.title ||
    item.document_name ||
    item.original_name ||
    item.url ||
    item.href ||
    item.link;

  return value ? String(value) : `Документ ${index + 1}`;
}

export function getDocumentDisplayMeta(document: unknown): string {
  const item = document as Record<string, unknown>;

  const parts = [
    item.type ? `Тип: ${String(item.type)}` : null,
    item.extension ? `Расширение: ${String(item.extension)}` : null,
    item.size ? `Размер: ${String(item.size)}` : null,
    item.created_at ? `Добавлен: ${String(item.created_at)}` : null,
  ].filter((part): part is string => Boolean(part));

  return parts.join(" · ");
}
