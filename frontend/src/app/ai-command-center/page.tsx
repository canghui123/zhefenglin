"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ClipboardList,
  MessageSquare,
  PlayCircle,
  ShieldCheck,
  Sparkles,
} from "lucide-react";

import { useSession } from "@/components/auth/session-provider";
import { hasRole } from "@/lib/auth";
import {
  getAiCommandOverview,
  runAiCommandAgent,
  type AgentEvidence,
  type AgentOutput,
  type AgentRun,
  type AgentWorkbenchItem,
  type AiAgentType,
  type AiCommandOverview,
} from "@/lib/api";

const AGENT_LABELS: Record<AiAgentType, string> = {
  asset_package_diagnosis_agent: "资产包解读",
  valuation_analysis_agent: "估值分析",
  pricing_strategy_agent: "定价策略",
  buyer_offer_analysis_agent: "买方报价反推",
  operation_planning_agent: "运营计划",
  task_generation_agent: "任务生成",
  report_generation_agent: "报告生成",
  cost_control_agent: "成本控制",
};

const STATUS_LABELS: Record<string, string> = {
  rules_based: "rules_based",
  mock: "mock",
  fallback: "fallback",
  llm_assisted: "llm_assisted",
  succeeded: "已完成",
  running: "运行中",
  failed: "失败",
  draft: "草稿",
};

const ROLE_LABELS: Record<string, string> = {
  viewer: "仅摘要",
  operator: "可发起分析",
  manager: "策略与任务",
  admin: "审计与成本",
};

