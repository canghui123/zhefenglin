# Commercial Readiness Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将当前汽车金融 AI 平台从可演示 MVP 升级为可部署、可审计、可扩展、可长期维护的商用版本。

**Architecture:** 保持“模块化单体”架构，不拆微服务。后端继续使用 FastAPI，前端继续使用 Next.js，但新增统一的数据访问层、认证与权限层、租户隔离层、对象存储层、后台任务层和可观测性基础设施。所有改造按“先基础设施、再横切能力、后业务收口”的顺序推进，避免返工。

**Tech Stack:** FastAPI, Next.js 16, React 19, PostgreSQL, SQLAlchemy + Alembic, Redis + arq, S3/OSS compatible object storage, pytest, GitHub Actions, structlog, Prometheus.

---

## Assumptions

- 本轮不拆微服务，不引入复杂工作流引擎。
- 默认认证方案使用邮箱/用户名 + 密码登录，后端签发 JWT，前端通过 HttpOnly Cookie 携带会话。
- 默认角色先定义为 `admin`、`manager`、`operator`、`viewer` 四档，后续再细化。
- 默认租户模型为“组织/客户 = tenant”，所有业务数据最终都要带 `tenant_id`。
- 本地开发对象存储使用 MinIO，生产环境兼容 S3/OSS。
- 本地开发任务队列使用 Redis，异步执行优先覆盖“资产包计算”和“报告生成”两条长流程。
- 当前 `backend/database.py` 的 SQLite 逻辑视为过渡层，最终要迁移到 PostgreSQL。

## Non-Goals

- 不在这一轮引入微服务、Kubernetes、Service Mesh。
- 不在这一轮做复杂 BI 平台重构。
- 不在这一轮重写前端视觉层；前端只做登录、权限、任务状态和错误体验补强。

## Preflight Prerequisite

- 在进入 Task 1 之前，先完成一轮 Session 0 / Preflight。
- Preflight 目标不是改业务代码，而是确认：
  - 根目录仓库边界和嵌套 git 仓库处理方式
  - Task 3 所需 PostgreSQL 本地运行路径
  - Task 8 所需 Redis 本地运行路径
- 推荐先执行：
  - [2026-04-03-session-0-preflight-claude-brief.md](/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-03-session-0-preflight-claude-brief.md)

## Delivery Order

1. 打基础：测试、CI、架构决策、环境变量矩阵。
2. 换地基：PostgreSQL、迁移体系、仓储层。
3. 加横切能力：认证、RBAC、租户隔离、审计日志。
4. 补生产基础设施：对象存储、异步任务、第三方调用韧性、监控告警。
5. 统一交付标准：错误码、OpenAPI、运行手册、备份与数据治理。

## Milestone Exit Criteria

- M1: 任意 PR 都会自动跑后端测试、前端 lint/build、依赖与 secret 扫描。
- M2: 业务数据跑在 PostgreSQL，Alembic 可重复迁移，SQLite 不再作为生产存储。
- M3: 所有核心 API 都需要认证，且跨租户访问被自动拒绝。
- M4: 上传文件与报告不再依赖本地磁盘；耗时流程可异步执行并查询状态。
- M5: 有统一错误码、结构化日志、指标暴露、备份恢复手册、数据留存策略。

### Task 1: 建立测试与 CI 基线

**Files:**
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/api/test_health.py`
- Create: `backend/tests/api/test_asset_package_smoke.py`
- Create: `backend/requirements-dev.txt`
- Create: `.github/workflows/ci.yml`
- Modify: `backend/requirements.txt`
- Modify: `frontend/package.json`
- Modify: `frontend/README.md`
- Test: `backend/tests/api/test_health.py`

**Step 1: 写第一个失败的后端 smoke test**

```python
from fastapi.testclient import TestClient
from main import app

