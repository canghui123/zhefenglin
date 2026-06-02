"""B2 — 评测框架核心:载入 case / 跑 / 评分 / 报告。

设计原则:
- Case YAML 完全声明式:输入 + must / should / forbidden 断言
- Agent 调用走真实代码路径(_diagnose_asset_package / _operation_planning_agent),
  确保评测和生产行为一致
- 报告分级:must fail = case FAIL;should fail = WARN(不影响通过率);forbidden hit = FAIL
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from evals.assertions import run_assertion
from evals.factories import build_package_context
from models.ai_command import AgentOutput, AgentRunCreate
from services.agent_orchestrator import (
    AGENT_CATALOG,
    PackageContext,
    PortfolioContext,
    _analyze_pricing,
    _diagnose_asset_package,
    _operation_planning_agent,
)
from models.ai_command import AgentRuleSettings


# 各 Agent 的入口函数(签名兼容 PackageContext + 必要参数)
def _diag_runner(ctx: PackageContext, case_input: dict) -> AgentOutput:
    return _diagnose_asset_package(ctx)


def _pricing_runner(ctx: PackageContext, case_input: dict) -> AgentOutput:
    return _analyze_pricing(ctx)


def _ops_runner(ctx: PackageContext, case_input: dict) -> AgentOutput:
    """运营计划 Agent 需要 portfolio 上下文 + rule_settings。"""
    portfolio = PortfolioContext(
        snapshot_id=None,
        snapshot_date=None,
        segments=[],
        capacity_plan=None,
        empty_reason=case_input.get("empty_reason"),
    )
    rule_settings = AgentRuleSettings()
    rule_profile: dict = {}
    recent_recommendations: list = []
    return _operation_planning_agent(
        ctx, portfolio, rule_settings, rule_profile, recent_recommendations
    )


AGENT_RUNNERS: dict[str, Callable[[PackageContext, dict], AgentOutput]] = {
    "asset_package_diagnosis_agent": _diag_runner,
    "pricing_strategy_agent": _pricing_runner,
    "operation_planning_agent": _ops_runner,
}


@dataclass
class AssertionResult:
    name: str
    passed: bool
    message: str
    severity: str  # 'must' | 'should' | 'forbidden'


@dataclass
class CaseResult:
    case_id: str
    description: str
    agent_type: str
    case_path: str
    elapsed_ms: float
    must_results: list[AssertionResult] = field(default_factory=list)
    should_results: list[AssertionResult] = field(default_factory=list)
    forbidden_results: list[AssertionResult] = field(default_factory=list)
    error: Optional[str] = None
    output_summary: Optional[str] = None
    output_confidence: Optional[float] = None
    output_requires_review: Optional[bool] = None
    output_status: Optional[str] = None

    @property
    def passed(self) -> bool:
        if self.error:
            return False
        must_ok = all(r.passed for r in self.must_results)
        forbidden_ok = all(r.passed for r in self.forbidden_results)
        return must_ok and forbidden_ok

    @property
    def should_pass_rate(self) -> float:
        if not self.should_results:
            return 1.0
        return sum(1 for r in self.should_results if r.passed) / len(self.should_results)


# ============================================================
# Case loading
# ============================================================

def load_cases(cases_dir: Path) -> list[dict]:
    """递归加载 cases_dir 下所有 .yaml,返回 case dict 列表(附 _path)。"""
    cases = []
    for yaml_path in sorted(cases_dir.rglob("*.yaml")):
        with yaml_path.open(encoding="utf-8") as f:
            case = yaml.safe_load(f)
        case["_path"] = str(yaml_path.relative_to(cases_dir.parent.parent))
        cases.append(case)
    return cases


# ============================================================
# Case runner
# ============================================================

def run_case(case: dict) -> CaseResult:
    case_id = case.get("case_id", "(unnamed)")
    description = case.get("description", "")
    agent_type = case.get("agent_type", "")
    case_path = case.get("_path", "")

    if agent_type not in AGENT_RUNNERS:
        return CaseResult(
            case_id=case_id,
            description=description,
            agent_type=agent_type,
            case_path=case_path,
            elapsed_ms=0,
            error=f"未知 agent_type: {agent_type!r}",
        )

    # 构造 context
    try:
        ctx = build_package_context(case.get("input", {}))
    except Exception as exc:  # noqa: BLE001
        return CaseResult(
            case_id=case_id,
            description=description,
            agent_type=agent_type,
            case_path=case_path,
            elapsed_ms=0,
            error=f"构造 context 失败:{type(exc).__name__}: {exc}",
        )

    # 跑 Agent
    runner = AGENT_RUNNERS[agent_type]
    start = time.perf_counter()
    try:
        output: AgentOutput = runner(ctx, case.get("input", {}))
    except Exception as exc:  # noqa: BLE001
        return CaseResult(
            case_id=case_id,
            description=description,
            agent_type=agent_type,
            case_path=case_path,
            elapsed_ms=round((time.perf_counter() - start) * 1000, 2),
            error=f"Agent 运行异常:{type(exc).__name__}: {exc}",
        )
    elapsed_ms = round((time.perf_counter() - start) * 1000, 2)

    # 跑断言
    expectations = case.get("expectations", {})
    result = CaseResult(
        case_id=case_id,
        description=description,
        agent_type=agent_type,
        case_path=case_path,
        elapsed_ms=elapsed_ms,
        output_summary=output.summary,
        output_confidence=output.confidence_score,
        output_requires_review=output.requires_human_review,
        output_status=output.agent_status,
    )

    for assertion in expectations.get("must", []):
        passed, name, msg = run_assertion(output, assertion)
        result.must_results.append(AssertionResult(name=name, passed=passed, message=msg, severity="must"))
    for assertion in expectations.get("should", []):
        passed, name, msg = run_assertion(output, assertion)
        result.should_results.append(AssertionResult(name=name, passed=passed, message=msg, severity="should"))
    for assertion in expectations.get("forbidden", []):
        passed, name, msg = run_assertion(output, assertion)
        result.forbidden_results.append(AssertionResult(name=name, passed=passed, message=msg, severity="forbidden"))

    return result


# ============================================================
# Report rendering
# ============================================================

def render_markdown_report(results: list[CaseResult], evals_dir: Path) -> str:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    fail = total - passed
    pass_rate = (passed / total * 100) if total else 0
    avg_elapsed = sum(r.elapsed_ms for r in results) / total if total else 0

    lines = [
        "# Agent 评测基线报告",
        "",
        f"- 时间:{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Case 总数:{total}",
        f"- 通过率:**{pass_rate:.1f}% ({passed}/{total})**",
        f"- 平均 Agent 响应:{avg_elapsed:.1f} ms",
        "",
    ]

    # 按 Agent 分组统计
    by_agent: dict[str, list[CaseResult]] = {}
    for r in results:
        by_agent.setdefault(r.agent_type, []).append(r)

    lines.extend([
        "## 按 Agent 分组",
        "",
        "| Agent | Case 数 | 通过 | 通过率 | 平均响应 (ms) |",
        "|---|---|---|---|---|",
    ])
    for agent, items in sorted(by_agent.items()):
        n = len(items)
        p = sum(1 for r in items if r.passed)
        avg = sum(r.elapsed_ms for r in items) / n if n else 0
        lines.append(f"| `{agent}` | {n} | {p} | {p / n * 100:.0f}% | {avg:.1f} |")

    lines.append("")

    # 详细 case 报告
    lines.append("## 详细 Case 结果")
    lines.append("")
    for r in results:
        status = "✅ PASS" if r.passed else "❌ FAIL"
        lines.append(f"### {status} `{r.case_id}` ({r.agent_type})")
        lines.append("")
        lines.append(f"- {r.description}")
        lines.append(f"- 路径:`{r.case_path}`")
        lines.append(f"- Agent 响应:{r.elapsed_ms} ms")
        if r.output_status:
            lines.append(f"- agent_status:`{r.output_status}` · confidence:`{r.output_confidence}` · requires_review:`{r.output_requires_review}`")
        if r.output_summary:
            lines.append(f"- summary:_{r.output_summary[:140]}_")
        if r.error:
            lines.append(f"- **ERROR**: `{r.error}`")
        lines.append("")
        if r.must_results:
            lines.append("**must 断言:**")
            for ar in r.must_results:
                check = "✓" if ar.passed else "✗"
                lines.append(f"- {check} `{ar.name}`:{ar.message}")
            lines.append("")
        if r.should_results:
            should_passed = sum(1 for ar in r.should_results if ar.passed)
            lines.append(f"**should 断言** ({should_passed}/{len(r.should_results)} 通过):")
            for ar in r.should_results:
                check = "✓" if ar.passed else "•"
                lines.append(f"- {check} `{ar.name}`:{ar.message}")
            lines.append("")
        if r.forbidden_results:
            lines.append("**forbidden 断言(违禁语句检查):**")
            for ar in r.forbidden_results:
                check = "✓" if ar.passed else "🚫"
                lines.append(f"- {check} `{ar.name}`:{ar.message}")
            lines.append("")

    return "\n".join(lines)


def save_reports(results: list[CaseResult], evals_dir: Path) -> tuple[Path, Path]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    reports_dir = evals_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    md_path = reports_dir / f"baseline_{timestamp}.md"
    md_path.write_text(render_markdown_report(results, evals_dir), encoding="utf-8")

    # JSON 给 CI / 后续对比用
    json_path = reports_dir / "latest.json"
    payload = {
        "timestamp": datetime.now().isoformat(),
        "total": len(results),
        "passed": sum(1 for r in results if r.passed),
        "cases": [
            {
                "case_id": r.case_id,
                "agent_type": r.agent_type,
                "passed": r.passed,
                "elapsed_ms": r.elapsed_ms,
                "must_pass": sum(1 for a in r.must_results if a.passed),
                "must_total": len(r.must_results),
                "should_pass": sum(1 for a in r.should_results if a.passed),
                "should_total": len(r.should_results),
                "forbidden_pass": sum(1 for a in r.forbidden_results if a.passed),
                "forbidden_total": len(r.forbidden_results),
                "error": r.error,
                "output_status": r.output_status,
                "output_confidence": r.output_confidence,
            }
            for r in results
        ],
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return md_path, json_path
