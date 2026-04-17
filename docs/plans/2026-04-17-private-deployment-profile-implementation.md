# Private Deployment Profile Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有 `/admin/settings` 中补齐“租户级技术交付档案”，让 `deployment.private_config` 真正落地为可编辑、可审计、可扩展的私有化交付配置模块。

**Architecture:** 继续复用商业化控制中台，新增独立数据表 `tenant_deployment_profiles` 承载租户级技术交付元数据；后端接口挂在 `admin/settings` 下，前端则把该模块嵌入现有系统设置页。运行时继续复用 `deployment.private_config` 做目标租户级编辑 gate，而不是做整页路由隐藏。

**Tech Stack:** FastAPI, SQLAlchemy 2.0, Alembic, Pydantic v2, Next.js App Router, React, TypeScript, pytest, ESLint.

---

### Task 1: 建立交付档案数据模型与迁移

**Files:**
- Create: `backend/db/models/deployment_profile.py`
- Modify: `backend/db/models/__init__.py`
- Create: `backend/alembic/versions/20260417_0008_tenant_deployment_profiles.py`
- Test: `backend/tests/db/test_alembic_upgrade.py`

**Step 1: 写失败测试，声明新表必须存在**

在 `backend/tests/db/test_alembic_upgrade.py` 里补充期望：

```python
"tenant_deployment_profiles",
```

**Step 2: 运行测试确认当前失败**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/backend && python3 -m pytest -q tests/db/test_alembic_upgrade.py`
Expected: FAIL，提示缺少 `tenant_deployment_profiles`

**Step 3: 写最小 ORM 模型**

```python
class TenantDeploymentProfile(Base):
    __tablename__ = "tenant_deployment_profiles"

    id = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    deployment_mode = mapped_column(String(32), nullable=False, default="saas_dedicated")
    delivery_status = mapped_column(String(32), nullable=False, default="planning")
    access_domain = mapped_column(String(255), nullable=True)
    sso_enabled = mapped_column(Boolean, nullable=False, default=False)
    sso_provider = mapped_column(String(64), nullable=True)
    sso_login_url = mapped_column(String(512), nullable=True)
    storage_mode = mapped_column(String(32), nullable=False, default="platform_managed")
    backup_level = mapped_column(String(32), nullable=False, default="standard")
    environment_notes = mapped_column(Text, nullable=True)
    handover_notes = mapped_column(Text, nullable=True)
    created_by = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
```

**Step 4: 写 migration**

迁移里创建 `tenant_deployment_profiles`，并建立：

- `tenant_id` 唯一约束
- `tenant_id` 索引

**Step 5: 运行测试确认通过**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/backend && python3 -m pytest -q tests/db/test_alembic_upgrade.py`
Expected: PASS

**Step 6: Commit**

```bash
git add backend/db/models/deployment_profile.py backend/db/models/__init__.py backend/alembic/versions/20260417_0008_tenant_deployment_profiles.py backend/tests/db/test_alembic_upgrade.py
git commit -m "feat: add tenant deployment profile schema"
```

### Task 2: 补仓储层与后端契约测试

**Files:**
- Create: `backend/repositories/deployment_profile_repo.py`
- Create: `backend/tests/api/test_admin_deployment_profiles.py`
- Modify: `backend/repositories/__init__.py`

**Step 1: 先写失败 API 测试**

至少覆盖：

```python
def test_admin_can_list_deployment_profiles():
    ...

def test_admin_can_upsert_profile_for_enabled_tenant():
    ...

def test_upsert_rejects_tenant_without_private_config():
    ...

def test_manager_can_read_but_cannot_write_deployment_profiles():
    ...
```

**Step 2: 运行测试确认当前失败**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/backend && python3 -m pytest -q tests/api/test_admin_deployment_profiles.py`
Expected: FAIL，原因是路由和仓储尚未存在

**Step 3: 写最小仓储**

补以下函数：

```python
def get_profile_by_tenant_id(session, *, tenant_id: int): ...
def list_profiles(session): ...
def upsert_profile(session, *, tenant_id: int, **fields): ...
```

要求：

- 已存在则更新同一条
- 不存在则创建新记录

**Step 4: 运行测试确认仍红在 API 层**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/backend && python3 -m pytest -q tests/api/test_admin_deployment_profiles.py`
Expected: FAIL，错误缩小到缺少 API

### Task 3: 实现后端 API 与审计

**Files:**
- Modify: `backend/api/admin_settings.py`
- Modify: `backend/repositories/tenant_repo.py`
- Modify: `backend/services/entitlement_service.py`
- Test: `backend/tests/api/test_admin_deployment_profiles.py`

**Step 1: 写请求与响应模型**

在 `backend/api/admin_settings.py` 中新增：

- `DeploymentProfileUpsertRequest`
- `DeploymentProfileOut`

请求模型至少包含：

- `deployment_mode`
- `delivery_status`
- `access_domain`
- `sso_enabled`
- `sso_provider`
- `sso_login_url`
- `storage_mode`
- `backup_level`
- `environment_notes`
- `handover_notes`