def test_health_returns_ok():
    client = TestClient(app)
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
```

**Step 2: 运行测试确认当前没有测试基线**

Run: `cd backend && pytest tests/api/test_health.py -q`
Expected: FAIL，原因通常是 `pytest` 未安装或测试目录尚不存在。

**Step 3: 补测试依赖和 fixtures**

```txt
# backend/requirements-dev.txt
pytest==8.3.5
pytest-asyncio==0.25.3
pytest-cov==6.0.0
```

```python
# backend/tests/conftest.py
import os
import tempfile
import pytest

@pytest.fixture(autouse=True)
def isolated_backend_env(monkeypatch):
    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setenv("DATABASE_PATH", os.path.join(tmp, "test.db"))
        monkeypatch.setenv("UPLOAD_DIR", os.path.join(tmp, "uploads"))
        yield
```

**Step 4: 建立 CI 工作流**

CI 至少执行以下命令：

```yaml
- run: cd backend && python3 -m pip install -r requirements.txt -r requirements-dev.txt
- run: cd backend && pytest -q
- run: cd backend && python3 -m compileall .
- run: cd frontend && npm ci
- run: cd frontend && npm run lint
- run: cd frontend && npm run build
```

**Step 5: 本地跑基线验证**

Run: `cd backend && pytest -q`
Expected: PASS

Run: `cd backend && python3 -m compileall .`
Expected: PASS

Run: `cd frontend && npm run lint && npm run build`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/tests backend/requirements-dev.txt backend/requirements.txt frontend/package.json frontend/README.md .github/workflows/ci.yml
git commit -m "chore: add test and ci baseline"
```

### Task 2: 固化商用目标架构与环境契约

**Files:**
- Create: `docs/adr/ADR-001-commercial-modular-monolith.md`
- Create: `docs/ops/env-matrix.md`
- Create: `.env.example`
- Create: `backend/.env.example`
- Create: `frontend/.env.example`
- Modify: `backend/config.py`
- Modify: `frontend/README.md`
- Test: `backend/tests/api/test_health.py`

**Step 1: 写环境矩阵文档**

必须列出以下变量及默认值来源：

- `DATABASE_URL`
- `REDIS_URL`
- `JWT_SECRET`
- `JWT_REFRESH_SECRET`
- `CORS_ORIGINS`
- `NEXT_PUBLIC_API_BASE`
- `STORAGE_BACKEND`
- `S3_ENDPOINT`
- `S3_BUCKET`
- `CHE300_*`
- `DEEPSEEK_*`

**Step 2: 统一后端配置入口**

在 `backend/config.py` 中把单机路径配置提升为商用配置结构，例如：

```python
class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://app:app@localhost:5432/auto_finance"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str
    jwt_refresh_secret: str
    storage_backend: str = "local"
    s3_endpoint: str = ""
    s3_bucket: str = ""
```

**Step 3: 给前后端都补 `.env.example`**

要求：

- 根目录 `.env.example` 只放共享示例说明，不让任何运行时直接依赖它。
- `backend/.env.example` 放后端示例变量。
- `frontend/.env.example` 放前端示例变量。

**Step 4: 写 ADR**

ADR 必须明确：

- 为什么继续采用模块化单体
- 为什么选择 PostgreSQL 而不是继续 SQLite
- 为什么用对象存储替代本地磁盘
- 为什么用 Redis 异步任务而不是同步长请求

**Step 5: 验证**

Run: `cd backend && pytest tests/api/test_health.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add docs/adr docs/ops .env.example backend/.env.example frontend/.env.example backend/config.py frontend/README.md
git commit -m "docs: define commercial architecture and env contract"
```

### Task 3: 引入 PostgreSQL、SQLAlchemy 和 Alembic

