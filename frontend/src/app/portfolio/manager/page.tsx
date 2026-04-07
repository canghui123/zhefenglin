"use client";

import { useEffect, useState } from "react";
import { getManagerPlaybook, type ManagerData } from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export default function ManagerPage() {
  const [data, setData] = useState<ManagerData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getManagerPlaybook()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-20 text-gray-500">加载中...</div>;
  if (!data) return <div className="text-center py-20 text-red-500">加载失败</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">经理作战手册</h1>
        <p className="text-sm text-gray-500 mt-1">本月KPI、打法、资源与作战节奏</p>
      </div>

      {/* KPI建议 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">本月KPI建议</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {data.kpis.map((kpi) => (
            <div key={kpi.name} className="border rounded-lg p-4">
              <div className="text-sm font-semibold text-gray-900 mb-2">{kpi.name}</div>
              <div className="space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-gray-500">推荐值</span>
                  <span className="font-bold text-blue-600">
                    {kpi.unit === "%"
                      ? `${(kpi.recommended_value * 100).toFixed(1)}%`
                      : typeof kpi.recommended_value === "number" && kpi.recommended_value > 100
                        ? `¥${fmt(kpi.recommended_value)}`
                        : kpi.recommended_value}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">历史均值</span>
                  <span>
                    {kpi.unit === "%"
                      ? `${(kpi.historical_avg * 100).toFixed(1)}%`
                      : typeof kpi.historical_avg === "number" && kpi.historical_avg > 100
                        ? `¥${fmt(kpi.historical_avg)}`
                        : kpi.historical_avg}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">产能可达</span>
                  <span className="text-emerald-600">
                    {kpi.unit === "%"
                      ? `${(kpi.achievable_value * 100).toFixed(1)}%`
                      : typeof kpi.achievable_value === "number" && kpi.achievable_value > 100
                        ? `¥${fmt(kpi.achievable_value)}`
                        : kpi.achievable_value}
                  </span>
                </div>
                <div className="p-2 bg-yellow-50 rounded text-yellow-700 mt-1">
                  {kpi.risk_note}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 分层打法建议 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">分层打法建议</h3>
        <div className="space-y-3">
          {data.recommendations.map((rec, i) => (
            <div key={i} className="p-4 border rounded-lg hover:bg-gray-50">
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                  rec.priority === 1 ? "bg-red-100 text-red-700" :
                  rec.priority === 2 ? "bg-yellow-100 text-yellow-700" : "bg-gray-100 text-gray-600"
                }`}>
                  P{rec.priority}
                </span>
                <span className="font-semibold text-sm">{rec.recommendation_title}</span>
              </div>
              <p className="text-sm text-gray-600">{rec.recommendation_text}</p>
              {rec.expected_impact && Object.keys(rec.expected_impact).length > 0 && (
                <div className="mt-1 text-xs text-blue-600">
                  预期影响: {Object.values(rec.expected_impact).join(", ")}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* 周作战节奏 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">周作战节奏</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {data.weekly_rhythm.map((w) => (
            <div key={w.week} className="border rounded-lg p-4">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-7 h-7 bg-blue-100 text-blue-700 rounded-full flex items-center justify-center text-sm font-bold">
                  {w.week}
                </span>
                <span className="text-sm font-semibold text-gray-900">{w.focus}</span>
              </div>
              <ul className="space-y-1">
                {w.actions.map((a, i) => (
                  <li key={i} className="text-xs text-gray-600 flex gap-1">
                    <span className="text-gray-400">-</span> {a}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
