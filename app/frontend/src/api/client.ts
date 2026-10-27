import type { ApiResponse } from "../types/api";
import { clearToken, getToken } from "../auth/session";

const API_BASE = "";

// Бэк (get_current_user) отвечает именно этим текстом, когда токен просрочен,
// подделан или пользователь ещё не подтверждён. На 401 «Invalid code» и т.п. не разлогиниваем.
const INVALID_TOKEN_DETAIL = "Invalid token";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

let onUnauthorized: () => void = () => {};

export function setUnauthorizedHandler(handler: () => void) {
  onUnauthorized = handler;
}

function errorText(data: unknown, status: number): string {
  const detail = (data as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => (item as { msg?: unknown })?.msg)
      .filter((msg): msg is string => typeof msg === "string");
    if (messages.length) return messages.join("; ");
  }
  return `HTTP ${status}`;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  form = false,
): Promise<ApiResponse<T>> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;

  let payload: BodyInit | undefined;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(body as Record<string, string>);
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${path}`, { method, headers, body: payload });

  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    // пустое тело или не JSON
  }

  if (!response.ok) {
    const message = errorText(data, response.status);
    if (response.status === 401 && token && message === INVALID_TOKEN_DETAIL) {
      clearToken();
      onUnauthorized();
    }
    throw new ApiError(response.status, message);
  }

  return data as ApiResponse<T>;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  patch: <T>(path: string, body: unknown) => request<T>("PATCH", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
  postForm: <T>(path: string, body: Record<string, string>) =>
    request<T>("POST", path, body, true),
};
