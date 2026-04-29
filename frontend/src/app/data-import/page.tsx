"use client";

import { useEffect, useState } from "react";
import {
  clearPortfolioDataSource,
  listDataImportBatches,
  listDataImportRows,
  selectPortfolioDataSource,
  uploadCustomerDataImport,
  type DataImportBatchInfo,
  type DataImportRowInfo,
  type DataImportUploadResult,
} from "@/lib/api";

const importTypeOptions = [
  { value: "asset_ledger", label: "资产/逾期台账" },
  { value: "gps_export", label: "GPS/寻车线索" },
  { value: "legal_status", label: "法务/司法状态" },
  { value: "disposal_result", label: "处置结果复盘" },
];

const fieldLabels: Record<string, string> = {
  asset_identifier: "资产编号",
  contract_number: "合同号",
  debtor_name: "客户",
  car_description: "车辆",
  vin: "VIN",
  license_plate: "车牌",
  province: "省份",
  city: "城市",
  overdue_bucket: "逾期阶段",
  overdue_days: "逾期天数",
  overdue_amount: "逾期金额",
  loan_principal: "剩余本金",
  vehicle_value: "车辆估值",
  recovered_status: "车辆状态",
  gps_last_seen: "最近定位",
};

function fmt(n: number | null) {
  if (n === null || Number.isNaN(n)) return "-";
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function shortDate(value: string) {
  if (!value) return "-";
  return value.replace("T", " ").slice(0, 16);
}

function statusBadge(status: string) {
  if (status === "active") return "bg-blue-50 text-blue-700 border-blue-200";
  if (status === "parsed") return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (status === "archived") return "bg-slate-50 text-slate-600 border-slate-200";
  if (status === "empty") return "bg-slate-50 text-slate-600 border-slate-200";
  if (status === "failed") return "bg-red-50 text-red-700 border-red-200";
  return "bg-blue-50 text-blue-700 border-blue-200";
}

function statusLabel(status: string) {
  if (status === "active") return "分析中";
  if (status === "parsed") return "可用";
  if (status === "archived") return "已归档";
  if (status === "empty") return "空批次";
  if (status === "failed") return "失败";
  return status;
}

function canSelectAsPortfolioSource(batch: DataImportBatchInfo) {
  return batch.import_type === "asset_ledger" && batch.success_rows > 0;
}

function rowBadge(status: string) {
  return status === "valid"
    ? "bg-emerald-50 text-emerald-700 border-emerald-200"
    : "bg-orange-50 text-orange-700 border-orange-200";
}

export default function DataImportPage() {
  const [file, setFile] = useState<File | null>(null);
  const [sourceSystem, setSourceSystem] = useState("");
  const [importType, setImportType] = useState("asset_ledger");
  const [uploading, setUploading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [selectingSource, setSelectingSource] = useState(false);
  const [loadingRows, setLoadingRows] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [batches, setBatches] = useState<DataImportBatchInfo[]>([]);
  const [selectedBatch, setSelectedBatch] = useState<DataImportBatchInfo | null>(null);
  const [selectedSourceBatchIds, setSelectedSourceBatchIds] = useState<number[]>([]);
  const [rows, setRows] = useState<DataImportRowInfo[]>([]);
  const [rowStatus, setRowStatus] = useState("");
  const [uploadResult, setUploadResult] = useState<DataImportUploadResult | null>(null);

  async function loadBatches() {
    const data = await listDataImportBatches();
    setBatches(data);
    setSelectedSourceBatchIds(
      data
        .filter((batch) => batch.status === "active" && canSelectAsPortfolioSource(batch))
        .map((batch) => batch.id)
    );
    if (!selectedBatch && data.length > 0) {
      await loadRows(data[0], "");
    }
  }

  async function loadRows(batch: DataImportBatchInfo, status = rowStatus) {
    setLoadingRows(true);
    setError("");
    try {
      const data = await listDataImportRows(batch.id, status || undefined);
      setSelectedBatch(data.batch);
      setRows(data.rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载导入明细失败");
    } finally {
      setLoadingRows(false);
    }
  }

  useEffect(() => {
    loadBatches().catch((err) => {
      setError(err instanceof Error ? err.message : "加载导入批次失败");
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError("");
    setMessage("");
    setUploadResult(null);
    try {
      const result = await uploadCustomerDataImport({
        file,
        source_system: sourceSystem || undefined,
        import_type: importType,
      });
      setUploadResult(result);
      setSelectedBatch(result.batch);
      setRows(result.rows_preview);
      setMessage(
        `已接入 ${result.batch.total_rows} 行，${result.batch.success_rows} 行可用，${result.batch.error_rows} 行待处理`
      );
      const data = await listDataImportBatches();
      setBatches(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传解析失败");
    } finally {
      setUploading(false);
    }
  }

  function handleStatusFilter(status: string) {
    setRowStatus(status);
    if (selectedBatch) {
      loadRows(selectedBatch, status).catch((err) => {
        setError(err instanceof Error ? err.message : "筛选明细失败");
      });
    }
  }

  async function handleClearPortfolioSource() {
    const confirmed = window.confirm(
      "确认清空当前组合分析数据源？历史导入批次和行明细会保留，组合页会进入空状态，直到你上传新的资产/逾期台账。"
    );
    if (!confirmed) return;
    setClearing(true);
    setError("");
    setMessage("");
    try {
      const result = await clearPortfolioDataSource();
      setMessage(`${result.message}，本次归档 ${result.cleared_batches} 个批次`);
      await loadBatches();
    } catch (err) {
      setError(err instanceof Error ? err.message : "清空组合数据源失败");
    } finally {
      setClearing(false);
    }
  }

  function toggleSourceBatch(batch: DataImportBatchInfo) {
    if (!canSelectAsPortfolioSource(batch)) return;
    setSelectedSourceBatchIds((current) =>
      current.includes(batch.id)
        ? current.filter((id) => id !== batch.id)
        : [...current, batch.id]
    );
  }

  async function handleSelectPortfolioSource() {
    if (selectedSourceBatchIds.length === 0) return;
    const confirmed = window.confirm(
      `确认将已勾选的 ${selectedSourceBatchIds.length} 个批次合并设为组合分析数据源？未勾选的资产台账批次会保留历史但不参与本次分析。`
    );
    if (!confirmed) return;
    setSelectingSource(true);
    setError("");
    setMessage("");
    try {
      const result = await selectPortfolioDataSource(selectedSourceBatchIds);
      setMessage(`${result.message}，组合分析将合并这些批次的可用行`);
      await loadBatches();
    } catch (err) {
      setError(err instanceof Error ? err.message : "设置组合分析数据源失败");
    } finally {
      setSelectingSource(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">客户数据接入中心</h1>
        <p className="mt-1 text-sm text-gray-500">
          把客户原有核心系统、GPS系统或 Excel 台账导出的数据，先进入可审计接入台账，再转入资产池、动作中心和模型复盘。
        </p>
      </div>

      {message && (
        <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          {message}
        </div>
      )}
      {error && (
        <div className="rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <section className="grid gap-6 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="rounded-xl border bg-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">上传客户原始数据</h2>
              <p className="mt-1 text-sm text-gray-500">
                支持 .xlsx、.xls、.csv。系统会自动识别资产编号、合同号、车辆、逾期、区域、状态等常见字段。
              </p>
            </div>
            <span className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs font-medium text-blue-700">
              Staging first
            </span>
          </div>

          <div className="mt-5 grid gap-4 md:grid-cols-3">
            <label className="space-y-1 text-sm">
              <span className="font-medium text-gray-700">来源系统</span>
              <input
                value={sourceSystem}
                onChange={(event) => setSourceSystem(event.target.value)}
                placeholder="如：核心贷后系统 / GPS平台"
                className="w-full rounded-lg border px-3 py-2 outline-none focus:border-blue-400"
              />
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-gray-700">数据类型</span>
              <select
                value={importType}
                onChange={(event) => setImportType(event.target.value)}
                className="w-full rounded-lg border px-3 py-2 outline-none focus:border-blue-400"
              >
                {importTypeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span className="font-medium text-gray-700">选择文件</span>
              <input
                type="file"
                accept=".xlsx,.xls,.csv"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
                className="w-full rounded-lg border px-3 py-1.5 text-sm file:mr-3 file:rounded file:border-0 file:bg-slate-100 file:px-3 file:py-1.5"
              />
            </label>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {uploading ? "接入解析中..." : "上传并解析"}
            </button>
            <button
              onClick={handleClearPortfolioSource}
              disabled={clearing}
              className="rounded-lg border border-orange-200 bg-orange-50 px-4 py-2 text-sm font-medium text-orange-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {clearing ? "清空中..." : "清空当前组合分析数据源"}
            </button>
            <p className="text-xs text-gray-500">
              解析结果会保留历史批次；组合分析默认使用最新可用的资产/逾期台账。
            </p>
          </div>

          {uploadResult && (
            <div className="mt-5 rounded-lg border bg-slate-50 p-4">
              <div className="grid gap-3 md:grid-cols-4">
                <Metric label="总行数" value={`${uploadResult.batch.total_rows}`} />
                <Metric label="可用行" value={`${uploadResult.batch.success_rows}`} tone="green" />
                <Metric label="错误行" value={`${uploadResult.batch.error_rows}`} tone="orange" />
                <Metric label="识别字段" value={`${Object.keys(uploadResult.detected_columns).length}`} />
              </div>
              <div className="mt-4">
                <div className="text-xs font-semibold text-gray-500">字段映射</div>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(uploadResult.detected_columns).map(([field, column]) => (
                    <span
                      key={field}
                      className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-700"
                    >
                      {fieldLabels[field] || field} ← {column}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="rounded-xl border bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900">接入流程</h2>
          <div className="mt-4 space-y-4 text-sm text-gray-600">
            <Step index="1" title="客户导出" text="从原核心系统、GPS平台、法务系统导出 Excel/CSV。" />
            <Step index="2" title="字段识别" text="系统自动映射合同、车辆、逾期、区域、状态等字段。" />
            <Step index="3" title="校验台账" text="先看可用行和错误行，保留原始数据和标准化数据。" />
            <Step index="4" title="业务入池" text="下一阶段可一键转入资产池、生成拖车/拍卖工单或复盘样本。" />
          </div>
        </div>
      </section>

      <section className="grid gap-6 xl:grid-cols-[0.75fr_1.25fr]">
        <div className="rounded-xl border bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">最近接入批次</h2>
              <p className="mt-1 text-xs text-gray-500">
                勾选多个资产/逾期台账，可合并设为组合分析数据源。
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-gray-500">已选 {selectedSourceBatchIds.length} 个</span>
              <button
                onClick={handleSelectPortfolioSource}
                disabled={selectedSourceBatchIds.length === 0 || selectingSource}
                className="rounded-lg bg-blue-600 px-3 py-1.5 text-xs font-medium text-white disabled:cursor-not-allowed disabled:bg-blue-200"
              >
                {selectingSource ? "设置中..." : "设为组合分析数据源"}
              </button>
              <button
                onClick={() => loadBatches().catch(console.error)}
                className="text-xs font-medium text-blue-600 hover:text-blue-700"
              >
                刷新
              </button>
            </div>
          </div>
          <div className="mt-4 space-y-2">
            {batches.length === 0 && (
              <div className="rounded-lg border border-dashed p-6 text-center text-sm text-gray-400">
                暂无导入批次
              </div>
            )}
            {batches.map((batch) => (
              <div
                key={batch.id}
                className={`flex items-start gap-3 rounded-lg border p-3 transition ${
                  selectedBatch?.id === batch.id
                    ? "border-blue-200 bg-blue-50"
                    : "border-gray-100 hover:bg-gray-50"
                }`}
              >
                <label className="mt-0.5 flex items-center gap-2 text-xs text-gray-600">
                  <input
                    type="checkbox"
                    checked={selectedSourceBatchIds.includes(batch.id)}
                    disabled={!canSelectAsPortfolioSource(batch)}
                    onChange={() => toggleSourceBatch(batch)}
                    className="h-4 w-4 rounded border-gray-300"
                    aria-label={`选择批次 ${batch.id} 作为组合分析数据源`}
                  />
                </label>
                <button
                  type="button"
                  onClick={() => loadRows(batch).catch(console.error)}
                  className="min-w-0 flex-1 text-left"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="truncate text-sm font-semibold text-gray-900">
                      {batch.filename}
                    </div>
                    <span className={`rounded-full border px-2 py-0.5 text-xs ${statusBadge(batch.status)}`}>
                      {statusLabel(batch.status)}
                    </span>
                  </div>
                  <div className="mt-2 text-xs text-gray-500">
                    {batch.source_system || "未标注来源"} · {shortDate(batch.created_at)}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-3 text-xs">
                    <span>{batch.import_type}</span>
                    <span>总 {batch.total_rows}</span>
                    <span className="text-emerald-600">可用 {batch.success_rows}</span>
                    <span className="text-orange-600">错误 {batch.error_rows}</span>
                  </div>
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-xl border bg-white p-5 shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">明细预览</h2>
              <p className="text-sm text-gray-500">
                {selectedBatch ? `${selectedBatch.filename} · 批次 #${selectedBatch.id}` : "选择一个批次查看明细"}
              </p>
            </div>
            <select
              value={rowStatus}
              onChange={(event) => handleStatusFilter(event.target.value)}
              disabled={!selectedBatch}
              className="rounded-lg border px-3 py-2 text-sm disabled:bg-gray-100"
            >
              <option value="">全部行</option>
              <option value="valid">仅可用</option>
              <option value="error">仅错误</option>
            </select>
          </div>

          <div className="mt-4 overflow-x-auto">
            <table className="min-w-[980px] w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-3 py-2 text-left">行</th>
                  <th className="px-3 py-2 text-left">状态</th>
                  <th className="px-3 py-2 text-left">资产/合同</th>
                  <th className="px-3 py-2 text-left">客户/车辆</th>
                  <th className="px-3 py-2 text-left">区域</th>
                  <th className="px-3 py-2 text-left">逾期</th>
                  <th className="px-3 py-2 text-right">金额</th>
                  <th className="px-3 py-2 text-left">错误</th>
                </tr>
              </thead>
              <tbody>
                {loadingRows && (
                  <tr>
                    <td colSpan={8} className="px-3 py-8 text-center text-gray-400">
                      加载中...
                    </td>
                  </tr>
                )}
                {!loadingRows && rows.length === 0 && (
                  <tr>
                    <td colSpan={8} className="px-3 py-8 text-center text-gray-400">
                      暂无明细
                    </td>
                  </tr>
                )}
                {!loadingRows &&
                  rows.map((row) => (
                    <tr key={row.id} className="border-t align-top hover:bg-gray-50">
                      <td className="px-3 py-3 text-gray-500">{row.row_number}</td>
                      <td className="px-3 py-3">
                        <span className={`rounded-full border px-2 py-0.5 text-xs ${rowBadge(row.row_status)}`}>
                          {row.row_status === "valid" ? "可用" : "错误"}
                        </span>
                      </td>
                      <td className="px-3 py-3">
                        <div className="font-medium text-gray-900">{row.asset_identifier || "-"}</div>
                        <div className="text-xs text-gray-500">{row.contract_number || row.vin || "-"}</div>
                      </td>
                      <td className="px-3 py-3">
                        <div>{row.debtor_name || "-"}</div>
                        <div className="text-xs text-gray-500">{row.car_description || row.license_plate || "-"}</div>
                      </td>
                      <td className="px-3 py-3">
                        {[row.province, row.city].filter(Boolean).join(" / ") || "-"}
                      </td>
                      <td className="px-3 py-3">
                        <div>{row.overdue_bucket || "-"}</div>
                        <div className="text-xs text-gray-500">
                          {row.overdue_days === null ? "-" : `${row.overdue_days}天`} · {row.recovered_status || "状态未知"}
                        </div>
                      </td>
                      <td className="px-3 py-3 text-right">
                        <div>逾期 ¥{fmt(row.overdue_amount)}</div>
                        <div className="text-xs text-gray-500">估值 ¥{fmt(row.vehicle_value)}</div>
                      </td>
                      <td className="px-3 py-3 text-xs text-orange-700">
                        {row.errors.length === 0
                          ? "-"
                          : row.errors.map((item) => `${fieldLabels[item.field] || item.field}: ${item.message}`).join("；")}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>
    </div>
  );
}

function Metric({
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
        : "text-slate-900";
  return (
    <div className="rounded-lg border bg-white p-3">
      <div className="text-xs text-gray-500">{label}</div>
      <div className={`mt-1 text-xl font-bold ${toneClass}`}>{value}</div>
    </div>
  );
}

function Step({ index, title, text }: { index: string; title: string; text: string }) {
  return (
    <div className="flex gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white">
        {index}
      </div>
      <div>
        <div className="font-semibold text-gray-900">{title}</div>
        <div className="mt-0.5 text-gray-500">{text}</div>
      </div>
    </div>
  );
}
