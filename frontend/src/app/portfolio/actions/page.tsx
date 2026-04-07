"use client";

import { useEffect, useState } from "react";
import { getActionCenter, type ActionCenterData } from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export default function ActionCenterPage() {
  const [data, setData] = useState<ActionCenterData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getActionCenter()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-20 text-gray-500">加载中...</div>;
  if (!data) return <div className="text-center py-20 text-red-500">加载失败</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">动作中心</h1>
        <p className="text-sm text-gray-500 mt-1">今天具体做什么 — 执行层待办清单</p>
      </div>

      {/* 今日待办 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">今日重点</h3>
        <div className="space-y-3">
          {data.recommendations.map((rec, i) => (
            <div key={i} className="p-4 border rounded-lg flex items-start gap-3">
              <div className={`w-2 h-2 rounded-full mt-2 shrink-0 ${
                rec.priority === 1 ? "bg-red-500" : "bg-yellow-500"
              }`} />
              <div>
                <div className="font-semibold text-sm text-gray-900">{rec.recommendation_title}</div>
                <p className="text-sm text-gray-600 mt-0.5">{rec.recommendation_text}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 竞拍/处置就绪 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-emerald-600 mb-3">竞拍/处置就绪清单</h3>
        {data.auction_ready.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">分层</th>
                  <th className="text-right px-3 py-2">台数</th>
                  <th className="text-right px-3 py-2">预估总值</th>
                  <th className="text-right px-3 py-2">建议底价(单台)</th>
                  <th className="text-left px-3 py-2">风险标签</th>
                </tr>
              </thead>
              <tbody>
                {data.auction_ready.map((item) => (
                  <tr key={item.segment_name} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-2 text-xs font-medium">{item.segment_name}</td>
                    <td className="text-right px-3 py-2">{item.count}台</td>
                    <td className="text-right px-3 py-2 text-emerald-600">¥{fmt(item.estimated_value)}</td>
                    <td className="text-right px-3 py-2">¥{fmt(item.recommended_floor_price)}</td>
                    <td className="px-3 py-2">
                      {item.risk_tags.map((tag) => (
                        <span key={tag} className="text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded mr-1">
                          {tag}
                        </span>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-400">暂无就绪资产</p>
        )}
      </div>

      {/* 收车推进 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-blue-600 mb-3">收车推进清单</h3>
        {data.recovery_tasks.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">分层</th>
                  <th className="text-right px-3 py-2">待收车数</th>
                  <th className="text-left px-3 py-2">逾期分段</th>
                  <th className="text-right px-3 py-2">EAD</th>
                </tr>
              </thead>
              <tbody>
                {data.recovery_tasks.map((item) => (
                  <tr key={item.segment_name} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-2 text-xs font-medium">{item.segment_name}</td>
                    <td className="text-right px-3 py-2 font-semibold">{item.count}台</td>
                    <td className="px-3 py-2 text-xs">{item.overdue_bucket}</td>
                    <td className="text-right px-3 py-2">¥{fmt(item.total_ead)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-400">暂无收车任务</p>
        )}
      </div>
    </div>
  );
}
