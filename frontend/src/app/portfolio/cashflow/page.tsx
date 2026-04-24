"use client";

import { useEffect, useState } from "react";
import { getCashflow, type CashflowData } from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
function pct(n: number) {
  return (n * 100).toFixed(2) + "%";
}

export default function CashflowPage() {
  const [data, setData] = useState<CashflowData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getCashflow()
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="text-center py-20 text-gray-500">加载中...</div>;
  if (!data) return <div className="text-center py-20 text-red-500">加载失败</div>;

  const maxCash = Math.max(...data.total_buckets.map((b) => b.net_cash_flow), 1);
  const bucket90 = data.total_buckets.find((b) => b.bucket_day === 90);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">现金回流分析</h1>
        <p className="text-sm text-gray-500 mt-1">
          {data.snapshot_date} | 未来现金何时回来、回多少、长尾有多长
        </p>
      </div>

      {/* 汇总卡片 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-xl border p-4">
          <div className="text-xs text-gray-500">总EAD</div>
          <div className="text-lg font-bold">¥{fmt(data.total_ead)}</div>
        </div>
        <div className="bg-white rounded-xl border p-4">
          <div className="text-xs text-gray-500">回现率</div>
          <div className="text-lg font-bold text-emerald-600">{pct(data.cash_return_rate)}</div>
        </div>
        <div className="bg-white rounded-xl border p-4">
          <div className="text-xs text-gray-500">长尾占压</div>
          <div className="text-lg font-bold text-red-600">¥{fmt(data.total_long_tail)}</div>
        </div>
        <div className="bg-white rounded-xl border p-4">
          <div className="text-xs text-gray-500">90天净回流</div>
          <div className="text-lg font-bold text-emerald-600">
            ¥{fmt(bucket90?.net_cash_flow || 0)}
          </div>
          <div className="text-[11px] text-gray-500 mt-1">
            区间 ¥{fmt(bucket90?.pessimistic_net_cash_flow || 0)} - ¥{fmt(bucket90?.optimistic_net_cash_flow || 0)}
          </div>
        </div>
      </div>

      {/* 总体现金回流时间线 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-4">净现金回流时间线</h3>
        <div className="flex items-end gap-3 h-40">
          {data.total_buckets.map((b) => {
            const height = maxCash > 0 ? (b.net_cash_flow / maxCash) * 100 : 0;
            return (
              <div key={b.bucket_day} className="flex-1 flex flex-col items-center">
                <div className="text-xs text-gray-600 font-medium mb-1">¥{fmt(b.net_cash_flow)}</div>
                <div className="text-[10px] text-gray-400 mb-1">
                  {fmt(b.pessimistic_net_cash_flow)}~{fmt(b.optimistic_net_cash_flow)}
                </div>
                <div className="w-full bg-gray-100 rounded-t relative" style={{ height: "120px" }}>
                  <div
                    className="absolute bottom-0 w-full bg-emerald-400 rounded-t transition-all"
                    style={{ height: `${Math.max(height, 2)}%` }}
                  />
                </div>
                <div className="text-xs text-gray-500 mt-1">{b.bucket_day}天</div>
              </div>
            );
          })}
        </div>

        {/* 明细表 */}
        <table className="w-full text-sm mt-4 border-t pt-3">
          <thead>
            <tr className="text-gray-500 text-xs">
              <th className="text-left py-2">时间窗口</th>
              <th className="text-right py-2">流入</th>
              <th className="text-right py-2">流出</th>
              <th className="text-right py-2">悲观</th>
              <th className="text-right py-2">中性</th>
              <th className="text-right py-2">乐观</th>
            </tr>
          </thead>
          <tbody>
            {data.total_buckets.map((b) => (
              <tr key={b.bucket_day} className="border-t">
                <td className="py-2 font-medium">{b.bucket_day}天</td>
                <td className="text-right text-emerald-600">¥{fmt(b.gross_cash_in)}</td>
                <td className="text-right text-red-500">¥{fmt(b.gross_cash_out)}</td>
                <td className="text-right text-gray-500">¥{fmt(b.pessimistic_net_cash_flow)}</td>
                <td className="text-right font-semibold">¥{fmt(b.neutral_net_cash_flow)}</td>
                <td className="text-right text-emerald-600">¥{fmt(b.optimistic_net_cash_flow)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 按路径拆分 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">按处置路径拆分</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-3 py-2">路径</th>
                {data.total_buckets.map((b) => (
                  <th key={b.bucket_day} className="text-right px-3 py-2">{b.bucket_day}天</th>
                ))}
                <th className="text-right px-3 py-2">合计</th>
              </tr>
            </thead>
            <tbody>
              {data.by_strategy.map((st) => (
                <tr key={st.strategy_type} className="border-t hover:bg-gray-50">
                  <td className="px-3 py-2 font-medium text-gray-900 whitespace-nowrap">{st.strategy_name}</td>
                  {st.buckets.map((b) => (
                    <td key={b.bucket_day} className="text-right px-3 py-2 text-xs">
                      ¥{fmt(b.net_cash_flow)}
                    </td>
                  ))}
                  <td className="text-right px-3 py-2 font-semibold text-emerald-600">
                    ¥{fmt(st.total_net_cash)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* 按分层拆分(前10) */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">按分层拆分 (Top 10)</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-3 py-2">分层</th>
                <th className="text-right px-3 py-2">合计净回流</th>
                <th className="text-right px-3 py-2">30天</th>
                <th className="text-right px-3 py-2">90天</th>
                <th className="text-right px-3 py-2">360天</th>
              </tr>
            </thead>
            <tbody>
              {data.by_segment.map((seg) => (
                <tr key={seg.segment_name} className="border-t hover:bg-gray-50">
                  <td className="px-3 py-2 text-xs font-medium whitespace-nowrap">{seg.segment_name}</td>
                  <td className="text-right px-3 py-2 font-semibold text-emerald-600">¥{fmt(seg.total_net_cash)}</td>
                  <td className="text-right px-3 py-2 text-xs">
                    ¥{fmt(seg.buckets.find(b => b.bucket_day === 30)?.net_cash_flow || 0)}
                  </td>
                  <td className="text-right px-3 py-2 text-xs">
                    ¥{fmt(seg.buckets.find(b => b.bucket_day === 90)?.net_cash_flow || 0)}
                  </td>
                  <td className="text-right px-3 py-2 text-xs">
                    ¥{fmt(seg.buckets.find(b => b.bucket_day === 360)?.net_cash_flow || 0)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
