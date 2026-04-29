"use client";

import { useEffect, useState } from "react";
import { getPortfolioOverview, type PortfolioOverviewData } from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
function pct(n: number) {
  return (n * 100).toFixed(2) + "%";
}

export default function PortfolioOverviewPage() {
  const [data, setData] = useState<PortfolioOverviewData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getPortfolioOverview()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-20 text-gray-500">加载中...</div>;
  if (!data) return <div className="text-center py-20 text-red-500">加载失败</div>;

  const judgmentColor = data.total_expected_loss_rate > 0.5
    ? "bg-red-50 border-red-200 text-red-800"
    : data.total_expected_loss_rate > 0.35
    ? "bg-yellow-50 border-yellow-200 text-yellow-800"
    : "bg-green-50 border-green-200 text-green-800";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">组合总览</h1>
        <p className="text-sm text-gray-500 mt-1">
          快照日期: {data.snapshot_date} | 公司级不良资产组合经营概览
        </p>
        <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600 shadow-sm">
          <span className="font-medium text-slate-900">数据来源</span>
          <span>
            {data.data_source === "customer_import" ? "客户导入表格" : "演示数据"}
            {data.source_batch_id ? ` #${data.source_batch_id}` : ""}
            {data.source_filename ? ` · ${data.source_filename}` : ""}
          </span>
        </div>
      </div>

      {/* 经营判断 */}
      <div className={`p-4 rounded-xl border ${judgmentColor}`}>
        <div className="font-semibold mb-1">本月经营判断</div>
        <div className="text-sm">{data.monthly_judgment}</div>
      </div>

      {/* KPI卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4">
        {[
          { label: "存量不良余额", value: `¥${fmt(data.total_ead)}`, sub: `${data.total_asset_count}笔` },
          { label: "预计总损失", value: `¥${fmt(data.total_expected_loss)}`, sub: `损失率 ${pct(data.total_expected_loss_rate)}` },
          { label: "30天现金回流", value: `¥${fmt(data.cash_30d)}` },
          { label: "90天现金回流", value: `¥${fmt(data.cash_90d)}` },
          { label: "已收车率", value: pct(data.recovered_rate), sub: `入库率 ${pct(data.in_inventory_rate)}` },
          { label: "平均库存天数", value: `${data.avg_inventory_days}天` },
          { label: "高风险分层", value: `${data.high_risk_segment_count}个` },
          { label: "拨备压力", value: `¥${fmt(data.provision_impact)}` },
          { label: "资本释放评分", value: `${data.capital_release_score}分` },
          { label: "180天现金回流", value: `¥${fmt(data.cash_180d)}` },
        ].map((card) => (
          <div key={card.label} className="bg-white rounded-xl border border-gray-200 p-4">
            <div className="text-xs text-gray-500 mb-1">{card.label}</div>
            <div className="text-lg font-bold text-gray-900">{card.value}</div>
            {card.sub && <div className="text-xs text-gray-400 mt-0.5">{card.sub}</div>}
          </div>
        ))}
      </div>

      {/* 图表区 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* 逾期分段分布 */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">逾期分段余额分布</h3>
          <div className="space-y-2">
            {data.charts.overdue_distribution.map((item) => {
              const ratio = item.ead / data.total_ead;
              return (
                <div key={item.bucket}>
                  <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                    <span>{item.bucket}</span>
                    <span>¥{fmt(item.ead)} ({pct(ratio)})</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full">
                    <div
                      className="h-full bg-blue-500 rounded-full"
                      style={{ width: `${Math.min(ratio * 100, 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 资产状态分布 */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">资产状态分布</h3>
          <div className="space-y-2">
            {data.charts.status_distribution.map((item) => {
              const ratio = item.ead / data.total_ead;
              const colors: Record<string, string> = {
                "未收回": "bg-red-400",
                "已收回未入库": "bg-yellow-400",
                "已入库": "bg-green-400",
              };
              return (
                <div key={item.status}>
                  <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                    <span>{item.status}</span>
                    <span>¥{fmt(item.ead)} ({pct(ratio)})</span>
                  </div>
                  <div className="h-2 bg-gray-100 rounded-full">
                    <div
                      className={`h-full rounded-full ${colors[item.status] || "bg-blue-400"}`}
                      style={{ width: `${Math.min(ratio * 100, 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* 现金回流趋势 */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-700 mb-3">现金回流趋势</h3>
          <div className="space-y-3">
            {data.charts.cashflow_trend.map((item) => {
              const ratio = item.amount / data.total_ead;
              return (
                <div key={item.period}>
                  <div className="flex justify-between text-xs text-gray-600 mb-0.5">
                    <span>{item.period}</span>
                    <span>¥{fmt(item.amount)}</span>
                  </div>
                  <div className="h-3 bg-gray-100 rounded-full">
                    <div
                      className="h-full bg-emerald-500 rounded-full"
                      style={{ width: `${Math.min(ratio * 100, 100)}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* 风险与行动 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-red-600 mb-2">三大风险点</h3>
          <ul className="space-y-2">
            {data.top_risks.map((r, i) => (
              <li key={i} className="text-sm text-gray-700 flex gap-2">
                <span className="text-red-400 font-bold">{i + 1}.</span> {r}
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-blue-600 mb-2">三大优先动作</h3>
          <ul className="space-y-2">
            {data.top_actions.map((a, i) => (
              <li key={i} className="text-sm text-gray-700 flex gap-2">
                <span className="text-blue-400 font-bold">{i + 1}.</span> {a}
              </li>
            ))}
          </ul>
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-purple-600 mb-2">资源配置建议</h3>
          <ul className="space-y-2">
            {data.resource_suggestions.map((s, i) => (
              <li key={i} className="text-sm text-gray-700 flex gap-2">
                <span className="text-purple-400">-</span> {s}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
