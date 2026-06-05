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