"use client";

import { ReactNode } from "react";

import { useSession } from "@/components/auth/session-provider";
import { hasFeature, hasRole, type Role } from "@/lib/auth";

function defaultRoleMessage(minRole: Role) {
  return minRole === "admin" ? "仅管理员可访问此页面" : "仅经理及以上角色可访问此页面";
}

export function AccessGate({
  children,
  minRole = "viewer",
  featureKey,
  featureFallback,
  roleFallback,
}: {
  children: ReactNode;
  minRole?: Role;
  featureKey?: string;
  featureFallback?: string;
  roleFallback?: string;
}) {
  const { user, loading } = useSession();

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[40vh] text-sm text-gray-500">
        加载权限中...
      </div>
    );
  }

  if (!hasRole(user, minRole)) {
    return (
      <div className="flex items-center justify-center min-h-[40vh] text-sm text-gray-500">
        {roleFallback || defaultRoleMessage(minRole)}
      </div>
    );
  }

  if (featureKey && !hasFeature(user, featureKey)) {
    return (
      <div className="flex items-center justify-center min-h-[40vh] text-sm text-gray-500">
        {featureFallback || "当前套餐未开通该页面"}
      </div>
    );
  }

  return <>{children}</>;
}
