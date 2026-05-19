"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getCapacityPlan,
  updateCapacitySettings,
  type CapacityPlanItem,
  type PortfolioCapacityPlan,
  type PortfolioCapacitySettings,
} from "@/lib/api";
import { useSession } from "@/components/auth/session-provider";
import { hasRole } from "@/lib/auth";

const RESOURCE_LABELS: Record<string, string> = {
  towing_tasks: "收车/拖车",
  litigation_cases: "法务案件",
  auction_units: "竞拍渠道",
  collection_accounts: "催收账户",
  inventory_units: "场地容量",
  legal_team_cases: "法务团队",
  external_vendor_units: "外部供应商",
};

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function money(n: number) {
  return `¥${fmt(n)}`;
}

function PlanTable({ title, items }: { title: string; items: CapacityPlanItem[] }) {
  return (
    <div className="rounded-xl border bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-800">{title}</h3>
        <span className="text-xs text-gray-500">{items.length} 个分层</span>
      </div>
      {items.length === 0 ? (
        <p className="py-8 text-center text-sm text-gray-400">暂无数据</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-xs text-gray-500">
              <tr>
                <th className="px-3 py-2 text-left">分层</th>
                <th className="px-3 py-2 text-left">策略</th>
                <th className="px-3 py-2 text-right">执行/递延</th>
                <th className="px-3 py-2 text-right">预计净回收</th>
                <th className="px-3 py-2 text-right">所需成本</th>
                <th className="px-3 py-2 text-left">原因/资源</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item, index) => (
                <tr key={`${item.segment_name}-${item.status}-${index}`} className="border-t">
                  <td className="px-3 py-2 text-xs font-medium text-gray-900">{item.segment_name}</td>
                  <td className="px-3 py-2">
                    <div className="font-medium text-gray-800">{item.strategy_name}</div>
                    <div className="text-xs text-gray-500">{item.task_type}</div>
                  </td>
                  <td className="px-3 py-2 text-right">
                    {item.selected_count} / {item.deferred_count}
                  </td>
                  <td className="px-3 py-2 text-right text-emerald-700">{money(item.expected_net_recovery)}</td>
                  <td className="px-3 py-2 text-right">{money(item.required_cost)}</td>
                  <td className="px-3 py-2 text-xs text-gray-500">
                    {item.reason ||
                      Object.entries(item.resource_needs)
                        .map(([key, value]) => `${RESOURCE_LABELS[key] || key}:${fmt(value)}`)
                        .join(" / ") ||
                      "-"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function CapacityInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="grid gap-1 text-sm">
      <span className="text-gray-600">{label}</span>
      <input
        type="number"
        min={0}
        value={value}
        onChange={(event) => onChange(Number(event.target.value || 0))}
        className="h-9 rounded-lg border border-gray-200 px-3"
      />
    </label>
  );
}

export default function CapacityPlanPage() {
  const { user } = useSession();
  const [plan, setPlan] = useState<PortfolioCapacityPlan | null>(null);
  const [settings, setSettings] = useState<PortfolioCapacitySettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const next = await getCapacityPlan();
      setPlan(next);
      setSettings(next.settings);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    if (!settings) return;
    setSaving(true);
    setError("");
    try {
      await updateCapacitySettings(settings);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  const canEdit = hasRole(user, "admin");

  if (loading) return <div className="py-20 text-center text-gray-500">加载中...</div>;
  if (!plan || !settings) return <div className="py-20 text-center text-red-500">{error || "加载失败"}</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">处置产能计划</h1>
        <p className="mt-1 text-sm text-gray-500">
          基于预算、法务、竞拍、收车和场地约束，输出本月可执行组合。
        </p>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-xl border bg-white p-5">
          <div className="text-sm text-gray-500">本月执行资产</div>
          <div className="mt-2 text-2xl font-bold">{fmt(plan.total_selected_assets)} 台</div>
        </div>
        <div className="rounded-xl border bg-white p-5">
          <div className="text-sm text-gray-500">预计净回收</div>
          <div className="mt-2 text-2xl font-bold text-emerald-700">{money(plan.total_expected_net_recovery)}</div>
        </div>
        <div className="rounded-xl border bg-white p-5">
          <div className="text-sm text-gray-500">增量回收</div>
          <div className="mt-2 text-2xl font-bold text-blue-700">{money(plan.total_expected_incremental_recovery)}</div>
        </div>
        <div className="rounded-xl border bg-white p-5">
          <div className="text-sm text-gray-500">扩容潜在增量</div>
          <div className="mt-2 text-2xl font-bold text-orange-700">
            {money(plan.incremental_recovery_if_capacity_added)}
          </div>
        </div>
      </div>

      <div className="rounded-xl border bg-slate-50 p-5 text-sm text-slate-700">{plan.summary}</div>

      <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-xl border bg-white p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-800">资源消耗</h3>
            <span className="text-xs text-gray-500">
              瓶颈：{plan.capacity_bottlenecks.length ? plan.capacity_bottlenecks.join("、") : "暂无"}
            </span>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {Object.entries(plan.resource_usage).map(([key, used]) => {
              const total = used + (plan.remaining_capacity[key] || 0);
              const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0;
              return (
                <div key={key}>
                  <div className="mb-1 flex justify-between text-xs text-gray-500">
                    <span>{RESOURCE_LABELS[key] || key}</span>
                    <span>
                      {fmt(used)} / {fmt(total)}
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-100">
                    <div className="h-2 rounded-full bg-slate-800" style={{ width: `${pct}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div className="rounded-xl border bg-white p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-semibold text-gray-800">产能配置</h3>
            {!canEdit && <span className="text-xs text-gray-400">仅管理员可修改</span>}
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <CapacityInput label="收车/拖车" value={settings.monthly_towing_capacity} onChange={(value) => setSettings({ ...settings, monthly_towing_capacity: value })} />
            <CapacityInput label="法务案件" value={settings.monthly_litigation_capacity} onChange={(value) => setSettings({ ...settings, monthly_litigation_capacity: value })} />
            <CapacityInput label="竞拍渠道" value={settings.monthly_auction_capacity} onChange={(value) => setSettings({ ...settings, monthly_auction_capacity: value })} />
            <CapacityInput label="催收账户" value={settings.monthly_collection_capacity} onChange={(value) => setSettings({ ...settings, monthly_collection_capacity: value })} />
            <CapacityInput label="场地容量" value={settings.inventory_yard_capacity} onChange={(value) => setSettings({ ...settings, inventory_yard_capacity: value })} />
            <CapacityInput label="月度预算" value={settings.monthly_disposal_budget} onChange={(value) => setSettings({ ...settings, monthly_disposal_budget: value })} />
            <CapacityInput label="法务团队" value={settings.legal_team_capacity} onChange={(value) => setSettings({ ...settings, legal_team_capacity: value })} />
            <CapacityInput label="外部供应商" value={settings.external_vendor_capacity} onChange={(value) => setSettings({ ...settings, external_vendor_capacity: value })} />
          </div>
          <button
            type="button"
            onClick={save}
            disabled={!canEdit || saving}
            className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:cursor-not-allowed disabled:bg-gray-300"
          >
            {saving ? "保存中..." : "保存产能配置"}
          </button>
        </div>
      </div>

      <PlanTable title="本月可执行计划" items={plan.current_month_execution_plan} />
      <PlanTable title="下月递延池" items={plan.next_month_deferred_pool} />
      <PlanTable title="暂缓池" items={plan.paused_pool} />
    </div>
  );
}
