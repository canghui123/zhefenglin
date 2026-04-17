"use client";

import { useEffect, useState } from "react";
import { AccessGate } from "@/components/auth/access-gate";
import { getExecutiveDashboard, type ExecutiveData } from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
function pct(n: number) {
  return (n * 100).toFixed(2) + "%";
}

export default function ExecutivePage() {
  return (
    <AccessGate
      minRole="manager"
      featureKey="portfolio.advanced_pages"
      featureFallback="当前套餐未开通高阶经营页"
    >
      <ExecutiveContent />
    </AccessGate>
  );
}

function ExecutiveContent() {
  const [data, setData] = useState<ExecutiveData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getExecutiveDashboard()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-20 text-gray-500">加载中...</div>;
  if (!data) return <div className="text-center py-20 text-red-500">加载失败</div>;

  const ov = data.overview;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">高管驾驶页</h1>
        <p className="text-sm text-gray-500 mt-1">整体经营判断、取舍与资源配置</p>
      </div>

      {/* 经营摘要 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "预计损失额", value: `¥${fmt(ov.total_expected_loss)}`, color: "text-red-600" },
          { label: "损失率", value: pct(ov.total_expected_loss_rate), color: ov.total_expected_loss_rate > 0.5 ? "text-red-600" : "text-yellow-600" },
          { label: "90天现金回流", value: `¥${fmt(ov.cash_90d)}`, color: "text-emerald-600" },
          { label: "资本释放评分", value: `${ov.capital_release_score}`, color: "text-blue-600" },
          { label: "已收车率", value: pct(ov.recovered_rate) },
          { label: "平均库存天数", value: `${ov.avg_inventory_days}天` },
          { label: "高风险分层", value: `${ov.high_risk_segment_count}个`, color: "text-red-500" },
          { label: "拨备压力", value: `¥${fmt(ov.provision_impact)}` },
        ].map((c) => (
          <div key={c.label} className="bg-white rounded-xl border p-4">
            <div className="text-xs text-gray-500">{c.label}</div>
            <div className={`text-xl font-bold ${c.color || "text-gray-900"}`}>{c.value}</div>
          </div>
        ))}
      </div>

      {/* AI建议 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">AI经营建议</h3>
        <div className="space-y-3">
          {data.recommendations.map((rec, i) => (
            <div
              key={i}
              className={`p-4 rounded-lg border ${
                rec.priority === 1
                  ? "border-red-200 bg-red-50"
                  : rec.priority === 2
                  ? "border-yellow-200 bg-yellow-50"
                  : "border-gray-200 bg-gray-50"
              }`}
            >
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${
                  rec.priority === 1 ? "bg-red-200 text-red-800" :
                  rec.priority === 2 ? "bg-yellow-200 text-yellow-800" : "bg-gray-200 text-gray-700"
                }`}>
                  P{rec.priority}
                </span>
                <span className="font-semibold text-sm text-gray-900">{rec.recommendation_title}</span>
                {rec.approval_needed && (
                  <span className="text-xs bg-purple-100 text-purple-700 px-1.5 py-0.5 rounded">需审批</span>
                )}
              </div>
              <p className="text-sm text-gray-700">{rec.recommendation_text}</p>
              <div className="flex gap-4 mt-2 text-xs text-gray-500">
                <span>可行性: {(rec.feasibility_score * 100).toFixed(0)}%</span>
                <span>现实性: {(rec.realism_score * 100).toFixed(0)}%</span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 亏损贡献排行 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">亏损贡献排行 (Top 10)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-3 py-2">分层</th>
                <th className="text-right px-3 py-2">损失额</th>
                <th className="text-right px-3 py-2">损失率</th>
                <th className="text-right px-3 py-2">贡献占比</th>
                <th className="text-right px-3 py-2">30天回流</th>
              </tr>
            </thead>
            <tbody>
              {data.loss_contribution_by_segment.map((seg) => (
                <tr key={seg.segment_name} className="border-t hover:bg-gray-50">
                  <td className="px-3 py-2 text-xs font-medium">{seg.segment_name}</td>
                  <td className="text-right px-3 py-2 text-red-600">¥{fmt(seg.loss_amount)}</td>
                  <td className="text-right px-3 py-2">{pct(seg.loss_rate)}</td>
                  <td className="text-right px-3 py-2">
                    <div className="flex items-center justify-end gap-2">
                      <div className="w-12 h-1.5 bg-gray-100 rounded-full">
                        <div className="h-full bg-red-400 rounded-full" style={{ width: `${Math.min(seg.contribution_pct, 100)}%` }} />
                      </div>
                      <span className="text-xs">{seg.contribution_pct.toFixed(1)}%</span>
                    </div>
                  </td>
                  <td className="text-right px-3 py-2 text-emerald-600">¥{fmt(seg.cash_30d)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 资源配置 + 审批 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl border p-5">
          <h3 className="text-sm font-semibold text-purple-600 mb-2">资源配置建议</h3>
          <ul className="space-y-2">
            {data.resource_suggestions.map((s, i) => (
              <li key={i} className="text-sm text-gray-700 flex gap-2">
                <span className="text-purple-400">-</span> {s}
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-white rounded-xl border p-5">
          <h3 className="text-sm font-semibold text-orange-600 mb-2">需审批事项</h3>
          {data.approval_items.length > 0 ? (
            <ul className="space-y-2">
              {data.approval_items.map((item, i) => (
                <li key={i} className="text-sm text-gray-700 flex gap-2">
                  <span className="text-orange-400 font-bold">{i + 1}.</span> {item}
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-gray-400">暂无需审批事项</p>
          )}
        </div>
      </div>
    </div>
  );
}
