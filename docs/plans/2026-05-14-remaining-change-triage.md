# 剩余未提交改动盘点与拆分建议

日期：2026-05-14
当前分支：`codex/asset-pricing-hardening-handoff`
当前锚点：`9a19085 fix: stabilize production sandbox reports`

## 背景

生产 P0 热修复已经独立提交并推送到远端。当前工作区仍有大量未提交改动，不能执行 `git add .`，也不适合直接继续叠加 P1 功能。

本文件用于把剩余改动先拆清楚，后续按组 staged / commit / validate。

## 当前规模

基于 `git status --short`、`git diff --stat` 和 `git ls-files --others --exclude-standard`：

- 已跟踪文件变更：54 个。
- 未跟踪文件：69 个。
- 已跟踪 diff 规模：约 `3835 insertions` / `299 deletions`。
- 未跟踪内容包含本地工具缓存、验收产物、部署模板、后端新增服务/测试、前端测试配置和文档。

## 总体原则

- 不要执行 `git add .`。
- 不要删除或回退未确认的本地文件。
- 每组提交前先 `git diff --cached --check`。
- 每组提交后至少跑相关定向测试；最终合并前跑完整验证。
- 对 `backend/config.py`、`backend/tests/conftest.py`、`frontend/package-lock.json` 这类共享文件优先使用 hunk-level staging。
- `deploy/.env.production` 提交前必须人工确认没有真实密钥。

## 建议拆分顺序

### 0. 本地产物与缓存处置

目标：先隔离不应进入代码提交的本地文件，避免后续误加。

建议不提交：

- `.playwright-cli/`
- `data/acceptance-artifacts/`
- `data/uploads/sandbox_1.html`

建议待确认：

- 是否新增或更新 `.gitignore`，忽略 `.playwright-cli/` 与 `data/acceptance-artifacts/`。
- `docs/acceptance/2026-05-13-p0-e2e-acceptance.md` 和 `docs/acceptance/2026-05-13-release-readiness.md` 是验收文档，可提交，但不要连同二进制/运行产物一起提交。

### 1. 访问申请、认证与安全基线

目标：把公开注册改为申请制，并补密码策略、限流、运行时安全和法律页。

候选文件：

- `backend/alembic/versions/20260421_0009_access_requests_and_terms.py`
- `backend/api/access_request.py`
- `backend/api/auth.py`
- `backend/db/models/access_request.py`
- `backend/db/models/user.py`
- `backend/db/models/user_session.py`
- `backend/repositories/access_request_repo.py`
- `backend/scripts/list_access_requests.py`
- `backend/services/password_policy.py`
- `backend/services/rate_limit_service.py`
- `backend/services/runtime_security.py`
- `backend/errors.py`
- `backend/main.py`
- `backend/config.py` 中与 `APP_ENV`、注册开关、条款版本、限流相关的 hunk
- `frontend/src/app/register/page.tsx`
- `frontend/src/app/legal/notice/page.tsx`
- `frontend/src/app/legal/terms/page.tsx`
- `frontend/src/components/layout/site-footer.tsx`
- `frontend/src/lib/auth.ts`
- `frontend/src/components/auth/session-provider.tsx` 中相关 hunk
- `frontend/src/app/layout.tsx` 中 footer / legal 相关 hunk
- `backend/tests/api/test_access_request.py`
- `backend/tests/api/test_auth_login.py`
- `backend/tests/api/test_rate_limits.py`
- `backend/tests/services/test_password_policy.py`
- `backend/tests/services/test_runtime_security.py`

风险与注意：

- 该组会改变用户注册/登录行为，属于外部可见变更。
- 需要确认 `ALLOW_PUBLIC_REGISTRATION=false` 在生产是否符合当前商业策略。
- cookie `secure` 逻辑要确认本地开发环境仍可登录。

建议验证：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 -m pytest -q tests/api/test_auth_login.py tests/api/test_access_request.py tests/api/test_rate_limits.py tests/services/test_password_policy.py tests/services/test_runtime_security.py

cd /Users/canghui/Desktop/汽车金融ai平台/frontend
npm run lint
npm run build
```

### 2. 部署、Nginx、对象存储与运维合规

目标：收口生产部署脚本、HTTPS/www 跳转、备份容器、S3 下载说明、Docker 构建源和合规文档。

候选文件：

- `backend/.env.example`
- `backend/Dockerfile`
- `backend/config.py` 中 `S3_PUBLIC_BASE_URL`、CORS、生产配置相关 hunk
- `backend/logging_config.py`
- `backend/services/storage/local.py`
- `backend/tests/api/test_asset_upload_storage.py`
- `backend/tests/services/test_report_storage.py`
- `backend/tests/services/test_s3_storage.py`
- `deploy/.env.production`
- `deploy/README.md`
- `deploy/COMPLIANCE.md`
- `deploy/docker-compose.yml`
- `deploy/nginx/conf.d/app.conf`
- `deploy/nginx/nginx.conf`
- `deploy/nginx/templates/app.http.conf.template`
- `deploy/nginx/templates/app.https.conf.template`
- `deploy/setup.sh`
- `docs/ops/env-matrix.md`
- `frontend/Dockerfile`

风险与注意：

- `deploy/.env.production` 必须做 secret scan。
- Nginx 模板会影响证书申请、HTTP 到 HTTPS、www 到裸域跳转。
- `postgres-backup` 会新增一个生产容器，需要确认磁盘和备份保留策略。

建议验证：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台
bash -n deploy/setup.sh

cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 -m pytest -q tests/api/test_asset_upload_storage.py tests/services/test_report_storage.py tests/services/test_s3_storage.py
python3 -m compileall .
```

