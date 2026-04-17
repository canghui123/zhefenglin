# 商业化控制中台

## 目标

在不破坏现有资产处置主链路的前提下，为系统补齐以下可商用能力：

- 套餐与订阅管理
- 高成本能力守门
- 业务内发起审批与审批后重试
- LLM 路由配置
- 车300 高级车况定价触发规则
- usage_event / cost_snapshot 成本沉淀
- 审批流
- 成本中心与价值看板后台页面

## 数据层

本次新增表：

- `plans`
- `tenant_subscriptions`
- `feature_entitlements`
- `usage_events`
- `cost_snapshots`
- `model_routing_rules`
- `valuation_trigger_rules`
- `approval_requests`

对应 migration：

- `backend/alembic/versions/20260416_0006_commercial_controls.py`

## 默认种子

初始化脚本：

```bash
cd backend
python -m scripts.seed_commercial_defaults
```

脚本会幂等写入：

- 默认套餐：`trial_poc` / `standard` / `pro_manager` / `enterprise_private`
- 默认 feature entitlements
- 默认全局模型路由
- 默认估值触发规则

## 高成本守门

### 车300

- 基础 VIN 估值默认按 `vin_call` 计量
- 高级车况定价需要显式请求 `advanced_condition_pricing`
- 当规则不满足或预算不足时：
  - 默认降级为基础 VIN 估值
  - `strict_policy=true` 时返回结构化业务错误

关键错误码：

- `HIGH_COST_ACTION_BLOCKED`
- `QUOTA_EXCEEDED`
- `BUDGET_EXCEEDED`

### LLM

- 按 `task_type` 走模型路由
- 优先使用 `preferred_model`
- 预算不足时尝试回退到 `fallback_model`
- 再不满足时回退模板化文本

## 后台 API

### 套餐与订阅

- `GET /api/admin/settings/plans`
- `POST /api/admin/settings/plans`
- `PUT /api/admin/settings/plans/{id}`
- `GET /api/admin/settings/subscriptions`
- `PUT /api/admin/settings/subscriptions/{tenant_id}`

### 成本中心

- `GET /api/admin/cost-center/overview`
- `GET /api/admin/cost-center/tenants`
- `GET /api/admin/cost-center/export`
- `GET /api/admin/cost-center/value-dashboard`

### 路由与规则

- `GET /api/admin/model-routing`
- `PUT /api/admin/model-routing`
- `GET /api/admin/valuation-rules`
- `PUT /api/admin/valuation-rules`

### 审批流

- `GET /api/admin/approval-requests`
- `POST /api/admin/approval-requests`
- `POST /api/admin/approval-requests/{id}/approve`
- `POST /api/admin/approval-requests/{id}/reject`

当前已经支持：

- 业务页在高级车况定价被拦截时，直接拿到结构化审批上下文
- 操作员可直接从业务页发起审批请求
- 审批通过后，业务页可以带 `approval_request_id` 重试高成本动作
- 审批单在成功执行后会记录消费时间和消费来源请求
- `seat_limit` 已经接入运行时校验，租户席位满额时会阻止继续分配 membership
- `feature_entitlements` 已经支持运行时解析，按“租户 override -> 套餐默认 -> plan feature_flags”顺序生效
- 登录态 `/api/auth/me` / `/api/auth/login` 已经返回 capability snapshot，前端可据此做导航和页面级 gate
- 成本中心 `export` 已接入 `audit.export` 权益控制
- 成本中心导出按钮已按 capability 预先禁用，并显示升级提示
- 成本中心 `overview` / `tenants` 已接入 `dashboard.advanced` 权益控制
- 模型路由 API 已接入 `routing.model_control` 权益控制
- 高管驾驶页与经理作战手册 API 已接入 `portfolio.advanced_pages` 权益控制
- 租户价值看板 API 已接入 `tenant.value_dashboard` 权益控制
- 库存沙盘“打印/保存PDF”按钮已接入 `audit.export` 能力控制，不会影响报告预览主链路
- 前端侧边栏已经按角色 + feature capability 过滤，高阶页和中台页不会再对未开通租户暴露入口

## 前端页面

新增页面：

- `/admin/settings`
- `/admin/billing`
- `/admin/cost-center`
- `/admin/model-routing`
- `/admin/valuation-rules`
- `/admin/approval-requests`
- `/admin/value-dashboard`

## 关键验证

后端：

```bash
cd backend
python3 -m pytest -q
python3 -m compileall .
```

前端：

```bash
cd frontend
npm run lint
npm run build
```

## 当前实现边界

- 高级车况定价已经有受控触发和降级能力，但仍复用当前车300估值链路，后续可继续对接独立的高级定价接口
- 高级车况定价审批闭环已经打通到资产包页和单车估值 API，但还未扩展为“审批通过后自动恢复执行”的异步工作流
- 价值看板指标当前为可替换的估算逻辑，适合销售演示和运营驾驶舱一期
- 套餐和内部成本价格目前已进入配置层和数据库层，下一步可继续做更细的后台调价和审计历史
- 目前已经覆盖导航、页面和高价值 API 的主要 feature gate；剩余可继续补的是更细粒度按钮级控制和套餐升级引导
