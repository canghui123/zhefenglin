"use client";

import { useEffect, useState } from "react";
import { getCashflow, type CashflowBucketItem, type CashflowData } from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
function pct(n: number) {
  return (n * 100).toFixed(2) + "%";
}

function linePath(points: Array<{ x: number; y: number }>) {
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
}

function bandPath(
  upper: Array<{ x: number; y: number }>,
  lower: Array<{ x: number; y: number }>,
) {
  if (!upper.length || !lower.length) return "";
  return `${linePath(upper)} ${lower
    .slice()
    .reverse()
    .map((point) => `L ${point.x} ${point.y}`)
    .join(" ")} Z`;
}

function CashflowConfidenceChart({ buckets }: { buckets: CashflowBucketItem[] }) {
  if (!buckets.length) {
    return (
      <div className="rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-8 text-center text-sm text-gray-500">
        暂无现金回流区间数据
      </div>
    );
  }

  const width = 760;
  const height = 280;
  const padding = { top: 28, right: 36, bottom: 44, left: 76 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const bucketValues = buckets.flatMap((bucket) => [
    bucket.pessimistic_net_cash_flow,
    bucket.neutral_net_cash_flow,
    bucket.optimistic_net_cash_flow,
    bucket.net_cash_flow,
    0,
  ]);
  const rawMin = Math.min(...bucketValues);
  const rawMax = Math.max(...bucketValues);
  const span = Math.max(rawMax - rawMin, 1);
  const minValue = rawMin - span * 0.08;
  const maxValue = rawMax + span * 0.12;
  const maxDay = Math.max(...buckets.map((bucket) => bucket.bucket_day), 1);
  const xFor = (day: number) => padding.left + (day / maxDay) * innerWidth;
  const yFor = (value: number) =>
    padding.top + ((maxValue - value) / Math.max(maxValue - minValue, 1)) * innerHeight;

  const optimisticPoints = buckets.map((bucket) => ({
    x: xFor(bucket.bucket_day),
    y: yFor(bucket.optimistic_net_cash_flow),
  }));
  const neutralPoints = buckets.map((bucket) => ({
    x: xFor(bucket.bucket_day),
    y: yFor(bucket.neutral_net_cash_flow),
  }));
  const pessimisticPoints = buckets.map((bucket) => ({
    x: xFor(bucket.bucket_day),
    y: yFor(bucket.pessimistic_net_cash_flow),
  }));
  const gridValues = [maxValue, (maxValue + minValue) / 2, minValue];
  const keyBuckets = buckets.filter((bucket) => [30, 90, 180, 360].includes(bucket.bucket_day));

  return (
    <div className="overflow-x-auto rounded-2xl border border-emerald-100 bg-gradient-to-br from-emerald-50 via-white to-slate-50 p-4">
      <div className="min-w-[720px]">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-sm font-semibold text-gray-800">三情景置信区间</div>
            <div className="text-xs text-gray-500">
              阴影为悲观-乐观区间，深色折线为中性净现金流
            </div>
          </div>
          <div className="flex items-center gap-4 text-xs text-gray-500">
            <span className="inline-flex items-center gap-1">
              <span className="h-2 w-5 rounded-full bg-emerald-500" />
              中性
            </span>
            <span className="inline-flex items-center gap-1">
              <span className="h-2 w-5 rounded-full bg-emerald-200" />
              区间
            </span>
          </div>
        </div>
        <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="现金回流三情景置信区间图">
          <defs>
            <linearGradient id="cashflow-band" x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.26" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.06" />
            </linearGradient>
            <filter id="cashflow-shadow" x="-20%" y="-20%" width="140%" height="140%">
              <feDropShadow dx="0" dy="8" stdDeviation="8" floodColor="#047857" floodOpacity="0.14" />
            </filter>
          </defs>

          {gridValues.map((value) => (
            <g key={value}>
              <line
                x1={padding.left}
                x2={width - padding.right}
                y1={yFor(value)}
                y2={yFor(value)}
                stroke="#d1fae5"
                strokeDasharray="4 6"
              />
              <text x={padding.left - 12} y={yFor(value) + 4} textAnchor="end" className="fill-gray-400 text-[11px]">
                ¥{fmt(value)}
              </text>
            </g>
          ))}

          <line
            x1={padding.left}
            x2={width - padding.right}
            y1={yFor(0)}
            y2={yFor(0)}
            stroke="#94a3b8"
            strokeOpacity="0.45"
          />
          <path d={bandPath(optimisticPoints, pessimisticPoints)} fill="url(#cashflow-band)" />
          <path
            d={linePath(neutralPoints)}
            fill="none"
            stroke="#047857"
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth="4"
            filter="url(#cashflow-shadow)"
          />
          <path
            d={linePath(optimisticPoints)}
            fill="none"
            stroke="#34d399"
            strokeDasharray="5 7"
            strokeLinecap="round"
            strokeWidth="2"
          />
          <path
            d={linePath(pessimisticPoints)}
            fill="none"
            stroke="#6ee7b7"
            strokeDasharray="5 7"
            strokeLinecap="round"
            strokeWidth="2"
          />

          {buckets.map((bucket) => {
            const x = xFor(bucket.bucket_day);
            const y = yFor(bucket.neutral_net_cash_flow);
            return (
              <g key={bucket.bucket_day}>
                <line
                  x1={x}
                  x2={x}
                  y1={padding.top}
                  y2={height - padding.bottom}
                  stroke="#ecfdf5"
                  strokeWidth="1"
                />
                <circle cx={x} cy={y} r="5" fill="#047857" stroke="white" strokeWidth="3" />
                <text x={x} y={height - 18} textAnchor="middle" className="fill-gray-500 text-[11px]">
                  {bucket.bucket_day}天
                </text>
              </g>
            );
          })}
        </svg>

        <div className="grid grid-cols-4 gap-3 border-t border-emerald-100 pt-3">
          {keyBuckets.map((bucket) => (
            <div key={bucket.bucket_day} className="rounded-xl bg-white/80 p-3 shadow-sm">
              <div className="text-xs text-gray-500">{bucket.bucket_day}天</div>
              <div className="mt-1 text-sm font-bold text-emerald-700">
                ¥{fmt(bucket.neutral_net_cash_flow)}
              </div>
              <div className="mt-1 text-[11px] text-gray-500">
                区间 ¥{fmt(bucket.pessimistic_net_cash_flow)} - ¥{fmt(bucket.optimistic_net_cash_flow)}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
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
        <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h3 className="text-sm font-semibold text-gray-700">净现金回流时间线</h3>
            <p className="mt-1 text-xs text-gray-500">
              将确定性预测升级为悲观 / 中性 / 乐观区间，辅助判断现金回笼弹性
            </p>
          </div>
          <div className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-medium text-emerald-700">
            中性值保持兼容原净现金流
          </div>
        </div>
        <CashflowConfidenceChart buckets={data.total_buckets} />

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
