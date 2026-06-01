#!/usr/bin/env python3
"""Production main-path smoke test for zhefenglin.com.

The script is intentionally API-only:
- no browser automation
- no uploads
- no task confirmation
- no user creation

Credentials are read from environment variables first, then prompted
interactively. Passwords are never printed or written to the report.
"""

from __future__ import annotations

import getpass
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Optional

import requests


BASE_URL = os.getenv("AF_SMOKE_BASE_URL", "https://zhefenglin.com").rstrip("/")
ONLINE_COMMIT = os.getenv("AF_SMOKE_COMMIT", "2e74aac")
DEFAULT_EMAIL = os.getenv("AF_SMOKE_EMAIL", "")
DEFAULT_PASSWORD = os.getenv("AF_SMOKE_PASSWORD", "")
REQUEST_TIMEOUT = float(os.getenv("AF_SMOKE_TIMEOUT", "30"))


@dataclass
class ApiResult:
    method: str
    path: str
    status_code: Optional[int]
    elapsed_ms: float
    ok: bool
    body: Any = None
    error: Optional[str] = None


@dataclass
class StepResult:
    number: int
    title: str
    api: str
    passed: bool
    elapsed_ms: float = 0
    status_code: Optional[int] = None
    checks: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    response_body: Any = None


class SmokeClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url
        self.session = requests.Session()
        self.timings: list[tuple[str, float]] = []

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: Optional[dict[str, Any]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> ApiResult:
        url = f"{self.base_url}{path}"
        print(f"将要调用：{method.upper()} {url}")
        start = time.perf_counter()
        try:
            response = self.session.request(
                method=method.upper(),
                url=url,
                json=json_body,
                params=params,
                timeout=REQUEST_TIMEOUT,
                verify=True,
            )
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            try:
                body: Any = response.json()
            except ValueError:
                body = response.text
            print(f"完成：{method.upper()} {path} -> HTTP {response.status_code}, {elapsed_ms} ms")
            self.timings.append((f"{method.upper()} {path}", elapsed_ms))
            return ApiResult(
                method=method.upper(),
                path=path,
                status_code=response.status_code,
                elapsed_ms=elapsed_ms,
                ok=response.ok,
                body=body,
            )
        except Exception as exc:  # noqa: BLE001 - smoke test should keep running.
            elapsed_ms = round((time.perf_counter() - start) * 1000, 2)
            print(f"失败：{method.upper()} {path} -> {exc}, {elapsed_ms} ms")
            self.timings.append((f"{method.upper()} {path}", elapsed_ms))
            return ApiResult(
                method=method.upper(),
                path=path,
                status_code=None,
                elapsed_ms=elapsed_ms,
                ok=False,
                error=str(exc),
            )


def require(condition: bool, passed: str, failed: str, checks: list[str], failures: list[str]) -> None:
    if condition:
        checks.append(passed)
    else:
        failures.append(failed)


def is_agent_output(value: Any, checks: list[str], failures: list[str], *, require_rules_based: bool = True) -> None:
    if not isinstance(value, dict):
        failures.append("AgentOutput 不是对象")
        return
    for key in [
        "summary",
        "key_findings",
        "recommended_actions",
        "risk_warnings",
        "confidence_score",
        "evidence",
        "requires_human_review",
        "agent_status",
    ]:
        require(key in value, f"AgentOutput 包含 {key}", f"AgentOutput 缺少 {key}", checks, failures)
    score = value.get("confidence_score")
    require(isinstance(score, (int, float)) and 0 <= score <= 1, "confidence_score 在 0..1", f"confidence_score 非法：{score}", checks, failures)
    require(value.get("requires_human_review") is True, "requires_human_review=true", "requires_human_review 不是 true", checks, failures)
    if require_rules_based:
        require(value.get("agent_status") == "rules_based", "agent_status=rules_based", f"agent_status 不是 rules_based：{value.get('agent_status')}", checks, failures)


def extract_operation_plan(run_body: Any) -> Optional[dict[str, Any]]:
    output = run_body.get("output") if isinstance(run_body, dict) else None
    evidence = output.get("evidence") if isinstance(output, dict) else None
    if not isinstance(evidence, list):
        return None
    for item in evidence:
        if isinstance(item, dict) and item.get("label") == "operation_plan" and isinstance(item.get("value"), dict):
            return item["value"]
    return None


def extract_pricing_labels(run_body: Any) -> set[str]:
    output = run_body.get("output") if isinstance(run_body, dict) else None
    evidence = output.get("evidence") if isinstance(output, dict) else None
    if not isinstance(evidence, list):
        return set()
    return {str(item.get("label")) for item in evidence if isinstance(item, dict)}


def json_pretty(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def run_step(
    number: int,
    title: str,
    api: str,
    fn: Callable[[list[str], list[str]], tuple[ApiResult, Any]],
) -> tuple[StepResult, Any]:
    checks: list[str] = []
    failures: list[str] = []
    extra: Any = None
    try:
        api_result, extra = fn(checks, failures)
    except Exception as exc:  # noqa: BLE001 - continue after each step failure.
        api_result = ApiResult("?", api, None, 0, False, error=str(exc))
        failures.append(str(exc))
    passed = api_result.ok and not failures
    step = StepResult(
        number=number,
        title=title,
        api=api,
        passed=passed,
        elapsed_ms=api_result.elapsed_ms,
        status_code=api_result.status_code,
        checks=checks,
        failures=failures,
        response_body=api_result.body if not passed else None,
    )
    print(
        f"Step {number} {'PASS' if passed else 'FAIL'}：{title} "
        f"HTTP={api_result.status_code} elapsed={api_result.elapsed_ms}ms"
    )
    for item in checks[:8]:
        print(f"  ✓ {item}")
    for item in failures:
        print(f"  ✗ {item}")
    return step, extra


def choose_asset_package(client: SmokeClient) -> tuple[Optional[int], list[dict[str, Any]]]:
    result = client.request("GET", "/api/asset-package/list/all")
    packages = result.body if isinstance(result.body, list) else []
    for pkg in packages:
        package_id = pkg.get("id")
        if not isinstance(package_id, int):
            continue
        detail = client.request("GET", f"/api/asset-package/{package_id}")
        body = detail.body if isinstance(detail.body, dict) else {}
        summary = ((body.get("results") or {}).get("summary") or {}) if isinstance(body, dict) else {}
        if summary.get("recommended_transfer_price_mid") is not None and summary.get("tradeability_level") is not None:
            return package_id, packages
    first_id = packages[0].get("id") if packages and isinstance(packages[0], dict) else None
    return first_id if isinstance(first_id, int) else None, packages


def write_report(
    steps: list[StepResult],
    timings: list[tuple[str, float]],
    report_path: Path,
) -> None:
    passed = sum(1 for step in steps if step.passed)
    total = len(steps)
    avg = round(statistics.mean([item[1] for item in timings]), 2) if timings else 0
    slowest = sorted(timings, key=lambda item: item[1], reverse=True)[:3]
    lines = [
        "# 线上主路径回归报告",
        "",
        f"- 测试时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 线上域名：{BASE_URL}",
        f"- 线上 commit：`{ONLINE_COMMIT}`",
        f"- 总体通过率：{passed}/{total} ({round(passed / total * 100, 2) if total else 0}%)",
        "- 说明：脚本使用 `requests.Session()` 管理 HttpOnly Cookie；未上传文件、未确认任务、未创建用户。",
        "- 代码签名修正：资产包列表实际接口为 `/api/asset-package/list/all`；AI 审计日志实际接口为 `/api/ai-command-center/decision-audit-logs`。",
        "",
    ]
    for step in steps:
        lines.extend(
            [
                f"## Step {step.number}: {step.title}",
                "",
                f"- API：`{step.api}`",
                f"- HTTP 状态：`{step.status_code}`",
                f"- 响应时间：`{step.elapsed_ms} ms`",
                f"- 结果：{'PASS' if step.passed else 'FAIL'}",
                "",
                "### 关键字段验证",
                "",
            ]
        )
        if step.checks:
            lines.extend([f"- [x] {item}" for item in step.checks])
        if step.failures:
            lines.extend([f"- [ ] {item}" for item in step.failures])
        if not step.checks and not step.failures:
            lines.append("- 无")
        if not step.passed:
            lines.extend(
                [
                    "",
                    "### Response Body",
                    "",
                    "```json",
                    json_pretty(step.response_body),
                    "```",
                ]
            )
        lines.append("")
    lines.extend(
        [
            "## 性能指标汇总",
            "",
            f"- 平均响应时间：`{avg} ms`",
            "- 最慢 3 个 API：",
        ]
    )
    if slowest:
        lines.extend([f"  - `{name}`：`{elapsed} ms`" for name, elapsed in slowest])
    else:
        lines.append("  - 无")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print("⚠️ 即将访问生产环境 zhefenglin.com，是否继续？")
    input("按回车继续，或 Ctrl+C 取消：")

    email = DEFAULT_EMAIL or input("请输入生产 smoke admin email（不会写入报告）：").strip()
    password = DEFAULT_PASSWORD or getpass.getpass("请输入生产 smoke admin password（不会显示/写入报告）：")
    if not email or not password:
        print("缺少 email 或 password，退出。", file=sys.stderr)
        return 2

    client = SmokeClient(BASE_URL)
    steps: list[StepResult] = []
    context: dict[str, Any] = {
        "agent_run_ids": {},
        "packages": [],
        "asset_package_id": None,
    }

    def step1(checks: list[str], failures: list[str]) -> tuple[ApiResult, Any]:
        result = client.request("POST", "/api/auth/login", json_body={"email": email, "password": password})
        body = result.body if isinstance(result.body, dict) else {}
        require(result.status_code == 200, "登录 HTTP 200", f"登录状态不是 200：{result.status_code}", checks, failures)
        require("access_token" in body, "响应含 access_token", "响应缺少 access_token", checks, failures)
        require("user" in body, "响应含 user", "响应缺少 user", checks, failures)
        require(bool(client.session.cookies), "Session 已持有 cookie", "Session 未收到 cookie", checks, failures)
        return result, body

    def step2(checks: list[str], failures: list[str]) -> tuple[ApiResult, Any]:
        result = client.request("GET", "/api/auth/me")
        body = result.body if isinstance(result.body, dict) else {}
        require(result.status_code == 200, "me HTTP 200", f"me 状态不是 200：{result.status_code}", checks, failures)
        require(body.get("role") == "admin", "role=admin", f"role 不是 admin：{body.get('role')}", checks, failures)
        require("feature_capabilities" in body and isinstance(body.get("feature_capabilities"), dict), "含 feature_capabilities snapshot", "缺少 feature_capabilities snapshot", checks, failures)
        require("id" in body and "email" in body, "含 user id/email", "缺少 user id/email", checks, failures)
        if "tenant_id" not in body:
            checks.append("实现说明：UserOut 当前不直接暴露 tenant_id，后续 API 通过登录态解析当前租户")
        return result, body

    def step3(checks: list[str], failures: list[str]) -> tuple[ApiResult, Any]:
        result = client.request("GET", "/api/ai-command-center/overview")
        body = result.body if isinstance(result.body, dict) else {}
        require(result.status_code == 200, "overview HTTP 200", f"overview 状态不是 200：{result.status_code}", checks, failures)
        for key in ["today_overview", "ai_today_judgment", "agent_workbench", "pending_tasks", "suggested_prompts"]:
            require(key in body, f"overview 含 {key}", f"overview 缺少 {key}", checks, failures)
        is_agent_output(body.get("ai_today_judgment"), checks, failures, require_rules_based=False)
        workbench = body.get("agent_workbench")
        require(isinstance(workbench, list) and len(workbench) == 8, f"agent_workbench 8 个：{len(workbench) if isinstance(workbench, list) else 'N/A'}", "agent_workbench 不是 8 个", checks, failures)
        return result, body

    def step4(checks: list[str], failures: list[str]) -> tuple[ApiResult, Any]:
        result = client.request("POST", "/api/ai-command-center/runs", json_body={"agent_type": "asset_package_diagnosis_agent", "question": "线上主路径回归：资产包诊断"})
        body = result.body if isinstance(result.body, dict) else {}
        require(result.status_code == 200, "Agent run HTTP 200", f"状态不是 200：{result.status_code}", checks, failures)
        require(body.get("agent_type") == "asset_package_diagnosis_agent", "agent_type 正确", f"agent_type 异常：{body.get('agent_type')}", checks, failures)
        is_agent_output(body.get("output"), checks, failures)
        if isinstance(body.get("id"), int):
            context["agent_run_ids"]["asset_package_diagnosis_agent"] = body["id"]
        return result, body

    def step5(checks: list[str], failures: list[str]) -> tuple[ApiResult, Any]:
        result = client.request("POST", "/api/ai-command-center/runs", json_body={"agent_type": "operation_planning_agent", "question": "线上主路径回归：生成本周处置作战计划"})
        body = result.body if isinstance(result.body, dict) else {}
        require(result.status_code == 200, "Agent run HTTP 200", f"状态不是 200：{result.status_code}", checks, failures)
        require(body.get("agent_type") == "operation_planning_agent", "agent_type 正确", f"agent_type 异常：{body.get('agent_type')}", checks, failures)
        is_agent_output(body.get("output"), checks, failures)
        plan = extract_operation_plan(body)
        require(isinstance(plan, dict), "evidence 含 operation_plan", "缺少 operation_plan evidence", checks, failures)
        if isinstance(plan, dict):
            for key in [
                "high_priority_asset_pool",
                "quick_auction_pool",
                "legal_advancement_pool",
                "data_completion_pool",
                "debt_transfer_pool",
                "observe_pool",
                "capacity_budget_constraints",
                "missing_data",
                "data_quality_notes",
            ]:
                require(key in plan, f"operation_plan 含 {key}", f"operation_plan 缺少 {key}", checks, failures)
        if isinstance(body.get("id"), int):
            context["agent_run_ids"]["operation_planning_agent"] = body["id"]
        return result, body

    def step6(checks: list[str], failures: list[str]) -> tuple[ApiResult, Any]:
        package_id = context.get("asset_package_id")
        if not package_id:
            package_id, packages = choose_asset_package(client)
            context["asset_package_id"] = package_id
            context["packages"] = packages
        payload = {"agent_type": "pricing_strategy_agent", "question": "线上主路径回归：定价策略"}
        if package_id:
            payload["asset_package_id"] = package_id
        result = client.request("POST", "/api/ai-command-center/runs", json_body=payload)
        body = result.body if isinstance(result.body, dict) else {}
        require(result.status_code == 200, "Agent run HTTP 200", f"状态不是 200：{result.status_code}", checks, failures)
        require(body.get("agent_type") == "pricing_strategy_agent", "agent_type 正确", f"agent_type 异常：{body.get('agent_type')}", checks, failures)
        require(bool(package_id), f"传入 asset_package_id={package_id}", "未能找到可用 asset_package_id", checks, failures)
        is_agent_output(body.get("output"), checks, failures)
        output = body.get("output") if isinstance(body.get("output"), dict) else {}
        findings_text = " ".join(str(item) for item in output.get("key_findings", []))
        labels = extract_pricing_labels(body)
        require("推荐出让中位价" in findings_text or "recommended_transfer_price_mid" in labels, "包含推荐出让中位价", "未识别到推荐出让中位价", checks, failures)
        require("建议价格区间" in findings_text, "包含建议价格区间", "未识别到建议价格区间", checks, failures)
        require("tradeability_level" in labels or "可交易性等级" in findings_text, "包含 tradeability", "未识别到 tradeability", checks, failures)
        if isinstance(body.get("id"), int):
            context["agent_run_ids"]["pricing_strategy_agent"] = body["id"]
        return result, body

    def step7(checks: list[str], failures: list[str]) -> tuple[ApiResult, Any]:
        result = client.request("GET", "/api/tasks")
        body = result.body if isinstance(result.body, list) else []
        require(result.status_code == 200, "tasks HTTP 200", f"tasks 状态不是 200：{result.status_code}", checks, failures)
        require(isinstance(result.body, list), "响应为任务数组", "响应不是任务数组", checks, failures)
        require(len(body) >= 6, f"work_orders 至少 6 条：{len(body)}", f"work_orders 少于 6 条：{len(body)}", checks, failures)
        return result, body

    def step8(checks: list[str], failures: list[str]) -> tuple[ApiResult, Any]:
        result = client.request("GET", "/api/asset-package/list/all")
        body = result.body if isinstance(result.body, list) else []
        require(result.status_code == 200, "asset package list HTTP 200", f"状态不是 200：{result.status_code}", checks, failures)
        require(isinstance(result.body, list), "响应为资产包数组", "响应不是资产包数组", checks, failures)
        require(len(body) == 17, f"资产包 17 个", f"资产包数量不是 17：{len(body)}", checks, failures)
        context["packages"] = body
        return result, body

    def step9(checks: list[str], failures: list[str]) -> tuple[ApiResult, Any]:
        result = client.request("GET", "/api/ai-command-center/decision-audit-logs", params={"limit": 100})
        body = result.body if isinstance(result.body, list) else []
        require(result.status_code == 200, "AI decision audit HTTP 200", f"状态不是 200：{result.status_code}", checks, failures)
        require(isinstance(result.body, list), "响应为审计数组", "响应不是审计数组", checks, failures)
        by_run_id = {row.get("agent_run_id"): row for row in body if isinstance(row, dict)}
        for agent_type, run_id in context["agent_run_ids"].items():
            row = by_run_id.get(run_id)
            require(row is not None, f"审计含 {agent_type} run_id={run_id}", f"审计缺少 {agent_type} run_id={run_id}", checks, failures)
            if row is not None:
                require(row.get("decision_type") == agent_type, f"{agent_type} decision_type 正确", f"{agent_type} decision_type 异常：{row.get('decision_type')}", checks, failures)
                require(bool(row.get("action")), f"{agent_type} action 齐全", f"{agent_type} action 缺失", checks, failures)
                require(row.get("tenant_id") is not None, f"{agent_type} tenant_id 齐全", f"{agent_type} tenant_id 缺失", checks, failures)
                require(row.get("requires_human_review") is True, f"{agent_type} requires_human_review=true", f"{agent_type} requires_human_review 异常", checks, failures)
        return result, body

    for number, title, api, fn in [
        (1, "登录", "POST /api/auth/login", step1),
        (2, "当前用户", "GET /api/auth/me", step2),
        (3, "AI 指挥中心总览", "GET /api/ai-command-center/overview", step3),
        (4, "资产包诊断 Agent", "POST /api/ai-command-center/runs", step4),
        (5, "运营计划 Agent", "POST /api/ai-command-center/runs", step5),
        (6, "定价策略 Agent", "POST /api/ai-command-center/runs", step6),
        (7, "任务列表", "GET /api/tasks", step7),
        (8, "资产包列表", "GET /api/asset-package/list/all", step8),
        (9, "AI 决策审计日志", "GET /api/ai-command-center/decision-audit-logs", step9),
    ]:
        step, _extra = run_step(number, title, api, fn)
        steps.append(step)

    report_path = Path(f"/tmp/smoke_report_{datetime.now().strftime('%Y%m%d_%H%M')}.md")
    write_report(steps, client.timings, report_path)
    print(f"报告已生成：{report_path}")
    passed = sum(1 for step in steps if step.passed)
    print(f"总体通过率：{passed}/{len(steps)}")
    return 0 if passed == len(steps) else 1


if __name__ == "__main__":
    raise SystemExit(main())
