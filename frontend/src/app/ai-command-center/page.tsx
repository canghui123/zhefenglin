"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ClipboardCheck,
  FileSearch,
  Gauge,
  PlayCircle,
  TrendingUp,
} from "lucide-react";

import { useSession } from "@/components/auth/session-provider";
import { hasRole } from "@/lib/auth";
import {
  confirmAiAgentTaskDraft,
  getAiCommandOverview,
  listAiDecisionAuditLogs,
  rejectAiAgentTaskDraft,
  runAiCommandAgent,
  type AgentEvidence,
  type AgentOutput,
  type AgentRun,
  type AgentTask,
  type AgentWorkbenchItem,
  type AiAgentType,
  type AiCommandOverview,
  type DecisionAuditLog,
} from "@/lib/api";

const AGENT_LABELS: Record<AiAgentType, string> = {
  asset_package_diagnosis_agent: "资产包分析",
  valuation_analysis_agent: "估值可信度分析",
  pricing_strategy_agent: "处置定价建议",
  buyer_offer_analysis_agent: "买方报价判断",
  operation_planning_agent: "本周作战计划",
  task_generation_agent: "任务草稿生成",
  report_generation_agent: "报告草稿生成",
  cost_control_agent: "成本与额度预警",
};

const AGENT_TECH_LABELS: Record<AiAgentType, string> = {
  asset_package_diagnosis_agent: "资产包解读 Agent",
  valuation_analysis_agent: "估值分析 Agent",
  pricing_strategy_agent: "定价策略 Agent",
  buyer_offer_analysis_agent: "买方报价反推 Agent",
  operation_planning_agent: "运营计划 Agent",
  task_generation_agent: "任务生成 Agent",
  report_generation_agent: "报告生成 Agent",
  cost_control_agent: "成本控制 Agent",
};

const STATUS_LABELS: Record<string, string> = {
  rules_based: "规则分析",
  mock: "预览能力",
  fallback: "降级输出",
  llm_assisted: "LLM 辅助",
  succeeded: "已完成",
  running: "分析中",
  failed: "失败",
  draft: "草稿",
};

const ROLE_LABELS: Record<string, string> = {
  viewer: "只能查看摘要",
  operator: "可发起基础分析",
  manager: "可查看策略和任务",
  admin: "可查看成本、审批和审计",
};

const REPORT_TYPE_LABELS: Record<string, string> = {
  executive_summary: "高管摘要",
  asset_package_brief: "资产包简报",
  buyer_offer_memo: "买方报价备忘录",
  weekly_operation_report: "周运营报告",
};

type ViewMode = "customer" | "workbench";

const QUICK_ANALYSES: Array<{ title: string; description: string; agentType: AiAgentType; question: string }> = [
  {
    title: "分析资产包",
    description: "识别资料缺口、风险标签和整体出让适配度",
    agentType: "asset_package_diagnosis_agent",
    question: "分析这个资产包适不适合整体出让",
  },
  {
    title: "判断买方报价",
    description: "反推报价是否合理，提示压价和折价风险",
    agentType: "buyer_offer_analysis_agent",
    question: "买方报价是否合理",
  },
  {
    title: "生成本周作战计划",
    description: "梳理优先处置池、补资料池和暂缓池",
    agentType: "operation_planning_agent",
    question: "生成本周处置作战计划",
  },
  {
    title: "生成报告草稿",
    description: "形成高管摘要、资产包简报或周报草稿",
    agentType: "report_generation_agent",
    question: "生成一份需要人工复核的报告草稿",
  },
];

const CONFIRMATION_GROUPS = [
  "报价确认",
  "高成本估值审批",
  "任务草稿确认",
  "报告草稿复核",
  "法务路径复核",
];

