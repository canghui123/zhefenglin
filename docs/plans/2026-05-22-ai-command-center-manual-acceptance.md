# AI 指挥中心第一阶段本地手动验收脚本

适用版本：第一阶段 AI 指挥中心 / Agent 化能力。

验收目标：确认 `/ai-command-center`、Agent Orchestrator、审计记录、权限边界、tenant 隔离和人工复核安全边界满足客户演示前要求。

## 1. 验收前准备

### 后端启动

推荐命令：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 start_server.py
```

备选命令：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

预期结果：

- 后端监听 `http://127.0.0.1:8000`
- `GET /api/health` 返回 `status=ok`

### 数据库迁移

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
alembic upgrade head
```

预期结果：

- 迁移执行成功
- 当前 revision 为 head
- 新增 Agent 相关表可查询

### 前端启动

演示前先构建确认：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/frontend
npm run build
```

启动前端：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/frontend
npm run dev
```

预期结果：

- 前端监听 `http://127.0.0.1:3000`
- 页面可正常打开

### 测试账号要求

至少准备四类角色账号：

- `viewer`：只读摘要
- `operator`：可发起基础 Agent
- `manager`：可查看策略和任务草稿，可发起策略/运营类 Agent
- `admin`：可查看成本、审批、审计，可发起成本控制 Agent

至少准备两个租户：

- 租户 A：用于发起 Agent
- 租户 B：用于验证不能读取租户 A 的 Agent run

## 2. 数据库迁移验收

执行：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
alembic upgrade head
```

检查四张表是否存在：

```sql
select tablename
from pg_tables
where schemaname = 'public'
  and tablename in (
    'agent_runs',
    'agent_tasks',
    'agent_recommendations',
    'decision_audit_logs'
  )
