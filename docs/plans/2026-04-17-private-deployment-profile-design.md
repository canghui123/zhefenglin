# Private Deployment Profile Design

## 背景

商业化控制中台当前已经具备：

- 套餐与订阅管理
- 功能开关后台 `/admin/feature-flags`
- `deployment.private_config` 的套餐默认能力和租户级三态覆盖
- 成本中心、模型路由、审批流等后台页面
- 运行时 capability gating 和审计日志

但“私有化配置”目前还停留在能力开关层，没有真正承接租户级技术交付档案：

- 管理员无法为企业租户维护部署模式、访问域名、SSO、对象存储、备份等级等交付信息
- `deployment.private_config` 不能真正驱动一个可编辑、可审计的后台配置模块
- 后续如果要推进私有化交付、专项实施或专属环境运维，当前系统没有稳定的数据承载层

## 目标

在不打散现有后台结构的前提下，为系统补一套“租户级技术交付档案”能力，满足：

1. 管理员可以在现有系统设置中心维护私有化交付档案
2. `deployment.private_config` 成为真实可运营的能力，而不是仅存在于 feature key
3. 未开通租户在后台仍然可见，但只能只读查看并看到开通引导
4. 所有变更可审计
5. 第一版只存交付元数据，不存敏感凭据

## 方案对比

### 方案 A：独立新页面 `/admin/private-deployment`

为私有化交付单独新增一页和单独导航入口。

优点：

- 页面职责清晰
- 后续扩展空间大

缺点：

- 当前后台信息架构更偏“租户经营设置中心”而不是“独立交付工作台”
- 会把刚建立的商业化中台入口再次拆散
- 对当前阶段来说入口层级偏重

### 方案 B：在 `/admin/settings` 中新增“私有化交付档案”模块

沿用现有系统设置中心，新增一个租户级技术交付档案区块；数据层单独建表。

优点：

- 与套餐、订阅、预算配置天然同域
- 管理员切换租户和处理配置更顺手
- 页面结构变动最小，但数据层依然清晰可扩展

缺点：

- `admin/settings` 页面会更重
- 后续如果私有化交付继续做大，可能仍要拆页

### 方案 C：把交付信息塞进 `tenant.notes` 或 JSON 字段

优点：

- 改动最快

缺点：

- 缺少结构化校验
- 难筛选、难审计、难扩展
- 容易变成商用阶段的技术债

## 推荐方案

选择方案 B。

也就是：

- 页面层：继续使用 `/admin/settings`
- 数据层：新增独立表 `tenant_deployment_profiles`

这样既不破坏现有后台入口，也避免把租户交付信息塞进松散字段里。

## 设计范围

第一版仅覆盖“技术交付档案元数据”，不覆盖真正的机密或凭据管理。

本轮纳入：

- 部署模式
- 交付状态
- 访问域名
- SSO 开关与提供方
- SSO 登录入口 URL
- 对象存储模式
- 备份等级
- 环境说明
- 交付/运维备注

本轮不纳入：

- SSO Client Secret / Metadata XML / 私钥
- 对象存储 AccessKey / SecretKey
- 证书密钥
- 支付、实施费、商务报价字段
- 自动化部署编排

## 数据模型设计

新增表：`tenant_deployment_profiles`

建议字段：

- `id`
- `tenant_id`
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
- `created_by`
- `updated_by`
- `created_at`
- `updated_at`

### 字段约束建议

- `tenant_id` 为唯一外键，一租户最多一条交付档案
- `deployment_mode` 枚举：
  - `saas_dedicated`
  - `private_vpc`
  - `on_premise`
- `delivery_status` 枚举：
  - `planning`
  - `provisioning`
  - `active`
  - `paused`
- `storage_mode` 枚举：
  - `platform_managed`
  - `customer_s3`
  - `hybrid`
- `backup_level` 枚举：
  - `standard`
  - `enhanced`
  - `regulated`
- `access_domain` 允许为空
- `sso_login_url` 允许为空；非空时必须是合法 URL
- `environment_notes`、`handover_notes` 做长度限制，避免滥用为大文本存储

### 安全边界

第一版只存交付档案元数据，不存任何敏感凭据。

也就是说，即使页面显示“客户自管 S3”或“已启用 SSO”，真实密钥、密文配置和私钥也不在这张表中保存。

## 后端设计

### 1. API 放置位置

继续挂在现有 `admin/settings` 命名空间下，保持商业化设置中心的一致性：

- `GET /api/admin/settings/deployment-profiles`
- `PUT /api/admin/settings/deployment-profiles/{tenant_id}`

