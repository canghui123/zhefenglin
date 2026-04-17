# 汽车金融 AI 平台

面向汽车金融不良资产场景的 AI 辅助平台，当前仓库采用模块化单体架构：

- 后端：FastAPI + SQLAlchemy + Alembic
- 前端：Next.js 16 + React 19
- 基础设施：PostgreSQL、对象存储抽象、本地 Docker 部署脚本

当前代码已经具备本地开发、基础认证、多租户数据隔离、资产包上传解析、定价计算、库存沙盘、组合分析等能力，并且已经补上了基础测试与 CI 验证链路。

运行时数据库策略已经收口为 PostgreSQL-only：应用通过 `DATABASE_URL` 连接数据库，schema 统一由 Alembic 管理。
## 仓库结构

```text
backend/           FastAPI 后端、数据库模型、业务服务、pytest
frontend/          Next.js 前端
deploy/            服务器部署脚本与 docker compose
infra/             本地基础设施说明（PostgreSQL / MinIO）
docs/              架构、运维、安全、交接与计划文档
```

## 本地启动

### 1. 准备环境变量

后端从仓库根目录 `.env` 读取配置，前端从 `frontend/.env` 和 `frontend/.env.local` 读取配置。

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

如需后端完整功能，优先使用 PostgreSQL：

```bash
cd infra/postgres
docker compose up -d
```

然后执行数据库迁移：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
alembic upgrade head
```

说明：

- 应用运行时不再支持 SQLite 本地模式
- `backend/data/npl.db` 只是历史遗留文件，不能代表当前可运行 schema
### 2. 启动后端

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 -m pip install -r requirements.txt -r requirements-dev.txt
python3 start_server.py
```

后端默认地址：`http://127.0.0.1:8000`

### 3. 启动前端

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/frontend
npm install
npm run dev
```

前端默认地址：`http://127.0.0.1:3000`

## 常用验证命令

后端：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 -m pytest -q
python3 -m compileall .
```

前端：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/frontend
npm run lint
npm run build
```

说明：
- 后端运行时只支持 PostgreSQL；不要再把 `DATABASE_PATH` 当作本地启动入口

- 请优先使用 `python3 -m pytest -q`，不要假设系统里有可直接执行的 `pytest`
- Next.js 前端不会读取仓库根目录 `.env`，前端变量请放在 `frontend/.env` 或 `frontend/.env.local`

## 关键文档

- 交接说明：[docs/HANDOFF.md](/Users/canghui/Desktop/汽车金融ai平台/docs/HANDOFF.md)
- 代理协作约束：[AGENTS.md](/Users/canghui/Desktop/汽车金融ai平台/AGENTS.md)
- 环境变量矩阵：[docs/ops/env-matrix.md](/Users/canghui/Desktop/汽车金融ai平台/docs/ops/env-matrix.md)
- 商用化实施计划：[docs/plans/2026-04-03-commercial-readiness.md](/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-03-commercial-readiness.md)
- 部署指南：[deploy/README.md](/Users/canghui/Desktop/汽车金融ai平台/deploy/README.md)

## 推荐接手顺序

如果是新的开发者或新的 Codex 会话，建议按下面顺序进入：

1. 先读 [README.md](/Users/canghui/Desktop/汽车金融ai平台/README.md)
2. 再读 [AGENTS.md](/Users/canghui/Desktop/汽车金融ai平台/AGENTS.md)
3. 然后读 [docs/HANDOFF.md](/Users/canghui/Desktop/汽车金融ai平台/docs/HANDOFF.md)
4. 最后跑一遍后端和前端验证命令，建立当前基线
