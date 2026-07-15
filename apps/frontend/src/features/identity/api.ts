import { api } from "../../lib/api";
import type { TokenResponse, UserProfile } from "../../types/identity";

export function register(email: string, password: string, displayName: string) {
  return api.post<UserProfile>("/auth/register", {
    email,
    password,
    display_name: displayName,
  });
}

export function login(email: string, password: string) {
  return api.post<TokenResponse>("/auth/login", { email, password });
}

export function getMe(token: string) {
  return api.get<UserProfile>("/auth/me", token);
}
