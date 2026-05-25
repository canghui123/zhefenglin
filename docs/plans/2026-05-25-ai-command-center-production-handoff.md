# AI 指挥中心生产上线交付记录

日期：2026-05-25

## 1. 上线记录

- 生产域名：`https://zhefenglin.com`
- 上线提交：`1083d0c feat: add AI command center governance loop`
- 远端分支：`codex/asset-pricing-hardening-handoff`
- 生产目录：`/opt/app`
- 部署方式：`docker compose build backend frontend` 后滚动重启 `backend`、`frontend`
- 数据库迁移：生产已执行 `alembic upgrade head`
- 服务健康：`/api/health` 返回 `ok`
- 页面路由：`/ai-command-center`、`/admin/ai-audit-logs` 均返回 `HTTP 200`

## 2. 客户演示前走查路径

1. 使用 `admin` 账号登录生产环境。
2. 打开 `/ai-command-center`。
3. 查看今日总览：资产包、待处理任务、待审批事项、今日 Agent 执行。
4. 查看 AI 今日判断：确认有 `rules_based`、置信度、`需人工复核` 和 Evidence。
5. 查看 Agent 工作台：确认 8 个 Agent 均可见，前 4 个为基础规则输出，后 4 个为半自动运营闭环能力。
6. 查看对话式指挥入口：可展示自然语言问题入口；客户演示时优先展示现有输出，避免无准备地新增生产数据。
7. 查看最近 10 次 Agent run：确认运行记录可追踪。
8. 打开 `/admin/ai-audit-logs`。
9. 查看规则阈值配置：确认阈值按 profile、场景、版本展示。
10. 查看复盘闭环：确认人工复盘表单和复盘洞察区域可见。
11. 查看 AI 决策审计日志：确认包含时间、决策类型、动作、Run、人工复核、结果摘要。

## 3. 演示口径

- 本系统不是普通聊天机器人，而是面向不良资产处置的 AI 指挥中心。
- Agent 输出只用于分析、建议、任务草稿、报告草稿、成本预警和审计复盘。
- Agent 不会自动批准资产出让、接受买方报价、批准高成本估值、删除数据、导出敏感数据或替代法律结论。
- 所有高影响动作均保留 `requires_human_review=true`，正式动作必须由人确认。
- 关键数值来自规则、公式和服务层计算，LLM 只负责解释、总结和草稿表达。
- 所有 Agent run、审计日志、阈值调整和复盘记录都带租户边界和审计留痕。

## 4. 生产备份记录

- 本轮交付前已验证过数据库备份与恢复链路。
- 本轮演示前补充备份：已执行 `sudo docker compose exec postgres-backup /backup.sh`。
- 备份结果：命令输出 `SQL backup created successfully`。
- 备份文件：`/backups/daily/auto_finance-20260525.sql.gz`，约 `337K`。
- 最新备份指针：`/backups/daily/auto_finance-latest.sql.gz` 指向 `auto_finance-20260525.sql.gz`。
- 生产冒烟截图：`/tmp/ai-command-center-production-handoff.png`。

## 5. 下一阶段建议

1. 增强 `/admin/ai-audit-logs` 的筛选、分页和明细查看。
2. 将 4 个规则化 Agent 的阈值从租户级配置推进到按 Agent、按场景、按版本治理。
3. 将复盘数据用于生成规则优化建议，但继续保持人工确认边界。
4. 补充客户演示数据集，避免在生产环境临时新增不可控 Agent run。