order by tablename;
```

预期结果：

- 返回 `agent_runs`
- 返回 `agent_tasks`
- 返回 `agent_recommendations`
- 返回 `decision_audit_logs`

检查必要字段：

```sql
select table_name, column_name, is_nullable
from information_schema.columns
where table_name in (
  'agent_runs',
  'agent_tasks',
  'agent_recommendations',
  'decision_audit_logs'
)
order by table_name, ordinal_position;
```

重点确认：

- `agent_runs.tenant_id` 非空
- `agent_runs.agent_type` 非空
- `agent_runs.input_json` 非空
- `agent_runs.status` 非空
- `agent_runs.requires_human_review` 非空
- `decision_audit_logs.tenant_id` 非空
- `decision_audit_logs.decision_type` 非空
- `decision_audit_logs.action` 非空
- `decision_audit_logs.requires_human_review` 非空

## 3. 页面可访问验收

### viewer

操作路径：

1. 使用 `viewer` 登录
2. 打开 `/ai-command-center`
3. 查看侧边栏是否存在“AI 指挥中心”

预期结果：

- 页面可打开
- 可看到“AI 指挥中心”
- 可看到“AI 今日判断”
- 可看到“Agent 工作台”
- 不能发起 Agent

### operator

操作路径：

1. 使用 `operator` 登录
2. 打开 `/ai-command-center`
3. 查看侧边栏入口和 Agent 工作台

预期结果：

- 页面可打开
- 可以发起 `asset_package_diagnosis_agent`
- 可以发起 `valuation_analysis_agent`
- 可以发起 `buyer_offer_analysis_agent`
- 不能发起 manager/admin 级 Agent

### manager

操作路径：

1. 使用 `manager` 登录
2. 打开 `/ai-command-center`

预期结果：

- 页面可打开
- 可发起 `pricing_strategy_agent`
- 可发起 `operation_planning_agent`
- 可发起 `task_generation_agent`
- 可发起 `report_generation_agent`
- 不能发起 `cost_control_agent`

### admin

操作路径：

1. 使用 `admin` 登录
2. 打开 `/ai-command-center`
3. 发起任意允许的 Agent
4. 调用或打开审计日志能力

预期结果：

- 页面可打开
- 可发起 `cost_control_agent`
- 可查询 AI 指挥中心审计日志

## 4. 权限验收

### viewer 只读摘要

操作路径：

1. 先用 operator 或 manager 发起一次 Agent
2. 退出登录
3. 使用同租户 viewer 登录
4. 打开 `/ai-command-center`

预期结果：

- viewer 可看到摘要
- viewer 不展示敏感 `evidence`
- viewer 不展示 `key_findings`、`recommended_actions` 等策略细节
- viewer 点击“运行 Agent”应被禁用或提示无权限

### operator 基础 Agent

操作路径：

1. operator 登录
2. 选择 `asset_package_diagnosis_agent`
3. 点击“运行 Agent”

预期结果：

- 请求成功
- 返回 `requires_human_review=true`
- 生成 `agent_runs`
- 生成 `agent_recommendations`
- 生成 `decision_audit_logs`

### manager 策略和任务

操作路径：

1. manager 登录
2. 发起 `pricing_strategy_agent`
3. 发起 `task_generation_agent`

预期结果：

- `pricing_strategy_agent` 可运行
- `task_generation_agent` 当前为 mock，但可生成安全草稿
- 如产生任务草稿，`agent_tasks.status=draft`
- 不自动派发任务

### admin 审计

操作路径：

1. admin 登录
2. 调用 `GET /api/ai-command-center/decision-audit-logs`

预期结果：

- 返回当前租户审计日志
- 每条记录包含 `decision_type`
- 每条记录包含 `action`
- 每条记录包含 `requires_human_review`

## 5. tenant_id 隔离验收

操作路径：

1. 租户 A 的 operator 登录
2. 发起一次 `asset_package_diagnosis_agent`
3. 记录返回的 `agent_run.id`
4. 租户 B 的 operator 登录
5. 请求 `GET /api/ai-command-center/runs/{agent_run.id}`

预期结果：

- 租户 A 能查询自己的 run
- 租户 B 查询租户 A 的 run 返回 404 或无权访问
- 租户 B 的列表接口不出现租户 A 的 run
- 管理员也受当前 tenant_id 业务边界限制，除非系统已另行定义超级管理员机制

## 6. 8 个 Agent 发起验收

逐个在 `/ai-command-center` 或 API 中发起：

| Agent | 角色 | 预期状态 |
|---|---|---|
| `asset_package_diagnosis_agent` | operator+ | `rules_based` |
| `valuation_analysis_agent` | operator+ | `rules_based` |
| `pricing_strategy_agent` | manager+ | `rules_based` |
| `buyer_offer_analysis_agent` | operator+ | `rules_based` |
| `operation_planning_agent` | manager+ | `mock` |
| `task_generation_agent` | manager+ | `mock` |
| `report_generation_agent` | manager+ | `mock` |
| `cost_control_agent` | admin | `mock` |

预期结果：

- 已实现 Agent 返回规则化输出
- mock Agent 返回统一 schema 的安全草稿
- 非授权角色返回明确权限错误
- mock Agent 不伪装成 fully implemented

## 7. 输出 schema 验收

每个 Agent 输出必须包含：

- `summary`
- `key_findings`
- `recommended_actions`
- `risk_warnings`
- `confidence_score`
- `evidence`
- `requires_human_review`

验收方式：

1. 发起每个 Agent
2. 查看响应 `output`
3. 逐项确认字段存在

预期结果：

- `confidence_score` 在 `0` 到 `1` 之间
- `evidence` 为数组
- `requires_human_review=true`

## 8. requires_human_review 验收

操作路径：

1. 发起任意 Agent
2. 查看响应体
3. 查询 `agent_runs`
4. 查询 `agent_recommendations`
5. 查询 `decision_audit_logs`

预期结果：

- API 响应 `requires_human_review=true`
- `output.requires_human_review=true`
- `agent_runs.requires_human_review=true`
- `agent_recommendations.requires_human_review=true`
- `decision_audit_logs.requires_human_review=true`

## 9. 安全边界验收

逐项确认：

- Agent 不得自动批准高成本估值
- Agent 不得自动接受买方报价
- Agent 不得自动导出敏感数据
- Agent 不得删除数据
- Agent 不得给出最终法律结论
- Agent 只能生成建议、草稿、任务草稿、风险提示

重点测试：

1. 发起 `buyer_offer_analysis_agent`
2. 输入低于建议价的买方报价
3. 查看风险提示

预期结果：

- 提示买方报价需人工复核
- 提示 Agent 不得自动接受买方报价
- 不出现自动成交、自动审批、自动导出等动作

## 10. 审计日志验收

操作路径：

1. 发起一次 Agent
2. 查询 `agent_runs`
3. 查询 `agent_recommendations`
4. 查询 `decision_audit_logs`
5. 若发起 `task_generation_agent`，查询 `agent_tasks`

预期结果：

- `agent_runs` 有记录
- `agent_recommendations` 有记录
- `decision_audit_logs` 有记录
- `decision_audit_logs.decision_type` 非空
- `decision_audit_logs.action` 非空
- 记录包含 `tenant_id`
- 记录包含 `created_by` 或 `actor_user_id`
- 记录包含 `status`
- `input_json` / `output_json` 可追踪

## 11. 异常场景验收

### 无资产包数据

操作路径：

1. 使用空租户登录
2. 发起 `asset_package_diagnosis_agent`

预期结果：

- 返回空数据安全模式
- 不生成正式处置结论
- `requires_human_review=true`

### 无权限访问

操作路径：

1. operator 发起 `cost_control_agent`

预期结果：

- 返回 403
- 错误提示当前角色无权运行该 Agent

### 不支持的 agent_type

操作路径：

1. POST `/api/ai-command-center/runs`
2. 传入 `agent_type=unknown_agent`

预期结果：

- 返回业务错误
- `error.code=unsupported_agent_type`
- `message=不支持的 Agent 类型`
- 返回 `supported_agent_types`

### LLM 未配置

操作路径：

1. 不配置外部 LLM Key
2. 发起 `valuation_analysis_agent`

预期结果：

- 仍返回 fallback 结构
- `evidence` 中可见 fallback 标记
- 不影响页面渲染

### 后端 API 失败

操作路径：

1. 停止后端
2. 刷新 `/ai-command-center`

预期结果：

- 前端显示错误状态
- 不出现空白页

## 12. 验收结论模板

### 通过

- 数据库迁移通过
- 页面可访问
- 8 个 Agent 均可按权限发起或正确拒绝
- 输出 schema 完整
- `requires_human_review=true`
- tenant 隔离通过
- 审计日志可追踪

### 阻塞

- 迁移失败
- 页面无法打开
- Agent run 无法创建
- tenant 数据串读
- 关键动作绕过人工复核
- 审计日志缺失 `tenant_id`、`decision_type` 或 `created_by/actor_user_id`

### 非阻塞缺陷

- 文案不够清晰
- evidence 展示字段不完整
- mock Agent 输出过于粗略
- 空状态提示可优化

### 后续优化

- 将 `operation_planning_agent` 改为规则化运营计划
- 将 `task_generation_agent` 改为任务草稿生成
- 将 `cost_control_agent` 改为成本预估
- 将 `report_generation_agent` 改为报告草稿生成
- 增强审计日志前端检索和筛选
