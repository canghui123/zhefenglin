"use client";

import { useEffect, useState } from "react";
import {
  createDisposalOutcome,
  createModelLearningRun,
  getModelFeedbackSummary,
  listDisposalOutcomes,
  listModelLearningRuns,
  type DisposalOutcomeCreate,
  type DisposalOutcomeInfo,
  type ModelFeedbackSummary,
  type ModelLearningRunInfo,
} from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function pct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}

const emptyForm: DisposalOutcomeCreate = {
  asset_identifier: "",
  strategy_path: "auction",
  province: "江苏省",
  city: "南京市",
  predicted_recovery_amount: 100000,
  actual_recovery_amount: 90000,
  predicted_cycle_days: 30,
  actual_cycle_days: 45,
  predicted_success_probability: 0.75,
  outcome_status: "partial",
  notes: "",
  metadata: {},
};

export default function PortfolioLearningPage() {
  const [summary, setSummary] = useState<ModelFeedbackSummary | null>(null);
  const [outcomes, setOutcomes] = useState<DisposalOutcomeInfo[]>([]);
  const [runs, setRuns] = useState<ModelLearningRunInfo[]>([]);
  const [form, setForm] = useState<DisposalOutcomeCreate>(emptyForm);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    const [nextSummary, nextOutcomes, nextRuns] = await Promise.all([
      getModelFeedbackSummary(),
      listDisposalOutcomes(),
      listModelLearningRuns(),
    ]);
    setSummary(nextSummary);
    setOutcomes(nextOutcomes);
    setRuns(nextRuns);
  }

  useEffect(() => {
    refresh()
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function handleCreateOutcome() {
    setSubmitting("outcome");
    setMessage("");
    try {
      await createDisposalOutcome({
        ...form,
        source_type: "manual_review",
        source_id: form.asset_identifier,
        city: form.city || null,
        notes: form.notes || null,
      });
      setForm({ ...emptyForm, asset_identifier: "" });
      await refresh();
      setMessage("已记录真实处置结果，模型复盘指标已更新");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "录入失败");
    } finally {
      setSubmitting("");
    }
  }

  async function handleLearningRun(apply: boolean) {
    setSubmitting(apply ? "apply-run" : "dry-run");
    setMessage("");
    try {
      await createModelLearningRun({ apply_region_adjustments: apply });
      await refresh();
      setMessage(apply ? "已生成学习记录并应用区域系数调整" : "已生成学习记录，暂未改动生产系数");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "学习运行失败");
    } finally {
      setSubmitting("");
    }
  }

  if (loading) return <div className="py-20 text-center text-gray-500">加载中...</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">复盘学习</h1>
        <p className="mt-1 text-sm text-gray-500">
          录入真实回款和处置周期，持续校准成功概率、现金回收和区域处置效率。
        </p>
      </div>

      {message && (
        <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          {message}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 md:grid-cols-5">
        <MetricCard title="样本数" value={`${summary?.sample_count || 0}`} />
        <MetricCard title="回款偏差" value={pct(summary?.recovery_bias_ratio || 0)} />
        <MetricCard title="周期偏差" value={pct(summary?.cycle_bias_ratio || 0)} />
        <MetricCard title="实际成功率" value={pct(summary?.actual_success_rate || 0)} />
        <MetricCard title="成功率建议修正" value={pct(summary?.suggested_success_adjustment || 0)} />
      </div>

      <div className="grid gap-6 lg:grid-cols-[420px_1fr]">
        <div className="rounded-xl border bg-white p-5">
          <h3 className="mb-4 text-sm font-semibold text-gray-700">录入真实处置结果</h3>
          <div className="space-y-3">
            <TextField
              label="资产/VIN/合同标识"
              value={form.asset_identifier}
              onChange={(value) => setForm((prev) => ({ ...prev, asset_identifier: value }))}
            />
            <label className="block text-xs font-medium text-gray-600">
              实际路径
              <select
                className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                value={form.strategy_path}
                onChange={(event) => setForm((prev) => ({ ...prev, strategy_path: event.target.value }))}
              >
                <option value="auction">拍卖处置</option>
                <option value="towing">收车处置</option>
                <option value="litigation">常规诉讼</option>
                <option value="special_procedure">实现担保物权特别程序</option>
                <option value="restructure">重组还款</option>
              </select>
            </label>
            <div className="grid grid-cols-2 gap-3">
              <TextField
                label="省份"
                value={form.province || ""}
                onChange={(value) => setForm((prev) => ({ ...prev, province: value }))}
              />
              <TextField
                label="城市"
                value={form.city || ""}
                onChange={(value) => setForm((prev) => ({ ...prev, city: value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <NumberField
                label="预测回款"
                value={form.predicted_recovery_amount}
                onChange={(value) => setForm((prev) => ({ ...prev, predicted_recovery_amount: value }))}
              />
              <NumberField
                label="实际回款"
                value={form.actual_recovery_amount}
                onChange={(value) => setForm((prev) => ({ ...prev, actual_recovery_amount: value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <NumberField
                label="预测周期(天)"
                value={form.predicted_cycle_days}
                onChange={(value) => setForm((prev) => ({ ...prev, predicted_cycle_days: value }))}
              />
              <NumberField
                label="实际周期(天)"
                value={form.actual_cycle_days}
                onChange={(value) => setForm((prev) => ({ ...prev, actual_cycle_days: value }))}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <NumberField
                label="预测成功率(0-1)"
                step="0.01"
                value={form.predicted_success_probability}
                onChange={(value) => setForm((prev) => ({ ...prev, predicted_success_probability: value }))}
              />
              <label className="block text-xs font-medium text-gray-600">
                实际结果
                <select
                  className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                  value={form.outcome_status}
                  onChange={(event) =>
                    setForm((prev) => ({
                      ...prev,
                      outcome_status: event.target.value as DisposalOutcomeCreate["outcome_status"],
                    }))
                  }
                >
                  <option value="success">成功</option>
                  <option value="partial">部分成功</option>
                  <option value="failed">失败</option>
                </select>
              </label>
            </div>
            <label className="block text-xs font-medium text-gray-600">
              复盘备注
              <textarea
                className="mt-1 min-h-20 w-full rounded-lg border px-3 py-2 text-sm"
                value={form.notes || ""}
                onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))}
              />
            </label>
            <button
              className="w-full rounded-lg bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
              disabled={!form.asset_identifier || submitting === "outcome"}
              onClick={handleCreateOutcome}
            >
              {submitting === "outcome" ? "保存中..." : "记录处置结果"}
            </button>
          </div>
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border bg-white p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-gray-700">模型学习建议</h3>
                <p className="mt-1 text-xs text-gray-500">先生成记录观察偏差，需要经理权限才可应用区域系数调整。</p>
              </div>
              <div className="flex gap-2">
                <button
                  className="rounded-lg border px-3 py-2 text-xs font-medium hover:bg-gray-50 disabled:opacity-50"
                  disabled={submitting === "dry-run"}
                  onClick={() => handleLearningRun(false)}
                >
                  生成学习记录
                </button>
                <button
                  className="rounded-lg border border-emerald-200 px-3 py-2 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                  disabled={submitting === "apply-run"}
                  onClick={() => handleLearningRun(true)}
                >
                  应用区域修正
                </button>
              </div>
            </div>
            {summary && summary.region_adjustments.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left">区域</th>
                      <th className="px-3 py-2 text-right">样本</th>
                      <th className="px-3 py-2 text-right">回款偏差</th>
                      <th className="px-3 py-2 text-right">周期偏差</th>
                      <th className="px-3 py-2 text-right">流通系数建议</th>
                      <th className="px-3 py-2 text-right">法务效率建议</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.region_adjustments.map((item) => (
                      <tr key={`${item.province}-${item.city || ""}`} className="border-t">
                        <td className="px-3 py-2">{item.province}{item.city ? ` / ${item.city}` : ""}</td>
                        <td className="px-3 py-2 text-right">{item.sample_count}</td>
                        <td className="px-3 py-2 text-right">{pct(item.recovery_bias_ratio)}</td>
                        <td className="px-3 py-2 text-right">{pct(item.cycle_bias_ratio)}</td>
                        <td className="px-3 py-2 text-right">{item.liquidity_speed_multiplier.toFixed(2)}x</td>
                        <td className="px-3 py-2 text-right">{item.legal_efficiency_multiplier.toFixed(2)}x</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-gray-400">暂无足够样本。先录入真实处置结果。</p>
            )}
          </div>

          <div className="rounded-xl border bg-white p-5">
            <h3 className="mb-3 text-sm font-semibold text-gray-700">最近处置结果</h3>
            {outcomes.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left">资产</th>
                      <th className="px-3 py-2 text-left">路径</th>
                      <th className="px-3 py-2 text-right">预测/实际回款</th>
                      <th className="px-3 py-2 text-right">预测/实际周期</th>
                      <th className="px-3 py-2 text-left">结果</th>
                    </tr>
                  </thead>
                  <tbody>
                    {outcomes.slice(0, 8).map((item) => (
                      <tr key={item.id} className="border-t">
                        <td className="px-3 py-2">{item.asset_identifier}</td>
                        <td className="px-3 py-2">{strategyName(item.strategy_path)}</td>
                        <td className="px-3 py-2 text-right">
                          ¥{fmt(item.predicted_recovery_amount)} / ¥{fmt(item.actual_recovery_amount)}
                        </td>
                        <td className="px-3 py-2 text-right">
                          {item.predicted_cycle_days}天 / {item.actual_cycle_days}天
                        </td>
                        <td className="px-3 py-2">{outcomeName(item.outcome_status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-gray-400">暂无复盘样本。</p>
            )}
          </div>

          <div className="rounded-xl border bg-white p-5">
            <h3 className="mb-3 text-sm font-semibold text-gray-700">最近学习运行</h3>
            {runs.length > 0 ? (
              <div className="space-y-2">
                {runs.slice(0, 5).map((run) => (
                  <div key={run.id} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                    <span>#{run.id} 样本 {run.sample_count}，成功率修正 {pct(run.suggested_success_adjustment)}</span>
                    <span className={run.applied ? "text-emerald-600" : "text-gray-500"}>
                      {run.applied ? "已应用" : "仅记录"}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">暂无学习运行记录。</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value }: { title: string; value: string }) {
  return (
    <div className="rounded-xl border bg-white p-4">
      <div className="text-xs text-gray-500">{title}</div>
      <div className="mt-2 text-xl font-bold text-gray-900">{value}</div>
    </div>
  );
}

function TextField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="block text-xs font-medium text-gray-600">
      {label}
      <input
        className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function NumberField({
  label,
  value,
  onChange,
  step = "1",
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  step?: string;
}) {
  return (
    <label className="block text-xs font-medium text-gray-600">
      {label}
      <input
        className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
        min={0}
        step={step}
        type="number"
        value={value}
        onChange={(event) => onChange(Number(event.target.value || 0))}
      />
    </label>
  );
}

function strategyName(value: string) {
  const names: Record<string, string> = {
    auction: "拍卖处置",
    towing: "收车处置",
    litigation: "常规诉讼",
    special_procedure: "特别程序",
    restructure: "重组还款",
  };
  return names[value] || value;
}

function outcomeName(value: string) {
  const names: Record<string, string> = {
    success: "成功",
    partial: "部分成功",
    failed: "失败",
  };
  return names[value] || value;
}
