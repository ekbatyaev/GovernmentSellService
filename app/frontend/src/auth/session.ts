const KEY = "auth_token";

export function getToken(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string) {
  try {
    localStorage.setItem(KEY, token);
  } catch {
    // приватный режим / заблокированное хранилище — живём без сохранения
  }
}

export function clearToken() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // см. setToken
  }
}

/** exp из payload JWT в миллисекундах. Подпись не проверяем — это делает бэк. */
export function getTokenExpiry(token: string): number | null {
  try {
    const part = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
    const payload = JSON.parse(atob(part));
    return typeof payload.exp === "number" ? payload.exp * 1000 : null;
  } catch {
    return null;
  }
}

export function isTokenAlive(token: string | null): token is string {
  const exp = token ? getTokenExpiry(token) : null;
  return exp !== null && exp > Date.now();
}
