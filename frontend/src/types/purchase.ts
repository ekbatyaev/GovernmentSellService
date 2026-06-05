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

export type PurchaseFilters = {
  token: string;

  name?: string;
  initial_sum_from?: number;
  initial_sum_to?: number;

  publication_datetime_from?: string;
  publication_datetime_to?: string;

  submission_start_datetime_from?: string;
  submission_start_datetime_to?: string;

  submission_close_datetime_from?: string;
  submission_close_datetime_to?: string;

  source_file?: string;

  filter_type_name?: string;
  region_number?: string;
  region_numbers?: string[];
};