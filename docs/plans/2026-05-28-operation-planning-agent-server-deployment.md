# operation_planning_agent 规则化服务器部署留痕

## 1. 部署结论

通过。

## 2. 部署提交和分支

- 远端分支：`codex/asset-pricing-hardening-handoff`
- 部署提交：`eed6533 feat: add rule-based operation planning agent`

## 3. 服务器路径

- 服务器代码路径：`/opt/app`
- 部署目录：`/opt/app/deploy`

## 4. 配置备份和数据库备份路径

- 配置备份：`/home/ecs-user/deploy-backup-before-eed6533-20260528_104241`
- 数据库备份：`/home/ecs-user/db-backup-before-eed6533-20260528_104241.sql.gz`

## 5. 部署方式

GitHub fetch 成功，本次未使用 git bundle 方式。

## 6. Alembic 状态

- Alembic current/head：`20260523_0016 (head)`
- `alembic upgrade head`：执行成功，无新增待迁移版本。

## 7. 容器状态

- `af_backend`：Up healthy
- `af_frontend`：Up running
- `af_postgres`：healthy
- `af_minio`：healthy
- `af_postgres_backup`：healthy
- `af_nginx`：running

## 8. 健康检查结果

- `https://zhefenglin.com/api/health`：正常，返回 `status ok`

## 9. 页面访问结果

- `https://zhefenglin.com/ai-command-center`：HTTP/2 200
- `https://zhefenglin.com/admin/ai-audit-logs`：HTTP/2 200

## 10. smoke-check.sh 结果

`smoke-check.sh` 通过，显示 `smoke check ok: https://zhefenglin.com`。

## 11. 本次上线能力摘要

- `operation_planning_agent` 从 mock 改为 `rules_based`
- 输出本周作战重点
- 输出高优先级资产池
- 输出快速竞拍池
- 输出法务推进池
- 输出补资料/估值复核池
- 输出债权转让池
- 输出暂缓观察池
- 输出报价复核池
- 输出产能/预算约束
- 输出 `missing_data`、`data_quality_notes`、`limited_data_reason`
- 保持 `requires_human_review=true`
- 不自动派发任务、不审批、不导出、不接受报价
- 如需落地，只引导 `task_generation_agent` 生成 `draft` 任务草稿

## 12. 剩余注意点

- Docker Compose `version is obsolete` 为警告，非阻断。
- 服务器当前为 detached HEAD，后续部署需明确 checkout 目标 commit。
- 本次未做线上登录态业务冒烟，建议后续用 manager/admin 登录验证一次“生成本周作战计划”。

## 13. 回退建议

- 使用配置备份恢复部署配置。
- 使用数据库备份恢复上线前数据。
- 回退到上一提交：`1a6aef3 feat: add reviewable AI task draft workflow`。

## 14. 下一步建议

- 做一次线上 manager/admin 登录态业务冒烟。
- 推进 `report_generation_agent` 草稿化。
- 推进 `cost_control_agent` 规则化。
- 后续再做 Tool Registry 和 AgentContextBuilder。