**Files:**
- Create: `backend/db/base.py`
- Create: `backend/db/session.py`
- Create: `backend/db/models/__init__.py`
- Create: `backend/db/models/asset_package.py`
- Create: `backend/db/models/valuation.py`
- Create: `backend/db/models/sandbox.py`
- Create: `backend/db/models/portfolio.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/script.py.mako`
- Create: `backend/alembic/versions/20260403_0001_initial_schema.py`
- Create: `infra/postgres/docker-compose.yml`
- Modify: `backend/requirements.txt`
- Modify: `backend/main.py`
- Modify: `backend/database.py`
- Test: `backend/tests/db/test_alembic_upgrade.py`

**Step 1: 写第一个失败的数据库迁移测试**

```python
def test_alembic_can_upgrade_to_head():
    # arrange test DATABASE_URL
    # run alembic upgrade head
    # assert required tables exist
    ...
```

**Step 2: 运行测试确认当前没有迁移体系**

Run: `cd backend && pytest tests/db/test_alembic_upgrade.py -q`
Expected: FAIL，原因通常是 `alembic`、`sqlalchemy`、`psycopg` 还未接入。

**Step 3: 加依赖**

在 `backend/requirements.txt` 增加：

```txt
sqlalchemy==2.0.38
alembic==1.14.1
psycopg[binary]==3.2.4
```

**Step 4: 建立新的 DB 访问层**

要求：

- `backend/db/base.py` 放 Declarative Base。
- `backend/db/session.py` 提供 engine、sessionmaker、`get_db_session()`。
- `backend/database.py` 暂时保留，但只做兼容层或迁移提示，不再继续扩展 sqlite schema。

**Step 5: 用 Alembic 创建当前业务表的首个正式迁移**

至少覆盖以下现有域表：

- `asset_packages`
- `assets`
- `valuation_cache`
- `sandbox_results`
- `portfolio_snapshots`
- `asset_segments`
- `segment_metrics`
- `strategy_runs`
- `cashflow_buckets`
- `management_goals`
- `recommended_actions`

**Step 6: 补本地 PostgreSQL 启动文件**

`infra/postgres/docker-compose.yml` 至少提供：

- PostgreSQL 服务
- 持久化 volume
- 健康检查

**Step 7: 跑迁移验证**

Run: `cd backend && alembic upgrade head`
Expected: PASS

Run: `cd backend && pytest tests/db/test_alembic_upgrade.py -q`
Expected: PASS

**Step 8: Commit**

```bash
git add backend/db backend/alembic.ini backend/alembic infra/postgres backend/requirements.txt backend/main.py backend/database.py backend/tests/db
git commit -m "feat: add postgres migration foundation"
```

### Task 4: 把现有业务读写切到仓储层

**Files:**
- Create: `backend/repositories/asset_package_repo.py`
- Create: `backend/repositories/valuation_repo.py`
- Create: `backend/repositories/sandbox_repo.py`
- Create: `backend/repositories/portfolio_repo.py`
- Modify: `backend/api/asset_package.py`
- Modify: `backend/api/car_valuation.py`
- Modify: `backend/api/inventory_sandbox.py`
- Modify: `backend/api/portfolio.py`
- Modify: `backend/services/che300_client.py`
- Test: `backend/tests/api/test_asset_package_repository_path.py`
- Test: `backend/tests/api/test_sandbox_repository_path.py`

**Step 1: 先为一个业务路径写失败测试**

先选 `asset_package upload -> calculate -> get` 这条路径：

```python
def test_asset_package_round_trip_uses_repository_layer(client, sample_excel):
    upload = client.post("/api/asset-package/upload", files={"file": sample_excel})
    package_id = upload.json()["package_id"]
    result = client.get(f"/api/asset-package/{package_id}")
    assert result.status_code == 200
```

**Step 2: 抽出仓储接口**

每个 repo 至少提供：

- `create_*`
- `get_*_by_id`
- `list_*`
- `update_*`
- `save_result_*`

**Step 3: API 层不再直接写 SQL**

要求：

- `backend/api/*.py` 不再直接调用 `sqlite3`。
- 所有数据库访问都通过 repo + SQLAlchemy session 完成。

**Step 4: 逐条跑核心路径**

