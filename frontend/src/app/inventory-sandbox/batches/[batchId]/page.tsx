"use client";

import { useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  downloadReport,
  generateReport,
  getSandboxBatch,
  type SandboxBatchDetail,
  type SandboxResult,
} from "@/lib/api";
import { pollJob } from "@/lib/jobs";

const pathNames: Record<string, string> = {
  A: "等待赎车",
  B: "常规诉讼",
  C: "立即竞拍",
  D: "担保物权特别程序",
  E: "分期重组/和解",
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

function badge(status: string) {
  if (status === "success") return "border-emerald-200 bg-emerald-50 text-emerald-700";
  if (status === "error") return "border-red-200 bg-red-50 text-red-700";
  return "border-slate-200 bg-slate-50 text-slate-600";
}

export default function SandboxBatchDetailPage() {
  const params = useParams();
  const rawBatchId = params?.batchId;
  const batchId = Number(Array.isArray(rawBatchId) ? rawBatchId[0] : rawBatchId);
  const [data, setData] = useState<SandboxBatchDetail | null>(null);
  const [activeItemId, setActiveItemId] = useState<number | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [reportLoading, setReportLoading] = useState(false);
  const [reportHtml, setReportHtml] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (!Number.isFinite(batchId) || batchId <= 0) {
      setError("批次编号不合法");
      setLoading(false);
      return;
    }
    setLoading(true);
    getSandboxBatch(batchId)
      .then((nextData) => {
        setData(nextData);
        const firstSuccess = nextData.items.find((item) => item.status === "success");
        setActiveItemId(firstSuccess?.id || nextData.items[0]?.id || null);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "加载批量模拟详情失败");
      })
      .finally(() => setLoading(false));
  }, [batchId]);

  const visibleItems = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return (data?.items || []).filter((item) => {
      if (statusFilter && item.status !== statusFilter) return false;
      if (!keyword) return true;
      return [
        item.row_number.toString(),
        item.car_description || "",
        item.overdue_bucket || "",
        item.best_path || "",
        item.error || "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(keyword);
    });
  }, [data, search, statusFilter]);

  const activeItem =
    data?.items.find((item) => item.id === activeItemId) ||
    data?.items.find((item) => item.status === "success") ||
    data?.items[0] ||
    null;
  const activeResult = activeItem?.result || null;

  async function handleReport() {
    if (!activeItem?.sandbox_result_id) return;
    setReportLoading(true);
    setMessage("");
    setError("");
    setReportHtml("");
    try {
      const { job_id } = await generateReport(activeItem.sandbox_result_id);
      const job = await pollJob(job_id);
      if (job.status === "failed") throw new Error(job.error_message || "报告生成失败");
      setReportHtml(await downloadReport(activeItem.sandbox_result_id));
      setMessage(`第${activeItem.row_number}行报告已生成`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "报告生成失败");
    } finally {
      setReportLoading(false);
    }
  }

  function printReport() {
    const win = window.open("", "_blank");
    if (!win) return;
    win.document.write(reportHtml);
    win.document.close();
    win.print();
  }

  if (loading) return <div className="py-20 text-center text-gray-500">加载批量模拟详情中...</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/inventory-sandbox" className="text-sm font-medium text-blue-600 hover:text-blue-700">
            返回库存决策沙盘
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">批量模拟结果详情</h1>
          <p className="mt-1 text-sm text-gray-500">
            查看本批次每台车的推荐路径、完整五路径结果、失败原因，并可针对单台生成报告。
          </p>
        </div>
        {data && (
          <div className="rounded-xl border bg-white px-4 py-3 text-sm text-gray-600">
            <div className="font-semibold text-gray-900">批次 #{data.batch.id}</div>
            <div>生成时间：{shortDate(data.batch.created_at)}</div>
          </div>
        )}
      </div>

      {message && <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">{message}</div>}
      {error && <div className="rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>}

      {data && (
        <>
          <section className="grid gap-4 md:grid-cols-4">
            <Stat label="总行数" value={`${data.batch.total_rows} 台`} />
            <Stat label="成功" value={`${data.batch.success_rows} 台`} tone="green" />
            <Stat label="失败" value={`${data.batch.error_rows} 台`} tone="red" />
            <Stat label="状态" value={data.batch.status === "completed" ? "已完成" : data.batch.status} />
          </section>

          <section className="rounded-xl border bg-white p-5">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="font-semibold text-gray-900">车辆明细</h2>
                <p className="mt-1 text-sm text-gray-500">点击单行可以在下方查看该车完整路径计算结果。</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <input
                  className="inp w-56"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="搜索车辆/路径/失败原因"
                />
                <select className="inp w-36" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                  <option value="">全部状态</option>
                  <option value="success">成功</option>
                  <option value="error">失败</option>
                </select>
              </div>
            </div>

            <div className="mt-4 overflow-x-auto rounded-lg border">
              <table className="min-w-[980px] w-full text-sm">
                <thead className="bg-gray-50 text-xs text-gray-500">
                  <tr>
                    <th className="px-3 py-2 text-left">行号</th>
                    <th className="px-3 py-2 text-left">状态</th>
                    <th className="px-3 py-2 text-left">车辆</th>
                    <th className="px-3 py-2 text-left">逾期阶段</th>
                    <th className="px-3 py-2 text-left">逾期金额</th>
                    <th className="px-3 py-2 text-left">估值</th>
                    <th className="px-3 py-2 text-left">推荐路径</th>
                    <th className="px-3 py-2 text-left">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleItems.map((item) => (
                    <tr key={item.id} className={`border-t ${item.id === activeItem?.id ? "bg-blue-50/60" : ""}`}>
                      <td className="px-3 py-3">第{item.row_number}行</td>
                      <td className="px-3 py-3">
                        <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${badge(item.status)}`}>
                          {item.status === "success" ? "成功" : "失败"}
                        </span>
                      </td>
                      <td className="px-3 py-3">{item.car_description || "-"}</td>
                      <td className="px-3 py-3">{item.overdue_bucket || "-"}</td>
                      <td className="px-3 py-3">¥{fmt(item.overdue_amount)}</td>
                      <td className="px-3 py-3">¥{fmt(item.che300_value)}</td>
                      <td className="px-3 py-3">
                        {item.best_path ? `路径${item.best_path} · ${pathNames[item.best_path] || item.best_path}` : item.error || "-"}
                      </td>
                      <td className="px-3 py-3">
                        <button
                          className="rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                          onClick={() => setActiveItemId(item.id)}
                        >
                          查看详情
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-xl border bg-white p-5">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="font-semibold text-gray-900">
                  {activeItem ? `第${activeItem.row_number}行：${activeItem.car_description || "未命名车辆"}` : "未选择车辆"}
                </h2>
                <p className="mt-1 text-sm text-gray-500">
                  {activeResult
                    ? `推荐路径：路径${activeResult.best_path} · ${pathNames[activeResult.best_path] || activeResult.best_path}`
                    : activeItem?.error || "该行没有可展示的模拟结果"}
                </p>
              </div>
              {activeItem?.sandbox_result_id && (
                <button
                  className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:bg-slate-300"
                  onClick={handleReport}
                  disabled={reportLoading}
                >
                  {reportLoading ? "生成报告中..." : "生成该车报告"}
                </button>
              )}
            </div>

            {activeResult && <ResultDetail result={activeResult} />}

            {reportHtml && (
              <div className="mt-5 rounded-lg border bg-slate-50 p-3">
                <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                  <div className="font-semibold text-gray-900">报告预览</div>
                  <button className="rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white hover:bg-blue-700" onClick={printReport}>
                    打印/保存PDF
                  </button>
                </div>
                <iframe title="sandbox-batch-report" srcDoc={reportHtml} className="h-[520px] w-full rounded border bg-white" />
              </div>
            )}
          </section>
        </>
      )}

      <style>{`.inp { padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 0.5rem; font-size: 0.875rem; outline: none; } .inp:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.15); }`}</style>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: "green" | "red" }) {
  const color = tone === "green" ? "text-emerald-600" : tone === "red" ? "text-red-600" : "text-gray-900";
  return (
    <div className="rounded-xl border bg-white p-4">
      <div className="text-sm text-gray-500">{label}</div>
      <div className={`mt-1 text-2xl font-bold ${color}`}>{value}</div>
    </div>
  );
}

function ResultDetail({ result }: { result: SandboxResult }) {
  const expectedLitigation = result.path_b.scenarios[1] || result.path_b.scenarios[0];
  const finalWait = result.path_a.timepoints[result.path_a.timepoints.length - 1];

  return (
    <div className="mt-5 grid gap-4 lg:grid-cols-2 xl:grid-cols-3">
      <PathPanel title="路径A：等待赎车" best={result.best_path === "A"} available={result.path_a.available}>
        <Metric label="成功率" value={rate(result.path_a.success_probability)} />
        <Metric label="最长观察净头寸" value={`¥${fmt(finalWait?.net_position)}`} />
        <Metric label="未来边际净收益" value={`¥${fmt(result.path_a.future_marginal_net_benefit)}`} strong />
      </PathPanel>

      <PathPanel title="路径B：常规诉讼" best={result.best_path === "B"}>
        <Metric label="预期情景" value={expectedLitigation?.label || "-"} />
        <Metric label="动态成功率" value={rate(result.path_b.success_probability)} />
        <Metric label="未来边际净收益" value={`¥${fmt(result.path_b.future_marginal_net_benefit)}`} strong />
      </PathPanel>

      <PathPanel title="路径C：立即竞拍" best={result.best_path === "C"} available={result.path_c.available} reason={result.path_c.unavailable_reason}>
        <Metric label="竞拍折扣" value={rate(result.path_c.auction_discount_rate)} />
        <Metric label="预计成交价" value={`¥${fmt(result.path_c.sale_price)}`} />
        <Metric label="未来边际净收益" value={`¥${fmt(result.path_c.future_marginal_net_benefit)}`} strong />
      </PathPanel>

      <PathPanel title="路径D：担保物权特别程序" best={result.best_path === "D"} available={result.path_d.available} reason={result.path_d.unavailable_reason}>
        <Metric label="周期" value={`约${result.path_d.duration_months}个月`} />
        <Metric label="期望拍卖价" value={`¥${fmt(result.path_d.expected_auction_price)}`} />
        <Metric label="未来边际净收益" value={`¥${fmt(result.path_d.future_marginal_net_benefit)}`} strong />
      </PathPanel>

      <PathPanel title="路径E：分期重组/和解" best={result.best_path === "E"}>
        <Metric label="月还款额" value={`¥${fmt(result.path_e.monthly_payment)}`} />
        <Metric label="再违约率" value={rate(result.path_e.redefault_rate)} />
        <Metric label="未来边际净收益" value={`¥${fmt(result.path_e.future_marginal_net_benefit)}`} strong />
      </PathPanel>

      <div className="rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-800 xl:col-span-1">
        <div className="font-semibold">系统推荐理由</div>
        <div className="mt-2 whitespace-pre-line leading-6">{result.recommendation}</div>
      </div>
    </div>
  );
}

function PathPanel({
  title,
  best,
  available = true,
  reason = "",
  children,
}: {
  title: string;
  best: boolean;
  available?: boolean;
  reason?: string;
  children: ReactNode;
}) {
  return (
    <div className={`rounded-xl border bg-white p-4 ${best && available ? "ring-2 ring-emerald-300" : ""} ${available ? "" : "opacity-65 grayscale"}`}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-semibold text-gray-900">{title}</h3>
        {best && available && <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-700">推荐</span>}
        {!available && <span className="rounded-full bg-gray-200 px-2 py-0.5 text-xs font-medium text-gray-600">不可用</span>}
      </div>
      {reason && <div className="mb-3 rounded bg-amber-50 p-2 text-xs text-amber-800">{reason}</div>}
      <div className="space-y-2 text-sm">{children}</div>
    </div>
  );
}

function Metric({ label, value, strong }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-gray-500">{label}</span>
      <span className={strong ? "font-bold text-emerald-600" : "font-medium text-gray-900"}>{value}</span>
    </div>
  );
}
