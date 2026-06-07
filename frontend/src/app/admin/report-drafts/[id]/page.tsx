"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  getReportDraft,
  transitionReportDraft,
  type ReportDraftAction,
  type ReportDraftDetail,
  type ReportDraftStatus,
  type ReportDraftDistribution,
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
  draft_only: "仅草稿(不可外发)",
  internal: "内部分发",
  external: "对外披露",
};

function formatTime(value: string | null | undefined): string {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return value;
  }
}

interface Section {
  heading?: string;
  body?: string;
}

export default function ReportDraftDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params?.id);

  const [draft, setDraft] = useState<ReportDraftDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [actionLoading, setActionLoading] = useState(false);
  const [notes, setNotes] = useState("");
  const [distribution, setDistribution] =
    useState<ReportDraftDistribution>("internal");

  const load = useCallback(async () => {
    if (!id || Number.isNaN(id)) return;
    setLoading(true);
    setError("");
    try {
      setDraft(await getReportDraft(id));
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleTransition(action: ReportDraftAction) {
    if (!draft) return;
    setActionLoading(true);
    setError("");
    try {
      const updated = await transitionReportDraft(draft.id, {
        action,
        notes: notes.trim() || undefined,
        distribution: action === "accept" ? distribution : undefined,
      });
      setDraft(updated);
      setNotes("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setActionLoading(false);
    }
  }

  if (loading) {
    return <div className="text-sm text-gray-500">加载中...</div>;
  }
  if (!draft) {
    return (
      <div>
        <div className="text-sm text-red-600 mb-4">{error || "草稿不存在"}</div>
        <Link
          href="/admin/report-drafts"
          className="text-blue-600 hover:text-blue-800 text-sm"
        >
          ← 返回列表
        </Link>
      </div>
    );
  }

  const status = draft.status as ReportDraftStatus;
  const sections = (draft.content_json?.sections as Section[]) || [];
  const checklistItems =
    (draft.review_checklist_json?.items as string[]) || [];
  const missingData = (draft.content_json?.missing_data as string[]) || [];
  const dataQualityNotes =
    (draft.content_json?.data_quality_notes as string[]) || [];
  const allowedActions =
    (draft.content_json?.allowed_actions as string[]) || [];
  const forbiddenActions =
    (draft.content_json?.forbidden_actions as string[]) || [];

  return (
    <div>
      <Link
        href="/admin/report-drafts"
        className="text-blue-600 hover:text-blue-800 text-sm inline-block mb-4"
      >
        ← 返回列表
      </Link>

      {/* Header */}
      <div className="bg-white rounded-lg border border-gray-200 p-6 mb-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span
                className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[status]}`}
              >
                {STATUS_LABELS[status] || status}
              </span>
              <span className="text-xs text-gray-500">
                {TYPE_LABELS[draft.report_type] || draft.report_type}
              </span>
              <span className="text-xs text-gray-400">#{draft.id}</span>
            </div>
            <h1 className="text-xl font-bold text-gray-900">{draft.title}</h1>
            <div className="mt-2 text-xs text-gray-500">
              分发: {DISTRIBUTION_LABELS[draft.distribution] || draft.distribution}
              {draft.confidence_score != null && (
                <>
                  {" · "}置信度: {(draft.confidence_score * 100).toFixed(0)}%
                </>
              )}
              {draft.requires_human_review && (
                <span className="ml-2 text-amber-700">
                  ⚠ requires_human_review
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs text-gray-600 border-t border-gray-100 pt-4">
          <div>
            <div className="text-gray-400">创建</div>
            <div>{formatTime(draft.created_at)}</div>
          </div>
          <div>
            <div className="text-gray-400">提交</div>
            <div>{formatTime(draft.submitted_at)}</div>
          </div>
          <div>
            <div className="text-gray-400">复核</div>
            <div>{formatTime(draft.reviewed_at)}</div>
          </div>
          <div>
            <div className="text-gray-400">关联</div>
            <div>
              {draft.related_object_type
                ? `${draft.related_object_type} #${draft.related_object_id}`
                : "-"}
            </div>
          </div>
        </div>

        {draft.review_notes && (
          <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded text-sm">
            <div className="text-xs text-amber-700 font-medium mb-1">
              复核备注
            </div>
            <div className="text-gray-800">{draft.review_notes}</div>
          </div>
        )}
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
          {error}
        </div>
      )}

      {/* Main content + sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: report content */}
        <div className="lg:col-span-2 space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h2 className="text-base font-semibold text-gray-900 mb-4">
              报告内容
            </h2>
            {sections.length === 0 ? (
              <div className="text-sm text-gray-500">暂无内容</div>
            ) : (
              <div className="space-y-4">
                {sections.map((sec, idx) => (
                  <div key={idx}>
                    <h3 className="text-sm font-semibold text-gray-900 mb-1">
                      {sec.heading || `Section ${idx + 1}`}
                    </h3>
                    <p className="text-sm text-gray-700 leading-relaxed">
                      {sec.body || "(空)"}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>

          {missingData.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-amber-800 mb-2">
                缺失数据
              </h3>
              <ul className="text-sm text-gray-700 space-y-1 list-disc list-inside">
                {missingData.map((m, i) => (
                  <li key={i}>{m}</li>
                ))}
              </ul>
            </div>
          )}

          {dataQualityNotes.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-700 mb-2">
                数据质量说明
              </h3>
              <ul className="text-sm text-gray-700 space-y-1 list-disc list-inside">
                {dataQualityNotes.map((n, i) => (
                  <li key={i}>{n}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Right: review controls + checklist */}
        <div className="space-y-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-3">
              复核操作
            </h3>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="复核备注(可选,记录到 audit log)"
              className="w-full text-sm border border-gray-300 rounded p-2 mb-3"
              rows={3}
              disabled={actionLoading}
            />

            {status === "accepted" && (
              <div className="mb-3">
                <label className="text-xs text-gray-600 block mb-1">
                  分发范围(仅 accepted 可配)
                </label>
                <select
                  value={distribution}
                  onChange={(e) =>
                    setDistribution(e.target.value as ReportDraftDistribution)
                  }
                  className="w-full text-sm border border-gray-300 rounded p-2"
                >
                  <option value="draft_only">仅草稿</option>
                  <option value="internal">内部分发</option>
                  <option value="external">对外披露</option>
                </select>
              </div>
            )}

            <div className="space-y-2">
              {status === "draft" || status === "needs_revision" ? (
                <button
                  onClick={() => handleTransition("submit")}
                  disabled={actionLoading}
                  className="w-full px-3 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded disabled:opacity-50"
                >
                  提交复核
                </button>
              ) : null}

              {status === "submitted" ? (
                <>
                  <div className="mb-3">
                    <label className="text-xs text-gray-600 block mb-1">
                      通过时设置分发范围
                    </label>
                    <select
                      value={distribution}
                      onChange={(e) =>
                        setDistribution(
                          e.target.value as ReportDraftDistribution,
                        )
                      }
                      className="w-full text-sm border border-gray-300 rounded p-2"
                    >
                      <option value="draft_only">仅草稿</option>
                      <option value="internal">内部分发</option>
                      <option value="external">对外披露</option>
                    </select>
                  </div>
                  <button
                    onClick={() => handleTransition("accept")}
                    disabled={actionLoading}
                    className="w-full px-3 py-2 bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium rounded disabled:opacity-50"
                  >
                    通过 (admin)
                  </button>
                  <button
                    onClick={() => handleTransition("request_revision")}
                    disabled={actionLoading}
                    className="w-full px-3 py-2 bg-amber-500 hover:bg-amber-600 text-white text-sm font-medium rounded disabled:opacity-50"
                  >
                    要求修订 (admin)
                  </button>
                  <button
                    onClick={() => handleTransition("reject")}
                    disabled={actionLoading}
                    className="w-full px-3 py-2 bg-rose-600 hover:bg-rose-700 text-white text-sm font-medium rounded disabled:opacity-50"
                  >
                    驳回 (admin)
                  </button>
                </>
              ) : null}

              {(status === "accepted" || status === "rejected") && (
                <div className="text-xs text-gray-500 text-center py-2">
                  当前已是终态,如需继续请重新生成草稿
                </div>
              )}
            </div>
          </div>

          {checklistItems.length > 0 && (
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-2">
                复核清单
              </h3>
              <ul className="text-sm text-gray-700 space-y-1.5">
                {checklistItems.map((item, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <input type="checkbox" className="mt-1" disabled />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(allowedActions.length > 0 || forbiddenActions.length > 0) && (
            <div className="bg-white rounded-lg border border-gray-200 p-4">
              <h3 className="text-sm font-semibold text-gray-900 mb-2">
                业务边界
              </h3>
              {allowedActions.length > 0 && (
                <div className="mb-2">
                  <div className="text-xs text-emerald-700 font-medium mb-1">
                    允许动作
                  </div>
                  <ul className="text-xs text-gray-700 space-y-0.5 list-disc list-inside">
                    {allowedActions.map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}
              {forbiddenActions.length > 0 && (
                <div>
                  <div className="text-xs text-rose-700 font-medium mb-1">
                    禁止动作
                  </div>
                  <ul className="text-xs text-gray-700 space-y-0.5 list-disc list-inside">
                    {forbiddenActions.map((a, i) => (
                      <li key={i}>{a}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
