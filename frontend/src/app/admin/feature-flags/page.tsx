"use client";

import { useEffect, useMemo, useState } from "react";

import { AdminAccess } from "@/components/admin/admin-access";
import { useSession } from "@/components/auth/session-provider";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  getFeatureFlagsSnapshot,
  updatePlanFeatureFlags,
  updateTenantFeatureFlags,
  type FeatureCatalogItem,
  type FeatureFlagsSnapshot,
  type PlanFeatureRow,
  type TenantFeatureRow,
} from "@/lib/api";

type TenantOverrideMode = "inherit" | "enabled" | "disabled";

function toTenantMode(value: boolean | null | undefined): TenantOverrideMode {
  if (value === true) return "enabled";
  if (value === false) return "disabled";
  return "inherit";
}

function fromTenantMode(value: TenantOverrideMode): boolean | null {
  if (value === "enabled") return true;
  if (value === "disabled") return false;
  return null;
}

function renderStatus(enabled: boolean) {
  return enabled ? (
    <Badge className="bg-emerald-100 text-emerald-700 hover:bg-emerald-100">已开启</Badge>
  ) : (
    <Badge variant="outline">未开启</Badge>
  );
}

export default function AdminFeatureFlagsPage() {
  return (
    <AdminAccess minRole="manager">
      <AdminFeatureFlagsContent />
    </AdminAccess>
  );
}

