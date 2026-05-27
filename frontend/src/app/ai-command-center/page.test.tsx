import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AiCommandCenterPage from "./page";
import {
  getAiCommandOverview,
  listAiDecisionAuditLogs,
  type AiCommandOverview,
} from "@/lib/api";
import { useSession } from "@/components/auth/session-provider";

vi.mock("@/components/auth/session-provider", () => ({
  useSession: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getAiCommandOverview: vi.fn(),
    listAiDecisionAuditLogs: vi.fn(),
    runAiCommandAgent: vi.fn(),
  };
});

const mockUseSession = vi.mocked(useSession);
const mockGetAiCommandOverview = vi.mocked(getAiCommandOverview);
const mockListAiDecisionAuditLogs = vi.mocked(listAiDecisionAuditLogs);

const baseOverview: AiCommandOverview = {
  today_overview: {
    asset_package_count: 12,
    pending_work_orders: 6,
    pending_approval_count: 2,
    agent_runs_today: 3,
    high_risk_asset_count: 4,
    weekly_recommended_disposal_count: 5,
    cost_warning_count: 1,
  },
  ai_today_judgment: {
    summary: "当前资产组合风险为中高，建议优先处理在库新能源车和买方报价偏离资产包。",
    key_findings: ["新能源车辆估值波动较大", "买方报价偏离内部建议区间"],
    recommended_actions: ["优先复核报价偏离资产包", "生成本周作战计划"],
    risk_warnings: ["有车辆估值覆盖低于35%", "存在资料缺口"],
    confidence_score: 0.5,
    evidence: [
      {
        source: "asset_packages",
        label: "asset_count",
        value: 12,
        evidence_source: "asset_packages",
        related_object_type: "asset_package",
        related_object_id: "12",
        calculation_basis: "按当前租户资产包读取",
        data_quality_notes: "-",
      },
    ],
    requires_human_review: true,
    agent_status: "fallback",
  },
  agent_workbench: [
    {
      agent_type: "asset_package_diagnosis_agent",
      name: "资产包解读 Agent",
      stage: "phase_1",
      status: "rules_based",
      min_role: "operator",
    },
    {
      agent_type: "operation_planning_agent",
      name: "运营计划 Agent",
      stage: "phase_2",
      status: "mock",
      min_role: "manager",
    },
  ],
  pending_tasks: [
    {
      id: 1,
      agent_run_id: 10,
      title: "补齐新能源车况资料",
      task_type: "data_completion",
      priority: "high",
      status: "draft",
      requires_human_review: true,
      created_at: "2026-05-22T10:00:00",
      payload: {
        description: "补齐车况照片和权属材料",
        suggested_owner_role: "operator",
        deadline_suggestion: "1天内",
        expected_result: "完成资料复核",
        required_documents: ["车况照片"],
      },
    },
  ],
  pending_approvals: [
    {
      id: 2,
      agent_run_id: 11,
      recommendation_type: "buyer_offer_review",
      title: "买方报价偏离确认",
      summary: "买方报价低于建议区间，需要经理复核。",
      confidence_score: 0.82,
      requires_human_review: true,
      created_at: "2026-05-22T10:00:00",
    },
  ],
  recent_runs: [
    {
      id: 31,
      tenant_id: 1,
      agent_type: "operation_planning_agent",
      status: "succeeded",
      created_by: 1,
      started_at: "2026-05-22T09:00:00",
      finished_at: "2026-05-22T09:01:00",
      requires_human_review: true,
      input: { question: "生成本周处置作战计划" },
      output: {
        summary: "已生成本周半自动运营计划草稿。",
        key_findings: ["高优先级资产池 1 个分层"],
        recommended_actions: ["经理复核高优先级资产池"],
        risk_warnings: ["存在暂缓处置池"],
        confidence_score: 0.72,
        evidence: [
          {
            source: "portfolio_capacity_plan",
            label: "operation_plan",
            value: {
              weekly_focus: ["优先处理高损失贡献分层", "补齐关键资料缺口"],
              high_priority_asset_pool: [{ segment_name: "在库新能源", asset_count: 8 }],
              auction_pool: [{ segment_name: "可竞拍资产", asset_count: 5 }],
              legal_pool: [{ segment_name: "法务路径", asset_count: 2 }],
              data_completion_pool: [{ package_id: 1 }],
              paused_pool: [{ segment_name: "暂缓池" }],
              cashflow_focus: { cash_90d: 1200000 },
            },
            evidence_source: "portfolio_capacity_plan",
            related_object_type: "portfolio_snapshot",
            related_object_id: "1",
            calculation_basis: "基于真实组合分层、资产包风险和产能约束生成规则化运营计划",
            data_quality_notes: "-",
          },
        ],
        requires_human_review: true,
        agent_status: "rules_based",
      },
    },
    {
      id: 32,
      tenant_id: 1,
      agent_type: "report_generation_agent",
      status: "succeeded",
      created_by: 1,
      started_at: "2026-05-22T09:05:00",
      finished_at: "2026-05-22T09:06:00",
      requires_human_review: true,
      input: { question: "生成报告草稿" },
      output: {
        summary: "已生成《高管摘要》草稿。",
        key_findings: ["核心判断"],
        recommended_actions: ["经理复核报告草稿"],
        risk_warnings: ["报告草稿不自动发送"],
        confidence_score: 0.68,
        evidence: [
          {
            source: "report_draft",
            label: "report_draft",
            value: {
              report_type: "executive_summary",
              title: "高管摘要",
              sections: [
                { heading: "核心判断", content: "资产包需人工复核。" },
                { heading: "运营重点", content: "优先处理高风险资产。" },
              ],
              requires_human_review: true,
            },
            evidence_source: "agent_orchestrator",
            related_object_type: "report_draft",
            related_object_id: "executive_summary",
            calculation_basis: "基于资产包定价、运营计划和风险提示生成报告草稿",
            data_quality_notes: "草稿未导出、未发送，需人工复核",
          },
        ],
        requires_human_review: true,
        agent_status: "rules_based",
      },
    },
  ],
  suggested_prompts: ["分析这个资产包适不适合整体出让", "生成本周处置作战计划"],
  role_scope: "operator",
};

