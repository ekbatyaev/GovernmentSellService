import { api } from "./client";

export type Stats = {
  purchases_count: number;
  newsletter_count: number;
  timestamp: string;
  last_backfill_at: string | null;
  last_process_day_at: string | null;
};

export function getStats() {
  return api.get<Stats>("/services/stats");
}
