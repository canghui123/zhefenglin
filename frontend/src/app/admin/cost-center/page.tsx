"use client";

import { useEffect, useState } from "react";

import { AdminAccess } from "@/components/admin/admin-access";
import { useSession } from "@/components/auth/session-provider";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ApiError,
  exportCostCenterCsv,
  getCostCenterOverview,
  getCostCenterTenants,
  getValueDashboard,
  type CostCenterOverview,
  type CostCenterTenantRow,
  type ValueDashboardData,
} from "@/lib/api";
import { hasFeature } from "@/lib/auth";

export default function AdminCostCenterPage() {
  return (
    <AdminAccess
      minRole="manager"
      featureKey="dashboard.advanced"
      featureFallback="当前套餐未开通高级成本驾驶舱"
    >
      <AdminCostCenterContent />
    </AdminAccess>
  );
}

function AdminCostCenterContent() {
  const { user } = useSession();
  const [overview, setOverview] = useState<CostCenterOverview | null>(null);
  const [tenants, setTenants] = useState<CostCenterTenantRow[]>([]);
  const [valueDashboard, setValueDashboard] = useState<ValueDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [pageError, setPageError] = useState<string | null>(null);
  const [valueDashboardError, setValueDashboardError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportLocked, setExportLocked] = useState(false);
  const exportAllowed = hasFeature(user, "audit.export");

  useEffect(() => {
    (async () => {
      setLoading(true);
      setPageError(null);
      setValueDashboardError(null);
      try {
        const [overviewResult, tenantResult, valueDashboardResult] = await Promise.allSettled([
          getCostCenterOverview(),
          getCostCenterTenants(),
          getValueDashboard(),
        ]);

        if (overviewResult.status === "fulfilled") {
          setOverview(overviewResult.value);
        } else {
          setOverview(null);
          setPageError(
            overviewResult.reason instanceof Error
              ? overviewResult.reason.message
              : "成本总览加载失败",
          );
        }

        if (tenantResult.status === "fulfilled") {
          setTenants(tenantResult.value);
        } else {
          setTenants([]);
          setPageError((prev) => prev || "租户成本明细加载失败");
        }

        if (valueDashboardResult.status === "fulfilled") {
          setValueDashboard(valueDashboardResult.value);
        } else {
          setValueDashboard(null);
          setValueDashboardError(
            valueDashboardResult.reason instanceof Error
              ? valueDashboardResult.reason.message
              : "价值看板暂不可用",
          );
        }
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleExport() {
    setExportError(null);
    try {
      const csv = await exportCostCenterCsv();
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "cost-center.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      const message = err instanceof Error ? err.message : "导出失败";
      setExportError(message);
      if (err instanceof ApiError && err.code === "FEATURE_NOT_ENABLED") {
        setExportLocked(true);
      }
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">成本中心</h1>
          <p className="text-sm text-gray-500 mt-1">按租户、模块、成本口径查看本月使用与毛利情况。</p>
        </div>
        <Button onClick={handleExport} variant="outline" disabled={exportLocked || !exportAllowed}>
          {exportLocked || !exportAllowed ? "导出未开通" : "导出 CSV"}
        </Button>
      </div>

      {pageError && (
        <Alert variant="destructive">
          <AlertDescription>{pageError}</AlertDescription>
        </Alert>
      )}

      {exportError && (
        <Alert>
          <AlertDescription>{exportError}</AlertDescription>
        </Alert>
      )}

      {!exportAllowed && (
        <Alert>
          <AlertDescription>当前套餐未开通审计导出能力，如需导出 CSV，请升级到支持 `audit.export` 的套餐。</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <MetricCard title="VIN 调用量" value={overview?.totals.vin_calls} />
        <MetricCard title="高级车况点数" value={overview?.totals.condition_pricing_calls} />
        <MetricCard title="本月总成本" value={overview ? `¥${overview.totals.total_cost.toFixed(1)}` : "-"} />
        <MetricCard title="估算毛利" value={overview ? `¥${overview.totals.estimated_gross_profit.toFixed(1)}` : "-"} />
      </div>

      {valueDashboardError && (
        <Alert>
          <AlertDescription>{valueDashboardError}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <MetricCard title="已节省工时" value={valueDashboard ? `${valueDashboard.estimated_hours_saved}h` : "-"} />
        <MetricCard title="高风险车辆数" value={valueDashboard?.high_risk_vehicles} />
        <MetricCard title="拦截高成本调用" value={valueDashboard?.blocked_high_cost_calls} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>模块成本分布</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-gray-500">加载中...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="pb-3 font-medium">模块</th>
                    <th className="pb-3 font-medium">事件数</th>
                    <th className="pb-3 font-medium">数量</th>
                    <th className="pb-3 font-medium">内部成本</th>
                  </tr>
                </thead>
                <tbody>
                  {overview?.modules.map((module) => (
                    <tr key={module.module} className="border-b last:border-0">
                      <td className="py-3">{module.module}</td>
                      <td className="py-3">{module.events}</td>
                      <td className="py-3">{module.quantity}</td>
                      <td className="py-3">¥{module.cost.toFixed(1)}</td>
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
          <CardTitle>租户成本明细</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-gray-500">加载中...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="pb-3 font-medium">租户</th>
                    <th className="pb-3 font-medium">套餐</th>
                    <th className="pb-3 font-medium">VIN</th>
                    <th className="pb-3 font-medium">车况点数</th>
                    <th className="pb-3 font-medium">总成本</th>
                    <th className="pb-3 font-medium">收入</th>
                    <th className="pb-3 font-medium">毛利</th>
                  </tr>
                </thead>
                <tbody>
                  {tenants.map((tenant) => (
                    <tr key={tenant.tenant_id} className="border-b last:border-0">
                      <td className="py-3">
                        <div className="font-medium">{tenant.tenant_name}</div>
                        <div className="text-xs text-gray-500">{tenant.tenant_code}</div>
                      </td>
                      <td className="py-3">{tenant.plan_name || "-"}</td>
                      <td className="py-3">{tenant.vin_calls}</td>
                      <td className="py-3">{tenant.condition_pricing_calls}</td>
                      <td className="py-3">¥{tenant.total_cost.toFixed(1)}</td>
                      <td className="py-3">¥{tenant.estimated_revenue.toFixed(1)}</td>
                      <td className="py-3">¥{tenant.estimated_gross_profit.toFixed(1)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function MetricCard({ title, value }: { title: string; value: string | number | undefined | null }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm text-gray-500">{title}</CardTitle>
      </CardHeader>
      <CardContent className="text-3xl font-semibold">{value ?? "-"}</CardContent>
    </Card>
  );
}
