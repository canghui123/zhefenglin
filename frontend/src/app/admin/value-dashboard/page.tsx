"use client";

import { useEffect, useState } from "react";

import { AdminAccess } from "@/components/admin/admin-access";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getValueDashboard, type ValueDashboardData } from "@/lib/api";

const metricMeta = [
  { label: "本月节省人工工时", suffix: "h", getValue: (data: ValueDashboardData) => data.estimated_hours_saved },
  { label: "识别高风险车辆数", suffix: "台", getValue: (data: ValueDashboardData) => data.high_risk_vehicles },
  { label: "预计避免损失", suffix: "元", getValue: (data: ValueDashboardData) => data.avoided_loss_amount },
  { label: "提前现金回流", suffix: "元", getValue: (data: ValueDashboardData) => data.accelerated_cash_in },
  { label: "任务完成率", suffix: "%", getValue: (data: ValueDashboardData) => data.task_completion_rate },
];

export default function AdminValueDashboardPage() {
  return (
    <AdminAccess
      minRole="manager"
      featureKey="tenant.value_dashboard"
      featureFallback="当前套餐未开通租户价值看板或已被管理员关闭"
    >
      <AdminValueDashboardContent />
    </AdminAccess>
  );
}

function AdminValueDashboardContent() {
  const [data, setData] = useState<ValueDashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await getValueDashboard();
        setData(result);
      } catch (err) {
        setData(null);
        setError(err instanceof Error ? err.message : "价值看板加载失败");
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">租户价值看板</h1>
        <p className="text-sm text-gray-500 mt-1">用于销售演示和续费沟通的价值指标总览。</p>
      </div>

      {error && (
        <Alert>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-5 gap-4">
        {metricMeta.map((metric) => (
          <Card key={metric.label}>
            <CardHeader>
              <CardTitle className="text-sm text-gray-500">{metric.label}</CardTitle>
            </CardHeader>
            <CardContent className="text-3xl font-semibold">
              {loading ? "-" : data ? `${metric.getValue(data)}${metric.suffix}` : "-"}
            </CardContent>
          </Card>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>客户汇报摘要</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm text-gray-600">
          <p className="rounded-lg bg-slate-50 p-4 text-gray-800">{data?.customer_summary || "暂无摘要"}</p>
          <p>工时节省：根据本月 VIN 估值、AI 报告和沙盘调用量按经验系数估算。</p>
          <p>价值指标：结合 usage events、任务闭环、资产包报告和沙盘结果，生成可追溯的续费证明口径。</p>
          <p>源数据：{data ? Object.entries(data.source_trace).map(([k, v]) => `${k}:${v}`).join(" / ") : "-"}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>按租户价值明细</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-gray-500">
                  <th className="pb-3 font-medium">租户</th>
                  <th className="pb-3 font-medium">任务数</th>
                  <th className="pb-3 font-medium">完成数</th>
                  <th className="pb-3 font-medium">预计回款</th>
                  <th className="pb-3 font-medium">实际回款</th>
                  <th className="pb-3 font-medium">增量回收</th>
                </tr>
              </thead>
              <tbody>
                {(data?.tenant_value_rows || []).map((row) => (
                  <tr key={row.tenant_id} className="border-b last:border-0">
                    <td className="py-3">
                      <div className="font-medium">{row.tenant_name}</div>
                      <div className="text-xs text-gray-500">{row.tenant_code}</div>
                    </td>
                    <td className="py-3">{row.task_count}</td>
                    <td className="py-3">{row.completed_task_count}</td>
                    <td className="py-3">¥{row.expected_recovery.toLocaleString("zh-CN")}</td>
                    <td className="py-3">¥{row.actual_recovery.toLocaleString("zh-CN")}</td>
                    <td className="py-3">¥{row.estimated_extra_recovery.toLocaleString("zh-CN")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
