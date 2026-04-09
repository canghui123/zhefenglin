# RBAC 角色权限矩阵

> 范围：Task 5 引入的认证 / RBAC 体系，Task 6 增补的多租户隔离与审计日志。所有业务读写在 repo 层强制按 `tenant_id` 过滤。

## 1. 角色定义

| 角色 | 代号 | 等级 | 典型用户 | 主要职责 |
| --- | --- | --- | --- | --- |
| 管理员 | `admin` | 40 | 平台管理员 | 创建用户、配置租户、审计、紧急干预 |
| 经理 | `manager` | 30 | 业务经理、风险经理 | 查看高管/经理决策视图，制定处置策略 |
| 操作员 | `operator` | 20 | 一线处置、运营 | 上传资产包、运行计算、生成报告 |
| 查看者 | `viewer` | 10 | 销售、稽核、外部观察 | 只读访问业务数据 |

角色等级用于 `require_role(min_role)` 判定：高等级角色自动包含所有低等级角色的权限。

## 2. 后端接口权限矩阵

| 接口 | 路径 | 方法 | 最低角色 | 备注 |
| --- | --- | --- | --- | --- |
| 健康检查 | `/api/health` | GET | 公开 | 探活和监控 |
| 登录 | `/api/auth/login` | POST | 公开 | 错误返回 401 |
| 登出 | `/api/auth/logout` | POST | 公开 | 携带 cookie / Bearer 时撤销 session |
| 当前用户 | `/api/auth/me` | GET | viewer | 任何已登录用户 |
| 估值 - 单车 | `/api/valuation/single` | POST | operator | 触发车300调用 |
| 估值 - 批量 | `/api/valuation/batch` | POST | operator | 触发车300调用 |
| 资产包 - 上传 | `/api/asset-package/upload` | POST | operator | 写文件 |
| 资产包 - 计算 | `/api/asset-package/calculate` | POST | operator | LLM/估值消耗 |
| 资产包 - 详情 | `/api/asset-package/{id}` | GET | viewer | 只读 |
| 资产包 - 列表 | `/api/asset-package/list/all` | GET | viewer | 只读 |
| 沙盘 - 模拟 | `/api/sandbox/simulate` | POST | operator | 写入沙盘结果 |
| 沙盘 - 报告 | `/api/sandbox/{id}/report` | POST | operator | 生成 HTML/PDF |
| 沙盘 - 详情 | `/api/sandbox/{id}` | GET | viewer | 只读 |
| 沙盘 - 列表 | `/api/sandbox/list/all` | GET | viewer | 只读 |
| 经营 - 总览 | `/api/portfolio/overview` | GET | viewer | 公司级 KPI |
| 经营 - 分层 | `/api/portfolio/segmentation` | GET | viewer | 维度切片 |
| 经营 - 策略 | `/api/portfolio/strategies` | GET | viewer | 路径对比 |
| 经营 - 现金流 | `/api/portfolio/cashflow` | GET | viewer | 现金流推演 |
| 经营 - 高管视图 | `/api/portfolio/executive` | GET | manager | 战略决策视图 |
| 经营 - 经理手册 | `/api/portfolio/manager-playbook` | GET | manager | 经理作战 |
| 经营 - 主管控制台 | `/api/portfolio/supervisor-console` | GET | operator | 一线主管 |
| 经营 - 动作中心 | `/api/portfolio/action-center` | GET | operator | 任务派发 |

> 401 = 未登录 / 会话失效；403 = 已登录但角色不足。

## 3. 前端路由可见性

| 路由 | 必需角色 | 守卫组件 |
| --- | --- | --- |
| `/login` | 公开 | — |
| `/` 首页 | viewer | `SessionProvider` 全局重定向 |
| `/asset-pricing` | viewer (查看) / operator (操作) | 页面内 `RoleGuard` |
| `/inventory-sandbox` | viewer (查看) / operator (操作) | 页面内 `RoleGuard` |
| `/portfolio/*` | viewer | 全局重定向 |
| `/portfolio/manager` | manager | 页面内 `RoleGuard` |
| `/portfolio/executive` | manager | 页面内 `RoleGuard` |

> 当前实现的最低保证：未登录用户访问任何非 `/login` 路由都会被 `SessionProvider` 重定向到 `/login?next=...`。页面级 `RoleGuard` 由后续接入按钮态/操作态时再细化。

## 4. 会话与令牌

- 登录成功后服务端签发 HS256 JWT (`12h` 默认 TTL) 并写入 `user_sessions` 表（`token_jti`）。
- 浏览器收到 `Set-Cookie: session=<token>; HttpOnly; SameSite=Lax`。
- 服务器在 `dependencies/auth.py:get_current_user` 同时支持 `Authorization: Bearer <token>` 和 cookie，方便测试客户端复用。
- 登出会调用 `services.auth_service.revoke`，把 `user_sessions.revoked_at` 写为当前时间，使该 jti 立刻失效。
- 生产环境部署时务必在反向代理强制 HTTPS，并把 cookie `secure` 标志改为 `True`（参见 `backend/api/auth.py`）。

## 5. 创建首个管理员

```bash
cd backend
alembic upgrade head
python -m scripts.create_admin --email admin@example.com --password 'Passw0rd!'
```

脚本对同邮箱用户做 upsert：第二次执行会覆盖密码、角色和昵称。

## 6. 多租户隔离（Task 6）

- 新增 `tenants` / `memberships` / `audit_logs` 三张表；`users` 增加 `default_tenant_id` 外键。
- 业务表 `asset_packages`、`sandbox_results` 增加 NOT NULL 的 `tenant_id` 与 `created_by`。`portfolio_snapshots`、`asset_segments`、`management_goals` 增加可空的 `tenant_id`，待后续 Task 接入持久化时再收紧。
- 租户解析在 `services/tenant_context.py:get_current_tenant_id`：
  1. 默认从用户的 `default_tenant_id` 取值。
  2. 客户端可通过 `X-Tenant-Code` header 显式切换租户，但必须在 `memberships` 中拥有该租户的成员资格，否则 403。
  3. 既无默认租户、又无 header 时直接 403，避免越权。
- 所有 repo 函数都强制 `tenant_id` 关键字参数；A 租户用户访问 B 租户的资源会得到 404（参见 `tests/api/test_tenant_isolation.py`）。

## 7. 审计日志

- 写入由 `services/audit_service.py:record` 统一负责，落入 `audit_logs` 表。
- 必填字段：`tenant_id`、`user_id`、`action`、`resource_type`、`resource_id`、`request_id`、`ip`、`user_agent`、`status`，可选 `before_json` / `after_json`。
- `request_id` 由 `middleware/request_context.RequestContextMiddleware` 在每个请求开始时生成；客户端可通过 `X-Request-Id` 预设以便端到端追踪，响应也会回写同一 header。
- 当前已埋点的动作：`login`（含登录失败）、`upload`、`calculate`、`simulate`、`report`。后续 Task 中策略 / 配置变更接入时按相同模式补齐。

## 8. 后续 TODO

- 增加密码复杂度策略和登录失败次数限制。
- `viewer` 之外的角色需要支持单点撤销（管理员页面）。
- 引入 refresh token + 滑动过期机制。
- 审计日志需要管理员只读视图与按时间窗导出。