Run: `cd backend && pytest tests/api/test_asset_package_repository_path.py -q`
Expected: PASS

Run: `cd backend && pytest tests/api/test_sandbox_repository_path.py -q`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/repositories backend/api backend/services/che300_client.py backend/tests/api
git commit -m "refactor: move core business flows to repositories"
```

### Task 5: 增加认证、会话和 RBAC

**Files:**
- Create: `backend/db/models/user.py`
- Create: `backend/db/models/role.py`
- Create: `backend/db/models/user_session.py`
- Create: `backend/services/password_service.py`
- Create: `backend/services/jwt_service.py`
- Create: `backend/services/auth_service.py`
- Create: `backend/dependencies/auth.py`
- Create: `backend/api/auth.py`
- Create: `backend/scripts/create_admin.py`
- Create: `docs/security/rbac-matrix.md`
- Modify: `backend/main.py`
- Modify: `backend/config.py`
- Modify: `backend/api/asset_package.py`
- Modify: `backend/api/car_valuation.py`
- Modify: `backend/api/inventory_sandbox.py`
- Modify: `backend/api/portfolio.py`
- Modify: `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/auth.ts`
- Create: `frontend/src/components/auth/session-provider.tsx`
- Create: `frontend/src/components/auth/role-guard.tsx`
- Create: `frontend/src/app/login/page.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Test: `backend/tests/api/test_auth_login.py`
- Test: `backend/tests/api/test_rbac.py`

**Step 1: 写失败测试**

```python
def test_login_returns_session_cookie(client, seeded_user):
    response = client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Passw0rd!"})
    assert response.status_code == 200
    assert "set-cookie" in response.headers

def test_viewer_cannot_call_manager_endpoint(client, viewer_token):
    response = client.get("/api/portfolio/manager-playbook", headers={"Authorization": f"Bearer {viewer_token}"})
    assert response.status_code == 403
```

**Step 2: 引入用户、角色、会话表**

角色最少：

- `admin`
- `manager`
- `operator`
- `viewer`

**Step 3: 统一认证依赖**

`backend/dependencies/auth.py` 至少提供：

- `get_current_user`
- `require_role("manager")`
- `require_any_role("admin", "manager")`

**Step 4: 前端接登录态**

要求：

- `frontend/src/lib/api.ts` 的 `fetch` 增加 `credentials: "include"`。
- `frontend/src/components/auth/session-provider.tsx` 统一维护当前用户信息。
- `frontend/src/components/auth/role-guard.tsx` 控制页面访问。

**Step 5: 验证**

Run: `cd backend && pytest tests/api/test_auth_login.py tests/api/test_rbac.py -q`
Expected: PASS

Run: `cd frontend && npm run lint && npm run build`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/db/models backend/services backend/dependencies backend/api/auth.py backend/scripts/create_admin.py docs/security/rbac-matrix.md frontend/src/lib frontend/src/components/auth frontend/src/app/login frontend/src/app/layout.tsx
git commit -m "feat: add authentication and role-based access control"
```

### Task 6: 增加租户隔离与审计日志

**Files:**
- Create: `backend/db/models/tenant.py`
- Create: `backend/db/models/membership.py`
- Create: `backend/db/models/audit_log.py`
- Create: `backend/services/tenant_context.py`
- Create: `backend/services/audit_service.py`
- Create: `backend/middleware/request_context.py`
- Modify: `backend/db/models/asset_package.py`
- Modify: `backend/db/models/sandbox.py`
- Modify: `backend/db/models/portfolio.py`
- Modify: `backend/repositories/asset_package_repo.py`
- Modify: `backend/repositories/sandbox_repo.py`
- Modify: `backend/repositories/portfolio_repo.py`
- Modify: `backend/api/asset_package.py`
- Modify: `backend/api/inventory_sandbox.py`
- Modify: `backend/api/portfolio.py`
- Test: `backend/tests/api/test_tenant_isolation.py`
- Test: `backend/tests/api/test_audit_logs.py`

**Step 1: 写跨租户访问失败测试**

```python
def test_user_cannot_read_other_tenant_asset_package(client, foreign_tenant_token, seeded_foreign_package):
    response = client.get(f"/api/asset-package/{seeded_foreign_package.id}", headers={"Authorization": f"Bearer {foreign_tenant_token}"})
    assert response.status_code in (403, 404)
