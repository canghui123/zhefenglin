"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ClipboardCheck, FileSearch, RefreshCw, Save, ShieldCheck } from "lucide-react";

import { AdminAccess } from "@/components/admin/admin-access";
import {
  createAiAgentRunReview,
  getAiAgentRunReviewInsights,
  getAiAgentRuleSettings,
  listAiAgentRuleProfiles,
  listAiAgentRunReviews,
  listAiDecisionAuditLogs,
  updateAiAgentRuleSettings,
  type AgentReviewInsight,
  type AgentRuleProfileSummary,
  type AgentRuleSettings,
  type AgentRuleSettingsInput,
  type AgentRunReview,
  type AgentRunReviewInput,
  type DecisionAuditLog,
} from "@/lib/api";

type NumericSettingKey = Exclude<keyof AgentRuleSettingsInput, "agent_type" | "scenario" | "is_active">;

const SETTING_FIELDS: Array<{
  key: NumericSettingKey;
  label: string;
  description: string;
  step?: string;
}> = [
  {
    key: "operation_high_priority_limit",
    label: "运营高优先级池上限",
    description: "operation_planning_agent 输出高优先级/暂缓/递延池的最大分层数。",
  },
  {
    key: "operation_data_gap_min_count",
    label: "资料缺口入池阈值",
    description: "资产包资料缺口达到该数量后进入补资料池。",
  },
  {
    key: "task_max_drafts",
    label: "任务草稿上限",
    description: "task_generation_agent 单次最多生成的草稿任务数量。",
  },
  {
    key: "task_urgent_deadline_days",
    label: "紧急任务建议天数",
    description: "高优先级任务草稿的默认截止时间。",
  },
  {
    key: "task_normal_deadline_days",
    label: "普通任务建议天数",
    description: "中低优先级任务草稿的默认截止时间。",
  },
  {
    key: "cost_budget_warning_percent",
    label: "成本预算预警比例",
    description: "预计成本超过月预算该比例后触发预算预警。",
    step: "0.05",
  },
  {
    key: "cost_condition_call_approval_threshold",
    label: "高级车况审批阈值",
    description: "高级车况调用量达到该值后建议提交管理员复核。",
  },
  {
    key: "cost_ai_report_merge_threshold",
    label: "AI 报告合并阈值",
    description: "AI 报告数量达到该值后建议合并报告。",
  },
  {
    key: "report_confidence_floor",
    label: "报告草稿置信度下限",
    description: "report_generation_agent 输出置信度的最低展示值。",
    step: "0.05",
  },
  {
    key: "report_max_sections",
    label: "报告草稿章节上限",
    description: "报告草稿最多保留的章节数量。",
  },
];

const DEFAULT_REVIEW: AgentRunReviewInput = {
  outcome: "partial",
  usefulness_score: 3,
  accuracy_score: 3,
  accepted_actions_count: 0,
  rejected_actions_count: 0,
  follow_up_required: false,
  feedback: "",
};

const RULE_AGENT_OPTIONS = [
  "global",
  "operation_planning_agent",
  "task_generation_agent",
  "report_generation_agent",
  "cost_control_agent",
];

function formatTime(value: string | null | undefined) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function jsonText(value: unknown) {
  try {
    return JSON.stringify(value ?? {}, null, 2);
  } catch {
    return String(value);
  }
}

function toSettingsInput(settings: AgentRuleSettings): AgentRuleSettingsInput {
  return {
    agent_type: settings.agent_type || "global",
    scenario: settings.scenario || "default",
    is_active: settings.is_active,
    operation_high_priority_limit: settings.operation_high_priority_limit,
    operation_data_gap_min_count: settings.operation_data_gap_min_count,
    task_max_drafts: settings.task_max_drafts,
    task_urgent_deadline_days: settings.task_urgent_deadline_days,
    task_normal_deadline_days: settings.task_normal_deadline_days,
    cost_budget_warning_percent: settings.cost_budget_warning_percent,
    cost_condition_call_approval_threshold: settings.cost_condition_call_approval_threshold,
    cost_ai_report_merge_threshold: settings.cost_ai_report_merge_threshold,
    report_confidence_floor: settings.report_confidence_floor,
    report_max_sections: settings.report_max_sections,
  };
}

