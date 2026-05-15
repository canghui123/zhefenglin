# P0 发布就绪与剩余动作清单

日期：2026-05-13
分支：`codex/asset-pricing-hardening-handoff`

## 当前状态

本地验收和完整验证已完成：

- 后端测试：`164 passed`
- 后端编译：通过
- 前端 lint：通过
- 前端 build：通过
- 前端 dev 服务已恢复运行在 `http://localhost:3000`

验收记录见：

- `/Users/canghui/Desktop/汽车金融ai平台/docs/acceptance/2026-05-13-p0-e2e-acceptance.md`
- `/Users/canghui/Desktop/汽车金融ai平台/data/acceptance-artifacts/p0-e2e-api-summary.json`

## 部署静态预检

已完成：

- `bash -n deploy/setup.sh`：通过
- `deploy/README.md` 已包含生产部署、更新、备份、SSL 和日常运维说明
- `deploy/setup.sh` 会检查关键生产变量占位符、密钥长度和 JWT 双密钥不同值

未完成：

- 本机未安装或不可访问 `docker` 命令，`docker compose config` 无法在本机完成。
- `deploy/.env.production` 仍包含模板占位符，正式部署前必须复制为服务器 `deploy/.env` 并替换真实值。

仍需替换的生产变量：

- `DOMAIN`
- `DB_PASSWORD`
- `JWT_SECRET`
- `JWT_REFRESH_SECRET`
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- 如启用真实估值：`CHE300_ACCESS_KEY`、`CHE300_ACCESS_SECRET`
- 如启用 AI 深度分析：`DEEPSEEK_API_KEY`

## 不建议直接执行的动作

不要直接执行：

```bash
git add .
```

原因：

- 当前工作区包含大量既有未提交改动，既有 P0 功能，也有商业化中台、部署脚本、测试、文档和本地验收产物。
- `data/acceptance-artifacts/` 包含 PDF/HTML/JSON 验收产物，适合交付归档，但未必适合进入业务代码提交。
- `.playwright-cli/` 是本地工具缓存，通常不应提交。

## 建议提交分组

建议至少拆成以下提交，避免一个巨大提交难以 review：

- P0 资产包增强：资产模型、估值可信度、交易适配度、买方报价分析、PDF、资产定价前端与测试。
- P0 库存沙盘增强：法律材料模型、法律路径评分、综合推荐评分、沙盘报告、沙盘前端与测试。
- 商业化/安全/部署配套：认证、访问申请、限流、运行时安全、部署脚本、Nginx、Docker、环境变量文档。
- 验收与交付资料：`docs/acceptance/` 和必要的验收摘要；二进制 PDF/HTML 是否提交需单独决定。

## 服务器部署前检查

在 ECS 或目标服务器执行前，先确认：

- 已完成域名 ICP 备案并解析到目标服务器公网 IP。
- 服务器已安装 Docker 和 Docker Compose V2。
- `deploy/.env` 已替换所有占位符，且密钥不复用、不短于脚本要求。
- 已备份现有生产数据库和上传/报告对象存储。
- 如已有线上服务，确认维护窗口和回滚路径。

## 推荐部署命令

首次部署：

```bash
cd /opt/auto-finance/deploy
bash setup.sh
```

已有部署更新：

```bash
cd /opt/auto-finance
git pull

cd deploy
docker compose build backend frontend
docker compose run --rm backend alembic upgrade head
docker compose up -d
docker compose ps
```

## 上线后冒烟验证

上线后至少验证：

- `GET /api/health` 返回健康状态。
- 管理员登录成功，前端不会跳回登录页。
- 资产包 Excel 上传成功，计算任务成功完成。
- 买方报价分析可写回，PDF 下载返回 `application/pdf`。
- 库存沙盘模拟成功，B/D 法律评分和材料缺口可见。
- 沙盘报告生成和下载成功。
- `docker compose logs --tail=100 backend` 无启动错误或迁移错误。

## 需要用户确认的动作

以下动作会影响远端或版本历史，需要确认后再执行：

- 登录 ECS Workbench 并操作服务器。
- 修改服务器 `deploy/.env` 的生产密钥和域名。
- 执行远端部署或重启线上服务。
- stage/commit 当前大批量改动。
- push 分支或创建 PR。
