import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type PropsWithChildren,
} from "react";
import { setUnauthorizedHandler } from "../api/client";
import { clearToken, getToken, getTokenExpiry, isTokenAlive, setToken } from "./session";

type AuthState = {
  token: string | null;
  login: (token: string) => void;
  logout: () => void;
};

const AuthContext = createContext<AuthState | null>(null);

function initialToken(): string | null {
  const token = getToken();
  if (isTokenAlive(token)) return token;
  clearToken();
  return null;
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [token, setTokenState] = useState<string | null>(initialToken);

  const logout = useCallback(() => {
    clearToken();
    setTokenState(null);
  }, []);

  const login = useCallback((newToken: string) => {
    setToken(newToken);
    setTokenState(newToken);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(logout);
  }, [logout]);

  // Автовыход в момент истечения JWT (JWT_EXPIRE_MINUTES на бэке)
  useEffect(() => {
    const exp = token ? getTokenExpiry(token) : null;
    if (exp === null) return undefined;
    const id = window.setTimeout(logout, Math.max(0, exp - Date.now()));
    return () => window.clearTimeout(id);
  }, [token, logout]);

  return (
    <AuthContext.Provider value={{ token, login, logout }}>{children}</AuthContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
