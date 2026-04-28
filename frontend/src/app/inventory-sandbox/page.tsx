"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  batchSimulateSandbox,
  downloadReport,
  generateReport,
  getSandboxSuggestions,
  listSandboxBatches,
  previewSandboxBatchImport,
  simulateSandbox,
  type AuctionRound,
  type LitigationScenario,
  type SandboxBatchImportRow,
  type SandboxBatchSimulationResult,
  type SandboxBatchSummary,
  type SandboxInput,
  type SandboxResult,
  type TimePoint,
} from "@/lib/api";
import { pollJob } from "@/lib/jobs";

type NumericInput = number | "";

interface FormState {
  car_description: string;
  vin: string;
  license_plate: string;
  first_registration: string;
  mileage_km: NumericInput;
  entry_date: string;
  overdue_bucket: string;
  overdue_amount: NumericInput;
  che300_value: NumericInput;
  province: string;
  city: string;
  vehicle_type: string;
  vehicle_age_years: number;
  daily_parking: number;
  recovery_cost: NumericInput;
  sunk_collection_cost: NumericInput;
  sunk_legal_cost: NumericInput;
  annual_interest_rate: number;
  vehicle_recovered: boolean;
  vehicle_in_inventory: boolean;
  debtor_dishonest_enforced: boolean;
  expected_sale_days: number;
  auction_discount_rate: NumericInput;
  litigation_lawyer_fee: number;
  litigation_has_recovery_fee: boolean;
  litigation_recovery_fee_rate: number;
  special_lawyer_fee: number;
  special_has_recovery_fee: boolean;
  special_recovery_fee_rate: number;
  restructure_monthly_payment: NumericInput;
  restructure_months: number;
  restructure_redefault_rate: NumericInput;
  collection_history_text: string;
}

const missingFieldLabels: Record<string, string> = {
  car_description: "车辆描述",
  entry_date: "入库/评估日期",
  overdue_amount: "逾期金额",
  che300_value: "车300估值",
};

function fmt(n: number | null | undefined) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function rate(n: number | null | undefined) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return `${(n * 100).toFixed(0)}%`;
}