```

**Step 2: 给核心业务表补 `tenant_id` 与 `created_by`**

至少补到：

- 资产包
- 单车资产
- 沙盘结果
- 经营驾驶舱快照及策略结果

**Step 3: 在 repo 层强制 tenant 过滤**

禁止在 API 层手写 `tenant_id` 过滤分支；统一在 repo 或 query helper 里处理。

**Step 4: 加审计日志**

审计记录至少包含：

- `tenant_id`
- `user_id`
- `action`
- `resource_type`
- `resource_id`
- `request_id`
- `ip`
- `user_agent`
- `before_json`
- `after_json`

必须记录以下动作：

- 登录
- 上传资产包
- 运行计算
- 生成报告
- 导出结果
- 修改策略或配置

**Step 5: 验证**

Run: `cd backend && pytest tests/api/test_tenant_isolation.py tests/api/test_audit_logs.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/db/models backend/services/tenant_context.py backend/services/audit_service.py backend/middleware/request_context.py backend/repositories backend/api backend/tests/api
git commit -m "feat: add tenant isolation and audit logging"
```

### Task 7: 抽象文件存储并迁移到对象存储

**Files:**
- Create: `backend/services/storage/base.py`
- Create: `backend/services/storage/local.py`
- Create: `backend/services/storage/s3.py`
- Create: `backend/services/storage/factory.py`
- Create: `infra/minio/docker-compose.yml`
- Create: `docs/ops/object-storage.md`
- Modify: `backend/config.py`
- Modify: `backend/api/asset_package.py`
- Modify: `backend/services/pdf_generator.py`
- Modify: `backend/repositories/asset_package_repo.py`
- Modify: `backend/repositories/sandbox_repo.py`
- Test: `backend/tests/api/test_asset_upload_storage.py`
- Test: `backend/tests/services/test_report_storage.py`

**Step 1: 写失败测试**

```python
def test_uploaded_file_is_stored_by_storage_service(client, sample_excel, storage_spy):
    response = client.post("/api/asset-package/upload", files={"file": sample_excel})
    assert response.status_code == 200
    assert storage_spy.put_object_called is True
```

**Step 2: 定义统一存储接口**

接口最少包含：

- `put_bytes(key: str, data: bytes, content_type: str) -> StoredObject`
- `get_bytes(key: str) -> bytes`
- `delete_object(key: str) -> None`
- `build_download_url(key: str, expires_in: int = 300) -> str`

**Step 3: 数据库存“对象 key”而不是“磁盘路径”**

要求：

- `asset_packages.upload_filename` 升级为 `storage_key` 或新增字段保存对象 key。
- `sandbox_results.report_pdf_path` 升级为 `report_storage_key`。

**Step 4: 前端下载必须走授权链路**

不要让前端直接拼公开路径；由后端提供授权下载地址或代理下载接口。

**Step 5: 验证**

Run: `cd backend && pytest tests/api/test_asset_upload_storage.py tests/services/test_report_storage.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/services/storage infra/minio docs/ops/object-storage.md backend/config.py backend/api/asset_package.py backend/services/pdf_generator.py backend/repositories backend/tests
git commit -m "feat: move uploads and reports behind storage abstraction"
```

### Task 8: 把长耗时流程改为异步任务

**Files:**
- Create: `backend/jobs/worker.py`
- Create: `backend/jobs/tasks.py`
- Create: `backend/services/job_dispatcher.py`
- Create: `backend/db/models/job_run.py`
- Create: `backend/api/jobs.py`
- Modify: `backend/api/asset_package.py`
- Modify: `backend/api/inventory_sandbox.py`
- Modify: `backend/services/pdf_generator.py`
- Modify: `backend/config.py`
- Create: `frontend/src/lib/jobs.ts`
- Modify: `frontend/src/app/asset-pricing/page.tsx`
- Modify: `frontend/src/app/inventory-sandbox/page.tsx`
- Test: `backend/tests/api/test_job_lifecycle.py`
- Test: `backend/tests/api/test_async_report_generation.py`

**Step 1: 写失败测试**

```python
def test_report_generation_returns_job_reference(client, auth_cookie):
    response = client.post("/api/sandbox/1/report")
    assert response.status_code == 202
    assert "job_id" in response.json()
