# Commercial Controls Platform Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为车途汽车金融 AI 平台补齐成本控制、模型路由、估值触发控制、套餐/额度管理、后台系统设置和商业化准备能力，并保证现有业务链路可继续运行。

**Architecture:** 新增一层“商业化控制中台”，把套餐、额度、预算、模型路由、车300 触发规则、审批、计量和成本统计集中在统一的数据模型与服务层中。业务模块继续负责自己的业务输入输出，但所有高成本外部调用统一先经过策略守门服务，再决定执行、降级或走审批。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Next.js 16 App Router, React 19, TypeScript, Tailwind, shadcn/ui, PostgreSQL, pytest.

---

### Task 1: 建立商业化核心数据模型

**Files:**
- Create: `backend/db/models/plan.py`
- Create: `backend/db/models/subscription.py`
- Create: `backend/db/models/usage.py`
- Create: `backend/db/models/model_routing.py`
- Create: `backend/db/models/valuation_control.py`
- Modify: `backend/db/models/__init__.py`
- Modify: `backend/tests/db/test_alembic_upgrade.py`

**Step 1: 先扩展数据库迁移测试断言**

在 `backend/tests/db/test_alembic_upgrade.py` 的 `REQUIRED_TABLES` 中加入：

```python
"plans",
"tenant_subscriptions",
"feature_entitlements",
"usage_events",
"cost_snapshots",
"model_routing_rules",
"valuation_trigger_rules",
"approval_requests",
```

**Step 2: 跑测试确认缺表失败**

Run: `cd backend && python3 -m pytest -q tests/db/test_alembic_upgrade.py`
Expected: FAIL，提示缺少新表

**Step 3: 写 ORM 模型**

最小模型集合：

- `plans`
- `tenant_subscriptions`
- `feature_entitlements`
- `usage_events`
- `cost_snapshots`
- `model_routing_rules`
- `valuation_trigger_rules`
- `approval_requests`

字段要覆盖：

- 套餐价格、年费、实施费、私有化部署费
- 默认额度与超额单价
- 订阅状态、预算上限、告警阈值
- usage_event 的 module / action / quantity / cost / request_id / related object
- 成本快照的 VIN、车况定价、LLM token、收入和毛利
- 路由规则的 scope / task_type / preferred_model / fallback_model / prompt_version
- 触发规则的 scope / trigger_type / trigger_config
- 审批单的申请人、审批人、成本和关联对象

**Step 4: 跑 lint-free 导入检查**

Run: `cd backend && python3 -m compileall db`
Expected: PASS

### Task 2: 添加 Alembic migration

**Files:**
- Create: `backend/alembic/versions/20260416_0006_commercial_controls.py`

**Step 1: 写 migration**

迁移中创建 Task 1 的全部新表，并为以下字段建立索引：

- `plans.code`
- `tenant_subscriptions.tenant_id`
- `tenant_subscriptions.status`
- `usage_events.tenant_id`
- `usage_events.module`
- `usage_events.created_at`
- `cost_snapshots.tenant_id`
- `cost_snapshots.month`
- `model_routing_rules.scope`
- `model_routing_rules.tenant_id`
- `model_routing_rules.task_type`
- `valuation_trigger_rules.scope`
- `valuation_trigger_rules.tenant_id`
- `approval_requests.tenant_id`
- `approval_requests.status`

**Step 2: 跑迁移测试**

Run: `cd backend && python3 -m pytest -q tests/db/test_alembic_upgrade.py`
Expected: PASS

### Task 3: 增加种子数据脚本

**Files:**
- Create: `backend/scripts/seed_commercial_defaults.py`
- Test: `backend/tests/services/test_seed_commercial_defaults.py`

**Step 1: 写失败测试**

测试至少断言：

- 会创建 `Trial/POC`
- 会创建 `Standard`
- 会创建 `Pro/Manager`
- 会创建 `Enterprise/Private`
- 每个套餐有额度和价格字段

**Step 2: 实现脚本**

脚本要支持幂等执行，并写入：

- 默认套餐
- 默认 feature entitlements
- 默认全局 model routing
- 默认 valuation trigger rules

**Step 3: 验证**

Run: `cd backend && python3 -m pytest -q tests/services/test_seed_commercial_defaults.py`
Expected: PASS

### Task 4: 实现商业化服务层

**Files:**
- Create: `backend/services/commercial_policy_service.py`
- Create: `backend/services/quota_service.py`
- Create: `backend/services/cost_metering_service.py`
- Create: `backend/services/model_routing_service.py`
- Create: `backend/services/valuation_control_service.py`
- Create: `backend/services/approval_service.py`
- Create: `backend/repositories/plan_repo.py`
- Create: `backend/repositories/subscription_repo.py`
- Create: `backend/repositories/usage_repo.py`
- Create: `backend/repositories/model_routing_repo.py`
- Create: `backend/repositories/valuation_rule_repo.py`
- Create: `backend/repositories/approval_repo.py`
- Test: `backend/tests/services/test_quota_service.py`
- Test: `backend/tests/services/test_model_routing_service.py`
- Test: `backend/tests/services/test_valuation_control_service.py`
- Test: `backend/tests/services/test_cost_metering_service.py`
- Test: `backend/tests/services/test_approval_service.py`

