import { api } from "./client";
import type { Purchase, PurchaseFilters } from "../types/purchase";

export function searchPurchases(filters: PurchaseFilters) {
  return api.post<Purchase[]>("/purchases/search", filters);
}

export function getPurchase(guid: string) {
  return api.get<Purchase>(`/purchases/${encodeURIComponent(guid)}`);
}

export type UpdatePurchasePayload = Partial<
  Pick<
    Purchase,
    | "name"
    | "registration_number"
    | "source_file"
    | "initial_sum"
    | "publication_datetime"
    | "submission_start_datetime"
    | "submission_close_datetime"
    | "customer"
    | "contact"
    | "apply_request"
    | "result_info"
    | "documents_list"
    | "lots"
    | "filter_type_name"
    | "region_number"
  >
>;

/** PATCH возвращает только guid — поэтому сразу перечитываем закупку целиком. */
export async function updatePurchase(guid: string, patch: UpdatePurchasePayload): Promise<Purchase> {
  await api.patch<{ guid: string }>(`/purchases/${encodeURIComponent(guid)}`, patch);
  const response = await getPurchase(guid);
  return response.data;
}

export function deletePurchase(guid: string) {
  return api.del<{ guid: string }>(`/purchases/${encodeURIComponent(guid)}`);
}
