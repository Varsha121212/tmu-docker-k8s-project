import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { getMe, login as loginRequest } from "../features/identity/api";
import type { UserProfile } from "../types/identity";

interface AuthContextValue {
  token: string | null;
  user: UserProfile | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

// Token lives in memory only (no localStorage/sessionStorage): the SDD defines a
// single short-lived access token with no refresh endpoint, so the safer tradeoff
// is "logged out on page refresh" over "token persists where XSS could read it".
const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(null);
  const [user, setUser] = useState<UserProfile | null>(null);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token: accessToken } = await loginRequest(email, password);
    const profile = await getMe(accessToken);
    setToken(accessToken);
    setUser(profile);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo(() => ({ token, user, login, logout }), [token, user, login, logout]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