**Step 1: 先写失败测试**

至少覆盖：

- 配额够用时放行
- 配额不足时阻止
- 高成本估值不满足触发规则时降级
- 模型路由能按 task_type 返回 preferred/fallback 模型
- usage_event 写入成功
- cost_snapshot 能按月聚合
- 审批状态流转正确

**Step 2: 实现最小服务**

关键接口建议：

```python
quota_service.check_allowance(...)
cost_metering_service.record_usage(...)
model_routing_service.resolve_route(...)
valuation_control_service.evaluate_request(...)
approval_service.create_request(...)
approval_service.approve(...)
approval_service.reject(...)
```

**Step 3: 跑服务层测试**

Run: `cd backend && python3 -m pytest -q tests/services/test_quota_service.py tests/services/test_model_routing_service.py tests/services/test_valuation_control_service.py tests/services/test_cost_metering_service.py tests/services/test_approval_service.py`
Expected: PASS

### Task 5: 把车300/LLM 调用接入守门层

**Files:**
- Modify: `backend/services/che300_client.py`
- Modify: `backend/services/llm_client.py`
- Modify: `backend/api/asset_package.py`
- Modify: `backend/api/inventory_sandbox.py`
- Modify: `backend/api/car_valuation.py`
- Modify: `backend/services/pdf_generator.py`
- Test: `backend/tests/api/test_commercial_guardrails.py`

**Step 1: 写失败的 API/集成测试**

至少验证：

- 高级车况定价默认不自动全量执行
- 预算不足时返回结构化错误
- 被拦截时触发降级逻辑
- 成功调用会写 usage_event

**Step 2: 最小接入**

- 为车300 调用增加 `valuation_level = basic | condition_pricing`
- 为 LLM 调用增加 `task_type`
- 在调用前统一走 quota/budget/routing guard
- 把 request_id、错误码、降级原因写入日志和 usage_event metadata

**Step 3: 验证**

Run: `cd backend && python3 -m pytest -q tests/api/test_commercial_guardrails.py`
Expected: PASS

### Task 6: 新增后台管理 API

**Files:**
- Create: `backend/api/admin_settings.py`
- Create: `backend/api/admin_cost_center.py`
- Create: `backend/api/admin_model_routing.py`
- Create: `backend/api/admin_valuation_rules.py`
- Create: `backend/api/admin_approval_requests.py`
- Modify: `backend/main.py`
- Test: `backend/tests/api/test_admin_commercial_settings.py`
- Test: `backend/tests/api/test_admin_cost_center.py`
- Test: `backend/tests/api/test_admin_approval_requests.py`

**Step 1: 先写失败测试**

至少覆盖：

- admin/manager 角色访问权限
- tenant 隔离
- 创建/更新套餐
- 更新订阅
- 查询成本中心
- 创建审批单
- 审批通过/拒绝

**Step 2: 实现 API**

对齐以下接口：

- `GET/POST/PUT /api/admin/settings/plans`
- `GET/PUT /api/admin/settings/subscriptions`
- `GET /api/admin/cost-center/overview`
- `GET /api/admin/cost-center/tenants`
- `GET /api/admin/cost-center/export`
- `GET/PUT /api/admin/model-routing`
- `GET/PUT /api/admin/valuation-rules`
- `POST /api/admin/approval-requests`
- `POST /api/admin/approval-requests/{id}/approve`
- `POST /api/admin/approval-requests/{id}/reject`

**Step 3: 验证**

Run: `cd backend && python3 -m pytest -q tests/api/test_admin_commercial_settings.py tests/api/test_admin_cost_center.py tests/api/test_admin_approval_requests.py`
Expected: PASS

### Task 7: 新增前端后台页面

**Files:**
- Create: `frontend/src/app/admin/settings/page.tsx`
- Create: `frontend/src/app/admin/billing/page.tsx`
- Create: `frontend/src/app/admin/cost-center/page.tsx`
- Create: `frontend/src/app/admin/model-routing/page.tsx`
- Create: `frontend/src/app/admin/feature-flags/page.tsx`
- Create: `frontend/src/app/admin/approval-requests/page.tsx`
- Create: `frontend/src/app/admin/tenant-value/page.tsx`
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/lib/api.ts`

**Step 1: 先补 API client**

为新增后台接口补齐前端调用函数和类型定义。

**Step 2: 实现页面**

每个页面至少包含：

- 筛选器
- 卡片概览
- 表格
- 状态标签
- 额度进度
- 错误态 / 空态 / 权限态

**Step 3: 验证**

Run: `cd frontend && npm run lint`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: PASS

### Task 8: 文档与全量回归

**Files:**
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/HANDOFF.md`
- Create: `docs/ops/commercial-controls.md`

**Step 1: 补文档**

说明：

- 商业化数据模型
- 套餐和额度逻辑
- 高成本调用守门策略
- 审批模式
- 种子脚本使用方式

**Step 2: 全量验证**

Run: `cd backend && python3 -m pytest -q`
Expected: PASS

Run: `cd backend && python3 -m compileall .`
Expected: PASS

Run: `cd frontend && npm run lint`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: PASS

**Step 3: Commit**

```bash
git add backend frontend docs
git commit -m "feat: add commercial controls platform"
```
