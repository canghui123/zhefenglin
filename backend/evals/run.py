"""B2 — Eval CLI entry point。

跑法:
    cd backend
    python3 -m evals.run                                    # 跑全部 case
    python3 -m evals.run --agent asset_package_diagnosis_agent
    python3 -m evals.run --case 03_high_overdue_package

输出:
    backend/evals/reports/baseline_YYYYMMDD_HHMMSS.md
    backend/evals/reports/latest.json
退出码:
    0 = 全部 must/forbidden 断言通过
    1 = 至少一个 case 失败(must 失败 / forbidden 命中 / 异常)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from evals.framework import (
    AGENT_RUNNERS,
    load_cases,
    render_markdown_report,
    run_case,
    save_reports,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent eval runner")
    parser.add_argument("--agent", help="只跑某个 agent_type 的 case", default=None)
    parser.add_argument("--case", help="只跑某个 case_id(支持子串匹配)", default=None)
    parser.add_argument("--no-save", action="store_true", help="不写报告到磁盘,只 print")
    args = parser.parse_args()

    evals_dir = Path(__file__).parent
    cases_dir = evals_dir / "cases"
    if not cases_dir.exists():
        print(f"❌ cases 目录不存在: {cases_dir}", file=sys.stderr)
        return 2

    cases = load_cases(cases_dir)
    if not cases:
        print(f"⚠️  cases 目录为空: {cases_dir}", file=sys.stderr)
        return 0

    # 过滤
    if args.agent:
        cases = [c for c in cases if c.get("agent_type") == args.agent]
    if args.case:
        cases = [c for c in cases if args.case in c.get("case_id", "")]

    if not cases:
        print(f"⚠️  过滤后没有 case 可跑", file=sys.stderr)
        return 0

    print(f"=== 开始跑 {len(cases)} 个 case ===")
    print()

    results = []
    for case in cases:
        result = run_case(case)
        results.append(result)
        status = "✅" if result.passed else "❌"
        must_p = sum(1 for r in result.must_results if r.passed)
        must_t = len(result.must_results)
        forbidden_hit = sum(1 for r in result.forbidden_results if not r.passed)
        suffix = f"must {must_p}/{must_t}"
        if forbidden_hit:
            suffix += f" · forbidden 违禁命中 {forbidden_hit}"
        print(f"  {status} {result.case_id:<45} ({result.agent_type[:30]:<30}) {suffix} · {result.elapsed_ms:.1f}ms")

    print()
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    pass_rate = (passed / total * 100) if total else 0
    print(f"=== 汇总:{passed}/{total} 通过 ({pass_rate:.1f}%) ===")

    if not args.no_save:
        md_path, json_path = save_reports(results, evals_dir)
        print(f"\n报告:{md_path}")
        print(f"JSON:{json_path}")

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
