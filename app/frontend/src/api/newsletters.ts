import { api } from "./client";

/** Отправляет код на почту. В data.guid — идентификатор кода, нужен для подтверждения. */
export function sendNewsletterCode(email: string) {
  return api.post<{ guid: string }>(`/services/send_auth_code/${encodeURIComponent(email)}`);
}

export type ConfirmNewsletterBody = {
  guid: string;
  email: string;
  code: number;
  option: "subscribe" | "unsubscribe";
  filter_type_name: string;
  district_name: string;
};

/** Проверяет код и сразу подписывает / отписывает. */
export function confirmNewsletter(body: ConfirmNewsletterBody) {
  return api.post<{ guid: string }>("/newsletters/confirm", body);
}
