from models.ai_command import AgentOutput
from services.agent_orchestrator import (
    AGENT_CATALOG,
    _task_draft,
    classify_intent,
    redact_output_for_role,
)


def test_classify_intent_routes_common_command_questions():
    assert classify_intent("买方报价是否合理") == "buyer_offer_analysis_agent"
    assert classify_intent("车300估值覆盖率怎么样") == "valuation_analysis_agent"
    assert classify_intent("分析这个资产包适不适合整体出让") == "pricing_strategy_agent"
    assert classify_intent("生成本周处置作战计划") == "operation_planning_agent"
    assert classify_intent("哪些车辆需要补资料") == "task_generation_agent"
    assert classify_intent("看看最新资产包有什么风险") == "asset_package_diagnosis_agent"


def test_agent_catalog_marks_semi_automated_agents_rules_based():
    assert AGENT_CATALOG["asset_package_diagnosis_agent"]["status"] == "rules_based"
    assert AGENT_CATALOG["valuation_analysis_agent"]["status"] == "rules_based"
    assert AGENT_CATALOG["pricing_strategy_agent"]["status"] == "rules_based"
    assert AGENT_CATALOG["buyer_offer_analysis_agent"]["status"] == "rules_based"
    assert AGENT_CATALOG["operation_planning_agent"]["status"] == "rules_based"
    assert AGENT_CATALOG["task_generation_agent"]["status"] == "rules_based"
    assert AGENT_CATALOG["report_generation_agent"]["status"] == "rules_based"
    assert AGENT_CATALOG["cost_control_agent"]["status"] == "rules_based"


def test_task_draft_schema_contains_reviewable_action_fields():
    draft = _task_draft(
        title="复核高成本能力调用审批",
        description="需要管理员复核额度与审批边界。",
        task_type="cost_approval",
        priority="high",
        related_object_type="tenant_cost_quota",
        related_object_id="tenant-1",
        suggested_owner_role="admin",
        deadline_days=1,
        required_documents=["成本预估", "套餐额度"],
        expected_result="形成是否允许高成本能力调用的人工审批意见",
        evidence=[{"source": "agent_request", "label": "single_task_budget", "value": 100}],
        confidence_score=0.66,
    )

    assert draft["task_type"] == "cost_approval"
    assert draft["status"] == "draft"
    assert draft["requires_human_review"] is True
    assert draft["suggested_owner_role"] == "admin"
    assert draft["deadline_suggestion"]
    assert draft["related_object_type"] == "tenant_cost_quota"
    assert draft["required_documents"]
    assert draft["expected_result"]
    assert draft["evidence"]
    assert draft["confidence_score"] == 0.66


def test_viewer_output_redaction_only_keeps_summary_and_review_flag():
    output = AgentOutput(
        summary="摘要可见",
        key_findings=["策略细节"],
        recommended_actions=["任务草稿"],
        risk_warnings=["风险提示"],
        confidence_score=0.8,
        evidence=[{"source": "assets", "label": "package_id", "value": 1}],
        requires_human_review=True,
        agent_status="rules_based",
    )

    redacted = redact_output_for_role(output, "viewer")

    assert redacted.summary == "摘要可见"
    assert redacted.key_findings == []
    assert redacted.recommended_actions == []
    assert redacted.risk_warnings == []
    assert redacted.evidence == []
    assert redacted.confidence_score == 0.8
    assert redacted.requires_human_review is True
    assert redacted.agent_status == "rules_based"
