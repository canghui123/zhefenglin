"use client";

import { useEffect, useState } from "react";
import { getStrategies, type StrategyData } from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}
function pct(n: number) {
  return (n * 100).toFixed(2) + "%";
}

export default function StrategiesPage() {
  const [data, setData] = useState<StrategyData | null>(null);
  const [segIdx, setSegIdx] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setData(null);
    (async () => {
      try {
        const result = await getStrategies(segIdx);
        if (!cancelled) setData(result);
      } catch (e) {
        console.error(e);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [segIdx]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">处置路径模拟</h1>
          <p className="text-sm text-gray-500 mt-1">对同一分层对比不同处置路径的经营效果</p>
        </div>
        {data && (
          <select
            value={segIdx}
            onChange={(e) => setSegIdx(Number(e.target.value))}
            className="px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white max-w-xs"
          >
            {data.segment_list.map((s) => (
              <option key={s.index} value={s.index}>
                {s.name}
              </option>
            ))}
          </select>
        )}
      </div>

      {loading && <div className="text-center py-20 text-gray-500">加载中...</div>}

      {data && !loading && (
        <>
          {/* 分层信息 */}
          <div className="bg-white rounded-xl border p-4 flex gap-6 items-center">
            <div>
              <span className="text-xs text-gray-500">当前分层</span>
              <div className="font-semibold text-gray-900">{data.segment_name}</div>
            </div>
            <div>
              <span className="text-xs text-gray-500">EAD</span>
              <div className="font-semibold">¥{fmt(data.segment_ead)}</div>
            </div>
            <div>
              <span className="text-xs text-gray-500">资产数</span>
              <div className="font-semibold">{data.segment_count}笔</div>
            </div>
            <div className="ml-auto text-xs text-gray-400 max-w-md text-right">
              系统仅展示各路径的量化测算与约束，不替代人工决策；请结合入库情况、法务资源、客户关系等综合判断。
            </div>
          </div>

          {/* 路径对比卡片 —— 不做推荐，只展示数据与约束 */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {data.strategies.map((s) => {
              const hasConstraint = s.not_recommended_reasons.length > 0;
              return (
                <div
                  key={s.strategy_type}
                  className={`rounded-xl border p-4 ${
                    hasConstraint
                      ? "border-amber-200 bg-amber-50/30"
                      : "border-gray-200 bg-white"
                  }`}
                >
                  <div className="flex items-center gap-2 mb-3">
                    <h3 className="text-sm font-semibold text-gray-900">{s.strategy_name}</h3>
                    {hasConstraint && (
                      <span className="text-xs bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">约束</span>
                    )}
                  </div>

                  <div className="space-y-2 text-xs">
                    <div className="flex justify-between">
                      <span className="text-gray-500">成功概率</span>
                      <span className="font-medium">{pct(s.success_probability)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">预期回收</span>
                      <span className="font-medium text-emerald-600">¥{fmt(s.expected_recovery_gross)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">总成本</span>
                      <span className="font-medium text-red-600">¥{fmt(s.total_cost)}</span>
                    </div>
                    <div className="flex justify-between border-t pt-1 mt-1">
                      <span className="text-gray-500 font-semibold">净回收PV</span>
                      <span className={`font-bold ${s.net_recovery_pv > 0 ? "text-emerald-700" : "text-red-700"}`}>
                        ¥{fmt(s.net_recovery_pv)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">损失率</span>
                      <span className={s.expected_loss_rate > 0.7 ? "text-red-600 font-semibold" : ""}>
                        {pct(s.expected_loss_rate)}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">回款周期</span>
                      <span>{s.expected_recovery_days}天</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">资本释放</span>
                      <span>{s.capital_release_score}分</span>
                    </div>
                  </div>

                  {/* 成本分解 */}
                  <div className="mt-3 pt-2 border-t">
                    <div className="text-xs text-gray-400 mb-1">成本分解</div>
                    {Object.entries(s.cost_breakdown).map(([k, v]) => {
                      if (v === 0) return null;
                      const labels: Record<string, string> = {
                        towing: "拖车", inventory: "库存", legal: "法务",
                        channel_fee: "渠道", funding_cost: "资金", management: "管理",
                      };
                      return (
                        <div key={k} className="flex justify-between text-xs text-gray-500">
                          <span>{labels[k] || k}</span>
                          <span>¥{fmt(v)}</span>
                        </div>
                      );
                    })}
                  </div>

                  {/* 约束提示（法律/物权/入库等硬性不可行原因） */}
                  {s.not_recommended_reasons.length > 0 && (
                    <div className="mt-2 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
                      <div className="font-medium mb-0.5">约束提示</div>
                      {s.not_recommended_reasons.map((r, i) => <div key={i}>· {r}</div>)}
                    </div>
                  )}
                  {/* 风险提示（周期长/损失高等软性提示） */}
                  {s.risk_notes.length > 0 && (
                    <div className="mt-2 p-2 bg-yellow-50 rounded text-xs text-yellow-700">
                      <div className="font-medium mb-0.5">风险提示</div>
                      {s.risk_notes.map((r, i) => <div key={i}>· {r}</div>)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
