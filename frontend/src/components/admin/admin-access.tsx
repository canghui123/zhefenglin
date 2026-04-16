"use client";

import { ReactNode } from "react";

import { useSession } from "@/components/auth/session-provider";

const ROLE_RANK: Record<string, number> = {
  viewer: 10,
  operator: 20,
  manager: 30,
  admin: 40,
};

export function AdminAccess({
  children,
  minRole = "manager",
}: {
  children: ReactNode;
  minRole?: "manager" | "admin";
}) {
  const { user, loading } = useSession();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh] text-sm text-gray-500">
        加载权限中...
      </div>
    );
  }

  if (!user || (ROLE_RANK[user.role] || 0) < ROLE_RANK[minRole]) {
    return (
      <div className="flex items-center justify-center min-h-[40vh] text-sm text-gray-500">
        {minRole === "admin" ? "仅管理员可访问此页面" : "仅经理及以上角色可访问此页面"}
      </div>
    );
  }

  return <>{children}</>;
}
