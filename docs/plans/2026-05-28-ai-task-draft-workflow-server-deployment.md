# AI 任务草稿确认链路服务器部署留痕

## 部署结论

通过。

## 部署提交和分支

- 远端分支：`codex/asset-pricing-hardening-handoff`
- 部署提交：`1a6aef3 feat: add reviewable AI task draft workflow`

## 服务器路径

- 应用路径：`/opt/app`
- 部署路径：`/opt/app/deploy`

## 备份路径

- 配置备份：`/home/ecs-user/deploy-backup-before-1a6aef3-20260528_095622`
- 数据库备份：`/home/ecs-user/db-backup-before-1a6aef3-20260528_095622.sql.gz`

## 部署方式

本次通过服务器侧 `GitHub fetch` 成功获取远端分支更新，未使用本地 `git bundle` 传输方式。

服务器当前处于 `detached HEAD`，指向部署提交 `1a6aef3`。

## Alembic 版本状态

- 部署前 current：`20260523_0016 (head)`
- 代码 heads：`20260523_0016 (head)`
- 已执行：`alembic upgrade head`
- 部署后 current：`20260523_0016 (head)`
- 结论：数据库 schema 已处于 head，无新增待执行迁移。

## 容器状态

- `af_backend`：Up，healthy
- `af_frontend`：Up，running
- `af_postgres`：Up，healthy
- `af_minio`：Up，healthy
- `af_postgres_backup`：Up，healthy
- `af_nginx`：Up，running

`backend` 和 `frontend` 镜像已基于 `1a6aef3` 重建并重启。

## 健康检查结果

- `https://zhefenglin.com/api/health`：正常
- 返回：`{"status":"ok","service":"汽车金融资产处置经营决策系统"}`

## 页面访问结果

- `https://zhefenglin.com/ai-command-center`：HTTP/2 200
- `https://zhefenglin.com/admin/ai-audit-logs`：HTTP/2 200

## smoke-check.sh 结果

`smoke-check.sh` 通过，覆盖：

- Compose 服务状态检查
- 后端 import 检查
- Alembic current=head 检查
- `/api/health` 健康检查
- 前端首页 HTTP 访问检查

## 本次上线能力摘要

- `task_generation_agent` 从 `mock` 改为 `rules_based`
- AI 建议可生成 `agent_tasks` 任务草稿
- 任务草稿默认 `status=draft`
- 任务草稿进入 AI 指挥中心待确认队列
- `manager` / `admin` 人工确认后创建正式 `work_orders`
- 确认后的 `work_orders` 状态为 `pending`
- `high` 优先级任务需 `admin` 确认
- 任务草稿确认 / 驳回写入 `decision_audit_logs`
- `tenant_id` 隔离、角色权限、viewer 脱敏、人工复核和安全边界保持有效

## 剩余注意点

- `Docker Compose version obsolete` 为 Docker Compose 配置警告，非阻断。
- 服务器当前为 `detached HEAD`，后续部署需明确 `checkout` 目标 commit。
- 本次服务器侧未做线上登录态业务冒烟；本地已完成 35/35 浏览器冒烟。

## 回退建议

如上线后发现阻断问题，建议按以下顺序回退：

1. 使用配置备份恢复部署配置：`/home/ecs-user/deploy-backup-before-1a6aef3-20260528_095622`
2. 必要时使用数据库备份恢复：`/home/ecs-user/db-backup-before-1a6aef3-20260528_095622.sql.gz`
3. 将 `/opt/app` 回退到上一稳定提交，再重建并重启 `backend` / `frontend`
4. 回退后重新执行 `alembic current`、`/api/health`、页面访问和 `smoke-check.sh`

## 下一步建议

- 推进 `operation_planning_agent` 规则化
- 生成本周 / 本月处置作战计划
- 与 `task_generation_agent` 串联形成“作战计划 -> 任务草稿 -> 人工确认”闭环
