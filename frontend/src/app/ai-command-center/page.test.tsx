import { render, screen } from "@testing-library/react";

import AiCommandCenterPage from "./page";
import { getAiCommandOverview, type AiCommandOverview } from "@/lib/api";
import { useSession } from "@/components/auth/session-provider";

vi.mock("@/components/auth/session-provider", () => ({
  useSession: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    getAiCommandOverview: vi.fn(),
    runAiCommandAgent: vi.fn(),
  };
});

const mockUseSession = vi.mocked(useSession);
const mockGetAiCommandOverview = vi.mocked(getAiCommandOverview);

const baseOverview: AiCommandOverview = {
  today_overview: {
    asset_package_count: 0,
    pending_work_orders: 0,
    pending_approval_count: 0,
    agent_runs_today: 0,
  },
  ai_today_judgment: {
    summary: "AI 指挥中心已就绪",
    key_findings: [],
    recommended_actions: [],
    risk_warnings: [],
    confidence_score: 0.5,
    evidence: [],
    requires_human_review: true,
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
      stage: "reserved",
      status: "mock",
      min_role: "manager",
    },
  ],
  pending_tasks: [],
  pending_approvals: [],
  recent_runs: [],
  suggested_prompts: ["分析这个资产包适不适合整体出让"],
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
  });

  it("renders title, agent workbench and human review notice", async () => {
    render(<AiCommandCenterPage />);

    expect(await screen.findByRole("heading", { name: "AI 指挥中心" })).toBeInTheDocument();
    expect(screen.getByText("Agent 工作台")).toBeInTheDocument();
    expect(screen.getByText("关键动作需人工复核")).toBeInTheDocument();
    expect(screen.getByText("rules_based")).toBeInTheDocument();
    expect(screen.getByText("mock")).toBeInTheDocument();
  });

  it("hides sensitive evidence for viewer role", async () => {
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
      },
    });

    render(<AiCommandCenterPage />);

    expect(await screen.findByText("当前角色仅显示摘要级 evidence，不展示敏感证据字段。")).toBeInTheDocument();
    expect(screen.queryByText("secret-evidence-value")).not.toBeInTheDocument();
    expect(screen.queryByText("secret-calculation-basis")).not.toBeInTheDocument();
  });

  it("shows API error state", async () => {
    mockGetAiCommandOverview.mockRejectedValue(new Error("后端 API 不可用"));

    render(<AiCommandCenterPage />);

    expect(await screen.findByText("后端 API 不可用")).toBeInTheDocument();
  });

  it("shows empty states when no tasks, approvals or runs exist", async () => {
    render(<AiCommandCenterPage />);

    expect(await screen.findByText("暂无 Agent 草拟任务")).toBeInTheDocument();
    expect(screen.getByText("暂无 Agent 建议待审批")).toBeInTheDocument();
    expect(screen.getByText("暂无 Agent 执行记录")).toBeInTheDocument();
  });
});