**Step 2: 加列表 API**

新增：

```python
@router.get("/deployment-profiles")
def list_deployment_profiles(...):
    ...
```

要求返回：

- 租户基础信息
- 当前套餐
- `private_config_enabled`
- `private_config_source`
- 交付档案字段
- `updated_at`
- `updated_by`

**Step 3: 加 upsert API**

新增：

```python
@router.put("/deployment-profiles/{tenant_id}")
def upsert_deployment_profile(...):
    ...
```

保存前执行：

1. 校验租户存在
2. 校验当前用户为 `admin`
3. 调用 `entitlement_service.ensure_feature_enabled(..., feature_key="deployment.private_config")`
4. upsert 档案
5. 写 `audit_service.record(...)`

审计要求：

- `action="deployment_profile_upsert"`
- `resource_type="tenant_deployment_profile"`
- `before` / `after` 保存结构化快照

**Step 4: 运行测试确认通过**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/backend && python3 -m pytest -q tests/api/test_admin_deployment_profiles.py`
Expected: PASS

**Step 5: Commit**

```bash
git add backend/api/admin_settings.py backend/repositories/deployment_profile_repo.py backend/repositories/__init__.py backend/repositories/tenant_repo.py backend/services/entitlement_service.py backend/tests/api/test_admin_deployment_profiles.py
git commit -m "feat: add deployment profile admin api"
```

### Task 4: 把 API 契约接入前端数据层

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Test: `frontend/src/app/admin/settings/page.tsx`

**Step 1: 先补 API 类型**

新增：

```ts
export interface DeploymentProfileRow { ... }
export interface DeploymentProfileInput { ... }
```

至少包含：

- `tenant_id`
- `tenant_code`
- `tenant_name`
- `plan_code`
- `plan_name`
- `private_config_enabled`
- `private_config_source`
- `deployment_mode`
- `delivery_status`
- `access_domain`
- `sso_enabled`
- `sso_provider`
- `sso_login_url`
- `storage_mode`
- `backup_level`
- `environment_notes`
- `handover_notes`

**Step 2: 补 API 调用函数**

新增：

```ts
export async function listDeploymentProfiles() { ... }
export async function upsertDeploymentProfile(tenantId: number, input: DeploymentProfileInput) { ... }
```

**Step 3: 前端基础验证**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/frontend && npm run lint`
Expected: PASS 或仅提示设置页尚未接入新函数

### Task 5: 在系统设置页实现私有化交付档案模块

**Files:**
- Modify: `frontend/src/app/admin/settings/page.tsx`
- Optionally Create: `frontend/src/components/admin/deployment-profile-panel.tsx`
- Test: `frontend/src/app/admin/settings/page.tsx`

**Step 1: 先补一个最小可失败的页面状态**

在设置页中新增：

- deployment profiles loading state
- selected tenant state
- selected profile form state

让页面先能拉取 `listDeploymentProfiles()`

**Step 2: 运行 lint/build 确认当前有明确报错或空引用**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/frontend && npm run build`
Expected: FAIL，如果状态或类型未完整接线

**Step 3: 实现最小页面结构**

在 `/admin/settings` 内新增三个区域：

1. 概览卡片
2. 租户列表
3. 选中租户交付档案表单

概览卡片至少显示：

- 已开通私有化配置的租户数
- 已建立交付档案的租户数
- `planning / provisioning / active` 数量

**Step 4: 实现只读 / 可编辑逻辑**

规则：

- `admin` 且 `private_config_enabled = true`：可编辑
- `manager`：只读
- 未开通：禁用表单并显示提示文案，附跳转 `/admin/feature-flags`

**Step 5: 实现保存逻辑**

点击保存时调用：

```ts
await upsertDeploymentProfile(selectedTenantId, form)
```

保存成功后重新拉取数据。

**Step 6: 运行前端验证**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/frontend && npm run lint`
Expected: PASS

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/frontend && npm run build`
Expected: PASS

**Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/app/admin/settings/page.tsx frontend/src/components/admin
git commit -m "feat: add deployment profile settings ui"
```

### Task 6: 文档与全量回归

**Files:**
- Modify: `docs/commercial-controls.md`
- Modify: `docs/HANDOFF.md`
- Modify: `README.md`

**Step 1: 更新文档**

明确补充：

- `/admin/settings` 现在支持租户级技术交付档案
- `deployment.private_config` 已进入真实后台配置闭环
- 第一版只存交付元数据，不存密钥

**Step 2: 运行后端全量验证**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/backend && python3 -m pytest -q`
Expected: PASS

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/backend && python3 -m compileall .`
Expected: PASS

**Step 3: 运行前端全量验证**

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/frontend && npm run lint`
Expected: PASS

Run: `cd /Users/canghui/Desktop/汽车金融ai平台/frontend && npm run build`
Expected: PASS

**Step 4: Commit**

```bash
git add docs README.md
git commit -m "docs: document deployment profile settings"
```