function AdminFeatureFlagsContent() {
  const { user } = useSession();
  const canEdit = user?.role === "admin";

  const [snapshot, setSnapshot] = useState<FeatureFlagsSnapshot | null>(null);
  const [planDrafts, setPlanDrafts] = useState<Record<string, Record<string, boolean>>>({});
  const [tenantDrafts, setTenantDrafts] = useState<Record<number, Record<string, TenantOverrideMode>>>({});
  const [selectedPlanCode, setSelectedPlanCode] = useState("");
  const [selectedTenantId, setSelectedTenantId] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingPlan, setSavingPlan] = useState(false);
  const [savingTenant, setSavingTenant] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const data = await getFeatureFlagsSnapshot();
      setSnapshot(data);
      setPlanDrafts(
        Object.fromEntries(
          data.plans.map((plan) => [plan.plan_code, { ...plan.features }]),
        ),
      );
      setTenantDrafts(
        Object.fromEntries(
          data.tenants.map((tenant) => [
            tenant.tenant_id,
            Object.fromEntries(
              data.catalog.map((feature) => [
                feature.key,
                toTenantMode(tenant.overrides[feature.key]),
              ]),
            ),
          ]),
        ),
      );
      setSelectedPlanCode((current) => current || data.plans[0]?.plan_code || "");
      setSelectedTenantId((current) => current || String(data.tenants[0]?.tenant_id || ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载功能开关失败");
      setSnapshot(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const selectedPlan = useMemo(
    () => snapshot?.plans.find((plan) => plan.plan_code === selectedPlanCode) || null,
    [snapshot, selectedPlanCode],
  );
  const selectedPlanDraft = selectedPlan ? planDrafts[selectedPlan.plan_code] : null;

  const selectedTenant = useMemo(
    () =>
      snapshot?.tenants.find((tenant) => String(tenant.tenant_id) === selectedTenantId) || null,
    [snapshot, selectedTenantId],
  );
  const selectedTenantDraft = selectedTenant ? tenantDrafts[selectedTenant.tenant_id] : null;
  const inheritedPlan = useMemo(
    () =>
      selectedTenant && snapshot
        ? snapshot.plans.find((plan) => plan.plan_code === selectedTenant.plan_code) || null
        : null,
    [selectedTenant, snapshot],
  );

  async function handleSavePlan() {
    if (!selectedPlan || !selectedPlanDraft) return;
    setSavingPlan(true);
    try {
      await updatePlanFeatureFlags(selectedPlan.plan_code, selectedPlanDraft);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "保存套餐默认能力失败");
    } finally {
      setSavingPlan(false);
    }
  }

  async function handleSaveTenant() {
    if (!selectedTenant || !selectedTenantDraft) return;
    setSavingTenant(true);
    try {
      const payload = Object.fromEntries(
        Object.entries(selectedTenantDraft).map(([key, value]) => [key, fromTenantMode(value)]),
      );
      await updateTenantFeatureFlags(selectedTenant.tenant_id, payload);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "保存租户覆盖失败");
    } finally {
      setSavingTenant(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">功能开关</h1>
        <p className="text-sm text-gray-500 mt-1">
          统一管理套餐默认能力与租户级覆盖策略，让能力开放、收紧和回退都可追踪。
        </p>
      </div>

      {error && (
        <Alert>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>功能目录</CardTitle>
        </CardHeader>
        <CardContent>
          {loading || !snapshot ? (
            <p className="text-sm text-gray-500">加载中...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="pb-3 font-medium">能力</th>
                    <th className="pb-3 font-medium">分类</th>
                    <th className="pb-3 font-medium">说明</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.catalog.map((feature) => (
                    <tr key={feature.key} className="border-b last:border-0 align-top">
                      <td className="py-3">
                        <div className="font-medium">{feature.label}</div>
                        <div className="text-xs text-gray-500">{feature.key}</div>
                      </td>
                      <td className="py-3">
                        <Badge variant="outline">{feature.category}</Badge>
                      </td>
                      <td className="py-3 text-gray-600">{feature.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>套餐默认能力</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading || !snapshot ? (
            <p className="text-sm text-gray-500">加载中...</p>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-[300px_1fr]">
                <div className="space-y-2">
                  <div className="text-sm font-medium text-gray-700">选择套餐</div>
                  <Select
                    value={selectedPlanCode}
                    onValueChange={(value) => setSelectedPlanCode(value || "")}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="选择套餐" />
                    </SelectTrigger>
                    <SelectContent>
                      {snapshot.plans.map((plan) => (
                        <SelectItem key={plan.plan_code} value={plan.plan_code}>
                          {plan.plan_name}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {selectedPlan && (
                  <div className="grid grid-cols-1 gap-3 rounded-xl border bg-slate-50 p-4 md:grid-cols-4">
                    <MetricBox label="套餐名称" value={selectedPlan.plan_name} />
                    <MetricBox label="套餐编码" value={selectedPlan.plan_code} />
                    <MetricBox
                      label="私有化配置"
                      value={
                        selectedPlanDraft?.["deployment.private_config"] ? "已纳入套餐" : "未纳入套餐"
                      }
                    />
                    <MetricBox label="当前权限" value={canEdit ? "管理员可编辑" : "仅查看"} />
                  </div>
                )}
              </div>

              {selectedPlan && selectedPlanDraft && (
                <FeaturePlanTable
                  catalog={snapshot.catalog}
                  plan={selectedPlan}
                  draft={selectedPlanDraft}
                  canEdit={canEdit}
                  onChange={(featureKey, enabled) =>
                    setPlanDrafts((prev) => ({
                      ...prev,
                      [selectedPlan.plan_code]: {
                        ...prev[selectedPlan.plan_code],
                        [featureKey]: enabled,
                      },
                    }))
                  }
                />
              )}

              {canEdit && (
                <div className="flex justify-end">
                  <Button onClick={handleSavePlan} disabled={!selectedPlan || savingPlan}>
                    {savingPlan ? "保存中..." : "保存套餐默认能力"}
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>租户覆盖策略</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading || !snapshot ? (
            <p className="text-sm text-gray-500">加载中...</p>
          ) : snapshot.tenants.length === 0 ? (
            <p className="text-sm text-gray-500">暂无有效订阅租户。</p>
          ) : (
            <>
              <div className="grid gap-4 md:grid-cols-[320px_1fr]">
                <div className="space-y-2">
                  <div className="text-sm font-medium text-gray-700">选择租户</div>
                  <Select
                    value={selectedTenantId}
                    onValueChange={(value) => setSelectedTenantId(value || "")}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue placeholder="选择租户" />
                    </SelectTrigger>
                    <SelectContent>
                      {snapshot.tenants.map((tenant) => (
                        <SelectItem key={tenant.tenant_id} value={String(tenant.tenant_id)}>
                          {tenant.tenant_name || tenant.tenant_code || `租户 ${tenant.tenant_id}`}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                {selectedTenant && (
                  <div className="grid grid-cols-1 gap-3 rounded-xl border bg-slate-50 p-4 md:grid-cols-4">
                    <MetricBox
                      label="租户"
                      value={
                        selectedTenant.tenant_name ||
                        selectedTenant.tenant_code ||
                        `租户 ${selectedTenant.tenant_id}`
                      }
                    />
                    <MetricBox
                      label="当前套餐"
                      value={selectedTenant.plan_name || selectedTenant.plan_code || "-"}
                    />
                    <MetricBox
                      label="私有化配置"
                      value={
                        selectedTenant.effective_features["deployment.private_config"]
                          ? "已生效"
                          : "未生效"
                      }
                    />
                    <MetricBox label="当前权限" value={canEdit ? "管理员可覆盖" : "仅查看"} />
                  </div>
                )}
              </div>

              {selectedTenant && selectedTenantDraft && (
                <FeatureTenantTable
                  catalog={snapshot.catalog}
                  tenant={selectedTenant}
                  inheritedPlan={inheritedPlan}
                  draft={selectedTenantDraft}
                  canEdit={canEdit}
                  onChange={(featureKey, mode) =>
                    setTenantDrafts((prev) => ({
                      ...prev,
                      [selectedTenant.tenant_id]: {
                        ...prev[selectedTenant.tenant_id],
                        [featureKey]: mode,
                      },
                    }))
                  }
                />
              )}

              {canEdit && (
                <div className="flex justify-end">
                  <Button onClick={handleSaveTenant} disabled={!selectedTenant || savingTenant}>
                    {savingTenant ? "保存中..." : "保存租户覆盖"}
                  </Button>
                </div>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function MetricBox({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs text-gray-500">{label}</div>
      <div className="mt-1 font-medium">{value}</div>
    </div>
  );
}

function FeaturePlanTable({
  catalog,
  plan,
  draft,
  canEdit,
  onChange,
}: {
  catalog: FeatureCatalogItem[];
  plan: PlanFeatureRow;
  draft: Record<string, boolean>;
  canEdit: boolean;
  onChange: (featureKey: string, enabled: boolean) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="pb-3 font-medium">能力</th>
            <th className="pb-3 font-medium">当前状态</th>
            <th className="pb-3 font-medium">套餐默认</th>
          </tr>
        </thead>
        <tbody>
          {catalog.map((feature) => (
            <tr key={feature.key} className="border-b last:border-0">
              <td className="py-3">
                <div className="font-medium">{feature.label}</div>
                <div className="text-xs text-gray-500">{feature.key}</div>
              </td>
              <td className="py-3">{renderStatus(Boolean(draft[feature.key]))}</td>
              <td className="py-3">
                {canEdit ? (
                  <Select
                    value={draft[feature.key] ? "enabled" : "disabled"}
                    onValueChange={(value) => onChange(feature.key, value === "enabled")}
                  >
                    <SelectTrigger className="w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="enabled">开启</SelectItem>
                      <SelectItem value="disabled">关闭</SelectItem>
                    </SelectContent>
                  </Select>
                ) : (
                  <span className="text-gray-600">
                    {plan.features[feature.key] ? "套餐默认开启" : "套餐默认关闭"}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function FeatureTenantTable({
  catalog,
  tenant,
  inheritedPlan,
  draft,
  canEdit,
  onChange,
}: {
  catalog: FeatureCatalogItem[];
  tenant: TenantFeatureRow;
  inheritedPlan: PlanFeatureRow | null;
  draft: Record<string, TenantOverrideMode>;
  canEdit: boolean;
  onChange: (featureKey: string, mode: TenantOverrideMode) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left text-gray-500">
            <th className="pb-3 font-medium">能力</th>
            <th className="pb-3 font-medium">套餐生效</th>
            <th className="pb-3 font-medium">租户覆盖</th>
            <th className="pb-3 font-medium">最终状态</th>
          </tr>
        </thead>
        <tbody>
          {catalog.map((feature) => {
            const inheritedValue = Boolean(inheritedPlan?.features[feature.key]);
            const mode = draft[feature.key] || "inherit";
            const effectiveValue =
              mode === "inherit" ? inheritedValue : mode === "enabled";

            return (
              <tr key={feature.key} className="border-b last:border-0">
                <td className="py-3">
                  <div className="font-medium">{feature.label}</div>
                  <div className="text-xs text-gray-500">{feature.key}</div>
                </td>
                <td className="py-3">{renderStatus(inheritedValue)}</td>
                <td className="py-3">
                  {canEdit ? (
                    <Select value={mode} onValueChange={(value) => onChange(feature.key, value as TenantOverrideMode)}>
                      <SelectTrigger className="w-40">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="inherit">继承套餐</SelectItem>
                        <SelectItem value="enabled">强制开启</SelectItem>
                        <SelectItem value="disabled">强制关闭</SelectItem>
                      </SelectContent>
                    </Select>
                  ) : (
                    <span className="text-gray-600">
                      {mode === "inherit"
                        ? "继承套餐"
                        : mode === "enabled"
                          ? "强制开启"
                          : "强制关闭"}
                    </span>
                  )}
                </td>
                <td className="py-3">
                  {renderStatus(mode === "inherit" ? tenant.effective_features[feature.key] : effectiveValue)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
