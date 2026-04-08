"use client";

import type { ReactNode } from "react";
import { hasRole, type Role } from "@/lib/auth";
import { useSession } from "./session-provider";

interface RoleGuardProps {
  required: Role;
  children: ReactNode;
  fallback?: ReactNode;
}

/**
 * Render `children` only when the current user has at least the
 * required role. Defaults to a small "权限不足" notice when blocked.
 */
export function RoleGuard({ required, children, fallback }: RoleGuardProps) {
  const { user, loading } = useSession();
  if (loading) return null;
  if (!hasRole(user, required)) {
    return (
      fallback ?? (
        <div className="rounded-md border border-amber-200 bg-amber-50 p-4 text-sm text-amber-700">
          当前账号无权限查看此页面（需要 {required} 及以上角色）。
        </div>
      )
    );
  }
  return <>{children}</>;
}
