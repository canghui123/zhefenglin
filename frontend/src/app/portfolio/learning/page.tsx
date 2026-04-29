"use client";

import { useEffect, useState } from "react";
import {
  createDisposalOutcome,
  importModelFeedbackBatch,
  createModelLearningRun,
  getModelFeedbackSummary,
  listDisposalOutcomes,
  listModelLearningRuns,
  type DisposalOutcomeCreate,
  type DisposalOutcomeInfo,
  type ModelFeedbackBatchImportResult,
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
  const [batchFile, setBatchFile] = useState<File | null>(null);
  const [batchApplySuccess, setBatchApplySuccess] = useState(false);
  const [batchApplyRegion, setBatchApplyRegion] = useState(false);
  const [batchResult, setBatchResult] = useState<ModelFeedbackBatchImportResult | null>(null);

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

  async function handleBatchImport() {
    if (!batchFile) return;
    setSubmitting("batch-import");
    setMessage("");
    setBatchResult(null);
    try {
      const result = await importModelFeedbackBatch(batchFile, {
        apply_region_adjustments: batchApplyRegion,
        apply_success_adjustment: batchApplySuccess,
      });
      setBatchResult(result);
      await refresh();
      if (result.imported_rows > 0) {
        setMessage(
          `已导入 ${result.imported_rows} 条复盘样本并生成学习记录，${result.error_rows} 行需修正`,
        );
      } else {
        setMessage("表格未导入有效复盘样本，请根据错误提示修正后重新上传");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "批量学习失败");
    } finally {
      setSubmitting("");
    }
  }

  async function handleLearningRun(options: {
    applyRegion?: boolean;
    applySuccess?: boolean;
  } = {}) {
    const applyRegion = Boolean(options.applyRegion);
    const applySuccess = Boolean(options.applySuccess);
    setSubmitting(applySuccess ? "success-run" : applyRegion ? "apply-run" : "dry-run");
    setMessage("");
    try {
      await createModelLearningRun({
        apply_region_adjustments: applyRegion,
        apply_success_adjustment: applySuccess,
      });
      await refresh();
      if (applySuccess && applyRegion) {
        setMessage("已生成学习记录，并应用成功率与区域系数修正");
      } else if (applySuccess) {
        setMessage("已生成学习记录，并应用成功率修正到后续沙盘模型");
      } else if (applyRegion) {
        setMessage("已生成学习记录并应用区域系数调整");
      } else {
        setMessage("已生成学习记录，暂未改动生产系数");
      }
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

      <div className="rounded-xl border border-blue-100 bg-gradient-to-r from-blue-50 via-white to-emerald-50 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="text-xs font-medium text-blue-700">当前生效模型校准</div>
            <div className="mt-1 text-sm text-gray-600">
              后续库存沙盘会优先按路径级成功率修正校准动态概率，硬性不可用路径仍保持 0%。
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-blue-700">
              {pct(summary?.active_success_adjustment || 0)}
            </div>
            <div className="text-xs text-gray-500">
              {summary?.active_success_adjustment_run_id
                ? `来源学习运行 #${summary.active_success_adjustment_run_id}`
                : "暂无已应用成功率修正"}
            </div>
          </div>
        </div>
        {summary?.active_strategy_adjustments && summary.active_strategy_adjustments.length > 0 && (
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            {summary.active_strategy_adjustments.map((item) => (
              <div
                key={item.strategy_path}
                className="rounded-lg border border-blue-100 bg-white/80 px-3 py-2"
              >
                <div className="text-xs text-gray-500">{item.strategy_name}</div>
                <div className="mt-1 text-sm font-semibold text-blue-700">
                  路径修正 {pct(item.suggested_success_adjustment)}
                </div>
                <div className="mt-1 text-[11px] text-gray-500">
                  样本 {item.sample_count}，实际 {pct(item.actual_success_rate)}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid gap-6 lg:grid-cols-[420px_1fr]">
        <div className="space-y-6">
        <div className="rounded-xl border border-emerald-100 bg-white p-5">
          <div className="mb-4">
            <h3 className="text-sm font-semibold text-gray-700">批量上传学习样本</h3>
            <p className="mt-1 text-xs text-gray-500">
              支持 CSV/XLS/XLSX。系统会把每一行真实处置结果导入复盘样本，并立即生成学习运行。
            </p>
          </div>
          <div className="space-y-3">
            <label className="block text-xs font-medium text-gray-600">
              复盘学习表格
              <input
                accept=".csv,.xls,.xlsx"
                className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
                type="file"
                onChange={(event) => setBatchFile(event.target.files?.[0] || null)}
              />
            </label>
            <div className="rounded-lg bg-emerald-50 px-3 py-2 text-xs leading-5 text-emerald-800">
              建议列名：资产标识、实际路径、预测回款、实际回款、预测周期、实际周期、预测成功率、实际结果。
            </div>
            <label className="flex items-start gap-2 text-xs text-gray-600">
              <input
                checked={batchApplySuccess}
                className="mt-0.5"
                type="checkbox"
                onChange={(event) => setBatchApplySuccess(event.target.checked)}
              />
              <span>导入后应用成功率修正到后续沙盘模型</span>
            </label>
            <label className="flex items-start gap-2 text-xs text-gray-600">
              <input
                checked={batchApplyRegion}
                className="mt-0.5"
                type="checkbox"
                onChange={(event) => setBatchApplyRegion(event.target.checked)}
              />
              <span>导入后应用区域系数修正</span>
            </label>
            <button
              className="w-full rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-600 disabled:opacity-50"
              disabled={!batchFile || submitting === "batch-import"}
              onClick={handleBatchImport}
            >
              {submitting === "batch-import" ? "学习中..." : "上传并学习"}
            </button>
            {batchResult && (
              <div className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-3 text-xs text-gray-600">
                <div className="grid grid-cols-3 gap-2 text-center">
                  <MetricPill label="总行数" value={`${batchResult.total_rows}`} />
                  <MetricPill label="已导入" value={`${batchResult.imported_rows}`} tone="green" />
                  <MetricPill label="需修正" value={`${batchResult.error_rows}`} tone="orange" />
                </div>
                {batchResult.learning_run && (
                  <div className="mt-3 rounded-md bg-white px-3 py-2">
                    学习运行 #{batchResult.learning_run.id}，样本 {batchResult.learning_run.sample_count}，
                    成功率建议修正 {pct(batchResult.learning_run.suggested_success_adjustment)}
                  </div>
                )}
                {batchResult.errors.length > 0 && (
                  <div className="mt-3 space-y-1">
                    {batchResult.errors.slice(0, 5).map((error) => (
                      <div key={`${error.row_number}-${error.field}-${error.message}`}>
                        第 {error.row_number} 行：{error.message}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

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
        </div>

        <div className="space-y-6">
          <div className="rounded-xl border bg-white p-5">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-gray-700">模型学习建议</h3>
                <p className="mt-1 text-xs text-gray-500">
                  先生成记录观察偏差；经理可将路径级成功率修正写入后续沙盘，也可应用区域系数。
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  className="rounded-lg border px-3 py-2 text-xs font-medium hover:bg-gray-50 disabled:opacity-50"
                  disabled={submitting === "dry-run"}
                  onClick={() => handleLearningRun()}
                >
                  生成学习记录
                </button>
                <button
                  className="rounded-lg border border-blue-200 px-3 py-2 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                  disabled={submitting === "success-run"}
                  onClick={() => handleLearningRun({ applySuccess: true })}
                >
                  应用成功率修正
                </button>
                <button
                  className="rounded-lg border border-emerald-200 px-3 py-2 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                  disabled={submitting === "apply-run"}
                  onClick={() => handleLearningRun({ applyRegion: true })}
                >
                  应用区域修正
                </button>
              </div>
            </div>
            {summary && summary.strategy_adjustments.length > 0 && (
              <div className="mb-5 overflow-x-auto">
                <div className="mb-2 text-xs font-semibold text-gray-500">路径级成功率修正建议</div>
                <table className="w-full text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-3 py-2 text-left">路径</th>
                      <th className="px-3 py-2 text-right">样本</th>
                      <th className="px-3 py-2 text-right">实际成功率</th>
                      <th className="px-3 py-2 text-right">预测成功率</th>
                      <th className="px-3 py-2 text-right">建议修正</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.strategy_adjustments.map((item) => (
                      <tr key={item.strategy_path} className="border-t">
                        <td className="px-3 py-2">{item.strategy_name}</td>
                        <td className="px-3 py-2 text-right">{item.sample_count}</td>
                        <td className="px-3 py-2 text-right">{pct(item.actual_success_rate)}</td>
                        <td className="px-3 py-2 text-right">{pct(item.avg_predicted_success_probability)}</td>
                        <td className="px-3 py-2 text-right font-medium text-blue-700">
                          {pct(item.suggested_success_adjustment)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {summary && summary.region_adjustments.length > 0 && (
              <div className="overflow-x-auto">
                <div className="mb-2 text-xs font-semibold text-gray-500">区域系数修正建议</div>
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
            )}
            {summary &&
              summary.strategy_adjustments.length === 0 &&
              summary.region_adjustments.length === 0 && (
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
                  <div key={run.id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm">
                    <span>#{run.id} 样本 {run.sample_count}，成功率修正 {pct(run.suggested_success_adjustment)}</span>
                    <div className="flex gap-2 text-xs">
                      {run.success_adjustment_applied && (
                        <span className="rounded-full bg-blue-50 px-2 py-1 text-blue-700">
                          成功率已应用
                        </span>
                      )}
                      <span className={run.applied ? "rounded-full bg-emerald-50 px-2 py-1 text-emerald-700" : "rounded-full bg-gray-50 px-2 py-1 text-gray-500"}>
                        {run.applied ? "已应用" : "仅记录"}
                      </span>
                    </div>
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

function MetricPill({
  label,
  value,
  tone = "slate",
}: {
  label: string;
  value: string;
  tone?: "slate" | "green" | "orange";
}) {
  const toneClass =
    tone === "green"
      ? "text-emerald-700"
      : tone === "orange"
        ? "text-orange-700"
        : "text-slate-700";
  return (
    <div className="rounded-md bg-white px-2 py-1">
      <div className="text-[11px] text-gray-400">{label}</div>
      <div className={`text-sm font-semibold ${toneClass}`}>{value}</div>
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
    retail_auction: "立即上架竞拍",
    towing: "收车处置",
    collection: "继续等待赎车/收车",
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