function metricValue(value: unknown) {
  if (typeof value !== "number") return "0";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function metricNumber(metrics: Record<string, unknown>, keys: string[], fallback = 0) {
  for (const key of keys) {
    const value = metrics[key];
    if (typeof value === "number" && Number.isFinite(value)) return value;
  }
  return fallback;
}

function formatAmount(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "-";
  return value.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

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

function confidenceText(score: number) {
  return `${Math.round(score * 100)}%`;
}

function evidenceText(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : null;
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function recordArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is Record<string, unknown> => !!asRecord(item)) : [];
}

function findEvidencePayload(runs: AgentRun[], agentType: AiAgentType, label: string) {
  for (const run of runs) {
    if (run.agent_type !== agentType) continue;
    const payload = run.output.evidence.find((item) => item.label === label);
    const value = asRecord(payload?.value);
    if (value) return value;
  }
  return null;
}

function listReportDraftPayloads(runs: AgentRun[]) {
  return runs
    .filter((run) => run.agent_type === "report_generation_agent")
    .map((run) => findEvidencePayload([run], "report_generation_agent", "report_draft"))
    .filter((item): item is Record<string, unknown> => item !== null);
}

function riskLevel(output: AgentOutput | null | undefined): "低" | "中" | "中高" | "高" {
  if (!output) return "低";
  const warningText = output.risk_warnings.join(" ");
  if (/高风险|严重|法律|权属|逾期|离线|低于35|超预算/.test(warningText) && output.risk_warnings.length >= 2) {
    return "中高";
  }
  if (/高风险|严重|禁止|删除|超预算/.test(warningText)) return "高";
  if (output.risk_warnings.length > 0) return "中";
  return "低";
}

function riskClass(level: string) {
  if (level === "高") return "border-red-200 bg-red-50 text-red-700";
  if (level === "中高") return "border-amber-200 bg-amber-50 text-amber-700";
  if (level === "中") return "border-amber-200 bg-amber-50 text-amber-700";
  return "border-emerald-200 bg-emerald-50 text-emerald-700";
}

function statusClass(status: string) {
  if (status === "mock") return "bg-gray-100 text-gray-600";
  if (status === "fallback") return "bg-amber-50 text-amber-700";
  if (status === "llm_assisted") return "bg-blue-50 text-blue-700";
  return "bg-emerald-50 text-emerald-700";
}

function payloadText(payload: Record<string, unknown> | undefined, key: string) {
  const value = payload?.[key];
  return typeof value === "string" && value.trim() ? value : "";
}

function payloadList(payload: Record<string, unknown> | undefined, key: string) {
  const value = payload?.[key];
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function payloadNumber(payload: Record<string, unknown> | undefined, key: string) {
  const value = payload?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function EvidenceDetails({ evidence, roleScope }: { evidence: AgentEvidence[]; roleScope: string }) {
  return (
    <details className="group rounded-2xl border border-gray-200 bg-gray-50 p-4">
      <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-semibold text-gray-900">
        <span>查看分析依据</span>
        <ChevronDown className="h-4 w-4 text-gray-400 transition group-open:rotate-180" />
      </summary>
      {roleScope === "viewer" ? (
        <p className="mt-3 text-sm text-gray-500">当前角色仅显示摘要级分析依据，不展示敏感证据字段。</p>
      ) : evidence.length === 0 ? (
        <p className="mt-3 text-sm text-gray-400">暂无分析依据。</p>
      ) : (
        <div className="mt-4 space-y-3">
          {evidence.map((item, index) => (
            <div key={`${item.source}-${item.label}-${index}`} className="rounded-2xl border border-gray-100 bg-white p-4 text-xs text-gray-600">
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <span className="font-medium text-gray-900">来源：</span>
                  {item.evidence_source || item.source || "-"}
                </div>
                <div>
                  <span className="font-medium text-gray-900">对象类型：</span>
                  {item.related_object_type || item.source || "-"}
                </div>
                <div>
                  <span className="font-medium text-gray-900">对象 ID：</span>
                  {item.related_object_id || "-"}
                </div>
                <div>
                  <span className="font-medium text-gray-900">计算依据：</span>
                  {item.calculation_basis || `${item.label}: ${evidenceText(item.value)}`}
                </div>
              </div>
              <div className="mt-3 rounded-xl bg-gray-50 p-3 text-gray-500">{evidenceText(item.value)}</div>
              <div className="mt-2">
                <span className="font-medium text-gray-900">数据质量：</span>
                {item.data_quality_notes || "-"}
              </div>
            </div>
          ))}
        </div>
      )}
    </details>
  );
}

function ViewModeSwitch({
  viewMode,
  setViewMode,
}: {
  viewMode: ViewMode;
  setViewMode: (value: ViewMode) => void;
}) {
  return (
    <section className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-200 bg-white p-3 shadow-sm">
      <div className="px-2">
        <div className="text-sm font-semibold text-gray-950">视图模式</div>
        <div className="text-xs text-gray-500">客户视图隐藏技术细节，内部工作台保留 Agent、审计和分析依据。</div>
      </div>
      <div className="flex rounded-xl bg-gray-100 p-1 text-sm">
        <button
          type="button"
          onClick={() => setViewMode("customer")}
          className={`rounded-lg px-4 py-2 font-medium ${viewMode === "customer" ? "bg-white text-blue-700 shadow-sm" : "text-gray-600"}`}
        >
          客户视图
        </button>
        <button
          type="button"
          onClick={() => setViewMode("workbench")}
          className={`rounded-lg px-4 py-2 font-medium ${viewMode === "workbench" ? "bg-white text-blue-700 shadow-sm" : "text-gray-600"}`}
        >
          内部工作台
        </button>
      </div>
    </section>
  );
}

function CustomerOperationPlan({
  plan,
  onGeneratePlan,
}: {
  plan: Record<string, unknown> | null;
  onGeneratePlan: () => void;
}) {
  const focus = stringArray(plan?.weekly_focus).slice(0, 4);
  const highPriorityPool = recordArray(plan?.high_priority_asset_pool);
  const auctionPool = recordArray(plan?.auction_pool);
  const legalPool = recordArray(plan?.legal_pool);
  const dataPool = recordArray(plan?.data_completion_pool);
  const pausedPool = recordArray(plan?.paused_pool);
  const cashflow = asRecord(plan?.cashflow_focus);

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-gray-950">本周作战计划</h2>
          <p className="mt-1 text-sm text-gray-500">只展示业务分池和行动重点，正式排期仍需人工确认。</p>
        </div>
        <button type="button" onClick={onGeneratePlan} className="inline-flex h-10 items-center rounded-xl bg-blue-600 px-4 text-sm font-semibold text-white hover:bg-blue-700">
          生成本周作战计划
        </button>
      </div>

      {!plan ? (
        <div className="mt-5 rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-500">
          尚未生成本周作战计划。可由经理发起运营计划分析，系统只生成草稿，不自动派发任务。
        </div>
      ) : (
        <div className="mt-5 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
          <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4">
            <div className="text-sm font-semibold text-blue-950">本周重点</div>
            <ul className="mt-3 space-y-2">
              {(focus.length ? focus : ["复核高风险资产池", "确认竞拍和法务优先级", "补齐关键资料缺口"]).map((item) => (
                <li key={item} className="text-sm leading-6 text-blue-900">{item}</li>
              ))}
            </ul>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
              <div className="text-xs text-gray-500">高优先级资产池</div>
              <div className="mt-1 text-2xl font-bold text-gray-950">{highPriorityPool.length}</div>
            </div>
            <div className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
              <div className="text-xs text-gray-500">建议竞拍池</div>
              <div className="mt-1 text-2xl font-bold text-gray-950">{auctionPool.length}</div>
            </div>
            <div className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
              <div className="text-xs text-gray-500">建议法务池</div>
              <div className="mt-1 text-2xl font-bold text-gray-950">{legalPool.length}</div>
            </div>
            <div className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
              <div className="text-xs text-gray-500">补资料 / 暂缓池</div>
              <div className="mt-1 text-2xl font-bold text-gray-950">{dataPool.length + pausedPool.length}</div>
            </div>
          </div>
          <div className="lg:col-span-2 rounded-2xl border border-gray-100 bg-gray-50 p-4 text-sm text-gray-600">
            90 天现金回流关注：{formatAmount(cashflow?.cash_90d)} 元。该计划为规则化草稿，需人工复核后进入任务或审批流程。
          </div>
        </div>
      )}
    </section>
  );
}

function ReportDraftsSection({
  drafts,
  onGenerateReport,
}: {
  drafts: Record<string, unknown>[];
  onGenerateReport: () => void;
}) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-gray-950">报告草稿</h2>
          <p className="mt-1 text-sm text-gray-500">报告草稿不会自动下载、外发或替代法律结论。</p>
        </div>
        <button type="button" onClick={onGenerateReport} className="inline-flex h-10 items-center rounded-xl border border-blue-200 bg-blue-50 px-4 text-sm font-semibold text-blue-700 hover:bg-blue-100">
          生成报告草稿
        </button>
      </div>
      {drafts.length === 0 ? (
        <div className="mt-5 rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-500">
          暂无报告草稿。生成后仅作为内部复核材料，不会自动对外发送。
        </div>
      ) : (
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          {drafts.map((draft, index) => {
            const title = typeof draft.title === "string" ? draft.title : "报告草稿";
            const sections = recordArray(draft.sections).slice(0, 3);
            return (
              <article key={`${title}-${index}`} className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-gray-950">{title}</div>
                    <div className="mt-1 text-xs text-gray-500">{REPORT_TYPE_LABELS[String(draft.report_type || "")] || "需人工复核"}</div>
                  </div>
                  <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">需人工复核</span>
                </div>
                <div className="mt-3 space-y-2">
                  {sections.map((section, sectionIndex) => (
                    <div key={`${section.heading}-${sectionIndex}`} className="rounded-xl bg-white p-3">
                      <div className="text-xs font-semibold text-gray-900">{evidenceText(section.heading)}</div>
                      <p className="mt-1 text-sm leading-5 text-gray-600">{evidenceText(section.content)}</p>
                    </div>
                  ))}
                </div>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function TopJudgmentCard({
  output,
  roleScope,
  onPlanClick,
  showEvidence,
}: {
  output: AgentOutput;
  roleScope: string;
  onPlanClick: () => void;
  showEvidence: boolean;
}) {
  const level = riskLevel(output);
  const findings = output.key_findings.slice(0, 4);
  const primaryAction = output.recommended_actions[0] || "先完成风险资产和待确认事项复核，再进入正式处置流程。";

  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-4xl">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className={`rounded-full border px-3 py-1 text-sm font-semibold ${riskClass(level)}`}>整体风险：{level}</span>
            <span className="rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700">需人工复核</span>
            {showEvidence && (
              <span className={`rounded-full px-3 py-1 text-sm font-semibold ${statusClass(output.agent_status)}`}>
                {STATUS_LABELS[output.agent_status] || output.agent_status}
              </span>
            )}
          </div>
          <h1 className="text-2xl font-bold leading-tight text-gray-950">汽车金融不良资产 AI 作战台</h1>
          <p className="mt-3 text-base leading-7 text-gray-700">{output.summary || "当前暂无 AI 判断，系统会在有资产包和任务数据后生成处置建议。"}</p>
        </div>
        <div className="rounded-2xl border border-gray-200 bg-gray-50 px-5 py-4 text-right">
          <div className="text-xs text-gray-500">置信度</div>
          <div className="mt-1 text-2xl font-bold text-gray-950">{confidenceText(output.confidence_score)}</div>
        </div>
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <div className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
          <div className="text-sm font-semibold text-gray-900">关键发现</div>
          {findings.length === 0 ? (
            <p className="mt-3 text-sm text-gray-500">暂无关键风险发现。系统不会跨租户读取其他数据。</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {findings.map((item, index) => (
                <li key={`${item}-${index}`} className="flex gap-2 text-sm leading-6 text-gray-700">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                  <span>{item}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-2xl border border-blue-100 bg-blue-50 p-4">
          <div className="text-sm font-semibold text-blue-900">AI 建议优先做</div>
          <p className="mt-3 text-sm leading-6 text-blue-800">{primaryAction}</p>
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        {showEvidence && (
          <a href="#analysis-evidence" className="inline-flex h-10 items-center rounded-xl border border-gray-200 bg-white px-4 text-sm font-medium text-gray-700 hover:bg-gray-50">
            查看详细依据
          </a>
        )}
        <button type="button" onClick={onPlanClick} className="inline-flex h-10 items-center rounded-xl bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700">
          生成本周作战计划
        </button>
        <a href="#confirmations" className="inline-flex h-10 items-center rounded-xl border border-blue-200 bg-blue-50 px-4 text-sm font-medium text-blue-700 hover:bg-blue-100">
          查看待确认事项
        </a>
      </div>

      {showEvidence && (
        <div id="analysis-evidence" className="mt-5">
          <EvidenceDetails evidence={output.evidence} roleScope={roleScope} />
        </div>
      )}
    </section>
  );
}

function MetricCard({ title, value, description, tone, icon: Icon }: { title: string; value: string; description: string; tone: "blue" | "red" | "amber" | "emerald"; icon: typeof ClipboardCheck }) {
  const toneClass = {
    blue: "bg-blue-50 text-blue-700",
    red: "bg-red-50 text-red-700",
    amber: "bg-amber-50 text-amber-700",
    emerald: "bg-emerald-50 text-emerald-700",
  }[tone];

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-gray-500">{title}</div>
          <div className="mt-2 text-3xl font-bold text-gray-950">{value}</div>
        </div>
        <span className={`rounded-2xl p-2 ${toneClass}`}>
          <Icon className="h-5 w-5" />
        </span>
      </div>
      <p className="mt-3 text-sm leading-5 text-gray-500">{description}</p>
    </div>
  );
}

function SuggestionCard({
  title,
  reason,
  action,
  output,
  roleScope,
  onGenerateTask,
  showEvidence,
}: {
  title: string;
  reason: string;
  action: string;
  output: AgentOutput;
  roleScope: string;
  onGenerateTask: () => void;
  showEvidence: boolean;
}) {
  const level = riskLevel({ ...output, risk_warnings: reason ? [reason] : output.risk_warnings });
  return (
    <article className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl">
          <h3 className="text-base font-semibold text-gray-950">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-gray-600">{reason || "基于当前资产包、任务和处置数据生成的优先建议。"}</p>
        </div>
        <span className={`rounded-full border px-3 py-1 text-xs font-semibold ${riskClass(level)}`}>{level}风险</span>
      </div>
      <div className="mt-4 rounded-2xl bg-gray-50 p-4 text-sm leading-6 text-gray-700">
        <span className="font-semibold text-gray-950">建议动作：</span>
        {action}
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
        <span className="rounded-full bg-blue-50 px-3 py-1 font-medium text-blue-700">置信度 {confidenceText(output.confidence_score)}</span>
        {output.requires_human_review && <span className="rounded-full bg-blue-50 px-3 py-1 font-medium text-blue-700">需人工复核</span>}
        {showEvidence && (
          <span className={`rounded-full px-3 py-1 font-medium ${statusClass(output.agent_status)}`}>{STATUS_LABELS[output.agent_status] || output.agent_status}</span>
        )}
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        <a href="#analysis-evidence" className="inline-flex h-9 items-center rounded-xl border border-gray-200 px-3 text-sm font-medium text-gray-700 hover:bg-gray-50">
          查看依据
        </a>
        <button type="button" onClick={onGenerateTask} className="inline-flex h-9 items-center rounded-xl border border-blue-200 bg-blue-50 px-3 text-sm font-medium text-blue-700 hover:bg-blue-100">
          生成任务草稿
        </button>
        <button type="button" className="inline-flex h-9 items-center rounded-xl border border-gray-200 px-3 text-sm font-medium text-gray-400" disabled>
          标记已复核
        </button>
      </div>
      {showEvidence && (
        <div className="mt-4">
          <EvidenceDetails evidence={output.evidence} roleScope={roleScope} />
        </div>
      )}
    </article>
  );
}

function ConfirmationQueue({
  overview,
  canConfirmTasks,
  canConfirmHighRiskTasks,
  actioningTaskId,
  onConfirmTask,
  onRejectTask,
}: {
  overview: AiCommandOverview;
  canConfirmTasks: boolean;
  canConfirmHighRiskTasks: boolean;
  actioningTaskId: number | null;
  onConfirmTask: (taskId: number) => void;
  onRejectTask: (taskId: number) => void;
}) {
  const queue = [
    ...overview.pending_approvals.map((item) => ({
      id: `approval-${item.id}`,
      taskId: null as number | null,
      group: item.recommendation_type.includes("report") ? "报告草稿复核" : item.recommendation_type.includes("cost") ? "高成本估值审批" : "报价确认",
      title: item.title,
      advice: item.summary,
      level: item.confidence_score >= 0.75 ? "中高" : "中",
      canConfirm: false,
      blockedReason: "",
    })),
    ...overview.pending_tasks.map((task) => ({
      id: `task-${task.id}`,
      taskId: task.id,
      group: "任务草稿确认",
      title: task.title,
      advice: payloadText(task.payload, "description") || "AI 已生成任务草稿，需人工确认后才能派发。",
      level: task.priority === "high" ? "中高" : "中",
      canConfirm: task.priority !== "high" || canConfirmHighRiskTasks,
      blockedReason: task.priority === "high" && !canConfirmHighRiskTasks ? "高风险任务需 admin 确认" : "",
    })),
  ];

  return (
    <section id="confirmations" className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-gray-950">需要你确认</h2>
          <p className="mt-1 text-sm text-gray-500">AI 只生成建议和草稿，正式动作必须由授权人员确认。</p>
        </div>
        <span className="rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700">{queue.length} 项待确认</span>
      </div>

      {queue.length === 0 ? (
        <div className="mt-5 rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-500">
          当前没有待确认事项。若当前租户没有相关数据，系统会保持安全空状态，不跨租户读取其他信息。
        </div>
      ) : (
        <div className="mt-5 grid gap-4 lg:grid-cols-2">
          {CONFIRMATION_GROUPS.map((group) => {
            const items = queue.filter((item) => item.group === group);
            return (
              <div key={group} className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
                <div className="mb-3 text-sm font-semibold text-gray-900">{group}</div>
                {items.length === 0 ? (
                  <p className="text-sm text-gray-400">暂无</p>
                ) : (
                  <div className="space-y-3">
                    {items.map((item) => (
                      <div key={item.id} className="rounded-2xl bg-white p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="text-sm font-semibold text-gray-950">{item.title}</div>
                            <p className="mt-1 text-sm leading-5 text-gray-600">{item.advice}</p>
                          </div>
                          <span className={`shrink-0 rounded-full border px-2 py-1 text-xs font-semibold ${riskClass(item.level)}`}>{item.level}</span>
                        </div>
                        <div className="mt-3 flex gap-2">
                          <a href="#task-drafts" className="rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700">查看</a>
                          {item.taskId ? (
                            <>
                              <button
                                type="button"
                                onClick={() => onConfirmTask(item.taskId as number)}
                                disabled={!canConfirmTasks || !item.canConfirm || actioningTaskId === item.taskId}
                                className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-medium text-emerald-700 disabled:cursor-not-allowed disabled:border-gray-200 disabled:bg-gray-50 disabled:text-gray-400"
                                title={item.blockedReason}
                              >
                                {actioningTaskId === item.taskId ? "处理中" : "确认派发"}
                              </button>
                              <button
                                type="button"
                                onClick={() => onRejectTask(item.taskId as number)}
                                disabled={!canConfirmTasks || actioningTaskId === item.taskId}
                                className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 disabled:cursor-not-allowed disabled:text-gray-400"
                              >
                                驳回
                              </button>
                              {item.blockedReason && <span className="text-xs leading-7 text-gray-400">{item.blockedReason}</span>}
                            </>
                          ) : (
                            <button type="button" className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-400" disabled>确认</button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

function QuickAnalysis({
  canRunAgent,
  running,
  question,
  setQuestion,
  agentType,
  setAgentType,
  overview,
  assetPackageId,
  setAssetPackageId,
  buyerOfferPrice,
  setBuyerOfferPrice,
  expectedVinCalls,
  setExpectedVinCalls,
  expectedConditionPricingCalls,
  setExpectedConditionPricingCalls,
  expectedAiReports,
  setExpectedAiReports,
  singleTaskBudget,
  setSingleTaskBudget,
  reportType,
  setReportType,
  ruleScenario,
  setRuleScenario,
  submitCommand,
}: {
  canRunAgent: boolean;
  running: boolean;
  question: string;
  setQuestion: (value: string) => void;
  agentType: AiAgentType | "";
  setAgentType: (value: AiAgentType | "") => void;
  overview: AiCommandOverview;
  assetPackageId: string;
  setAssetPackageId: (value: string) => void;
  buyerOfferPrice: string;
  setBuyerOfferPrice: (value: string) => void;
  expectedVinCalls: string;
  setExpectedVinCalls: (value: string) => void;
  expectedConditionPricingCalls: string;
  setExpectedConditionPricingCalls: (value: string) => void;
  expectedAiReports: string;
  setExpectedAiReports: (value: string) => void;
  singleTaskBudget: string;
  setSingleTaskBudget: (value: string) => void;
  reportType: string;
  setReportType: (value: string) => void;
  ruleScenario: string;
  setRuleScenario: (value: string) => void;
  submitCommand: () => void;
}) {
  return (
    <section id="quick-analysis" className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-gray-950">你想让 AI 帮你做什么？</h2>
          <p className="mt-1 text-sm text-gray-500">常用分析入口会自动映射到对应分析类型，高级选项仍可手动选择。</p>
        </div>
        {!canRunAgent && <span className="rounded-full bg-gray-100 px-3 py-1 text-sm font-medium text-gray-600">当前角色只能查看摘要</span>}
      </div>

      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {QUICK_ANALYSES.map((item) => (
          <button
            key={item.agentType}
            type="button"
            onClick={() => {
              setAgentType(item.agentType);
              setQuestion(item.question);
            }}
            disabled={!canRunAgent}
            className={`rounded-2xl border p-4 text-left transition ${agentType === item.agentType ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-gray-50 hover:border-gray-300"} disabled:cursor-not-allowed disabled:opacity-60`}
          >
            <div className="text-base font-semibold text-gray-950">{item.title}</div>
            <p className="mt-2 text-sm leading-5 text-gray-500">{item.description}</p>
          </button>
        ))}
      </div>

      <div className="mt-5 space-y-4 rounded-2xl border border-gray-100 bg-gray-50 p-4">
        <textarea
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          className="min-h-24 w-full rounded-2xl border border-gray-200 bg-white p-3 text-sm outline-none focus:border-blue-500"
          placeholder="输入自然语言问题"
        />
        <div className="flex flex-wrap gap-2">
          {overview.suggested_prompts.map((prompt) => (
            <button
              key={prompt}
              type="button"
              onClick={() => setQuestion(prompt)}
              className="rounded-full border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100"
            >
              {prompt}
            </button>
          ))}
        </div>

        <details className="group rounded-2xl border border-gray-200 bg-white p-4">
          <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-semibold text-gray-900">
            <span>高级选项</span>
            <ChevronDown className="h-4 w-4 text-gray-400 transition group-open:rotate-180" />
          </summary>
          <div className="mt-4 space-y-4">
            <div className="grid gap-3 md:grid-cols-3">
              <label className="grid gap-1 text-sm text-gray-600">
                分析类型
                <select
                  value={agentType}
                  onChange={(event) => setAgentType(event.target.value as AiAgentType | "")}
                  className="h-10 rounded-xl border border-gray-200 px-3 text-sm"
                >
                  <option value="">自动识别</option>
                  {overview.agent_workbench.map((agent) => (
                    <option key={agent.agent_type} value={agent.agent_type}>
                      {AGENT_LABELS[agent.agent_type] || agent.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="grid gap-1 text-sm text-gray-600">
                资产包 ID
                <input
                  value={assetPackageId}
                  onChange={(event) => setAssetPackageId(event.target.value)}
                  inputMode="numeric"
                  className="h-10 rounded-xl border border-gray-200 px-3 text-sm"
                  placeholder="留空使用最新资产包"
                />
              </label>
              <label className="grid gap-1 text-sm text-gray-600">
                买方报价
                <input
                  value={buyerOfferPrice}
                  onChange={(event) => setBuyerOfferPrice(event.target.value)}
                  inputMode="decimal"
                  className="h-10 rounded-xl border border-gray-200 px-3 text-sm"
                  placeholder="报价分析时填写"
                />
              </label>
            </div>
            {agentType === "cost_control_agent" && (
              <div className="grid gap-3 md:grid-cols-4">
                <label className="grid gap-1 text-sm text-gray-600">
                  VIN 调用量
                  <input value={expectedVinCalls} onChange={(event) => setExpectedVinCalls(event.target.value)} inputMode="numeric" className="h-10 rounded-xl border border-gray-200 px-3 text-sm" placeholder="默认按资产数" />
                </label>
                <label className="grid gap-1 text-sm text-gray-600">
                  高级车况调用量
                  <input value={expectedConditionPricingCalls} onChange={(event) => setExpectedConditionPricingCalls(event.target.value)} inputMode="numeric" className="h-10 rounded-xl border border-gray-200 px-3 text-sm" placeholder="默认按估值缺口" />
                </label>
                <label className="grid gap-1 text-sm text-gray-600">
                  AI 报告数量
                  <input value={expectedAiReports} onChange={(event) => setExpectedAiReports(event.target.value)} inputMode="numeric" className="h-10 rounded-xl border border-gray-200 px-3 text-sm" placeholder="默认 1" />
                </label>
                <label className="grid gap-1 text-sm text-gray-600">
                  单次预算
                  <input value={singleTaskBudget} onChange={(event) => setSingleTaskBudget(event.target.value)} inputMode="decimal" className="h-10 rounded-xl border border-gray-200 px-3 text-sm" placeholder="可选" />
                </label>
              </div>
            )}
            {agentType === "report_generation_agent" && (
              <label className="grid gap-1 text-sm text-gray-600 md:max-w-xs">
                报告草稿类型
                <select value={reportType} onChange={(event) => setReportType(event.target.value)} className="h-10 rounded-xl border border-gray-200 px-3 text-sm">
                  {Object.entries(REPORT_TYPE_LABELS).map(([value, label]) => (
                    <option key={value} value={value}>{label}</option>
                  ))}
                </select>
              </label>
            )}
            {agentType && ["operation_planning_agent", "task_generation_agent", "report_generation_agent", "cost_control_agent"].includes(agentType) && (
              <label className="grid gap-1 text-sm text-gray-600 md:max-w-xs">
                规则场景
                <input value={ruleScenario} onChange={(event) => setRuleScenario(event.target.value)} className="h-10 rounded-xl border border-gray-200 px-3 text-sm" placeholder="default" />
              </label>
            )}
          </div>
        </details>

        <button
          type="button"
          onClick={submitCommand}
          disabled={running || !canRunAgent}
          className="inline-flex h-11 items-center gap-2 rounded-xl bg-blue-600 px-5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          <PlayCircle className="h-4 w-4" />
          {running ? "分析中..." : "开始分析"}
        </button>
      </div>
    </section>
  );
}

function TaskDraftCard({
  task,
  canConfirmTasks,
  canConfirmThisTask,
  actioning,
  onConfirm,
  onReject,
}: {
  task: AgentTask;
  canConfirmTasks: boolean;
  canConfirmThisTask: boolean;
  actioning: boolean;
  onConfirm: () => void;
  onReject: () => void;
}) {
  const payload = task.payload || {};
  const description = payloadText(payload, "description");
  const ownerRole = payloadText(payload, "suggested_owner_role");
  const deadline = payloadText(payload, "deadline_suggestion");
  const expectedResult = payloadText(payload, "expected_result");
  const requiredDocuments = payloadList(payload, "required_documents");
  const relatedObjectType = payloadText(payload, "related_object_type");
  const relatedObjectId = payloadText(payload, "related_object_id");
  const confidenceScore = payloadNumber(payload, "confidence_score");
  const evidenceItems = recordArray(payload.evidence);

  return (
    <div className="rounded-2xl border border-gray-100 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-gray-950">{task.title}</div>
          <div className="mt-1 text-xs text-gray-500">{task.task_type} · {task.priority} · {STATUS_LABELS[task.status] || task.status}</div>
        </div>
        {task.requires_human_review && <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">待人工确认</span>}
      </div>
      {description && <p className="mt-2 text-sm leading-5 text-gray-600">{description}</p>}
      <div className="mt-3 grid gap-2 text-xs text-gray-500 md:grid-cols-2">
        <div>类型：{task.task_type}</div>
        <div>优先级：{task.priority}</div>
        <div>建议角色：{ownerRole || "-"}</div>
        <div>建议截止：{deadline || "-"}</div>
        <div>关联对象：{relatedObjectType || "-"} {relatedObjectId ? `#${relatedObjectId}` : ""}</div>
        <div>置信度：{confidenceScore === null ? "-" : confidenceText(confidenceScore)}</div>
        <div className="md:col-span-2">预期结果：{expectedResult || "-"}</div>
      </div>
      {requiredDocuments.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {requiredDocuments.map((item) => <span key={item} className="rounded-full bg-gray-100 px-2 py-1 text-xs text-gray-600">{item}</span>)}
        </div>
      )}
      <details className="mt-4 rounded-2xl border border-gray-100 bg-gray-50 p-3">
        <summary className="cursor-pointer text-xs font-semibold text-gray-700">分析依据</summary>
        {evidenceItems.length === 0 ? (
          <p className="mt-2 text-xs text-gray-400">暂无分析依据。</p>
        ) : (
          <div className="mt-3 space-y-2">
            {evidenceItems.map((item, index) => (
              <div key={`${evidenceText(item.label)}-${index}`} className="rounded-xl bg-white p-3 text-xs text-gray-600">
                <div className="font-medium text-gray-900">{evidenceText(item.label || item.source || "依据")}</div>
                <div className="mt-1 break-words text-gray-500">{evidenceText(item.value)}</div>
              </div>
            ))}
          </div>
        )}
      </details>
      <div className="mt-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onConfirm}
          disabled={!canConfirmTasks || !canConfirmThisTask || actioning}
          className="inline-flex h-9 items-center rounded-xl bg-emerald-600 px-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:bg-gray-300"
        >
          {actioning ? "处理中..." : "确认派发"}
        </button>
        <button
          type="button"
          onClick={onReject}
          disabled={!canConfirmTasks || actioning}
          className="inline-flex h-9 items-center rounded-xl border border-gray-200 px-3 text-sm font-medium text-gray-700 disabled:cursor-not-allowed disabled:text-gray-400"
        >
          驳回草稿
        </button>
        {!canConfirmTasks && <span className="text-xs leading-9 text-gray-400">仅 manager/admin 可确认任务草稿</span>}
        {canConfirmTasks && !canConfirmThisTask && <span className="text-xs leading-9 text-gray-400">高风险任务需 admin 确认</span>}
      </div>
    </div>
  );
}

function AgentWorkbench({ agents }: { agents: AgentWorkbenchItem[] }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-bold text-gray-950">Agent 工作台</h2>
      <p className="mt-1 text-sm text-gray-500">技术状态放在次级区域，便于管理员核对能力边界。</p>
      <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {agents.map((agent) => (
          <div key={agent.agent_type} className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="text-sm font-semibold text-gray-950">{AGENT_TECH_LABELS[agent.agent_type]}</div>
                <div className="mt-1 text-xs text-gray-500">最小角色：{ROLE_LABELS[agent.min_role] || agent.min_role}</div>
              </div>
              <span className={`rounded-full px-2 py-1 text-xs font-semibold ${statusClass(agent.status)}`}>{STATUS_LABELS[agent.status] || agent.status}</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2 text-xs">
              <span className="rounded-full bg-white px-2 py-1 text-gray-600">{agent.stage === "phase_1" ? "已实现" : "半自动能力"}</span>
              <span className="rounded-full bg-blue-50 px-2 py-1 text-blue-700">需人工复核</span>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function RecentAnalysisRecords({ latestRun, overview }: { latestRun: AgentRun | null; overview: AiCommandOverview }) {
  const runs = latestRun ? [latestRun, ...overview.recent_runs.filter((run) => run.id !== latestRun.id)] : overview.recent_runs;
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <h2 className="text-xl font-bold text-gray-950">AI 分析记录</h2>
      <p className="mt-1 text-sm text-gray-500">最近运行用于追踪分析结果，详细 JSON 保留在审计链路中。</p>
      {runs.length === 0 ? (
        <div className="mt-5 rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-500">暂无 AI 分析记录。</div>
      ) : (
        <div className="mt-5 space-y-3">
          {runs.slice(0, 10).map((run) => (
            <div key={run.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-gray-100 bg-gray-50 p-4">
              <div>
                <div className="text-sm font-semibold text-gray-950">{AGENT_LABELS[run.agent_type as AiAgentType] || run.agent_type}</div>
                <div className="mt-1 text-xs text-gray-500">#{run.id} · {STATUS_LABELS[run.status] || run.status} · {formatTime(run.finished_at || run.started_at)}</div>
              </div>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className={`rounded-full px-2 py-1 font-medium ${statusClass(run.output.agent_status)}`}>{STATUS_LABELS[run.output.agent_status] || run.output.agent_status}</span>
                {run.requires_human_review && <span className="rounded-full bg-blue-50 px-2 py-1 font-medium text-blue-700">需人工复核</span>}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function AuditLogPanel({ logs }: { logs: DecisionAuditLog[] }) {
  return (
    <section className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
      <div className="mb-4 flex items-center gap-2">
        <FileSearch className="h-5 w-5 text-blue-600" />
        <h2 className="text-xl font-bold text-gray-950">审计日志</h2>
      </div>
      {logs.length === 0 ? (
        <p className="text-sm text-gray-400">暂无 AI 审计日志</p>
      ) : (
        <div className="space-y-3">
          {logs.map((log) => (
            <div key={log.id} className="rounded-2xl border border-gray-100 bg-gray-50 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="text-sm font-semibold text-gray-950">{log.decision_type}</div>
                  <div className="mt-1 text-xs text-gray-500">动作={log.action} · 操作人={log.actor_user_id || "-"} · {formatTime(log.created_at)}</div>
                </div>
                {log.requires_human_review && <span className="rounded-full bg-blue-50 px-2 py-1 text-xs font-medium text-blue-700">需人工复核</span>}
              </div>
              <details className="mt-3 rounded-xl bg-white p-3 text-xs text-gray-500">
                <summary className="cursor-pointer font-medium text-gray-700">查看分析结果摘要</summary>
                <div className="mt-2 max-h-24 overflow-auto font-mono text-[11px]">{evidenceText(log.after)}</div>
              </details>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default function AiCommandCenterPage() {
  const { user } = useSession();
  const [overview, setOverview] = useState<AiCommandOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [question, setQuestion] = useState("看看最新资产包有什么风险");
  const [agentType, setAgentType] = useState<AiAgentType | "">("");
  const [assetPackageId, setAssetPackageId] = useState("");
  const [buyerOfferPrice, setBuyerOfferPrice] = useState("");
  const [expectedVinCalls, setExpectedVinCalls] = useState("");
  const [expectedConditionPricingCalls, setExpectedConditionPricingCalls] = useState("");
  const [expectedAiReports, setExpectedAiReports] = useState("");
  const [singleTaskBudget, setSingleTaskBudget] = useState("");
  const [reportType, setReportType] = useState("executive_summary");
  const [ruleScenario, setRuleScenario] = useState("default");
  const [auditLogs, setAuditLogs] = useState<DecisionAuditLog[]>([]);
  const [latestRun, setLatestRun] = useState<AgentRun | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("customer");
  const [actioningTaskId, setActioningTaskId] = useState<number | null>(null);
  const currentRole = user?.role;

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const nextOverview = await getAiCommandOverview();
      setOverview(nextOverview);
      if (currentRole === "admin") {
        setAuditLogs(await listAiDecisionAuditLogs(20));
      } else {
        setAuditLogs([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 作战台加载失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }, [currentRole]);

  useEffect(() => {
    void load();
  }, [load]);

  const canRunAgent = hasRole(user, "operator");
  const canConfirmTasks = hasRole(user, "manager");
  const canConfirmHighRiskTasks = hasRole(user, "admin");

  const metricCards = useMemo(() => {
    const metrics = overview?.today_overview || {};
    const pendingConfirmations =
      metricNumber(metrics, ["pending_confirmation_count", "pending_approval_count"]) + (overview?.pending_tasks.filter((task) => task.requires_human_review).length || 0);
    const highRiskAssets = metricNumber(metrics, ["high_risk_asset_count", "high_risk_assets"], overview?.ai_today_judgment.risk_warnings.length || 0);
    const weeklyDisposals = metricNumber(metrics, ["weekly_recommended_disposal_count", "recommended_disposals_this_week"], overview?.pending_tasks.length || 0);
    const costWarnings = metricNumber(metrics, ["cost_warning_count", "quota_warning_count", "budget_warning_count"]);
    return [
      { title: "待人工确认", value: metricValue(pendingConfirmations), description: "报价、任务草稿、报告草稿等需人工确认后才能推进。", tone: "blue" as const, icon: ClipboardCheck },
      { title: "高风险资产", value: metricValue(highRiskAssets), description: "建议优先核查权属、GPS、估值覆盖和资料完整性。", tone: highRiskAssets > 0 ? "red" as const : "emerald" as const, icon: AlertTriangle },
      { title: "本周建议处置", value: metricValue(weeklyDisposals), description: "适合进入本周处置节奏的资产或任务草稿。", tone: "emerald" as const, icon: TrendingUp },
      { title: "成本/额度预警", value: metricValue(costWarnings), description: "VIN、车况和 AI 报告调用需关注额度与审批边界。", tone: costWarnings > 0 ? "amber" as const : "emerald" as const, icon: Gauge },
    ];
  }, [overview]);

  const suggestions = useMemo(() => {
    if (!overview) return [];
    const actions = overview.ai_today_judgment.recommended_actions.slice(0, 3);
    const findings = overview.ai_today_judgment.key_findings;
    const warnings = overview.ai_today_judgment.risk_warnings;
    if (actions.length === 0) {
      return [
        {
          title: "先补齐可分析数据",
          reason: "当前租户暂无足够的资产、任务或审批数据，系统保持安全空状态。",
          action: "上传资产包或选择已有资产包后，再发起资产包分析。",
        },
      ];
    }
    return actions.map((action, index) => ({
      title: index === 0 ? "优先处理本周最高影响事项" : `建议 ${index + 1}`,
      reason: warnings[index] || findings[index] || "基于当前资产包、估值、定价、任务和成本数据综合判断。",
      action,
    }));
  }, [overview]);

  const analysisRuns = useMemo(() => {
    if (!overview) return latestRun ? [latestRun] : [];
    return latestRun ? [latestRun, ...overview.recent_runs.filter((run) => run.id !== latestRun.id)] : overview.recent_runs;
  }, [latestRun, overview]);

  const operationPlanPayload = useMemo(
    () => findEvidencePayload(analysisRuns, "operation_planning_agent", "operation_plan"),
    [analysisRuns],
  );

  const reportDraftPayloads = useMemo(() => listReportDraftPayloads(analysisRuns), [analysisRuns]);

  async function submitCommand() {
    if (!canRunAgent) {
      setError("当前角色只能查看摘要，不能发起 AI 分析");
      return;
    }
    if (!question.trim() && !agentType) {
      setError("请输入问题或选择分析类型");
      return;
    }

    const packageId = Number(assetPackageId);
    const offerPrice = Number(buyerOfferPrice);
    const vinCalls = Number(expectedVinCalls);
    const conditionCalls = Number(expectedConditionPricingCalls);
    const aiReports = Number(expectedAiReports);
    const budget = Number(singleTaskBudget);
    setRunning(true);
    setError("");
    try {
      const run = await runAiCommandAgent({
        question: question.trim(),
        agent_type: agentType || undefined,
        asset_package_id: Number.isFinite(packageId) && packageId > 0 ? packageId : undefined,
        buyer_offer_price: Number.isFinite(offerPrice) && offerPrice > 0 ? offerPrice : undefined,
        expected_vin_calls: Number.isFinite(vinCalls) && vinCalls >= 0 ? vinCalls : undefined,
        expected_condition_pricing_calls:
          Number.isFinite(conditionCalls) && conditionCalls >= 0 ? conditionCalls : undefined,
        expected_ai_reports: Number.isFinite(aiReports) && aiReports >= 0 ? aiReports : undefined,
        single_task_budget: Number.isFinite(budget) && budget > 0 ? budget : undefined,
        report_type: agentType === "report_generation_agent" ? reportType : undefined,
        rule_scenario:
          agentType &&
          ["operation_planning_agent", "task_generation_agent", "report_generation_agent", "cost_control_agent"].includes(agentType)
            ? ruleScenario.trim() || "default"
            : undefined,
      });
      setLatestRun(run);
      await load();
    } catch (err) {
      const message = err instanceof Error ? err.message : "AI 分析失败";
      setError(message.includes("unsupported_agent_type") || message.includes("agent_type") ? "暂不支持该分析类型" : message);
    } finally {
      setRunning(false);
    }
  }

  async function confirmTaskDraft(taskId: number) {
    if (!canConfirmTasks) {
      setError("当前角色无权确认任务草稿");
      return;
    }
    setActioningTaskId(taskId);
    setError("");
    try {
      await confirmAiAgentTaskDraft(taskId, "人工确认进入正式任务池");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "任务草稿确认失败");
    } finally {
      setActioningTaskId(null);
    }
  }

  async function rejectTaskDraft(taskId: number) {
    if (!canConfirmTasks) {
      setError("当前角色无权驳回任务草稿");
      return;
    }
    setActioningTaskId(taskId);
    setError("");
    try {
      await rejectAiAgentTaskDraft(taskId, "人工复核后驳回任务草稿");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "任务草稿驳回失败");
    } finally {
      setActioningTaskId(null);
    }
  }

  function prepareTaskDraft() {
    setAgentType("task_generation_agent");
    setQuestion("基于当前 AI 建议生成需要人工确认的任务草稿");
    setViewMode("workbench");
    window.setTimeout(() => {
      const target = document.getElementById("quick-analysis");
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function prepareWeeklyPlan() {
    setAgentType("operation_planning_agent");
    setQuestion("生成本周处置作战计划");
    setViewMode("workbench");
    window.setTimeout(() => {
      const target = document.getElementById("quick-analysis");
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  function prepareReportDraft() {
    setAgentType("report_generation_agent");
    setQuestion("生成一份需要人工复核的报告草稿");
    setViewMode("workbench");
    window.setTimeout(() => {
      const target = document.getElementById("quick-analysis");
      target?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  if (loading) {
    return <div className="py-20 text-center text-gray-500">AI 作战台加载中...</div>;
  }

  if (!overview) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-red-700">
        <div className="text-lg font-semibold">AI 作战台暂时不可用</div>
        <p className="mt-2 text-sm">{error || "加载失败，请稍后重试。"}</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 bg-gray-50/70 pb-8">
      <TopJudgmentCard
        output={overview.ai_today_judgment}
        roleScope={overview.role_scope}
        onPlanClick={prepareWeeklyPlan}
        showEvidence={viewMode === "workbench"}
      />

      <ViewModeSwitch viewMode={viewMode} setViewMode={setViewMode} />

      {error && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error}
        </div>
      )}

      {viewMode === "workbench" && (
        <nav className="flex flex-wrap gap-2 rounded-2xl border border-gray-200 bg-white p-3 text-sm shadow-sm" aria-label="AI 作战台页面导航">
          {[
            ["总览", "#overview-metrics"],
            ["AI 建议", "#priority-suggestions"],
            ["待确认", "#confirmations"],
            ["快捷分析", "#quick-analysis"],
            ["任务草稿", "#task-drafts"],
            ["报告草稿", "#report-drafts"],
            ...(currentRole === "admin" ? [["审计日志", "#agent-audit"]] : []),
            ["Agent 工作台", "#agent-workbench"],
          ].map(([label, href]) => (
            <a key={label} href={href} className="rounded-xl px-3 py-2 text-gray-600 hover:bg-gray-50 hover:text-gray-950">
              {label}
            </a>
          ))}
        </nav>
      )}

      {viewMode === "customer" ? (
        <>
          <section id="overview-metrics" className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {metricCards.map((item) => (
              <MetricCard key={item.title} {...item} />
            ))}
          </section>

          <section id="priority-suggestions" className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-gray-950">AI 建议你优先处理</h2>
                <p className="mt-1 text-sm text-gray-500">客户视图只展示业务建议，完整分析依据保留在内部工作台。</p>
              </div>
              <span className="rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700">所有输出需人工复核</span>
            </div>
            <div className="mt-5 space-y-4">
              {suggestions.map((item, index) => (
                <SuggestionCard
                  key={`${item.title}-${index}`}
                  title={item.title}
                  reason={item.reason}
                  action={item.action}
                  output={overview.ai_today_judgment}
                  roleScope={overview.role_scope}
                  onGenerateTask={prepareTaskDraft}
                  showEvidence={false}
                />
              ))}
            </div>
          </section>

          <ConfirmationQueue
            overview={overview}
            canConfirmTasks={canConfirmTasks}
            canConfirmHighRiskTasks={canConfirmHighRiskTasks}
            actioningTaskId={actioningTaskId}
            onConfirmTask={confirmTaskDraft}
            onRejectTask={rejectTaskDraft}
          />
          <CustomerOperationPlan plan={operationPlanPayload} onGeneratePlan={prepareWeeklyPlan} />
          <div id="report-drafts">
            <ReportDraftsSection drafts={reportDraftPayloads} onGenerateReport={prepareReportDraft} />
          </div>
        </>
      ) : (
        <>
          <section id="overview-metrics" className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {metricCards.map((item) => (
              <MetricCard key={item.title} {...item} />
            ))}
          </section>

          <section id="priority-suggestions" className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-xl font-bold text-gray-950">AI 建议你优先处理</h2>
                <p className="mt-1 text-sm text-gray-500">先展示可执行建议，详细分析依据按需展开。</p>
              </div>
              <span className="rounded-full bg-blue-50 px-3 py-1 text-sm font-semibold text-blue-700">所有输出需人工复核</span>
            </div>
            <div className="mt-5 space-y-4">
              {suggestions.map((item, index) => (
                <SuggestionCard
                  key={`${item.title}-${index}`}
                  title={item.title}
                  reason={item.reason}
                  action={item.action}
                  output={overview.ai_today_judgment}
                  roleScope={overview.role_scope}
                  onGenerateTask={prepareTaskDraft}
                  showEvidence
                />
              ))}
            </div>
          </section>

          <ConfirmationQueue
            overview={overview}
            canConfirmTasks={canConfirmTasks}
            canConfirmHighRiskTasks={canConfirmHighRiskTasks}
            actioningTaskId={actioningTaskId}
            onConfirmTask={confirmTaskDraft}
            onRejectTask={rejectTaskDraft}
          />

          <QuickAnalysis
            canRunAgent={canRunAgent}
            running={running}
            question={question}
            setQuestion={setQuestion}
            agentType={agentType}
            setAgentType={setAgentType}
            overview={overview}
            assetPackageId={assetPackageId}
            setAssetPackageId={setAssetPackageId}
            buyerOfferPrice={buyerOfferPrice}
            setBuyerOfferPrice={setBuyerOfferPrice}
            expectedVinCalls={expectedVinCalls}
            setExpectedVinCalls={setExpectedVinCalls}
            expectedConditionPricingCalls={expectedConditionPricingCalls}
            setExpectedConditionPricingCalls={setExpectedConditionPricingCalls}
            expectedAiReports={expectedAiReports}
            setExpectedAiReports={setExpectedAiReports}
            singleTaskBudget={singleTaskBudget}
            setSingleTaskBudget={setSingleTaskBudget}
            reportType={reportType}
            setReportType={setReportType}
            ruleScenario={ruleScenario}
            setRuleScenario={setRuleScenario}
            submitCommand={submitCommand}
          />

          <section id="task-drafts" className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-2xl border border-gray-200 bg-white p-6 shadow-sm">
              <h2 className="text-xl font-bold text-gray-950">任务草稿</h2>
              <p className="mt-1 text-sm text-gray-500">草稿不会自动派发，必须人工确认。</p>
              {overview.pending_tasks.length === 0 ? (
                <div className="mt-5 rounded-2xl border border-dashed border-gray-200 bg-gray-50 p-5 text-sm text-gray-500">暂无任务草稿。</div>
              ) : (
                <div className="mt-5 space-y-3">
                  {overview.pending_tasks.map((task) => (
                    <TaskDraftCard
                      key={task.id}
                      task={task}
                      canConfirmTasks={canConfirmTasks}
                      canConfirmThisTask={task.priority !== "high" || canConfirmHighRiskTasks}
                      actioning={actioningTaskId === task.id}
                      onConfirm={() => confirmTaskDraft(task.id)}
                      onReject={() => rejectTaskDraft(task.id)}
                    />
                  ))}
                </div>
              )}
            </div>
            <RecentAnalysisRecords latestRun={latestRun} overview={overview} />
          </section>

          <div id="report-drafts">
            <ReportDraftsSection drafts={reportDraftPayloads} onGenerateReport={prepareReportDraft} />
          </div>

          <div id="agent-workbench">
            <AgentWorkbench agents={overview.agent_workbench} />
          </div>
          {currentRole === "admin" && (
            <div id="agent-audit">
              <AuditLogPanel logs={auditLogs} />
            </div>
          )}
        </>
      )}
    </div>
  );
}