### 2. 权限模型

- `GET`：`manager` 及以上可读取
- `PUT`：仅 `admin` 可写

### 3. feature gate 语义

`deployment.private_config` 不作为整页路由 gate，而作为“目标租户是否允许编辑这个模块”的能力判断：

- 未开通租户：可见、只读、不可保存
- 已开通租户：可编辑、可保存

这样后台不会失去对未开通租户的视野，也符合商业化运营场景。

### 4. 列表输出结构

`GET /api/admin/settings/deployment-profiles` 建议返回：

- 租户基础信息：
  - `tenant_id`
  - `tenant_code`
  - `tenant_name`
- 当前订阅：
  - `plan_code`
  - `plan_name`
- 能力状态：
  - `private_config_enabled`
  - `private_config_source`
- 交付档案：
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
- 元信息：
  - `updated_at`
  - `updated_by`

### 5. 写入逻辑

`PUT /api/admin/settings/deployment-profiles/{tenant_id}` 行为采用 upsert：

- 如果租户已有交付档案：更新
- 如果没有：创建

在保存前执行：

1. 校验租户存在
2. 校验当前用户为 `admin`
3. 校验目标租户 `deployment.private_config` 已开通
4. 校验字段枚举、URL 和长度

### 6. 审计日志

每次成功保存都记录一条审计：

- `action`: `deployment_profile_upsert`
- `resource_type`: `tenant_deployment_profile`
- `resource_id`: 交付档案主键
- `tenant_id`: 目标租户
- `before` / `after`: 结构化快照

## 前端设计

### 1. 页面位置

在 `/admin/settings` 中新增“私有化交付档案”模块，而不是单开导航页。

### 2. 页面结构

建议拆成三层：

#### 概览卡片

显示：

- 已开通私有化配置的租户数
- 已建立交付档案的租户数
- `planning / provisioning / active` 各状态数量

#### 租户列表

每行显示：

- 租户名
- 当前套餐
- 私有化能力是否开通
- 部署模式
- 交付状态
- 域名
- 最近更新时间

#### 选中租户详情表单

用于编辑：

- 部署模式
- 交付状态
- 域名
- SSO 开关/提供方/登录 URL
- 存储模式
- 备份等级
- 环境说明
- 交付备注

### 3. 交互语义

- 已开通、管理员：可编辑、可保存
- 已开通、经理：只读
- 未开通：表单禁用，并提示“当前套餐/租户策略未开通私有化配置”
- 未开通租户同时给出跳转 `/admin/feature-flags` 的引导
- 已开通但无档案：显示空态并支持直接创建

## 错误处理

复用现有业务错误体系：

- 租户不存在：`NOT_FOUND`
- 未开通 `deployment.private_config`：`FEATURE_NOT_ENABLED`
- 参数不合法：`VALIDATION_ERROR`

`FEATURE_NOT_ENABLED.details` 至少应包含：

- `feature_key`
- `tenant_id`
- `source`

## 测试策略

### 后端 API 测试

至少覆盖：

- 管理员可读取交付档案列表
- 管理员可为已开通租户创建交付档案
- 管理员可更新已有交付档案
- 未开通租户保存时返回 `FEATURE_NOT_ENABLED`
- `manager` 可读但不可写
- 保存成功后会写入审计日志

### 后端 service/repository 测试

至少覆盖：

- upsert 创建新记录
- upsert 更新已有记录而不重复插入
- 列表返回时能正确带出套餐和 capability 状态

### 前端验证

至少保证：

- `/admin/settings` 新模块正常渲染
- 未开通租户显示禁用态与引导
- 已开通租户可编辑保存
- `manager` 只读
- `npm run lint`
- `npm run build`

## 风险与约束

- 当前 `admin/settings` 已经偏重，本轮继续加模块要注意信息密度和可读性
- 第一版不处理真实密钥，后续如果要接“机密配置中心”，需要单独设计安全存储
- 交付档案当前偏“运营记录 + 技术元数据”，不是自动化运维系统
- 若后续交付场景继续扩大，再把这一块拆成 `/admin/private-deployment` 也不会推翻当前数据模型

## 验收标准

1. 管理员可以在 `/admin/settings` 为指定租户维护一份技术交付档案。
2. 未开通 `deployment.private_config` 的租户仍然可见，但只能只读查看并看到开通引导。
3. 所有保存动作都会写审计日志。
4. 后端测试、前端 lint、前端 build 全部通过。
5. 这套结构后续可以扩展，但第一版不保存任何敏感凭据。
