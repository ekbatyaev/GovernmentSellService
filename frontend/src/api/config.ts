import { apiGet } from "./client";

export type AppConfig = {
  system_token: string;
};

export function getConfig() {
  return apiGet<AppConfig>("/config");
}