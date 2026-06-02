# Agent 评测体系 v1(B2)

## 目的

评测 Rules-Based Agent 的**输出正确性 + 业务边界**:
- M3/M6/M12 分层有没有正确进入 findings / actions / warnings
- requires_human_review 是否永远 true
- 是否出现违禁语句("自动批准" / "自动接受报价" / "最终法律意见" 等)
- 各种边缘 case(空数据 / 未定价 / 高风险 / 健康包)Agent 行为是否合理

## 架构

```
backend/evals/
├── framework.py              # Case / Runner / Report 核心
├── factories.py              # PackageContext / PackageSummary 工厂
├── assertions.py             # 7 种断言原语
├── run.py                    # CLI 入口
├── cases/                    # YAML golden set
│   ├── asset_package_diagnosis/    (4 case)
│   ├── pricing_strategy/           (3 case)
│   └── operation_planning/         (4 case)
└── reports/                  # 输出报告(gitignore)
    ├── baseline_YYYYMMDD_HHMMSS.md
    └── latest.json
```

## 跑法

```bash
cd backend

# 跑全部 case
python3 -m evals.run

# 只跑某个 Agent
python3 -m evals.run --agent asset_package_diagnosis_agent

# 只跑某个 case
python3 -m evals.run --case 02_high_overdue

# 不写报告,只 print(快速本地验证)
python3 -m evals.run --no-save
```

退出码:`0` = 全部通过 / `1` = 至少一个 case 失败。

## Case YAML 格式

```yaml
case_id: <唯一 id,与文件名一致>
description: <人类可读说明>
agent_type: <asset_package_diagnosis_agent | pricing_strategy_agent | operation_planning_agent>

input:
  package:                       # 可选(为 null 时表示无资产包)
    id: 100
    tenant_id: 1
    name: "..."
    total_assets: 30
  result_summary:                # 可选(无 result 时表示已上传未定价)
    total_assets: 30
    overdue_segments_breakdown:
      "M3-": 0
      "M3-M6": 0
      "M6-M12": 0
      "M12+": 19
      "unknown": 11
    m12_plus_count: 19
    missing_vin_count: 3
    # ... 其他 PackageSummary 字段

expectations:
  must:           # 必须通过,否则 case FAIL
    - field_equals:
        path: requires_human_review
        value: true
    - find_text:
        in: key_findings
        substr: "M12+"

  should:         # 不强制,但记录通过率
    - find_text:
        in: recommended_actions
        substr: "债权转让"

  forbidden:      # 违禁语句,出现即 FAIL
    - forbidden_text:
        in: recommended_actions
        substr: "自动出让"
```

## 7 种断言原语

| 名称 | 参数 | 含义 |
|---|---|---|
| `field_equals` | `path`, `value` | 字段精确等于 |
| `field_in_range` | `path`, `min`, `max` | 数值字段在区间 |
| `find_text` | `in`, `substr` | 字符串或 list 含子串 |
| `find_any_text` | `in`, `substrings: [...]` | list 任一子串命中 |
| `list_length_min` | `path`, `count` | 列表长度 >= |
| `list_length_max` | `path`, `count` | 列表长度 <= |
| `forbidden_text` | `in`, `substr` | 字段**不应**含子串 |

字段路径支持点分嵌套:`summary.recommended_transfer_price_mid`。

## 业务边界(永远不应被破坏的断言)

每一个新 case 都应该考虑加入这些 forbidden 断言:

```yaml
forbidden:
  - forbidden_text: { in: recommended_actions, substr: "自动批准" }
  - forbidden_text: { in: recommended_actions, substr: "自动出让" }
  - forbidden_text: { in: recommended_actions, substr: "自动接受报价" }
  - forbidden_text: { in: recommended_actions, substr: "最终法律意见" }
  - forbidden_text: { in: summary, substr: "无需人工" }
```

每一个 case 都应该有:

```yaml
must:
  - field_equals: { path: requires_human_review, value: true }
  - field_equals: { path: agent_status, value: rules_based }
```

## 何时跑

- ✅ **每次改 Agent 规则后**:跑一次确认没破坏现有行为
- ✅ **演示彩排前**:确认 11/11 = 100% 后才彩排
- ✅ **直播前一小时**:最后一道关
- ⏳ **CI(未来)**:每 PR 自动跑,失败阻止 merge

## 怎么加新 case

1. 在 `cases/<agent>/` 下加 YAML 文件
2. 文件名 = `case_id`,加序号便于排序(如 `05_xxx.yaml`)
3. 至少包含 2-3 个 must 断言(其中 `requires_human_review` 和 `agent_status` 必加)
4. 加 forbidden 断言保护业务边界
5. 跑 `python3 -m evals.run --case <case_id>` 验证

## 当前基线

`reports/latest.json` 是最近一次跑的机器可读结果。基线版本:

- 总 case 数:**11**
- 通过率:**100.0%**
- Agent 平均响应:< 1 ms(纯函数式,无 DB,无 LLM)
- 覆盖 3 个 Agent:asset_package_diagnosis / pricing_strategy / operation_planning

## 后续路线

- **本周(6/8 前)**:再加 5-7 个 case,把覆盖拉到 16-18(每个 Agent 5-6 个 case)
- **直播后**:接入 CI(stage 环境,不直跑生产)
- **下一阶段**:覆盖 buyer_offer_analysis_agent / task_generation_agent / valuation_analysis_agent
- **B2 终局**:Golden Set 30+,每次 Agent 改动跑回归对比基线
