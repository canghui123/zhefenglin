# AI 指挥中心客户视图服务器部署验证记录

## 部署结论

通过。

AI 指挥中心客户视图已完成线上部署验证，后端健康检查、前端页面访问、AI 审计日志页面访问和 `smoke-check.sh` 均通过。

## 部署提交和分支

- 分支：`codex/asset-pricing-hardening-handoff`
- 提交：`d095b87 feat: polish AI command center customer view`

## 服务器路径

- 应用路径：`/opt/app`
- 部署路径：`/opt/app/deploy`

## 配置备份路径

- 配置备份：`/home/ecs-user/deploy-backup-before-d095b87-20260527_105502`

## 部署方式

本次服务器侧 GitHub fetch 当时失败，因此采用本地 git bundle 传输方式完成部署：

1. 本地生成包含目标提交的 git bundle。
2. 通过 SSH/SCP 上传到服务器。
3. 服务器从 bundle fetch 对应分支引用。
4. 服务器 `/opt/app` checkout 到 `d095b87`。
5. 重建并重启前端容器。

## Alembic Head

- 当前 Alembic 版本：`20260523_0016`
- 状态：`head`

## 后端容器状态

- 容器：`af_backend`
- 镜像：`deploy-backend`
- 状态：`Up`
- 健康状态：`healthy`

## 前端容器状态

- 容器：`af_frontend`
- 镜像：`deploy-frontend`
- 状态：`Up`
- 本次已完成前端镜像重建并重启。

## 健康检查结果

- 地址：`https://zhefenglin.com/api/health`
- 结果：正常
- 返回：`{"status":"ok","service":"汽车金融资产处置经营决策系统"}`

## AI 指挥中心访问结果

- 地址：`https://zhefenglin.com/ai-command-center`
- 结果：`HTTP/2 200`
- 结论：AI 指挥中心客户视图页面可访问。

## AI 审计日志访问结果

- 地址：`https://zhefenglin.com/admin/ai-audit-logs`
- 结果：`HTTP/2 200`
- 结论：admin-only AI 审计日志页面路由可访问。

## smoke-check.sh 结果

- 命令：`sudo bash smoke-check.sh`
- 结果：通过
- 覆盖：
  - Docker Compose 服务状态
  - 后端 import 检查
  - Alembic 当前版本检查
  - API 健康检查
  - 前端首页访问检查

## 剩余注意点

- 服务器当前处于 detached HEAD 状态，当前提交为 `d095b87`。
- GitHub fetch 当时失败，本次采用 git bundle 传输完成部署。
- 部署前服务器脏工作区已 stash，可作为回退和排查参考。
- Docker Compose 输出 `version is obsolete` 为警告，不影响本次部署验证。

## 回退建议

如需回退，建议按以下顺序处理：

1. 使用配置备份路径 `/home/ecs-user/deploy-backup-before-d095b87-20260527_105502` 恢复 `.env` 和 nginx 配置。
2. 使用上一提交或部署前 stash 作为代码回退参考。
3. 回退后重新执行容器构建、启动和 `smoke-check.sh`。
4. 确认 `/api/health`、核心页面和后台容器状态恢复正常。

## 下一步建议

- 准备脱敏演示数据。
- 准备 3-5 分钟客户演示脚本。
- 推进 `operation_planning_agent` 规则化。
- 推进 `task_generation_agent` 草稿化。
- 推进 `cost_control_agent` 规则化。
- 推进 `report_generation_agent` 草稿化。