function shortDate(value: string | null | undefined) {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function numberOrNull(value: NumericInput) {
  return value === "" ? null : value;
}

function numberOrZero(value: NumericInput) {
  return value === "" ? 0 : value;
}

function buildPayload(form: FormState): SandboxInput {
  return {
    car_description: form.car_description,
    vin: form.vin || null,
    license_plate: form.license_plate || null,
    first_registration: form.first_registration || null,
    mileage_km: numberOrNull(form.mileage_km),
    entry_date: form.entry_date,
    overdue_bucket: form.overdue_bucket,
    overdue_amount: numberOrZero(form.overdue_amount),
    che300_value: numberOrNull(form.che300_value),
    province: form.province || null,
    city: form.city || null,
    vehicle_type: form.vehicle_type,
    vehicle_age_years: form.vehicle_age_years,
    daily_parking: form.daily_parking,
    recovery_cost: numberOrZero(form.recovery_cost),
    sunk_collection_cost: numberOrZero(form.sunk_collection_cost),
    sunk_legal_cost: numberOrZero(form.sunk_legal_cost),
    annual_interest_rate: form.annual_interest_rate,
    vehicle_recovered: form.vehicle_recovered,
    vehicle_in_inventory: form.vehicle_in_inventory,
    debtor_dishonest_enforced: form.debtor_dishonest_enforced,
    expected_sale_days: form.expected_sale_days,
    auction_discount_rate: numberOrNull(form.auction_discount_rate),
    auction_discount_auto: form.auction_discount_rate === "",
    litigation_lawyer_fee: form.litigation_lawyer_fee,
    litigation_has_recovery_fee: form.litigation_has_recovery_fee,
    litigation_recovery_fee_rate: form.litigation_recovery_fee_rate,
    special_lawyer_fee: form.special_lawyer_fee,
    special_has_recovery_fee: form.special_has_recovery_fee,
    special_recovery_fee_rate: form.special_recovery_fee_rate,
    restructure_monthly_payment: numberOrZero(form.restructure_monthly_payment),
    restructure_months: form.restructure_months,
    restructure_redefault_rate: numberOrNull(form.restructure_redefault_rate),
    collection_history_text: form.collection_history_text || null,
    redefault_rate_auto: form.restructure_redefault_rate === "",
  };
}

export default function InventorySandboxPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [result, setResult] = useState<SandboxResult | null>(null);
  const [reportHtml, setReportHtml] = useState("");
  const [batchFile, setBatchFile] = useState<File | null>(null);
  const [batchRows, setBatchRows] = useState<SandboxBatchImportRow[]>([]);
  const [batchLoading, setBatchLoading] = useState(false);
  const [batchResult, setBatchResult] = useState<SandboxBatchSimulationResult | null>(null);
  const [batchHistory, setBatchHistory] = useState<SandboxBatchSummary[]>([]);

  const [form, setForm] = useState<FormState>({
    car_description: "",
    vin: "",
    license_plate: "",
    first_registration: "",
    mileage_km: "",
    entry_date: "",
    overdue_bucket: "M3(61-90天)",
    overdue_amount: "",
    che300_value: "",
    province: "",
    city: "",
    vehicle_type: "auto",
    vehicle_age_years: 3,
    daily_parking: 30,
    recovery_cost: "",
    sunk_collection_cost: "",
    sunk_legal_cost: "",
    annual_interest_rate: 24,
    vehicle_recovered: true,
    vehicle_in_inventory: true,
    debtor_dishonest_enforced: false,
    expected_sale_days: 7,
    auction_discount_rate: "",
    litigation_lawyer_fee: 5000,
    litigation_has_recovery_fee: false,
    litigation_recovery_fee_rate: 0.05,
    special_lawyer_fee: 3000,
    special_has_recovery_fee: false,
    special_recovery_fee_rate: 0.03,
    restructure_monthly_payment: "",
    restructure_months: 12,
    restructure_redefault_rate: 0.30,
    collection_history_text: "",
  });

  function upd(field: keyof FormState, value: string | number | boolean) {
    if (field === "vehicle_recovered" && value === false) {
      setForm((prev) => ({ ...prev, vehicle_recovered: false, vehicle_in_inventory: false }));
      return;
    }
    if (field === "vehicle_in_inventory" && value === true) {
      setForm((prev) => ({ ...prev, vehicle_recovered: true, vehicle_in_inventory: true }));
      return;
    }
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  useEffect(() => {
    listSandboxBatches()
      .then(setBatchHistory)
      .catch(() => {
        // 历史入口只是辅助信息，加载失败不影响单台/批量模拟主流程。
      });
  }, []);

  async function ensureSuggestions(payload: SandboxInput): Promise<SandboxInput | null> {
    const needsDiscount = payload.auction_discount_rate === null || payload.auction_discount_rate === undefined;
    const needsRedefault = payload.restructure_redefault_rate === null || payload.restructure_redefault_rate === undefined;
    if (!needsDiscount && !needsRedefault) return payload;
    if (needsRedefault && !payload.collection_history_text) {
      setError("再违约率填写为“无”时，请先输入该客户过往催收记录或逾期记录，系统会据此建议再违约率。");
      return null;
    }

    const suggestions = await getSandboxSuggestions({
      car_description: payload.car_description,
      vehicle_type: payload.vehicle_type,
      vehicle_age_years: payload.vehicle_age_years,
      overdue_bucket: payload.overdue_bucket,
      overdue_amount: payload.overdue_amount,
      che300_value: payload.che300_value,
      vehicle_recovered: payload.vehicle_recovered,
      vehicle_in_inventory: payload.vehicle_in_inventory,
      collection_history_text: payload.collection_history_text,
    });

    const next = { ...payload };
    if (needsDiscount) {
      const accepted = window.confirm(
        `系统建议竞拍折扣比例为 ${rate(suggestions.auction_discount_rate)}。\n原因：${suggestions.auction_discount_note}\n\n是否接受该比例？取消后请自行填写竞拍折扣比例。`
      );
      if (!accepted) {
        setError("请手动填写竞拍折扣比例后再模拟。");
        return null;
      }
      next.auction_discount_rate = suggestions.auction_discount_rate;
      next.auction_discount_auto = true;
      setForm((prev) => ({ ...prev, auction_discount_rate: suggestions.auction_discount_rate }));
    }
    if (needsRedefault && suggestions.redefault_rate !== null) {
      const accepted = window.confirm(
        `系统根据催收/逾期记录建议再违约率为 ${rate(suggestions.redefault_rate)}。\n原因：${suggestions.redefault_rate_note || "规则模型建议"}\n\n是否接受该比例？取消后请自行填写再违约率。`
      );
      if (!accepted) {
        setError("请手动填写再违约率后再模拟。");
        return null;
      }
      next.restructure_redefault_rate = suggestions.redefault_rate;
      next.redefault_rate_auto = true;
      setForm((prev) => ({ ...prev, restructure_redefault_rate: suggestions.redefault_rate || 0 }));
    }
    return next;
  }

  async function handleSimulate() {
    if (!form.car_description || !form.entry_date || !form.overdue_amount) {
      setError("请填写车辆描述、入库/评估日期和逾期金额。车300估值可留空，系统会自动估值。");
      return;
    }
    setLoading(true);
    setError("");
    setMessage("");
    setReportHtml("");
    try {
      const payload = await ensureSuggestions(buildPayload(form));
      if (!payload) return;
      const res = await simulateSandbox(payload);
      setResult(res);
      if (!payload.che300_value && res.input.che300_value) {
        setMessage(`车300估值已自动补全为 ¥${fmt(res.input.che300_value)}。`);
        setForm((prev) => ({ ...prev, che300_value: res.input.che300_value || "" }));
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "模拟失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleBatchPreview() {
    if (!batchFile) return;
    setBatchLoading(true);
    setError("");
    setMessage("");
    setBatchResult(null);
    try {
      const preview = await previewSandboxBatchImport(batchFile);
      setBatchRows(preview.rows);
      setMessage(`已解析 ${preview.total_rows} 行，缺字段行可在下方逐台补填或取消勾选。`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "批量导入解析失败");
    } finally {
      setBatchLoading(false);
    }
  }

  function updateBatchRow(index: number, patch: Partial<SandboxBatchImportRow["input"]> & { selected?: boolean }) {
    setBatchRows((prev) =>
      prev.map((row, i) => {
        if (i !== index) return row;
        const input = { ...row.input, ...patch };
        const missing = [
          !input.car_description ? "car_description" : "",
          !input.entry_date ? "entry_date" : "",
          !input.overdue_amount ? "overdue_amount" : "",
          !input.che300_value ? "che300_value" : "",
        ].filter(Boolean);
        return {
          ...row,
          selected: patch.selected ?? row.selected,
          input,
          missing_fields: missing,
        };
      })
    );
  }

  async function handleBatchSimulate() {
    const selected = batchRows.filter((row) => row.selected);
    if (selected.length === 0) {
      setError("请至少勾选一台车辆。");
      return;
    }
    setBatchLoading(true);
    setError("");
    setMessage("");
    try {
      const res = await batchSimulateSandbox(selected);
      setBatchResult(res);
      setMessage(`批量模拟完成：成功 ${res.success_rows} 台，失败 ${res.error_rows} 台。`);
      listSandboxBatches().then(setBatchHistory).catch(() => {});
    } catch (e) {
      setError(e instanceof Error ? e.message : "批量模拟失败");
    } finally {
      setBatchLoading(false);
    }
  }

  async function handleReport() {
    if (!result?.id) return;
    try {
      const { job_id } = await generateReport(result.id);
      const job = await pollJob(job_id);
      if (job.status === "failed") throw new Error(job.error_message || "报告生成失败");
      setReportHtml(await downloadReport(result.id));
    } catch {
      setError("报告生成失败");
    }
  }

  function printReport() {
    const win = window.open("", "_blank");
    if (win) {
      win.document.write(reportHtml);
      win.document.close();
      win.print();
    }
  }

  const pathNames: Record<string, string> = {
    A: "继续等待赎车",
    B: "常规诉讼",
    C: "立即上架竞拍",
    D: "担保物权特别程序",
    E: "分期重组/和解",
  };
  const specialProcedureStageAllowed = !form.overdue_bucket.startsWith("M1") && !form.overdue_bucket.startsWith("M2");
  const specialProcedureBlocked = !form.vehicle_recovered || !form.vehicle_in_inventory || !specialProcedureStageAllowed;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">库存决策沙盘</h1>
        <p className="text-gray-500 mt-1">支持单台录入和客户表格批量导入，自动补全估值、折扣和重组风险建议</p>
      </div>

      {error && <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>}
      {message && <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-lg text-emerald-700 text-sm">{message}</div>}

      <div className="bg-white border rounded-xl p-6 space-y-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-semibold text-gray-900">批量导入库存车辆</h2>
            <p className="mt-1 text-sm text-gray-500">
              上传客户 Excel/CSV 后，系统自动识别字段并补车300估值；缺字段车辆可逐台补填，也可取消勾选。
            </p>
          </div>
          <span className="rounded-full bg-blue-50 border border-blue-100 px-3 py-1 text-xs font-medium text-blue-700">
            批量沙盘
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <input
            type="file"
            accept=".xlsx,.xls,.csv"
            onChange={(event) => setBatchFile(event.target.files?.[0] || null)}
            className="inp max-w-md"
          />
          <button
            onClick={handleBatchPreview}
            disabled={!batchFile || batchLoading}
            className="btn-primary disabled:bg-slate-300"
          >
            {batchLoading ? "解析中..." : "上传并预览"}
          </button>
          {batchRows.length > 0 && (
            <button onClick={handleBatchSimulate} disabled={batchLoading} className="btn-dark">
              批量运行已勾选车辆
            </button>
          )}
        </div>

        {batchRows.length > 0 && (
          <div className="overflow-x-auto border rounded-lg">
            <table className="min-w-[1180px] w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-3 py-2 text-left">选择</th>
                  <th className="px-3 py-2 text-left">行号</th>
                  <th className="px-3 py-2 text-left">车辆</th>
                  <th className="px-3 py-2 text-left">日期</th>
                  <th className="px-3 py-2 text-left">逾期</th>
                  <th className="px-3 py-2 text-left">估值</th>
                  <th className="px-3 py-2 text-left">状态</th>
                  <th className="px-3 py-2 text-left">竞拍折扣</th>
                  <th className="px-3 py-2 text-left">缺字段/错误</th>
                </tr>
              </thead>
              <tbody>
                {batchRows.map((row, index) => (
                  <tr key={row.row_id} className="border-t align-top">
                    <td className="px-3 py-3">
                      <input
                        type="checkbox"
                        checked={row.selected}
                        onChange={(event) => updateBatchRow(index, { selected: event.target.checked })}
                      />
                    </td>
                    <td className="px-3 py-3">{row.row_number}</td>
                    <td className="px-3 py-3">
                      <input
                        className="inp w-56"
                        value={row.input.car_description}
                        onChange={(event) => updateBatchRow(index, { car_description: event.target.value })}
                        placeholder="车辆描述"
                      />
                      <input
                        className="inp mt-1 w-56"
                        value={row.input.vin || ""}
                        onChange={(event) => updateBatchRow(index, { vin: event.target.value || null })}
                        placeholder="VIN，可用于自动估值"
                      />
                    </td>
                    <td className="px-3 py-3">
                      <input
                        className="inp w-36"
                        type="date"
                        value={row.input.entry_date}
                        onChange={(event) => updateBatchRow(index, { entry_date: event.target.value })}
                      />
                    </td>
                    <td className="px-3 py-3">
                      <select
                        className="inp w-36"
                        value={row.input.overdue_bucket}
                        onChange={(event) => updateBatchRow(index, { overdue_bucket: event.target.value })}
                      >
                        <OverdueOptions />
                      </select>
                      <input
                        className="inp mt-1 w-36"
                        type="number"
                        value={row.input.overdue_amount || ""}
                        onChange={(event) => updateBatchRow(index, { overdue_amount: Number(event.target.value) })}
                        placeholder="逾期金额"
                      />
                    </td>
                    <td className="px-3 py-3">
                      <input
                        className="inp w-32"
                        type="number"
                        value={row.input.che300_value || ""}
                        onChange={(event) => updateBatchRow(index, { che300_value: Number(event.target.value) || null })}
                        placeholder="无则自动"
                      />
                      {row.che300_auto_filled && (
                        <div className="mt-1 text-xs text-emerald-600">已自动估值</div>
                      )}
                    </td>
                    <td className="px-3 py-3 text-xs">
                      <label className="block">
                        <input
                          type="checkbox"
                          checked={row.input.vehicle_recovered !== false}
                          onChange={(event) => updateBatchRow(index, { vehicle_recovered: event.target.checked, vehicle_in_inventory: event.target.checked ? row.input.vehicle_in_inventory : false })}
                        /> 已收回
                      </label>
                      <label className="mt-1 block">
                        <input
                          type="checkbox"
                          checked={row.input.vehicle_in_inventory !== false}
                          onChange={(event) => updateBatchRow(index, { vehicle_recovered: event.target.checked ? true : row.input.vehicle_recovered, vehicle_in_inventory: event.target.checked })}
                        /> 已入库
                      </label>
                    </td>
                    <td className="px-3 py-3">
                      <input
                        className="inp w-28"
                        type="number"
                        step="0.01"
                        value={row.input.auction_discount_rate || ""}
                        onChange={(event) => updateBatchRow(index, { auction_discount_rate: Number(event.target.value) || null })}
                        placeholder={row.suggested_auction_discount_rate ? rate(row.suggested_auction_discount_rate) : "自动"}
                      />
                    </td>
                    <td className="px-3 py-3 text-xs text-orange-700">
                      {[...row.missing_fields.map((field) => missingFieldLabels[field] || field), ...row.errors].join("；") || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {batchHistory.length > 0 && (
          <div className="rounded-lg border bg-white p-4 text-sm">
            <div className="mb-3 flex items-center justify-between">
              <div className="font-semibold text-gray-900">最近批量模拟</div>
              <span className="text-xs text-gray-500">保留最近 {batchHistory.length} 个批次</span>
            </div>
            <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
              {batchHistory.slice(0, 6).map((batch) => (
                <Link
                  key={batch.id}
                  href={`/inventory-sandbox/batches/${batch.id}`}
                  className="rounded-lg border border-slate-200 p-3 hover:border-blue-300 hover:bg-blue-50"
                >
                  <div className="font-semibold text-gray-900">批次 #{batch.id}</div>
                  <div className="mt-1 text-xs text-gray-500">{shortDate(batch.created_at)}</div>
                  <div className="mt-2 text-xs text-gray-600">
                    总 {batch.total_rows} 台，成功 {batch.success_rows} 台，失败 {batch.error_rows} 台
                  </div>
                </Link>
              ))}
            </div>
          </div>
        )}

        {batchResult && (
          <div className="rounded-lg border bg-slate-50 p-4 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="font-semibold text-gray-900">
                批量模拟结果：成功 {batchResult.success_rows} 台，失败 {batchResult.error_rows} 台
              </div>
              {batchResult.batch_id && (
                <Link
                  href={`/inventory-sandbox/batches/${batchResult.batch_id}`}
                  className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700"
                >
                  查看批量详情
                </Link>
              )}
            </div>
            <div className="mt-2 grid gap-2 md:grid-cols-2">
              {batchResult.results.map((item) => (
                <div key={item.row_id} className="rounded border bg-white p-3">
                  第{item.row_number}行：
                  {item.status === "success" && item.result
                    ? `推荐路径${item.result.best_path}，估值 ¥${fmt(item.result.input.che300_value)}`
                    : item.error}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="bg-white border rounded-xl p-6 space-y-6">
        <h2 className="font-semibold text-gray-900">单台车辆信息</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Field label="车辆描述">
            <input className="inp" value={form.car_description} onChange={(e) => upd("car_description", e.target.value)} placeholder="如：2021丰田凯美瑞2.0G豪华版" />
          </Field>
          <Field label="VIN/车架号">
            <input className="inp" value={form.vin} onChange={(e) => upd("vin", e.target.value)} placeholder="可为空，填写后优先调用车300VIN估值" />
          </Field>
          <Field label="首次上牌日期">
            <input className="inp" type="date" value={form.first_registration} onChange={(e) => upd("first_registration", e.target.value)} />
          </Field>
          <Field label="表显里程 (公里)">
            <input className="inp" type="number" value={form.mileage_km} onChange={(e) => upd("mileage_km", e.target.value === "" ? "" : +e.target.value)} />
          </Field>
          <Field label="入库/评估日期">
            <input className="inp" type="date" value={form.entry_date} onChange={(e) => upd("entry_date", e.target.value)} />
          </Field>
          <Field label="逾期阶段">
            <select className="inp" value={form.overdue_bucket} onChange={(e) => upd("overdue_bucket", e.target.value)}>
              <OverdueOptions />
            </select>
          </Field>
          <Field label="逾期金额 (元)">
            <input className="inp" type="number" value={form.overdue_amount} onChange={(e) => upd("overdue_amount", e.target.value === "" ? "" : +e.target.value)} />
          </Field>
          <Field label="当前车300估值 (元)">
            <input className="inp" type="number" value={form.che300_value} onChange={(e) => upd("che300_value", e.target.value === "" ? "" : +e.target.value)} placeholder="无则自动调用估值" />
          </Field>
          <Field label="省份">
            <input className="inp" value={form.province} onChange={(e) => upd("province", e.target.value)} placeholder="如：江苏省" />
          </Field>
          <Field label="城市">
            <input className="inp" value={form.city} onChange={(e) => upd("city", e.target.value)} placeholder="如：南京市" />
          </Field>
          <Field label="车辆类型">
            <select className="inp" value={form.vehicle_type} onChange={(e) => upd("vehicle_type", e.target.value)}>
              <option value="auto">自动识别</option>
              <option value="luxury">豪华品牌</option>
              <option value="japanese">日系</option>
              <option value="german">德系非豪华</option>
              <option value="domestic">国产品牌</option>
              <option value="new_energy">新能源</option>
            </select>
          </Field>
          <Field label="车龄 (年)">
            <input className="inp" type="number" step="0.5" value={form.vehicle_age_years} onChange={(e) => upd("vehicle_age_years", +e.target.value)} />
          </Field>
          <Field label="收车成本 (元)">
            <input className="inp" type="number" value={form.recovery_cost} onChange={(e) => upd("recovery_cost", e.target.value === "" ? "" : +e.target.value)} placeholder="含拖车/GPS/人工" />
          </Field>
          <Field label="已发生催收成本 (元)">
            <input className="inp" type="number" value={form.sunk_collection_cost} onChange={(e) => upd("sunk_collection_cost", e.target.value === "" ? "" : +e.target.value)} />
          </Field>
          <Field label="已发生法务成本 (元)">
            <input className="inp" type="number" value={form.sunk_legal_cost} onChange={(e) => upd("sunk_legal_cost", e.target.value === "" ? "" : +e.target.value)} />
          </Field>
          <Field label="日停车费 (元)">
            <input className="inp" type="number" value={form.daily_parking} onChange={(e) => upd("daily_parking", +e.target.value)} />
          </Field>
          <CheckboxField label="车辆是否已回收" checked={form.vehicle_recovered} onChange={(checked) => upd("vehicle_recovered", checked)} text={form.vehicle_recovered ? "已收回" : "未收回（路径C/D屏蔽）"} />
          <CheckboxField label="车辆是否已入库" checked={form.vehicle_in_inventory} disabled={!form.vehicle_recovered} onChange={(checked) => upd("vehicle_in_inventory", checked)} text={form.vehicle_in_inventory ? "已入库" : "未入库（路径D屏蔽）"} />
          <CheckboxField label="司法风险：失信被执行人" checked={form.debtor_dishonest_enforced} onChange={(checked) => upd("debtor_dishonest_enforced", checked)} text={form.debtor_dishonest_enforced ? "否决等待赎车" : "未命中阻断"} />
        </div>

        {specialProcedureBlocked && (
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-sm">
            路径D硬前提：车辆已收回、已入库形成证据链，且逾期阶段至少达到 M3。
          </div>
        )}

        <hr className="border-gray-200" />
        <h2 className="font-semibold text-gray-900">竞拍参数</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="预计成交天数">
            <input className="inp" type="number" value={form.expected_sale_days} onChange={(e) => upd("expected_sale_days", +e.target.value)} />
          </Field>
          <Field label="竞拍折扣比例">
            <input className="inp" type="number" step="0.01" value={form.auction_discount_rate} onChange={(e) => upd("auction_discount_rate", e.target.value === "" ? "" : +e.target.value)} placeholder="无则系统建议并询问" />
          </Field>
          <Field label="逾期年利率 (%)">
            <input className="inp" type="number" value={form.annual_interest_rate} onChange={(e) => upd("annual_interest_rate", +e.target.value)} />
          </Field>
        </div>

        <hr className="border-gray-200" />
        <h2 className="font-semibold text-gray-900">常规诉讼律师费</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="固定律师费 (元)">
            <input className="inp" type="number" value={form.litigation_lawyer_fee} onChange={(e) => upd("litigation_lawyer_fee", +e.target.value)} />
          </Field>
          <CheckboxField label="有回款比例律师费" checked={form.litigation_has_recovery_fee} onChange={(checked) => upd("litigation_has_recovery_fee", checked)} text="启用" />
          {form.litigation_has_recovery_fee && (
            <Field label="回款比例">
              <input className="inp" type="number" step="0.01" value={form.litigation_recovery_fee_rate} onChange={(e) => upd("litigation_recovery_fee_rate", +e.target.value)} />
            </Field>
          )}
        </div>

        <hr className="border-gray-200" />
        <h2 className="font-semibold text-gray-900">担保物权特别程序律师费</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="固定律师费 (元)">
            <input className="inp" type="number" value={form.special_lawyer_fee} onChange={(e) => upd("special_lawyer_fee", +e.target.value)} />
          </Field>
          <CheckboxField label="有回款比例律师费" checked={form.special_has_recovery_fee} onChange={(checked) => upd("special_has_recovery_fee", checked)} text="启用" />
          {form.special_has_recovery_fee && (
            <Field label="回款比例">
              <input className="inp" type="number" step="0.01" value={form.special_recovery_fee_rate} onChange={(e) => upd("special_recovery_fee_rate", +e.target.value)} />
            </Field>
          )}
        </div>

        <hr className="border-gray-200" />
        <h2 className="font-semibold text-gray-900">分期重组/和解参数</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Field label="月还款额 (元)">
            <input className="inp" type="number" value={form.restructure_monthly_payment} onChange={(e) => upd("restructure_monthly_payment", e.target.value === "" ? "" : +e.target.value)} placeholder="无=按逾期额/12" />
          </Field>
          <Field label="重组期数 (月)">
            <input className="inp" type="number" value={form.restructure_months} onChange={(e) => upd("restructure_months", +e.target.value)} />
          </Field>
          <Field label="再违约率">
            <input className="inp" type="number" step="0.05" value={form.restructure_redefault_rate} onChange={(e) => upd("restructure_redefault_rate", e.target.value === "" ? "" : +e.target.value)} placeholder="无则输入历史记录" />
          </Field>
          <Field label="过往催收/逾期记录">
            <textarea className="inp min-h-20" value={form.collection_history_text} onChange={(e) => upd("collection_history_text", e.target.value)} placeholder="如：近6个月两次承诺还款未履行，但最近主动联系并部分还款" />
          </Field>
        </div>

        <button className="btn-primary mt-4 disabled:bg-slate-300" onClick={handleSimulate} disabled={loading}>
          {loading ? "模拟计算中..." : "开始五路径模拟"}
        </button>
      </div>

      {result && (
        <>
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl">
            <div className="font-bold text-lg text-blue-900 mb-1">
              系统推荐：路径{result.best_path} — {pathNames[result.best_path]}
            </div>
            <div className="text-sm text-gray-700 whitespace-pre-line">{result.recommendation}</div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <PathCard title="路径A：等待赎车" best={result.best_path === "A"} unavailable={result.path_a.available === false} unavailableReason={result.path_a.unavailable_reason || ""}>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs">
                    <th className="text-left py-1">天数</th>
                    <th className="text-right py-1">贬值</th>
                    <th className="text-right py-1">成功率</th>
                    <th className="text-right py-1">边际收益</th>
                  </tr>
                </thead>
                <tbody>
                  {result.path_a.timepoints.map((tp: TimePoint) => (
                    <tr key={tp.days} className="border-t">
                      <td className="py-1.5">{tp.days}天</td>
                      <td className="text-right text-red-500">-{fmt(tp.depreciation_amount)}</td>
                      <td className="text-right">{rate(tp.success_probability)}</td>
                      <td className={`text-right font-medium ${tp.future_marginal_net_benefit >= 0 ? "text-emerald-600" : "text-red-600"}`}>{fmt(tp.future_marginal_net_benefit)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </PathCard>

            <PathCard title="路径B：常规诉讼" best={result.best_path === "B"}>
              <div className="text-xs text-gray-500 mb-2">诉讼费 ¥{fmt(result.path_b.legal_cost.court_fee)} | 执行费 ¥{fmt(result.path_b.legal_cost.execution_fee)}</div>
              <table className="w-full text-sm">
                <tbody>
                  {result.path_b.scenarios.map((s: LitigationScenario) => (
                    <tr key={s.label} className="border-t">
                      <td className="py-1.5 text-xs">{s.label}</td>
                      <td className="text-right">{rate(s.success_probability)}</td>
                      <td className={`text-right font-medium ${s.future_marginal_net_benefit >= 0 ? "text-emerald-600" : "text-red-600"}`}>{fmt(s.future_marginal_net_benefit)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </PathCard>

            <PathCard title="路径C：立即竞拍" best={result.best_path === "C"} unavailable={result.path_c.available === false} unavailableReason={result.path_c.unavailable_reason || ""}>
              <div className="space-y-2 text-sm">
                <Row label="预计成交天数" value={`${result.path_c.expected_sale_days}天`} />
                <Row label="竞拍折扣" value={rate(result.path_c.auction_discount_rate)} />
                <Row label="成交价" value={`¥${fmt(result.path_c.sale_price)}`} />
                <Row label="停车费" value={`-¥${fmt(result.path_c.parking_during_sale)}`} red />
                <Row label="动态成功率" value={rate(result.path_c.success_probability)} />
                {result.path_c.auction_discount_suggested && (
                  <div className="rounded bg-blue-50 p-2 text-xs text-blue-700">{result.path_c.auction_discount_note}</div>
                )}
                <div className="border-t pt-2">
                  <Row label="未来边际净收益" value={`¥${fmt(result.path_c.future_marginal_net_benefit)}`} bold green />
                </div>
              </div>
            </PathCard>

            <PathCard title="路径D：担保物权特别程序" best={result.best_path === "D"} unavailable={result.path_d.available === false} unavailableReason={result.path_d.unavailable_reason || ""}>
              <div className="space-y-2 text-sm">
                <Row label="周期" value={`约${result.path_d.duration_months}个月`} />
                {result.path_d.auction_rounds.map((r: AuctionRound) => (
                  <Row key={r.round_name} label={`${r.round_name}(${rate(r.discount_rate)})`} value={`¥${fmt(r.auction_price)}`} />
                ))}
                <Row label="期望拍卖价" value={`¥${fmt(result.path_d.expected_auction_price)}`} />
                <Row label="法律费用" value={`-¥${fmt(result.path_d.legal_cost.total_legal_cost)}`} red />
                <Row label="动态成功率" value={rate(result.path_d.success_probability)} />
                <div className="border-t pt-2">
                  <Row label="未来边际净收益" value={`¥${fmt(result.path_d.future_marginal_net_benefit)}`} bold green />
                </div>
              </div>
            </PathCard>

            <PathCard title="路径E：分期重组/和解" best={result.best_path === "E"}>
              <div className="space-y-2 text-sm">
                <Row label="月还款额" value={`¥${fmt(result.path_e.monthly_payment)}`} />
                <Row label="还款期数" value={`${result.path_e.total_months}个月`} />
                <Row label="再违约率" value={rate(result.path_e.redefault_rate)} />
                <Row label="风险调整后回收" value={`¥${fmt(result.path_e.risk_adjusted_recovery)}`} />
                {result.path_e.redefault_rate_suggested && (
                  <div className="rounded bg-blue-50 p-2 text-xs text-blue-700">{result.path_e.redefault_rate_note}</div>
                )}
                <div className="border-t pt-2">
                  <Row label="未来边际净收益" value={`¥${fmt(result.path_e.future_marginal_net_benefit)}`} bold green />
                </div>
              </div>
            </PathCard>
          </div>

          <div className="bg-white border rounded-xl p-5 flex items-center gap-4">
            <button className="btn-dark" onClick={handleReport}>生成报告预览</button>
            {reportHtml && <button className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm" onClick={printReport}>打印/保存PDF</button>}
          </div>
          {reportHtml && (
            <div className="bg-white border rounded-xl p-4">
              <iframe srcDoc={reportHtml} className="w-full h-[800px] border rounded" title="报告预览" />
            </div>
          )}
        </>
      )}

      <style>{`.inp { width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 0.5rem; font-size: 0.875rem; outline: none; } .inp:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.15); } .btn-primary { padding: 0.625rem 1rem; background: #2563eb; color: white; border-radius: 0.5rem; font-size: 0.875rem; font-weight: 600; } .btn-primary:hover { background: #1d4ed8; } .btn-dark { padding: 0.625rem 1rem; background: #111827; color: white; border-radius: 0.5rem; font-size: 0.875rem; font-weight: 600; } .btn-dark:hover { background: #1f2937; }`}</style>
    </div>
  );
}

function OverdueOptions() {
  return (
    <>
      <option value="M1(1-30天)">M1（1-30天）</option>
      <option value="M2(31-60天)">M2（31-60天）</option>
      <option value="M3(61-90天)">M3（61-90天）</option>
      <option value="M4(91-120天)">M4（91-120天）</option>
      <option value="M5(121-150天)">M5（121-150天）</option>
      <option value="M6+(150天以上)">M6+（150天以上）</option>
    </>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
    </div>
  );
}

function CheckboxField({
  label,
  checked,
  disabled,
  onChange,
  text,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  onChange: (checked: boolean) => void;
  text: string;
}) {
  return (
    <Field label={label}>
      <label className="flex h-10 items-center gap-2 text-sm text-gray-700">
        <input type="checkbox" checked={checked} disabled={disabled} onChange={(event) => onChange(event.target.checked)} className="h-4 w-4 disabled:opacity-50" />
        {text}
      </label>
    </Field>
  );
}

function PathCard({
  title,
  best,
  unavailable,
  unavailableReason,
  children,
}: {
  title: string;
  best: boolean;
  unavailable?: boolean;
  unavailableReason?: string;
  children: React.ReactNode;
}) {
  const highlight = best && !unavailable ? "ring-2 ring-green-400 border-green-300" : "";
  const disabled = unavailable ? "opacity-60 grayscale" : "";
  return (
    <div className={`bg-white border rounded-xl p-4 relative ${highlight} ${disabled}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-sm text-gray-900">{title}</h3>
        {best && !unavailable && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">推荐</span>}
        {unavailable && <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full font-medium">不可用</span>}
      </div>
      {unavailable && unavailableReason && (
        <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
          {unavailableReason}
        </div>
      )}
      {children}
    </div>
  );
}

function Row({ label, value, red, green, bold }: { label: string; value: string; red?: boolean; green?: boolean; bold?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <span className={`text-gray-500 ${bold ? "font-semibold text-gray-700" : ""}`}>{label}</span>
      <span className={`${bold ? "font-bold text-lg" : "font-medium"} ${red ? "text-red-500" : ""} ${green ? "text-emerald-600" : ""}`}>
        {value}
      </span>
    </div>
  );
}
