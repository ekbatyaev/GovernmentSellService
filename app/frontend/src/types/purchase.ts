export type Purchase = {
  guid: string;
  registration_number?: string | null;
  name: string;
  source_file?: string | null;
  initial_sum?: number | null;

  publication_datetime?: string | null;
  submission_start_datetime?: string | null;
  submission_close_datetime?: string | null;

  customer: Record<string, unknown> | null;
  contact: Record<string, unknown> | null;
  apply_request: Record<string, unknown> | null;
  result_info: Record<string, unknown> | null;
  documents_list: unknown[];
  lots: unknown[];

  filter_type_name?: string | null;
  region_number?: string | null;
};

// Совпадает с FilterNotice на бэке (app/schemas/purchase.py)
export type PurchaseFilters = {
  name?: string;
  registration_number?: string;
  initial_sum_from?: number;
  initial_sum_to?: number;

  publication_datetime_from?: string;
  publication_datetime_to?: string;

  submission_start_datetime_from?: string;
  submission_start_datetime_to?: string;

  submission_close_datetime_from?: string;
  submission_close_datetime_to?: string;

  source_file?: string;

  list_filter_type_name?: string[];
  region_numbers?: string[];

  oem_flag?: string; // "Есть" | "Нету" — только для «Тендеры для OEM»
  itm_option?: string; // "ITCLG" | "ITRAA" | ... — только для «Тендеры для ITM»
};