```

**Step 2: 只先异步化两条路径**

- 资产包批量计算
- 报告生成

不要第一步就把所有接口都改成异步。

**Step 3: 定义任务状态机**

状态最少：

- `queued`
- `running`
- `succeeded`
- `failed`

字段最少：

- `job_type`
- `tenant_id`
- `requested_by`
- `payload_json`
- `result_json`
- `error_code`
- `error_message`

**Step 4: 前端增加任务态 UI**

要求：

- 页面可见“排队中/处理中/成功/失败”。
- 成功后自动刷新结果。
- 失败后展示错误码和重试入口。

**Step 5: 验证**

Run: `cd backend && pytest tests/api/test_job_lifecycle.py tests/api/test_async_report_generation.py -q`
Expected: PASS

Run: `cd frontend && npm run lint && npm run build`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/jobs backend/services/job_dispatcher.py backend/db/models/job_run.py backend/api/jobs.py backend/api backend/config.py frontend/src/lib/jobs.ts frontend/src/app/asset-pricing/page.tsx frontend/src/app/inventory-sandbox/page.tsx backend/tests/api
git commit -m "feat: add async jobs for long-running workflows"
```

### Task 9: 加固第三方调用与可观测性

**Files:**
- Create: `backend/services/http_client.py`
- Create: `backend/logging.py`
- Create: `backend/middleware/request_id.py`
- Create: `backend/api/metrics.py`
- Create: `docs/runbooks/integration-failures.md`
- Create: `docs/runbooks/observability.md`
- Modify: `backend/services/che300_client.py`
- Modify: `backend/services/llm_client.py`
- Modify: `backend/main.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/services/test_che300_resilience.py`
- Test: `backend/tests/services/test_llm_timeout.py`
- Test: `backend/tests/api/test_metrics.py`

**Step 1: 写失败测试**

```python
def test_che300_timeout_is_translated_to_domain_error(...):
    ...

def test_metrics_endpoint_exposes_request_counter(client):
    response = client.get("/api/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text
```

**Step 2: 接入重试、超时、熔断的统一 HTTP client**

推荐能力：

- 默认超时
- 指数退避重试
- 幂等请求限制
- 服务降级错误包装

**Step 3: 加结构化日志**

日志字段最少：

- `timestamp`
- `level`
- `request_id`
- `tenant_id`
- `user_id`
- `path`
- `method`
- `duration_ms`
- `error_code`

**Step 4: 加指标暴露**

至少暴露：

- 请求总量
- 请求耗时
- 外部 API 成功率
- 任务队列长度
- 报告生成耗时

**Step 5: 验证**

