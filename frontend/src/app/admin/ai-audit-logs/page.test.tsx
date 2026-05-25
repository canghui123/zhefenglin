import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import AiAuditLogsPage from "./page";
import {
  createAiAgentRunReview,
  getAiAgentRunReviewInsights,
  getAiAgentRuleSettings,
  listAiAgentRuleProfiles,
  listAiAgentRunReviews,
  listAiDecisionAuditLogs,
  updateAiAgentRuleSettings,
  type AgentRuleSettings,
} from "@/lib/api";

vi.mock("@/components/admin/admin-access", () => ({
  AdminAccess: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    createAiAgentRunReview: vi.fn(),
    getAiAgentRunReviewInsights: vi.fn(),
    getAiAgentRuleSettings: vi.fn(),
    listAiAgentRuleProfiles: vi.fn(),
    listAiAgentRunReviews: vi.fn(),
    listAiDecisionAuditLogs: vi.fn(),
    updateAiAgentRuleSettings: vi.fn(),
  };
});

const mockGetSettings = vi.mocked(getAiAgentRuleSettings);
const mockUpdateSettings = vi.mocked(updateAiAgentRuleSettings);
const mockListProfiles = vi.mocked(listAiAgentRuleProfiles);
const mockGetInsights = vi.mocked(getAiAgentRunReviewInsights);
const mockListLogs = vi.mocked(listAiDecisionAuditLogs);
const mockListReviews = vi.mocked(listAiAgentRunReviews);
const mockCreateReview = vi.mocked(createAiAgentRunReview);

const baseSettings: AgentRuleSettings = {
  tenant_id: 1,
  agent_type: "global",
  scenario: "default",
  version: 1,
  is_active: true,
  updated_by: null,
  updated_at: null,
  operation_high_priority_limit: 5,
  operation_data_gap_min_count: 1,
  task_max_drafts: 8,
  task_urgent_deadline_days: 1,
  task_normal_deadline_days: 7,
  cost_budget_warning_percent: 0.8,
  cost_condition_call_approval_threshold: 1,
  cost_ai_report_merge_threshold: 2,
  report_confidence_floor: 0.4,
  report_max_sections: 3,
};

describe("AiAuditLogsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetSettings.mockResolvedValue(baseSettings);
    mockUpdateSettings.mockResolvedValue(baseSettings);
    mockListProfiles.mockResolvedValue([
      {
        tenant_id: 1,
        agent_type: "operation_planning_agent",
        scenario: "stress_week",
        version: 2,
        is_active: true,
        updated_by: 1,
        updated_at: "2026-05-23T10:00:00",
      },
    ]);
    mockGetInsights.mockResolvedValue({
      tenant_id: 1,
      review_count: 1,
      average_usefulness_score: 4,
      average_accuracy_score: 3,
      accepted_actions_count: 2,
      rejected_actions_count: 1,
      follow_up_required_count: 1,
      acceptance_rate: 0.67,
      recommendations: ["建议复核 Agent evidence 和阈值配置"],
      requires_human_review: true,
    });
    mockListLogs.mockResolvedValue([
      {
        id: 1,
        agent_run_id: 12,
        decision_type: "task_generation_agent",
        action: "completed",
        actor_user_id: 1,
        requires_human_review: true,
        created_at: "2026-05-23T10:00:00",
        after: { status: "succeeded" },
      },
    ]);
    mockListReviews.mockResolvedValue([]);
    mockCreateReview.mockResolvedValue({
      id: 1,
      tenant_id: 1,
      agent_run_id: 12,
      reviewer_user_id: 1,
      outcome: "partial",
      usefulness_score: 3,
      accuracy_score: 3,
      accepted_actions_count: 0,
      rejected_actions_count: 0,
      follow_up_required: false,
      feedback: "",
      created_at: "2026-05-23T10:05:00",
    });
  });

  it("renders independent AI audit page with settings, logs and review loop", async () => {
    render(<AiAuditLogsPage />);

    expect(await screen.findByRole("heading", { name: "AI 审计日志" })).toBeInTheDocument();
    expect(screen.getByText("规则阈值配置")).toBeInTheDocument();
    expect(screen.getByText("复盘闭环")).toBeInTheDocument();
    expect(screen.getByText("AI 决策审计日志")).toBeInTheDocument();
    expect(screen.getAllByText("task_generation_agent").length).toBeGreaterThan(0);
    expect(screen.getByText("operation_planning_agent/stress_week v2")).toBeInTheDocument();
    expect(screen.getByText("复盘洞察")).toBeInTheDocument();
    expect(screen.getByText("建议复核 Agent evidence 和阈值配置")).toBeInTheDocument();
    expect(screen.getAllByDisplayValue("5").length).toBeGreaterThan(0);
  });

  it("saves rule settings and creates a review record", async () => {
    const user = userEvent.setup();
    render(<AiAuditLogsPage />);

    await screen.findByText("规则阈值配置");
    await user.click(screen.getByRole("button", { name: /保存阈值/ }));

    await waitFor(() => {
      expect(mockUpdateSettings).toHaveBeenCalledWith(
        expect.objectContaining({ agent_type: "global", scenario: "default", task_max_drafts: 8 }),
      );
    });
    expect(await screen.findByText("阈值配置已保存，后续 Agent run 将使用新配置。")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /提交复盘/ }));

    await waitFor(() => {
      expect(mockCreateReview).toHaveBeenCalledWith(12, expect.objectContaining({ outcome: "partial" }));
    });
  });

  it("shows API error state", async () => {
    mockGetSettings.mockRejectedValue(new Error("AI 审计 API 不可用"));

    render(<AiAuditLogsPage />);

    expect(await screen.findByText("AI 审计 API 不可用")).toBeInTheDocument();
  });
});
