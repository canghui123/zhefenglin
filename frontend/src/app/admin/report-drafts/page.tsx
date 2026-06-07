"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  listReportDrafts,
  type ReportDraftListItem,
  type ReportDraftStatus,
} from "@/lib/api";

const STATUS_LABELS: Record<ReportDraftStatus, string> = {
  draft: "草稿",
  submitted: "待复核",
  accepted: "已通过",
  rejected: "已驳回",
  needs_revision: "需修订",
};

const STATUS_STYLES: Record<ReportDraftStatus, string> = {
  draft: "bg-gray-100 text-gray-700",
  submitted: "bg-amber-100 text-amber-800",
  accepted: "bg-emerald-100 text-emerald-800",
  rejected: "bg-rose-100 text-rose-800",
  needs_revision: "bg-blue-100 text-blue-800",
};

const TYPE_LABELS: Record<string, string> = {
  executive_summary: "高管摘要",
  asset_package_brief: "资产包简报",
  buyer_offer_memo: "买方报价备忘录",
  weekly_operation_report: "周运营报告",
  custom: "自定义",
};

const DISTRIBUTION_LABELS: Record<string, string> = {
  draft_only: "仅草稿",
  internal: "内部分发",
  external: "对外披露",
};

const STATUS_FILTERS: { value: "" | ReportDraftStatus; label: string }[] = [
  { value: "", label: "全部" },
  { value: "draft", label: "草稿" },
  { value: "submitted", label: "待复核" },
  { value: "accepted", label: "已通过" },
  { value: "rejected", label: "已驳回" },
  { value: "needs_revision", label: "需修订" },
];

function formatTime(value: string | null): string {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return value;
  }
}

export default function ReportDraftsPage() {
  const [rows, setRows] = useState<ReportDraftListItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<"" | ReportDraftStatus>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await listReportDrafts(
        statusFilter ? { status: statusFilter } : undefined,
      );
      setRows(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "报告草稿加载失败");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">报告草稿</h1>
        <p className="text-sm text-gray-500 mt-1">
          AI 生成的报告草稿 / 人工复核 / 状态机闭环 (B3)
        </p>
      </div>

      <div className="mb-4 flex flex-wrap gap-2">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value || "all"}
            onClick={() => setStatusFilter(f.value)}
            className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
              statusFilter === f.value
                ? "bg-gray-900 text-white"
                : "bg-white text-gray-700 border border-gray-300 hover:bg-gray-50"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {error}
        </div>
      )}

      {loading ? (
        <div className="text-sm text-gray-500">加载中...</div>
      ) : rows.length === 0 ? (
        <div className="text-sm text-gray-500 p-8 text-center bg-white rounded-lg border border-gray-200">
          暂无草稿。AI 指挥中心生成报告草稿后会在此显示。
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr className="text-left">
                <th className="px-4 py-3 font-medium text-gray-700">ID</th>
                <th className="px-4 py-3 font-medium text-gray-700">类型</th>
                <th className="px-4 py-3 font-medium text-gray-700">标题</th>
                <th className="px-4 py-3 font-medium text-gray-700">状态</th>
                <th className="px-4 py-3 font-medium text-gray-700">分发</th>
                <th className="px-4 py-3 font-medium text-gray-700">置信度</th>
                <th className="px-4 py-3 font-medium text-gray-700">关联</th>
                <th className="px-4 py-3 font-medium text-gray-700">提交时间</th>
                <th className="px-4 py-3 font-medium text-gray-700">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rows.map((row) => {
                const status = row.status as ReportDraftStatus;
                return (
                  <tr key={row.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-600">#{row.id}</td>
                    <td className="px-4 py-3 text-gray-900">
                      {TYPE_LABELS[row.report_type] || row.report_type}
                    </td>
                    <td className="px-4 py-3 text-gray-900 max-w-[220px] truncate">
                      {row.title}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[status]}`}
                      >
                        {STATUS_LABELS[status] || status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {DISTRIBUTION_LABELS[row.distribution] || row.distribution}
                    </td>
                    <td className="px-4 py-3 text-gray-600">
                      {row.confidence_score != null
                        ? `${(row.confidence_score * 100).toFixed(0)}%`
                        : "-"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {row.related_object_type && row.related_object_id
                        ? `${row.related_object_type} #${row.related_object_id}`
                        : "-"}
                    </td>
                    <td className="px-4 py-3 text-gray-500 text-xs">
                      {formatTime(row.submitted_at || row.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <Link
                        href={`/admin/report-drafts/${row.id}`}
                        className="text-blue-600 hover:text-blue-800 text-sm"
                      >
                        查看 →
                      </Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
