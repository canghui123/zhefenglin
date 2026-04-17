# Approval Closure Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为高级车况定价补齐“业务页发起审批 -> 后台审批 -> 原页带审批单重试 -> 审批单消费落库”的完整闭环，并同步固化 Codex 接手规范。

**Architecture:** 继续复用现有商业化控制中台，在审批单上增加轻量消费字段，并把审批单校验嵌入高成本守门层。业务页通过结构化 `approval_context` 感知是否应发起审批；管理员仍使用现有审批后台，但审批结果可以回流到业务页进行带 `approval_request_id` 的重试。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Next.js App Router, React, TypeScript, pytest, ESLint.

---

### Task 1: 固化 Codex 接手文档

**Files:**
- Create: `docs/CODEX_PLAYBOOK.md`
- Create: `docs/plans/2026-04-17-approval-closure-design.md`
- Modify: `README.md`
- Modify: `docs/HANDOFF.md`

**Step 1: 写接手与设计文档**

文档至少明确：

- Codex 的推荐阅读顺序
- 基线验证命令
- 单主题提交规则
- 商业化控制中台当前边界
- 本轮审批闭环的设计决策

**Step 2: 在索引文档补入口**

把 `docs/CODEX_PLAYBOOK.md` 和审批闭环设计文档挂到 `README.md` 与 `docs/HANDOFF.md`。

**Step 3: 验证**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台 && git diff -- docs README.md`
Expected: only docs-related changes

### Task 2: 扩展审批单模型与仓储层

**Files:**
- Modify: `backend/db/models/valuation_control.py`
- Modify: `backend/repositories/approval_repo.py`
- Modify: `backend/api/admin_approval_requests.py`
- Modify: `frontend/src/lib/api.ts`
- Create: `backend/alembic/versions/20260417_0007_approval_consumption.py`
- Test: `backend/tests/api/test_admin_approval_requests.py`

**Step 1: 先扩测试期望**

补断言让审批请求输出包含：

- `consumed_at`
- `consumed_request_id`
- `is_consumed`

**Step 2: 写 migration 和模型**

给 `approval_requests` 增加：

- `consumed_at`
- `consumed_request_id`

**Step 3: 补仓储能力**

补以下操作：

- 根据 ID 获取审批单
- 标记审批单已消费
- 查找指定对象的审批单列表

**Step 4: 验证**

Run: `cd backend && python3 -m pytest -q tests/api/test_admin_approval_requests.py`
Expected: PASS

### Task 3: 实现审批校验与消费服务

**Files:**
- Modify: `backend/errors.py`
- Modify: `backend/services/approval_service.py`
- Test: `backend/tests/services/test_approval_service.py`

**Step 1: 先写失败测试**

至少覆盖：

- 审批单状态不是 `approved` 时不能执行
- 审批单对象不匹配时不能执行
- 审批单已消费时不能再次执行
- 审批单消费后会记录 `consumed_at`

**Step 2: 增加服务接口**

新增类似：

```python
approval_service.validate_for_execution(...)
approval_service.consume_request(...)
```

**Step 3: 增加错误码**

至少需要：

- `APPROVAL_NOT_APPROVED`
- `APPROVAL_CONTEXT_MISMATCH`
- `APPROVAL_ALREADY_CONSUMED`

**Step 4: 验证**

Run: `cd backend && python3 -m pytest -q tests/services/test_approval_service.py`
Expected: PASS

### Task 4: 把审批闭环接入高成本守门

**Files:**
- Modify: `backend/services/commercial_policy_service.py`
- Modify: `backend/services/che300_client.py`
- Modify: `backend/models/valuation.py`
- Modify: `backend/models/asset.py`
- Modify: `backend/api/car_valuation.py`
- Modify: `backend/api/asset_package.py`
- Test: `backend/tests/api/test_commercial_guardrails.py`

**Step 1: 先写失败测试**

至少覆盖：

- 被拦截时错误详情里包含 `approval_context`
- 携带已批准审批单可执行高级车况定价
- 执行后审批单会被消费
- usage_event metadata 会写入 `approval_request_id`

**Step 2: 扩展请求模型**

需要高成本重试的请求增加：

- `approval_request_id: Optional[int]`

**Step 3: 守门逻辑最小实现**

- 被拦截时补 `approval_context`
- 有 `approval_request_id` 时先校验审批单
- 校验通过后允许执行高级车况定价
- 执行成功后标记审批单已消费

**Step 4: 验证**

Run: `cd backend && python3 -m pytest -q tests/api/test_commercial_guardrails.py`
Expected: PASS

### Task 5: 在业务页补审批闭环 UI

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/app/asset-pricing/page.tsx`
- Test: existing frontend lint/build

**Step 1: 扩 API 契约**

补：

- 业务请求的 `approval_request_id`
- 审批列表里的消费字段
- 能从 `ApiError` 里读取结构化 `details`

**Step 2: 资产包页增加审批卡片**

被拦截时展示：

- 原因
- 预计成本
- 发起审批按钮
- 审批状态
- 审批通过后的重试按钮

**Step 3: 接入一键发起审批**

发起审批时自动带上：

- `type`
- `reason`
- `related_object_type`
- `related_object_id`
- `estimated_cost`
- `metadata`

**Step 4: 验证**

Run: `cd frontend && npm run lint`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: PASS

### Task 6: 回归与文档收尾

**Files:**
- Modify: `docs/commercial-controls.md`
- Modify: `docs/HANDOFF.md`

**Step 1: 更新中台文档**

明确当前已经支持：

- 业务内发起审批
- 带审批单重试
- 审批单消费追踪

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
git add docs backend frontend
git commit -m "feat: add approval closure for condition pricing"
```
