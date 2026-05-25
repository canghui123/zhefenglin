# AI 指挥中心治理风险收口记录

日期：2026-05-24

## 收口结论

第一阶段验收后的三项剩余风险已转为可执行、可验证的治理闭环：

1. 生产部署迁移风险：部署 smoke check 增加 Alembic current/head 对比，迁移未到 head 时直接失败。
2. 阈值治理风险：Agent 阈值从单一租户配置升级为按 `agent_type + scenario + version` 管理的规则 profile。
3. 复盘闭环风险：人工复盘不自动反哺模型，但会生成复盘洞察，供管理员调整阈值和排查 evidence。

## 部署迁移门禁

部署更新后必须执行：

```bash
cd /opt/auto-finance/deploy
docker compose run --rm backend alembic upgrade head
docker compose up -d
bash smoke-check.sh
```

`smoke-check.sh` 已检查：

- Docker Compose 服务状态
- 后端 import
- `alembic current` 是否等于 `alembic heads`
- `/api/health`
- 前端页面响应

如果迁移未到 head，脚本会输出当前 revision、head revision 和修复命令，并退出失败。

## 规则 Profile

`agent_rule_settings` 当前支持：

- `agent_type`：`global` 或具体 Agent
- `scenario`：例如 `default`、`stress_week`
- `version`：同一 Agent/场景每次保存生成新版本
- `is_active`：仅启用版本参与 Agent run

解析优先级：

1. 指定 Agent + 指定场景
2. 指定 Agent + default
3. global + 指定场景
4. global + default
5. 系统默认阈值

Agent 输出 evidence 会带出命中的 profile、版本号和阈值快照。阈值只影响草稿数量、预警强度和报告章节等半自动输出，不会自动派发任务、批准成本、接受报价或外发报告。

## 复盘闭环

`agent_run_reviews` 记录人工复核结果：

- 复盘结论
- 有用性评分
- 准确性评分
- 采纳/驳回动作数
- 是否需后续跟进
- 复盘备注

`/api/ai-command-center/run-reviews/insights` 输出：

- 样本数
- 平均有用性
- 平均准确性
- 采纳率
- 后续跟进数量
- 规则调整建议

该闭环坚持 human-in-the-loop：复盘洞察只作为阈值调整建议，不自动修改规则、不训练模型、不改变任务派发逻辑。

## 验收重点

- 管理员可在 `/admin/ai-audit-logs` 查看审计日志、规则 profile、历史版本和复盘洞察。
- 管理员保存阈值会创建新版本并写入 `decision_audit_logs`。
- Manager 可查看 profile 和复盘记录，但不能保存阈值。
- Agent run 可通过 `rule_scenario` 使用指定场景阈值。
- Viewer 仍不能查看敏感 evidence。

## 安全边界

- 所有规则、复盘和审计数据必须带 `tenant_id`。
- 所有高影响输出仍必须 `requires_human_review=true`。
- Agent 不得自动接受买方报价、批准资产出让、批准高成本估值、导出敏感数据、删除数据或给出最终法律结论。