Run: `cd backend && pytest tests/services/test_che300_resilience.py tests/services/test_llm_timeout.py tests/api/test_metrics.py -q`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/services/http_client.py backend/logging.py backend/middleware/request_id.py backend/api/metrics.py backend/services/che300_client.py backend/services/llm_client.py backend/main.py backend/requirements.txt docs/runbooks backend/tests
git commit -m "feat: harden integrations and observability"
```

### Task 10: 统一错误码、API 契约、备份与数据治理

**Files:**
- Create: `backend/errors.py`
- Create: `backend/schemas/error.py`
- Create: `frontend/src/lib/errors.ts`
- Create: `docs/api/error-codes.md`
- Create: `docs/security/data-classification.md`
- Create: `docs/security/data-retention.md`
- Create: `docs/runbooks/backup-restore.md`
- Create: `docs/runbooks/tenant-onboarding.md`
- Create: `scripts/backup_postgres.sh`
- Create: `scripts/backup_storage.sh`
- Create: `.github/workflows/security.yml`
- Modify: `.gitignore`
- Modify: `frontend/src/lib/api.ts`
- Modify: `backend/main.py`
- Test: `backend/tests/contracts/test_openapi_contract.py`
- Test: `backend/tests/api/test_error_envelope.py`

**Step 1: 写失败测试**

```python
def test_business_errors_return_standard_envelope(client):
    response = client.get("/api/asset-package/999999")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "ASSET_PACKAGE_NOT_FOUND"
```

**Step 2: 统一错误响应格式**

标准错误体：

```json
{
  "error": {
    "code": "ASSET_PACKAGE_NOT_FOUND",
    "message": "资产包不存在",
    "request_id": "req_123",
    "details": {}
  }
}
```

**Step 3: 固化 OpenAPI 契约**

要求：

- FastAPI 导出的 OpenAPI 文档必须包含认证、错误码、分页、任务状态模型。
- `backend/tests/contracts/test_openapi_contract.py` 需要验证关键路径是否仍存在。

**Step 4: 增加安全与交付文档**

必须覆盖：

- 数据分级
- 脱敏规则
- 数据保留期限
- 备份频率
- 恢复演练步骤
- 新租户开通 checklist

**Step 5: 加安全扫描工作流**

安全工作流至少执行：

```yaml
- run: pip install pip-audit
- run: pip-audit -r backend/requirements.txt
- run: cd frontend && npm audit --audit-level=high
- uses: gitleaks/gitleaks-action@v2
```

**Step 6: 验证**

Run: `cd backend && pytest tests/contracts/test_openapi_contract.py tests/api/test_error_envelope.py -q`
Expected: PASS

**Step 7: Commit**

```bash
git add backend/errors.py backend/schemas/error.py frontend/src/lib/errors.ts docs/api docs/security docs/runbooks scripts .github/workflows/security.yml .gitignore frontend/src/lib/api.ts backend/main.py backend/tests/contracts backend/tests/api
git commit -m "feat: standardize contracts governance and release safeguards"
```

## Recommended Execution Sequence

1. 完成 Task 1-2，先把 CI、文档、环境契约立住。
2. 完成 Task 3-4，先把数据库地基换掉，再迁业务读写。
3. 完成 Task 5-6，把认证、RBAC、租户隔离、审计一起收口。
4. 完成 Task 7-8，把文件与长任务从“本地同步模式”迁到“生产模式”。
5. 完成 Task 9-10，把系统拉到可观测、可交付、可审计状态。

## Explicit Stop Conditions

- 如果 Task 3 的 PostgreSQL 迁移在三次尝试后仍不能稳定跑通，暂停后续认证与租户工作，先修数据库基础设施。
- 如果 Task 5 的认证方案在浏览器跨域 Cookie 上卡住，暂停前端页面改造，先用 Postman/TestClient 验证后端会话模型。
- 如果 Task 8 的异步任务稳定性不足，不要继续扩展更多异步场景，先把“资产包计算”和“报告生成”两条链路做稳。

## Definition of Done

- 所有业务 API 默认受认证保护，权限矩阵可验证。
- 所有核心数据表都具备租户隔离和审计能力。
- 文件与报告存储不依赖本地磁盘。
- 长任务可异步执行、查询、重试、追踪。
- 系统有统一错误码、OpenAPI 契约、CI 检查、安全扫描、备份恢复文档。
- `cd backend && pytest -q`、`cd backend && python3 -m compileall .`、`cd frontend && npm run lint`、`cd frontend && npm run build` 全部通过。
