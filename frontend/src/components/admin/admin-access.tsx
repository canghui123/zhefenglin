"use client";

import { ReactNode } from "react";

import { AccessGate } from "@/components/auth/access-gate";

export function AdminAccess({
  children,
  minRole = "manager",
  featureKey,
  featureFallback,
}: {
  children: ReactNode;
  minRole?: "manager" | "admin";
  featureKey?: string;
  featureFallback?: string;
}) {
  return (
    <AccessGate
      minRole={minRole}
      featureKey={featureKey}
      featureFallback={featureFallback}
    >
      {children}
    </AccessGate>
  );
}