function metricValue(value: unknown) {
  if (typeof value !== "number") return "0";
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

function EvidencePanel({
  evidence,
  roleScope,
}: {
  evidence: AgentEvidence[];
  roleScope: string;
}) {
  if (roleScope === "viewer") {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
        <div className="text-sm font-semibold text-gray-900">Evidence</div>
        <p className="mt-2 text-sm text-gray-500">当前角色仅显示摘要级 evidence，不展示敏感证据字段。</p>
      </div>
    );
  }

  if (evidence.length === 0) {
    return (
      <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
        <div className="text-sm font-semibold text-gray-900">Evidence</div>
        <p className="mt-2 text-sm text-gray-400">暂无 evidence</p>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
      <div className="mb-3 text-sm font-semibold text-gray-900">Evidence</div>
      <div className="space-y-3">
        {evidence.map((item, index) => (
          <div key={`${item.source}-${item.label}-${index}`} className="rounded-lg bg-white p-3 text-xs text-gray-600">
            <div className="grid gap-2 md:grid-cols-2">
              <div>
                <span className="font-medium text-gray-900">evidence_source：</span>
                {item.evidence_source || item.source}
              </div>
              <div>
                <span className="font-medium text-gray-900">related_object_type：</span>
                {item.related_object_type || item.source || "-"}
              </div>
              <div>
                <span className="font-medium text-gray-900">related_object_id：</span>
                {item.related_object_id || "-"}
              </div>
              <div>
                <span className="font-medium text-gray-900">calculation_basis：</span>
                {item.calculation_basis || `${item.label}: ${evidenceText(item.value)}`}
              </div>
            </div>
            <div className="mt-2">
              <span className="font-medium text-gray-900">data_quality_notes：</span>
              {item.data_quality_notes || "-"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function OutputBlock({ output, roleScope }: { output: AgentOutput; roleScope: string }) {
  return (
    <div className="space-y-4">
      <p className="text-sm leading-6 text-gray-700">{output.summary}</p>
      <div className="flex flex-wrap gap-2 text-xs">
        <span className="rounded-full bg-blue-50 px-3 py-1 font-medium text-blue-700">
          置信度 {confidenceText(output.confidence_score)}
        </span>
        {output.requires_human_review && (
          <span className="rounded-full bg-amber-50 px-3 py-1 font-medium text-amber-700">
            需人工复核
          </span>
        )}
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <ListPanel title="关键发现" items={output.key_findings} emptyText="当前角色仅可查看摘要或暂无发现" />
        <ListPanel title="建议动作" items={output.recommended_actions} emptyText="暂无任务草稿" />
        <ListPanel title="风险提示" items={output.risk_warnings} emptyText="暂无可见风险提示" />
      </div>
      <EvidencePanel evidence={output.evidence} roleScope={roleScope} />
    </div>
  );
}

function ListPanel({
  title,
  items,
  emptyText,
}: {
  title: string;
  items: string[];
  emptyText: string;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4">
      <div className="mb-2 text-sm font-semibold text-gray-900">{title}</div>
      {items.length === 0 ? (
        <p className="text-sm text-gray-400">{emptyText}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, index) => (
            <li key={`${title}-${index}`} className="text-sm leading-5 text-gray-600">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function AgentCard({
  agent,
  selected,
  onSelect,
}: {
  agent: AgentWorkbenchItem;
  selected: boolean;
  onSelect: (agentType: AiAgentType) => void;
}) {
  const isMock = agent.status === "mock";
  return (
    <button
      type="button"
      onClick={() => onSelect(agent.agent_type)}
      className={`h-full rounded-lg border p-4 text-left transition ${
        selected ? "border-blue-500 bg-blue-50" : "border-gray-200 bg-white hover:border-gray-300"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-900">{agent.name}</div>
          <div className="mt-1 text-xs text-gray-500">
            {ROLE_LABELS[agent.min_role] || agent.min_role} · {agent.stage === "phase_1" ? "第一阶段" : "后续阶段"}
          </div>
        </div>
        <span
          className={`shrink-0 rounded-full px-2 py-1 text-xs font-medium ${
            isMock ? "bg-gray-100 text-gray-600" : "bg-emerald-50 text-emerald-700"
          }`}
        >
          {STATUS_LABELS[agent.status] || agent.status}
        </span>
      </div>
    </button>
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
  const [latestRun, setLatestRun] = useState<AgentRun | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setOverview(await getAiCommandOverview());
    } catch (err) {
      setError(err instanceof Error ? err.message : "AI 指挥中心加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const canRunAgent = hasRole(user, "operator");
  const metrics = overview?.today_overview || {};
  const activeAgent = overview?.agent_workbench.find((agent) => agent.agent_type === agentType);

  async function submitCommand() {
    if (!canRunAgent) {
      setError("当前角色只能查看摘要，不能发起 Agent 分析");
      return;
    }
    if (!question.trim() && !agentType) {
      setError("请输入问题或选择 Agent");
      return;
    }

    const packageId = Number(assetPackageId);
    const offerPrice = Number(buyerOfferPrice);
    setRunning(true);
    setError("");
    try {
      const run = await runAiCommandAgent({
        question: question.trim(),
        agent_type: agentType || undefined,
        asset_package_id: Number.isFinite(packageId) && packageId > 0 ? packageId : undefined,
        buyer_offer_price: Number.isFinite(offerPrice) && offerPrice > 0 ? offerPrice : undefined,
      });
      setLatestRun(run);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent 执行失败");
    } finally {
      setRunning(false);
    }
  }

  if (loading) return <div className="py-20 text-center text-gray-500">AI 指挥中心加载中...</div>;
  if (!overview) return <div className="py-20 text-center text-red-500">{error || "加载失败"}</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">AI 指挥中心</h1>
          <p className="mt-1 text-sm text-gray-500">
            基于资产包、估值、定价、沙盘、组合、任务和成本数据生成分析草稿。
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
          <ShieldCheck className="h-4 w-4" />
          关键动作需人工复核
        </div>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <section className="grid gap-4 md:grid-cols-4">
        <div className="rounded-lg border bg-white p-5">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Sparkles className="h-4 w-4" />
            资产包
          </div>
          <div className="mt-2 text-2xl font-bold text-gray-900">{metricValue(metrics.asset_package_count)}</div>
        </div>
        <div className="rounded-lg border bg-white p-5">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <ClipboardList className="h-4 w-4" />
            待处理任务
          </div>
          <div className="mt-2 text-2xl font-bold text-gray-900">{metricValue(metrics.pending_work_orders)}</div>
        </div>
        <div className="rounded-lg border bg-white p-5">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <CheckCircle2 className="h-4 w-4" />
            待审批事项
          </div>
          <div className="mt-2 text-2xl font-bold text-gray-900">{metricValue(metrics.pending_approval_count)}</div>
        </div>
        <div className="rounded-lg border bg-white p-5">
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Bot className="h-4 w-4" />
            今日 Agent 执行
          </div>
          <div className="mt-2 text-2xl font-bold text-gray-900">{metricValue(metrics.agent_runs_today)}</div>
        </div>
      </section>

      <section className="rounded-lg border bg-white p-5">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold text-gray-900">AI 今日判断</h2>
            <p className="mt-1 text-sm text-gray-500">
              当前角色：{ROLE_LABELS[overview.role_scope] || overview.role_scope}
            </p>
          </div>
          <AlertTriangle className="h-5 w-5 text-amber-500" />
        </div>
        <OutputBlock output={overview.ai_today_judgment} roleScope={overview.role_scope} />
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Agent 工作台</h2>
          {activeAgent && <span className="text-sm text-gray-500">已选择：{activeAgent.name}</span>}
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {overview.agent_workbench.map((agent) => (
            <AgentCard
              key={agent.agent_type}
              agent={agent}
              selected={agent.agent_type === agentType}
              onSelect={setAgentType}
            />
          ))}
        </div>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border bg-white p-5">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">待处理任务</h2>
          {overview.pending_tasks.length === 0 ? (
            <p className="text-sm text-gray-400">暂无 Agent 草拟任务</p>
          ) : (
            <div className="space-y-3">
              {overview.pending_tasks.map((task) => (
                <div key={task.id} className="rounded-lg border border-gray-100 p-3">
                  <div className="text-sm font-medium text-gray-900">{task.title}</div>
                  <div className="mt-1 text-xs text-gray-500">
                    {task.task_type} · {task.priority} · {STATUS_LABELS[task.status] || task.status}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border bg-white p-5">
          <h2 className="mb-4 text-lg font-semibold text-gray-900">待审批事项</h2>
          {overview.pending_approvals.length === 0 ? (
            <p className="text-sm text-gray-400">暂无 Agent 建议待审批</p>
          ) : (
            <div className="space-y-3">
              {overview.pending_approvals.map((item) => (
                <div key={item.id} className="rounded-lg border border-gray-100 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-medium text-gray-900">{item.title}</div>
                      <p className="mt-1 text-sm text-gray-600">{item.summary}</p>
                    </div>
                    <span className="shrink-0 rounded-full bg-blue-50 px-2 py-1 text-xs text-blue-700">
                      {confidenceText(item.confidence_score)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="rounded-lg border bg-white p-5">
        <div className="mb-4 flex items-center gap-2">
          <MessageSquare className="h-5 w-5 text-blue-600" />
          <h2 className="text-lg font-semibold text-gray-900">对话式指挥入口</h2>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="space-y-4">
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              className="min-h-28 w-full rounded-lg border border-gray-200 p-3 text-sm outline-none focus:border-blue-500"
              placeholder="输入自然语言问题"
            />
            <div className="flex flex-wrap gap-2">
              {overview.suggested_prompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  onClick={() => setQuestion(prompt)}
                  className="rounded-full border border-gray-200 bg-gray-50 px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100"
                >
                  {prompt}
                </button>
              ))}
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <label className="grid gap-1 text-sm text-gray-600">
                Agent
                <select
                  value={agentType}
                  onChange={(event) => setAgentType(event.target.value as AiAgentType | "")}
                  className="h-10 rounded-lg border border-gray-200 px-3 text-sm"
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
                  className="h-10 rounded-lg border border-gray-200 px-3 text-sm"
                  placeholder="留空使用最新资产包"
                />
              </label>
              <label className="grid gap-1 text-sm text-gray-600">
                买方报价
                <input
                  value={buyerOfferPrice}
                  onChange={(event) => setBuyerOfferPrice(event.target.value)}
                  inputMode="decimal"
                  className="h-10 rounded-lg border border-gray-200 px-3 text-sm"
                  placeholder="报价分析时填写"
                />
              </label>
            </div>
            <button
              type="button"
              onClick={submitCommand}
              disabled={running || !canRunAgent}
              className="inline-flex h-10 items-center gap-2 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white disabled:cursor-not-allowed disabled:bg-gray-300"
            >
              <PlayCircle className="h-4 w-4" />
              {running ? "执行中..." : "运行 Agent"}
            </button>
          </div>

          <div className="rounded-lg border border-gray-200 bg-gray-50 p-4">
            <div className="mb-3 text-sm font-semibold text-gray-900">最近执行</div>
            {latestRun ? (
              <div className="space-y-3">
                <div className="text-xs text-gray-500">
                  #{latestRun.id} · {AGENT_LABELS[latestRun.agent_type as AiAgentType] || latestRun.agent_type} ·{" "}
                  {formatTime(latestRun.finished_at)}
                </div>
                <OutputBlock output={latestRun.output} roleScope={overview.role_scope} />
              </div>
            ) : overview.recent_runs.length > 0 ? (
              <div className="space-y-3">
                {overview.recent_runs.map((run) => (
                  <div key={run.id} className="rounded-lg bg-white p-3">
                    <div className="text-sm font-medium text-gray-900">
                      {AGENT_LABELS[run.agent_type as AiAgentType] || run.agent_type}
                    </div>
                    <div className="mt-1 text-xs text-gray-500">
                      {STATUS_LABELS[run.status] || run.status} · {formatTime(run.finished_at)}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-gray-400">暂无 Agent 执行记录</p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
