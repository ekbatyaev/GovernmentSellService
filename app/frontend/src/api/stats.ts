import { apiGet } from "./client";

export type Stats = {
  purchases_count: number;
  timestamp: string;
};

export function getStats() {
  return apiGet<Stats>("/stats");
}