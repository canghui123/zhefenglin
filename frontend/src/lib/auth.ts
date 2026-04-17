import { API_BASE, ApiError } from "./api";

export type Role = "admin" | "manager" | "operator" | "viewer";

export interface CurrentUser {
  id: number;
  email: string;
  display_name: string | null;
  role: Role;
  last_login_at: string | null;
  feature_capabilities?: Record<string, boolean>;
}

const ROLE_RANK: Record<Role, number> = {
  admin: 40,
  manager: 30,
  operator: 20,
  viewer: 10,
};

export function hasRole(user: CurrentUser | null, required: Role): boolean {
  if (!user) return false;
  return ROLE_RANK[user.role] >= ROLE_RANK[required];
}

export function hasFeature(user: CurrentUser | null, featureKey: string): boolean {
  if (!user) return false;
  return user.feature_capabilities?.[featureKey] ?? true;
}

export async function login(email: string, password: string): Promise<CurrentUser> {
  const res = await fetch(`${API_BASE}/api/auth/login`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "登录失败" }));
    throw new ApiError(body.detail || "登录失败", res.status);
  }
  const data = await res.json();
  return data.user as CurrentUser;
}

export async function register(email: string, password: string, displayName?: string): Promise<CurrentUser> {
  const res = await fetch(`${API_BASE}/api/auth/register`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, display_name: displayName }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: "注册失败" }));
    throw new ApiError(body.detail || "注册失败", res.status);
  }
  const data = await res.json();
  return data.user as CurrentUser;
}

export async function logout(): Promise<void> {
  await fetch(`${API_BASE}/api/auth/logout`, {
    method: "POST",
    credentials: "include",
  });
}

export async function fetchCurrentUser(): Promise<CurrentUser | null> {
  const res = await fetch(`${API_BASE}/api/auth/me`, {
    credentials: "include",
  });
  if (res.status === 401) return null;
  if (!res.ok) throw new ApiError("无法获取当前用户", res.status);
  return (await res.json()) as CurrentUser;
}
