"use client";

import { useEffect, useState } from "react";
import { getSupervisorConsole, type SupervisorData } from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export default function SupervisorPage() {
  const [data, setData] = useState<SupervisorData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getSupervisorConsole()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-20 text-gray-500">加载中...</div>;
  if (!data) return <div className="text-center py-20 text-red-500">加载失败</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">主管执行控制台</h1>
        <p className="text-sm text-gray-500 mt-1">本周先做什么、怎么分配、哪些要升级</p>
      </div>

      {/* 本周行动建议 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">本周行动建议</h3>
        <div className="space-y-3">
          {data.recommendations.map((rec, i) => (
            <div key={i} className="p-4 border rounded-lg flex items-start gap-3">
              <span className={`mt-0.5 w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                rec.priority === 1 ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"
              }`}>
                {i + 1}
              </span>
              <div>
                <div className="font-semibold text-sm text-gray-900">{rec.recommendation_title}</div>
                <p className="text-sm text-gray-600 mt-0.5">{rec.recommendation_text}</p>
                <div className="flex gap-3 mt-1 text-xs text-gray-500">
                  <span>可行性: {(rec.feasibility_score * 100).toFixed(0)}%</span>
                  <span>现实性: {(rec.realism_score * 100).toFixed(0)}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 高优先级资产池 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">高优先级资产池</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-3 py-2">分层</th>
                <th className="text-left px-3 py-2">状态</th>
                <th className="text-left px-3 py-2">推荐动作</th>
                <th className="text-center px-3 py-2">紧急度</th>
                <th className="text-right px-3 py-2">损失影响</th>
                <th className="text-right px-3 py-2">现金影响</th>
              </tr>
            </thead>
            <tbody>
              {data.high_priority_pool.map((item) => (
                <tr key={item.segment_name} className="border-t hover:bg-gray-50">
                  <td className="px-3 py-2 text-xs font-medium">{item.segment_name}</td>
                  <td className="px-3 py-2 text-xs">{item.status}</td>
                  <td className="px-3 py-2 text-xs text-blue-600">{item.next_action}</td>
                  <td className="text-center px-3 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                      item.urgency === "高" ? "bg-red-100 text-red-700" : "bg-yellow-100 text-yellow-700"
                    }`}>
                      {item.urgency}
                    </span>
                  </td>
                  <td className="text-right px-3 py-2 text-xs text-red-600">¥{fmt(item.loss_impact)}</td>
                  <td className="text-right px-3 py-2 text-xs text-emerald-600">¥{fmt(item.cash_impact)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