function mockSession(role: "viewer" | "operator" | "manager" | "admin" = "operator") {
  mockUseSession.mockReturnValue({
    user: {
      id: 1,
      email: `${role}@example.com`,
      display_name: role,
      role,
      last_login_at: null,
    },
    loading: false,
    refresh: vi.fn(),
    logout: vi.fn(),
    login: vi.fn(),
    register: vi.fn(),
  });
}

describe("AiCommandCenterPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSession("operator");
    mockGetAiCommandOverview.mockResolvedValue(baseOverview);
    mockListAiDecisionAuditLogs.mockResolvedValue([]);
  });

  it("renders the AI daily judgment card", async () => {
    render(<AiCommandCenterPage />);

    expect(await screen.findByRole("heading", { name: "汽车金融不良资产 AI 作战台" })).toBeInTheDocument();
    expect(screen.getByText("整体风险：中高")).toBeInTheDocument();
    expect(screen.getAllByText("需人工复核").length).toBeGreaterThan(0);
    expect(screen.queryByText("降级输出")).not.toBeInTheDocument();
  });

  it("renders four business metric cards", async () => {
    render(<AiCommandCenterPage />);

    expect((await screen.findAllByText("待人工确认")).length).toBeGreaterThan(0);
    expect(screen.getByText("高风险资产")).toBeInTheDocument();
    expect(screen.getByText("本周建议处置")).toBeInTheDocument();
    expect(screen.getByText("成本/额度预警")).toBeInTheDocument();
  });

  it("renders prioritized AI suggestions", async () => {
    render(<AiCommandCenterPage />);

    expect(await screen.findByText("AI 建议你优先处理")).toBeInTheDocument();
    expect(screen.getByText("优先处理本周最高影响事项")).toBeInTheDocument();
    expect(screen.getAllByText("生成任务草稿").length).toBeGreaterThan(0);
  });

  it("renders confirmation queue", async () => {
    render(<AiCommandCenterPage />);

    expect(await screen.findByText("需要你确认")).toBeInTheDocument();
    expect(screen.getByText("报价确认")).toBeInTheDocument();
    expect(screen.getByText("任务草稿确认")).toBeInTheDocument();
    expect(screen.getByText("买方报价偏离确认")).toBeInTheDocument();
  });

  it("renders customer view sections and hides the technical workbench by default", async () => {
    render(<AiCommandCenterPage />);

    expect(await screen.findByText("客户视图")).toBeInTheDocument();
    expect(screen.getByText("本周作战计划")).toBeInTheDocument();
    expect(screen.getByText("报告草稿")).toBeInTheDocument();
    expect(screen.getByText("90 天现金回流关注：1,200,000 元。该计划为规则化草稿，需人工复核后进入任务或审批流程。")).toBeInTheDocument();
    expect(screen.getAllByText("高管摘要").length).toBeGreaterThan(0);
    expect(screen.queryByText("Agent 工作台")).not.toBeInTheDocument();
    expect(screen.queryByText("查看详细依据")).not.toBeInTheDocument();
  });

  it("renders quick analysis entry points in internal workbench and keeps mock status visible", async () => {
    const user = userEvent.setup();
    render(<AiCommandCenterPage />);

    await screen.findByText("客户视图");
    await user.click(screen.getByRole("button", { name: "内部工作台" }));

    expect(await screen.findByText("你想让 AI 帮你做什么？")).toBeInTheDocument();
    expect(screen.getByText("分析资产包")).toBeInTheDocument();
    expect(screen.getByText("判断买方报价")).toBeInTheDocument();
    expect(screen.getAllByText("生成本周作战计划").length).toBeGreaterThan(0);
    expect(screen.getAllByText("生成报告草稿").length).toBeGreaterThan(0);
    expect(screen.getByText("预览能力")).toBeInTheDocument();
  });

  it("hides sensitive evidence for viewer role", async () => {
    const user = userEvent.setup();
    mockSession("viewer");
    mockGetAiCommandOverview.mockResolvedValue({
      ...baseOverview,
      role_scope: "viewer",
      ai_today_judgment: {
        ...baseOverview.ai_today_judgment,
        evidence: [
          {
            source: "asset_packages",
            label: "sensitive_value",
            value: "secret-evidence-value",
            evidence_source: "asset_packages",
            related_object_type: "asset_package",
            related_object_id: "99",
            calculation_basis: "secret-calculation-basis",
            data_quality_notes: "secret-data-quality-note",
          },
        ],
        agent_status: "rules_based",
      },
    });

    render(<AiCommandCenterPage />);

    expect(await screen.findByText("客户视图")).toBeInTheDocument();
    expect(screen.queryByText("查看详细依据")).not.toBeInTheDocument();
    expect(screen.queryByText("secret-evidence-value")).not.toBeInTheDocument();
    expect(screen.queryByText("secret-calculation-basis")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "内部工作台" }));

    expect(await screen.findAllByText("当前角色仅显示摘要级分析依据，不展示敏感证据字段。")).toHaveLength(3);
  });

  it("shows API error state", async () => {
    mockGetAiCommandOverview.mockRejectedValue(new Error("后端 API 不可用"));

    render(<AiCommandCenterPage />);

    expect(await screen.findByText("AI 作战台暂时不可用")).toBeInTheDocument();
    expect(screen.getByText("后端 API 不可用")).toBeInTheDocument();
  });

  it("shows empty states when no tasks, approvals or runs exist", async () => {
    mockGetAiCommandOverview.mockResolvedValue({
      ...baseOverview,
      today_overview: {
        asset_package_count: 0,
        pending_work_orders: 0,
        pending_approval_count: 0,
        agent_runs_today: 0,
      },
      ai_today_judgment: {
        ...baseOverview.ai_today_judgment,
        key_findings: [],
        recommended_actions: [],
        risk_warnings: [],
        evidence: [],
      },
      pending_tasks: [],
      pending_approvals: [],
      recent_runs: [],
    });

    render(<AiCommandCenterPage />);

    expect(await screen.findByText("当前没有待确认事项。若当前租户没有相关数据，系统会保持安全空状态，不跨租户读取其他信息。")).toBeInTheDocument();
    expect(screen.getByText("尚未生成本周作战计划。可由经理发起运营计划分析，系统只生成草稿，不自动派发任务。")).toBeInTheDocument();
    expect(screen.getByText("暂无报告草稿。生成后仅作为内部复核材料，不会自动对外发送。")).toBeInTheDocument();
  });

  it("shows admin audit log panel", async () => {
    const user = userEvent.setup();
    mockSession("admin");
    mockListAiDecisionAuditLogs.mockResolvedValue([
      {
        id: 1,
        agent_run_id: 10,
        decision_type: "cost_control_agent",
        action: "completed",
        actor_user_id: 1,
        requires_human_review: true,
        created_at: "2026-05-22T10:00:00",
        after: { agent_type: "cost_control_agent", status: "succeeded" },
      },
    ]);

    render(<AiCommandCenterPage />);

    await screen.findByText("客户视图");
    await user.click(screen.getByRole("button", { name: "内部工作台" }));

    expect((await screen.findAllByText("审计日志")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("cost_control_agent").length).toBeGreaterThan(0);
    expect(screen.getAllByText("需人工复核").length).toBeGreaterThan(0);
  });
});
