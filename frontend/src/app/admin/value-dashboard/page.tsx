"use client";

import { useEffect, useState } from "react";

import { AdminAccess } from "@/components/admin/admin-access";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getValueDashboard, type ValueDashboardData } from "@/lib/api";

const metricMeta = [
  { label: "本月节省人工工时", suffix: "h", getValue: (data: ValueDashboardData) => data.estimated_hours_saved },
  { label: "识别高风险车辆数", suffix: "台", getValue: (data: ValueDashboardData) => data.high_risk_vehicles },
  { label: "拦截高成本调用", suffix: "次", getValue: (data: ValueDashboardData) => data.blocked_high_cost_calls },
  { label: "最优路径覆盖率", suffix: "%", getValue: (data: ValueDashboardData) => data.recommended_path_coverage },
  { label: "预计处理车辆数", suffix: "台", getValue: (data: ValueDashboardData) => data.estimated_decisions_processed },
];

export default function AdminValueDashboardPage() {
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
    <AdminAccess minRole="manager">
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
            <CardTitle>指标说明</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-gray-600">
            <p>工时节省：根据本月 VIN 估值、AI 报告和沙盘调用量按经验系数估算。</p>
            <p>高风险车辆：以审批请求和高级车况定价触发次数作为阶段性代理指标。</p>
            <p>覆盖率：以高价值建议动作次数占总处理动作的比例估算，后续可接真实运营埋点替换。</p>
          </CardContent>
        </Card>
      </div>
    </AdminAccess>
  );
}
