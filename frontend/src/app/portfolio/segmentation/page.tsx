"use client";

import { useEffect, useState } from "react";
import { getSegmentation, type SegmentationData } from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
function pct(n: number) {
  return (n * 100).toFixed(2) + "%";
}

export default function SegmentationPage() {
  const [data, setData] = useState<SegmentationData | null>(null);
  const [dimension, setDimension] = useState("overdue_bucket");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setData(null);
    (async () => {
      try {
        const result = await getSegmentation(dimension);
        if (!cancelled) setData(result);
      } catch (e) {
        console.error(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [dimension]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">分层分析</h1>
          <p className="text-sm text-gray-500 mt-1">按不同维度精细分析，找出亏损黑洞与现金贡献层</p>
        </div>
        <select
          value={dimension}
          onChange={(e) => setDimension(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
        >
          <option value="overdue_bucket">按逾期时长</option>
          <option value="recovered_status">按资产状态</option>
        </select>
      </div>

      {loading && <div className="text-center py-20 text-gray-500">加载中...</div>}
      {!loading && !data && <div className="text-center py-20 text-red-500">加载失败</div>}

      {data && (
        <>
          {/* 汇总 */}
          <div className="flex gap-4">
            <div className="bg-white rounded-xl border p-4 flex-1">
              <div className="text-xs text-gray-500">总EAD</div>
              <div className="text-lg font-bold">¥{fmt(data.total_ead)}</div>
            </div>
            <div className="bg-white rounded-xl border p-4 flex-1">
              <div className="text-xs text-gray-500">总预计损失</div>
              <div className="text-lg font-bold text-red-600">¥{fmt(data.total_loss)}</div>
            </div>
            <div className="bg-white rounded-xl border p-4 flex-1">
              <div className="text-xs text-gray-500">分层数</div>
              <div className="text-lg font-bold">{data.groups.length}</div>
            </div>
          </div>

          {/* 分层表格 */}
          <div className="bg-white rounded-xl border overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 border-b">
                  <tr>
                    <th className="text-left px-4 py-3 font-semibold text-gray-700">分层</th>
                    <th className="text-right px-4 py-3 font-semibold text-gray-700">笔数</th>
                    <th className="text-right px-4 py-3 font-semibold text-gray-700">EAD</th>
                    <th className="text-right px-4 py-3 font-semibold text-gray-700">预计损失</th>
                    <th className="text-right px-4 py-3 font-semibold text-gray-700">损失率</th>
                    <th className="text-right px-4 py-3 font-semibold text-gray-700">30天回流</th>
                    <th className="text-right px-4 py-3 font-semibold text-gray-700">90天回流</th>
                    <th className="text-right px-4 py-3 font-semibold text-gray-700">180天回流</th>
                    <th className="text-right px-4 py-3 font-semibold text-gray-700">EAD占比</th>
                  </tr>
                </thead>
                <tbody>
                  {data.groups.map((g) => {
                    const eadPct = data.total_ead > 0 ? g.total_ead / data.total_ead : 0;
                    const lrColor = g.expected_loss_rate > 0.6
                      ? "text-red-600 font-semibold"
                      : g.expected_loss_rate > 0.4
                      ? "text-yellow-600"
                      : "text-green-600";
                    return (
                      <tr key={g.dimension_value} className="border-b hover:bg-gray-50">
                        <td className="px-4 py-3 font-medium text-gray-900">{g.dimension_value}</td>
                        <td className="text-right px-4 py-3">{g.asset_count}</td>
                        <td className="text-right px-4 py-3">¥{fmt(g.total_ead)}</td>
                        <td className="text-right px-4 py-3 text-red-600">¥{fmt(g.expected_loss_amount)}</td>
                        <td className={`text-right px-4 py-3 ${lrColor}`}>{pct(g.expected_loss_rate)}</td>
                        <td className="text-right px-4 py-3 text-emerald-600">¥{fmt(g.cash_30d)}</td>
                        <td className="text-right px-4 py-3 text-emerald-600">¥{fmt(g.cash_90d)}</td>
                        <td className="text-right px-4 py-3 text-emerald-600">¥{fmt(g.cash_180d)}</td>
                        <td className="text-right px-4 py-3">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-16 h-1.5 bg-gray-100 rounded-full">
                              <div className="h-full bg-blue-500 rounded-full" style={{ width: `${eadPct * 100}%` }} />
                            </div>
                            <span className="text-xs text-gray-500">{pct(eadPct)}</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