如本机 Docker 可用，再补：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/deploy
docker compose config
```

### 3. 商业化后台、估值规则与权限控制

目标：整理后台设置、模型路由、估值规则、商业化守卫和 RBAC/租户测试。

候选文件：

- `backend/api/admin_model_routing.py`
- `backend/api/admin_settings.py`
- `backend/api/admin_valuation_rules.py`
- `backend/api/car_valuation.py`
- `backend/db/models/__init__.py`
- `backend/db/models/plan.py`
- `backend/db/models/tenant.py`
- `backend/db/models/valuation_control.py`
- `backend/repositories/model_routing_repo.py`
- `backend/repositories/valuation_rule_repo.py`
- `backend/tests/api/admin_commercial_helpers.py`
- `backend/tests/api/test_admin_model_routing.py`
- `backend/tests/api/test_admin_valuation_rules.py`
- `backend/tests/api/test_commercial_guardrails.py`
- `backend/tests/api/test_rbac.py`
- `backend/tests/api/test_tenant_isolation.py`
- `backend/tests/db/test_alembic_upgrade.py`
- `frontend/src/app/admin/settings/page.test.tsx`

风险与注意：

- 该组可能涉及套餐/租户/权限边界，提交前需要重点 review tenant isolation。
- `test_alembic_upgrade.py` 和模型变更必须与 Alembic 状态一致。

建议验证：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 -m pytest -q tests/api/test_admin_model_routing.py tests/api/test_admin_valuation_rules.py tests/api/test_commercial_guardrails.py tests/api/test_rbac.py tests/api/test_tenant_isolation.py tests/db/test_alembic_upgrade.py
```

### 4. P0 资产包与沙盘业务回归补强

目标：把 P0 相关的解析、估值可信度、交易适配度、买方报价、法律路径评分和任务生命周期测试整理成独立提交。

候选文件：

- `backend/services/depreciation.py`
- `backend/services/excel_parser.py`
- `backend/services/job_dispatcher.py`
- `backend/tests/api/test_async_report_generation.py`
- `backend/tests/api/test_audit_logs.py`
- `backend/tests/api/test_error_envelope.py`
- `backend/tests/api/test_job_lifecycle.py`
- `backend/tests/api/test_p0_enhancements.py`
- `backend/tests/api/test_upload_validation.py`
- `backend/tests/services/test_excel_parser.py`
- `backend/tests/services/test_legal_path_assessment.py`
- `backend/tests/services/test_pricing_engine.py`
- `backend/tests/services/test_tradeability_and_buyer_offer.py`
- `backend/tests/services/test_valuation_confidence.py`

风险与注意：

- `excel_parser.py` 已改变旧“买断价/转让价”识别逻辑，需确认与产品策略一致。
- `job_dispatcher.py` 可能影响异步任务状态语义，需和前端轮询逻辑一致。
- 若某些测试依赖已经在已提交 P0 代码中存在，建议先跑测试确认没有遗漏实现文件。

建议验证：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 -m pytest -q tests/api/test_p0_enhancements.py tests/api/test_upload_validation.py tests/api/test_async_report_generation.py tests/api/test_audit_logs.py tests/api/test_error_envelope.py tests/api/test_job_lifecycle.py tests/services/test_excel_parser.py tests/services/test_legal_path_assessment.py tests/services/test_pricing_engine.py tests/services/test_tradeability_and_buyer_offer.py tests/services/test_valuation_confidence.py
```

### 5. 前端测试基础设施与页面回归

目标：补 Vitest/Testing Library，并整理资产定价页、设置页等前端测试。

候选文件：

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/vitest.config.ts`
- `frontend/src/test/setup.ts`
- `frontend/src/app/admin/settings/page.test.tsx`
- `frontend/src/app/asset-pricing/page.test.tsx`
- `frontend/src/app/page.tsx`
- `frontend/src/components/auth/session-provider.tsx` 中测试/状态相关 hunk

风险与注意：

- `frontend/package-lock.json` diff 很大，建议和 `package.json` 一起单独提交。
- 前端测试新增后要确认 CI 是否会运行 `npm run test`；若不运行，也需要在 README/交付说明里明确。

建议验证：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/frontend
npm run lint
npm run build
npm run test
```

### 6. 文档与知识沉淀

目标：提交对外/对 ChatGPT 学习有价值的文档，但不混入运行产物。

候选文件：

- `docs/acceptance/2026-05-13-p0-e2e-acceptance.md`
- `docs/acceptance/2026-05-13-release-readiness.md`
- `docs/system-knowledge-for-chatgpt.md`
- 本文件：`docs/plans/2026-05-14-remaining-change-triage.md`

风险与注意：

- 文档里不要写真实密码、token、生产密钥或私密用户数据。
- 验收产物路径可以引用，但不要默认提交 `data/acceptance-artifacts/`。

建议验证：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台
git diff --check -- docs/acceptance docs/system-knowledge-for-chatgpt.md docs/plans/2026-05-14-remaining-change-triage.md
```

## 建议下一步

优先做第 0 步和第 1 步：

1. 先确认是否新增 `.gitignore` 规则来隔离 `.playwright-cli/`、`data/acceptance-artifacts/` 和 `data/uploads/sandbox_1.html`。
2. 再整理“访问申请、认证与安全基线”提交。

这样可以先把最高风险、最外部可见的用户入口改动收口，避免后续 P1 功能继续叠在注册/登录和合规入口的半成品之上。
