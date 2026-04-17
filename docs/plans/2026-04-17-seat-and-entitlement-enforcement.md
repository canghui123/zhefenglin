# Seat And Entitlement Enforcement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为商业化控制中台补齐席位上限和功能权益的运行时约束，让套餐配置能够真实限制用户入驻与后台高价值能力访问。

**Architecture:** 继续复用现有 `plans`、`tenant_subscriptions`、`feature_entitlements` 结构，在后端增加一个轻量 entitlement 解析服务，统一处理“套餐默认值 + 租户级覆盖”。席位限制放到 `create_membership()` 这条公共通道，功能限制先接到 `audit.export` 和 `tenant.value_dashboard` 两个高价值入口，再由前端把 403/409 转成明确的升级提示。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Pydantic v2, Next.js App Router, React, TypeScript, pytest, ESLint.

---

### Task 1: 固化运行时约束设计

**Files:**
- Create: `docs/plans/2026-04-17-seat-and-entitlement-enforcement.md`
- Modify: `docs/HANDOFF.md`

**Step 1: 记录本轮边界**

明确本轮只做：

- `seat_limit` 运行时校验
- `audit.export` 套餐级限制
- `tenant.value_dashboard` 租户级 override 限制
- 前端错误态与升级提示

**Step 2: 验证**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台 && git diff -- docs`
Expected: only current plan / handoff docs changed

### Task 2: 写席位限制失败测试

**Files:**
- Modify: `backend/tests/api/test_auth_login.py`
- Test: `backend/tests/api/test_auth_login.py`

**Step 1: 写失败测试**

新增测试覆盖：

- 当默认租户存在当前订阅且 `seat_limit=1` 时，第二个注册用户不能再加入默认租户
- 错误返回必须是结构化业务错误，能说明当前套餐席位已满

**Step 2: 运行测试确认失败**

Run: `cd backend && python3 -m pytest -q tests/api/test_auth_login.py -k seat_limit`
Expected: FAIL because membership creation is not enforced yet

### Task 3: 实现席位限制服务与仓储接入

**Files:**
- Create: `backend/services/entitlement_service.py`
- Modify: `backend/errors.py`
- Modify: `backend/repositories/tenant_repo.py`
- Modify: `backend/api/auth.py`
- Test: `backend/tests/api/test_auth_login.py`

**Step 1: 最小实现 seat limit 解析**

新增统一服务能力：

- 解析 tenant 当前订阅与当前 plan
- 计算当前 tenant 的 `seat_limit`
- 统计当前 tenant 已占用席位

**Step 2: 在 membership 创建口执行校验**

`create_membership()` 在真正插入前：

- 先跳过重复 membership
- 若无当前订阅则保持兼容，允许通过
- 若已达到上限则抛结构化业务错误

**Step 3: 让注册接口返回业务错误**

保持 `/api/auth/register` 现有链路不变，只让席位异常沿统一错误体系返回。

**Step 4: 验证**

Run: `cd backend && python3 -m pytest -q tests/api/test_auth_login.py`
Expected: PASS

### Task 4: 写功能权益失败测试

**Files:**
- Modify: `backend/tests/api/test_admin_cost_center.py`
- Test: `backend/tests/api/test_admin_cost_center.py`

**Step 1: 写失败测试**

新增测试覆盖：

- `standard` 套餐访问 `/api/admin/cost-center/export` 返回 403，因为 `audit.export=false`
- 对某个租户写入 `tenant.value_dashboard=false` 的租户级 entitlement override 后，访问 `/api/admin/cost-center/value-dashboard` 返回 403

**Step 2: 运行测试确认失败**

Run: `cd backend && python3 -m pytest -q tests/api/test_admin_cost_center.py`
Expected: FAIL because endpoints currently do not enforce entitlements

### Task 5: 实现功能权益解析与 API 限制

**Files:**
- Create: `backend/services/feature_entitlement_service.py`
- Modify: `backend/errors.py`
- Modify: `backend/repositories/subscription_repo.py`
- Modify: `backend/api/admin_cost_center.py`
- Test: `backend/tests/api/test_admin_cost_center.py`

**Step 1: 实现统一 entitlement 解析**

服务至少支持：

- 读取 tenant 当前订阅计划
- 优先读租户级 `feature_entitlements`
- 回退到 plan 级 `feature_entitlements`
- 返回 `enabled/source/feature_key/tenant_id/plan_code`

**Step 2: 增加强制校验接口**

提供类似：

- `get_effective_feature(...)`
- `ensure_feature_enabled(...)`

**Step 3: 接入成本中心高价值能力**

先在以下 API 接口执行限制：

- `/api/admin/cost-center/export` -> `audit.export`
- `/api/admin/cost-center/value-dashboard` -> `tenant.value_dashboard`

**Step 4: 验证**

Run: `cd backend && python3 -m pytest -q tests/api/test_admin_cost_center.py`
Expected: PASS

### Task 6: 前端补套餐反馈与降级提示

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/admin/cost-center/page.tsx`
- Modify: `frontend/src/app/admin/value-dashboard/page.tsx`

**Step 1: 透传业务错误细节**

前端复用现有 `ApiError`，把 403/409 的 message 直接反馈到页面，而不是只弹模糊错误。

**Step 2: 成本中心页增加导出受限态**

当导出被拦截时：

- 给出明确文案
- 不影响总览数据展示

当 value dashboard 被拦截时：

- 卡片区显示升级提示，不让整页静默空白

**Step 3: 租户价值看板页增加无权限 / 未开通态**

当接口 403 时展示：

- 当前套餐未开通或被租户策略关闭
- 建议联系管理员开通

**Step 4: 验证**

Run: `cd frontend && npm run lint`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: PASS

### Task 7: 回归与交接文档

**Files:**
- Modify: `docs/commercial-controls.md`
- Modify: `docs/HANDOFF.md`

**Step 1: 更新当前已交付边界**

补充说明当前已支持：

- 席位限制
- 功能权益解析
- 套餐默认 + 租户 override
- 成本中心高价值能力限制

**Step 2: 全量验证**

Run: `cd backend && python3 -m pytest -q`
Expected: PASS

Run: `cd frontend && npm run lint`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: PASS
