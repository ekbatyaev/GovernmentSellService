import { api } from "./client";

export type UserRole = "admin" | "user" | "guest";

/** OAuth2PasswordRequestForm на бэке — поля username/password в form-urlencoded. */
export function login(email: string, password: string) {
  return api.postForm<{ access_token: string; token_type: string }>("/users/login", {
    username: email,
    password,
  });
}

/** Шаг 1 регистрации: код на почту. В data.guid — идентификатор кода для шага 2. */
export function requestRegisterCode(email: string) {
  return api.post<{ guid: string }>("/users/confirm", { email });
}

/** Шаг 2 регистрации: код + пароль. Пользователь создаётся с ролью guest. */
export function register(codeGuid: string, email: string, password: string, code: number) {
  return api.post<{ guid: string }>(`/users/register/${encodeURIComponent(codeGuid)}`, {
    email,
    password,
    code,
  });
}

/** Только для администратора. */
export function approveUser(guid: string, role: UserRole) {
  return api.post<Record<string, never>>(`/users/approve/${encodeURIComponent(guid)}`, { role });
}