function InsightPanel({ insight }: { insight: AgentReviewInsight | null }) {
  if (!insight) {
    return <p className="text-sm text-gray-400">暂无复盘洞察</p>;
  }

  return (
    <div className="rounded-lg border border-blue-100 bg-blue-50 p-3">
      <div className="text-sm font-semibold text-blue-950">复盘洞察</div>
      <div className="mt-3 grid gap-2 text-xs text-blue-900 md:grid-cols-2">
        <div>样本数：{insight.review_count}</div>
        <div>采纳率：{Math.round(insight.acceptance_rate * 100)}%</div>
        <div>有用性均分：{insight.average_usefulness_score}</div>
        <div>准确性均分：{insight.average_accuracy_score}</div>
      </div>
      <ul className="mt-3 space-y-1">
        {insight.recommendations.map((item) => (
          <li key={item} className="text-xs leading-5 text-blue-900">
            {item}
          </li>
        ))}
      </ul>
      {insight.requires_human_review && (
        <div className="mt-3 text-xs font-medium text-amber-700">洞察只作为阈值调整建议，仍需人工确认。</div>
      )}
    </div>
  );
}

function LogTable({ logs }: { logs: DecisionAuditLog[] }) {
  if (logs.length === 0) {
    return <p className="py-10 text-center text-sm text-gray-400">暂无 AI 审计日志</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-xs text-gray-500">
          <tr>
            <th className="px-3 py-2 text-left">时间</th>
            <th className="px-3 py-2 text-left">决策类型</th>
            <th className="px-3 py-2 text-left">动作</th>
            <th className="px-3 py-2 text-left">Run</th>
            <th className="px-3 py-2 text-left">人工复核</th>
            <th className="px-3 py-2 text-left">结果摘要</th>
          </tr>
        </thead>
        <tbody>
          {logs.map((row) => (
            <tr key={row.id} className="border-t">
              <td className="px-3 py-2 text-xs text-gray-500">{formatTime(row.created_at)}</td>
              <td className="px-3 py-2 font-medium text-gray-900">{row.decision_type}</td>
              <td className="px-3 py-2 text-gray-600">{row.action}</td>
              <td className="px-3 py-2 text-gray-600">{row.agent_run_id ? `#${row.agent_run_id}` : "-"}</td>
              <td className="px-3 py-2">
                {row.requires_human_review ? (
                  <span className="rounded-full bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700">
                    required
                  </span>
                ) : (
                  <span className="text-xs text-gray-400">-</span>
                )}
              </td>
              <td className="px-3 py-2">
                <pre className="max-h-20 max-w-xl overflow-auto whitespace-pre-wrap rounded-md bg-gray-50 p-2 text-[11px] text-gray-500">
                  {jsonText(row.after)}
                </pre>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ReviewList({ reviews }: { reviews: AgentRunReview[] }) {
  if (reviews.length === 0) {
    return <p className="text-sm text-gray-400">暂无复盘记录</p>;
  }
  return (
    <div className="space-y-3">
      {reviews.map((review) => (
        <div key={review.id} className="rounded-lg border border-gray-100 p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <div className="text-sm font-semibold text-gray-900">
                Run #{review.agent_run_id} · {review.outcome}
              </div>
              <div className="mt-1 text-xs text-gray-500">
                useful={review.usefulness_score} · accuracy={review.accuracy_score} ·{" "}
                {formatTime(review.created_at)}
              </div>
            </div>
            {review.follow_up_required && (
              <span className="rounded-full bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700">
                需后续跟进
              </span>
            )}
          </div>
          {review.feedback && <p className="mt-2 text-sm leading-5 text-gray-600">{review.feedback}</p>}
        </div>
      ))}
    </div>
  );
}

export default function AiAuditLogsPage() {
  const [settings, setSettings] = useState<AgentRuleSettings | null>(null);
  const [profiles, setProfiles] = useState<AgentRuleProfileSummary[]>([]);
  const [insight, setInsight] = useState<AgentReviewInsight | null>(null);
  const [logs, setLogs] = useState<DecisionAuditLog[]>([]);
  const [reviews, setReviews] = useState<AgentRunReview[]>([]);
  const [reviewRunId, setReviewRunId] = useState("");
  const [review, setReview] = useState<AgentRunReviewInput>(DEFAULT_REVIEW);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const latestRunId = useMemo(() => {
    const runId = logs.find((row) => row.agent_run_id)?.agent_run_id;
    return runId ? String(runId) : "";
  }, [logs]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [nextSettings, nextProfiles, nextInsight, nextLogs, nextReviews] = await Promise.all([
        getAiAgentRuleSettings(),
        listAiAgentRuleProfiles(),
        getAiAgentRunReviewInsights(),
        listAiDecisionAuditLogs(50),
        listAiAgentRunReviews(20),
      ]);
      setSettings(nextSettings);
      setProfiles(nextProfiles);
      setInsight(nextInsight);
      setLogs(nextLogs);
      setReviews(nextReviews);
      setReviewRunId((current) => current || (nextLogs.find((row) => row.agent_run_id)?.agent_run_id?.toString() ?? ""));
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 审计日志加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function updateSetting(key: NumericSettingKey, value: string) {
    if (!settings) return;
    const numericValue = Number(value);
    setSettings({
      ...settings,
      [key]: Number.isFinite(numericValue) ? numericValue : 0,
    });
  }

  async function handleLoadProfile(profile: AgentRuleProfileSummary) {
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const nextSettings = await getAiAgentRuleSettings({
        agent_type: profile.agent_type,
        scenario: profile.scenario,
      });
      setSettings(nextSettings);
      setMessage(`已加载 ${profile.agent_type}/${profile.scenario} v${profile.version}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "规则 profile 加载失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleSaveSettings() {
    if (!settings) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const saved = await updateAiAgentRuleSettings(toSettingsInput(settings));
      setSettings(saved);
      setMessage("阈值配置已保存，后续 Agent run 将使用新配置。");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "阈值配置保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleCreateReview() {
    const runId = Number(reviewRunId || latestRunId);
    if (!Number.isFinite(runId) || runId <= 0) {
      setError("请输入有效的 Agent run ID");
      return;
    }
    setSaving(true);
    setError("");
    setMessage("");
    try {
      await createAiAgentRunReview(runId, review);
      setReview(DEFAULT_REVIEW);
      setMessage("复盘记录已创建，并写入 AI 决策审计日志。");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "复盘记录创建失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <AdminAccess minRole="admin">
      <div className="space-y-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">AI 审计日志</h1>
            <p className="mt-1 text-sm text-gray-500">
              管理 Agent 决策留痕、规则阈值和人工复盘，确保 AI 输出可追踪、可复核。
            </p>
          </div>
          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex h-10 items-center gap-2 rounded-lg border px-4 text-sm text-gray-700"
          >
            <RefreshCw className="h-4 w-4" />
            刷新
          </button>
        </div>

        <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-800">
          <ShieldCheck className="h-4 w-4" />
          Agent 仍只生成建议、草稿和预警；阈值变更与复盘记录都会进入审计留痕。
        </div>

        {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}
        {message && (
          <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-700">
            {message}
          </div>
        )}

        {loading ? (
          <div className="py-20 text-center text-gray-500">AI 审计日志加载中...</div>
        ) : (
          <>
            <section className="rounded-lg border bg-white p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <ShieldCheck className="h-5 w-5 text-blue-600" />
                  <h2 className="text-lg font-semibold text-gray-900">规则阈值配置</h2>
                </div>
                <button
                  type="button"
                  onClick={handleSaveSettings}
                  disabled={saving || !settings}
                  className="inline-flex h-9 items-center gap-2 rounded-lg bg-blue-600 px-3 text-sm font-medium text-white disabled:bg-gray-300"
                >
                  <Save className="h-4 w-4" />
                  保存阈值
                </button>
              </div>
              {settings ? (
                <>
                  <div className="mb-4 grid gap-3 md:grid-cols-4">
                    <label className="grid gap-1 text-sm text-gray-600">
                      Agent profile
                      <select
                        value={settings.agent_type}
                        onChange={(event) => setSettings({ ...settings, agent_type: event.target.value })}
                        className="h-10 rounded-lg border border-gray-200 px-3 text-sm text-gray-900"
                      >
                        {RULE_AGENT_OPTIONS.map((item) => (
                          <option key={item} value={item}>
                            {item}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="grid gap-1 text-sm text-gray-600">
                      场景
                      <input
                        value={settings.scenario}
                        onChange={(event) => setSettings({ ...settings, scenario: event.target.value || "default" })}
                        className="h-10 rounded-lg border border-gray-200 px-3 text-sm text-gray-900"
                      />
                    </label>
                    <label className="grid gap-1 text-sm text-gray-600">
                      状态
                      <select
                        value={settings.is_active ? "true" : "false"}
                        onChange={(event) => setSettings({ ...settings, is_active: event.target.value === "true" })}
                        className="h-10 rounded-lg border border-gray-200 px-3 text-sm text-gray-900"
                      >
                        <option value="true">启用</option>
                        <option value="false">停用</option>
                      </select>
                    </label>
                    <div className="rounded-lg border border-gray-100 bg-gray-50 p-3 text-sm text-gray-600">
                      <div className="text-xs text-gray-400">当前版本</div>
                      <div className="mt-1 font-semibold text-gray-900">v{settings.version}</div>
                    </div>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {SETTING_FIELDS.map((field) => (
                      <label key={field.key} className="grid gap-1 text-sm text-gray-600">
                        {field.label}
                        <input
                          type="number"
                          step={field.step || "1"}
                          value={settings[field.key]}
                          onChange={(event) => updateSetting(field.key, event.target.value)}
                          className="h-10 rounded-lg border border-gray-200 px-3 text-sm text-gray-900"
                        />
                        <span className="text-xs leading-5 text-gray-400">{field.description}</span>
                      </label>
                    ))}
                  </div>
                  <div className="mt-5">
                    <div className="mb-2 text-sm font-semibold text-gray-900">历史 profile</div>
                    {profiles.length === 0 ? (
                      <p className="text-sm text-gray-400">暂无已保存 profile，当前使用系统默认阈值。</p>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {profiles.map((profile) => (
                          profile.is_active ? (
                            <button
                              key={`${profile.agent_type}-${profile.scenario}-${profile.version}`}
                              type="button"
                              onClick={() => void handleLoadProfile(profile)}
                              className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs text-blue-700"
                            >
                              {profile.agent_type}/{profile.scenario} v{profile.version}
                            </button>
                          ) : (
                            <span
                              key={`${profile.agent_type}-${profile.scenario}-${profile.version}`}
                              className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs text-gray-500"
                            >
                              {profile.agent_type}/{profile.scenario} v{profile.version} 历史
                            </span>
                          )
                        ))}
                      </div>
                    )}
                  </div>
                </>
              ) : (
                <p className="text-sm text-gray-400">暂无阈值配置</p>
              )}
            </section>

            <section className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
              <div className="rounded-lg border bg-white p-5">
                <div className="mb-4 flex items-center gap-2">
                  <ClipboardCheck className="h-5 w-5 text-blue-600" />
                  <h2 className="text-lg font-semibold text-gray-900">复盘闭环</h2>
                </div>
                <div className="space-y-3">
                  <label className="grid gap-1 text-sm text-gray-600">
                    Agent run ID
                    <input
                      value={reviewRunId}
                      onChange={(event) => setReviewRunId(event.target.value)}
                      inputMode="numeric"
                      className="h-10 rounded-lg border border-gray-200 px-3 text-sm"
                      placeholder="从审计日志选择或手动输入"
                    />
                  </label>
                  <div className="grid gap-3 md:grid-cols-2">
                    <label className="grid gap-1 text-sm text-gray-600">
                      复盘结论
                      <select
                        value={review.outcome}
                        onChange={(event) =>
                          setReview({ ...review, outcome: event.target.value as AgentRunReviewInput["outcome"] })
                        }
                        className="h-10 rounded-lg border border-gray-200 px-3 text-sm"
                      >
                        <option value="partial">部分采纳</option>
                        <option value="accepted">采纳</option>
                        <option value="needs_revision">需修订</option>
                        <option value="rejected">不采纳</option>
                      </select>
                    </label>
                    <label className="grid gap-1 text-sm text-gray-600">
                      是否需跟进
                      <select
                        value={review.follow_up_required ? "true" : "false"}
                        onChange={(event) =>
                          setReview({ ...review, follow_up_required: event.target.value === "true" })
                        }
                        className="h-10 rounded-lg border border-gray-200 px-3 text-sm"
                      >
                        <option value="false">否</option>
                        <option value="true">是</option>
                      </select>
                    </label>
                    <label className="grid gap-1 text-sm text-gray-600">
                      有用性评分
                      <input
                        type="number"
                        min={1}
                        max={5}
                        value={review.usefulness_score}
                        onChange={(event) =>
                          setReview({ ...review, usefulness_score: Number(event.target.value) })
                        }
                        className="h-10 rounded-lg border border-gray-200 px-3 text-sm"
                      />
                    </label>
                    <label className="grid gap-1 text-sm text-gray-600">
                      准确性评分
                      <input
                        type="number"
                        min={1}
                        max={5}
                        value={review.accuracy_score}
                        onChange={(event) =>
                          setReview({ ...review, accuracy_score: Number(event.target.value) })
                        }
                        className="h-10 rounded-lg border border-gray-200 px-3 text-sm"
                      />
                    </label>
                    <label className="grid gap-1 text-sm text-gray-600">
                      采纳动作数
                      <input
                        type="number"
                        min={0}
                        value={review.accepted_actions_count}
                        onChange={(event) =>
                          setReview({ ...review, accepted_actions_count: Number(event.target.value) })
                        }
                        className="h-10 rounded-lg border border-gray-200 px-3 text-sm"
                      />
                    </label>
                    <label className="grid gap-1 text-sm text-gray-600">
                      驳回动作数
                      <input
                        type="number"
                        min={0}
                        value={review.rejected_actions_count}
                        onChange={(event) =>
                          setReview({ ...review, rejected_actions_count: Number(event.target.value) })
                        }
                        className="h-10 rounded-lg border border-gray-200 px-3 text-sm"
                      />
                    </label>
                  </div>
                  <label className="grid gap-1 text-sm text-gray-600">
                    复盘备注
                    <textarea
                      value={review.feedback || ""}
                      onChange={(event) => setReview({ ...review, feedback: event.target.value })}
                      className="min-h-24 rounded-lg border border-gray-200 p-3 text-sm"
                      placeholder="记录人工复核结论、证据缺口和下一步优化建议"
                    />
                  </label>
                  <button
                    type="button"
                    onClick={handleCreateReview}
                    disabled={saving}
                    className="inline-flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white disabled:bg-gray-300"
                  >
                    <ClipboardCheck className="h-4 w-4" />
                    提交复盘
                  </button>
                </div>
              </div>

              <div className="rounded-lg border bg-white p-5">
                <h2 className="mb-4 text-lg font-semibold text-gray-900">最近复盘记录</h2>
                <div className="mb-4">
                  <InsightPanel insight={insight} />
                </div>
                <ReviewList reviews={reviews} />
              </div>
            </section>

            <section className="rounded-lg border bg-white p-5">
              <div className="mb-4 flex items-center gap-2">
                <FileSearch className="h-5 w-5 text-blue-600" />
                <h2 className="text-lg font-semibold text-gray-900">AI 决策审计日志</h2>
              </div>
              <LogTable logs={logs} />
            </section>
          </>
        )}
      </div>
    </AdminAccess>
  );
}
