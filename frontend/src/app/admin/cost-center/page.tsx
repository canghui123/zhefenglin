"use client";

import { useEffect, useState } from "react";

import { AdminAccess } from "@/components/admin/admin-access";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  exportCostCenterCsv,
  getCostCenterOverview,
  getCostCenterTenants,
  getValueDashboard,
  type CostCenterOverview,
  type CostCenterTenantRow,
  type ValueDashboardData,
} from "@/lib/api";

export default function AdminCostCenterPage() {
  const [overview, setOverview] = useState<CostCenterOverview | null>(null);
  const [tenants, setTenants] = useState<CostCenterTenantRow[]>([]);
  const [valueDashboard, setValueDashboard] = useState<ValueDashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [overviewData, tenantRows, valueData] = await Promise.all([
          getCostCenterOverview(),
          getCostCenterTenants(),
          getValueDashboard(),
        ]);
        setOverview(overviewData);
        setTenants(tenantRows);
        setValueDashboard(valueData);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  async function handleExport() {
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
      alert(err instanceof Error ? err.message : "导出失败");
    }
  }

  return (
    <AdminAccess minRole="manager">
      <div className="space-y-6">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold">成本中心</h1>
            <p className="text-sm text-gray-500 mt-1">按租户、模块、成本口径查看本月使用与毛利情况。</p>
          </div>
          <Button onClick={handleExport} variant="outline">导出 CSV</Button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <MetricCard title="VIN 调用量" value={overview?.totals.vin_calls} />
          <MetricCard title="高级车况点数" value={overview?.totals.condition_pricing_calls} />
          <MetricCard title="本月总成本" value={overview ? `¥${overview.totals.total_cost.toFixed(1)}` : "-"} />
          <MetricCard title="估算毛利" value={overview ? `¥${overview.totals.estimated_gross_profit.toFixed(1)}` : "-"} />
        </div>

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
    </AdminAccess>
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
