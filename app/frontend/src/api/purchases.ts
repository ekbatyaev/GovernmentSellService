import { apiPost } from "./client";
import type { Purchase, PurchaseFilters } from "../types/purchase";

export function getAllPurchases(filters: PurchaseFilters) {
  return apiPost<Purchase[], PurchaseFilters>("/get_all_purchases", filters);
}

export function getPurchaseByGuid(token: string, guid: string) {
  return apiPost<Purchase, { token: string; guid: string }>("/get_purchase", {
    token,
    guid,
  });
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
> & {
  token: string;
  guid: string;
};

export function updatePurchase(payload: UpdatePurchasePayload) {
  return apiPost<Purchase, UpdatePurchasePayload>("/update_purchase", payload);
}

export function deletePurchase(token: string, guid: string) {
  return apiPost<{ guid: string }, { token: string; guid: string }>("/delete_purchase", {
    token,
    guid,
  });
}
