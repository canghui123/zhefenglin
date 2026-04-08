"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useRouter, usePathname } from "next/navigation";
import {
  fetchCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  type CurrentUser,
} from "@/lib/auth";

interface SessionState {
  user: CurrentUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
}

const SessionContext = createContext<SessionState | null>(null);

const PUBLIC_PATHS = new Set(["/login"]);

export function SessionProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const pathname = usePathname();

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const me = await fetchCurrentUser();
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Redirect anonymous users to /login on protected routes.
  useEffect(() => {
    if (loading) return;
    const isPublic = PUBLIC_PATHS.has(pathname);
    if (!user && !isPublic) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [user, loading, pathname, router]);

  const login = useCallback(
    async (email: string, password: string) => {
      const next = await loginRequest(email, password);
      setUser(next);
    },
    [],
  );

  const logout = useCallback(async () => {
    await logoutRequest();
    setUser(null);
    router.replace("/login");
  }, [router]);

  const value = useMemo(
    () => ({ user, loading, login, logout, refresh }),
    [user, loading, login, logout, refresh],
  );

  return (
    <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
  );
}

export function useSession(): SessionState {
  const ctx = useContext(SessionContext);
  if (!ctx) {
    throw new Error("useSession must be used inside <SessionProvider>");
  }
  return ctx;
}
