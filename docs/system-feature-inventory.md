# 汽车金融不良资产 AI 平台功能清单

更新时间：2026-05-28  
当前分支基线提交：`1729a16 feat: harden AI report draft generation`  
线上生产基线提交：`d55cd5a Implement P1 P2 commercial readiness features`  
本分支领先线上 15 个 commit，AI 指挥中心、运营计划 Agent、任务生成 Agent、报告生成 Agent、AI 治理与复盘等增量尚未上线。

本文用于面向客户演示、内部交付、部署验收和后续研发排期，集中列举当前系统已具备的主要功能。系统定位不是普通估值工具或聊天机器人，而是面向汽车金融公司、融资租赁公司、银行车贷、AMC 和贷后处置服务商的“半自动、可复核、可审计”的不良资产处置工作流平台。

## 1. 基础平台能力

### 1.1 认证与会话

- 邮箱密码登录。
- 用户注册。
- HttpOnly Cookie 登录态。
- JWT access token 与 refresh secret 配置。
- 登录失败限流与账号粒度锁定。
- `/api/auth/me` 返回当前用户、角色和 feature capability snapshot。
- 登出与会话撤销。
- 登录、失败登录、关键操作审计记录。

### 1.2 多租户与权限

- `tenant_id` 业务数据隔离。
- 默认租户与租户成员关系。
- 角色分层：
  - `viewer`
  - `operator`
  - `manager`
  - `admin`
- 侧边栏按角色和功能权益自动过滤。
- viewer 脱敏敏感 evidence 和敏感业务字段。
- operator 可执行基础业务操作。
- manager 可进入策略、审批、任务确认等管理场景。
- admin 可管理用户、AI 审计、成本和系统级配置。

### 1.3 审计与安全

- 通用审计日志。
- AI 决策审计日志。
- 请求上下文包含 request_id、client_ip、user_agent。
- 统一错误响应结构。
- 参数校验错误 JSON-safe 输出。
- 高影响动作保留人工确认边界。
- 禁止 AI 自动批准资产出让、自动接受报价、自动导出敏感数据、自动删除数据或替代法律结论。

## 2. 资产包上传、解析与定价

### 2.1 资产包 Excel 上传

- 资产包 Excel 上传。
- 字段识别与标准字段映射。
- 常见中文数值单位解析：
  - `万`
  - `万元`
  - `w`
  - `万公里`
- 销售侧价格列识别保护，避免将挂牌价、拍卖价、成交价、报价、底价误识别为买断成本。
- 上传后生成资产包和资产明细。
- 上传、解析和计算链路具备租户隔离。

### 2.2 车辆估值

- 车300 VIN 基础估值。
- mock 估值 fallback。
- 高级车况定价触发规则。
- 高成本估值能力守门。
- 预算不足或规则不满足时可降级为基础估值。
- 高级车况定价被拦截时可生成审批上下文。
- 审批通过后支持带审批单重试。
- 估值调用计入 usage event 和成本统计。

### 2.3 资产包定价

- 在库车资产包定价。
- 非在库车资产包定价。
- 买断成本、贷款本金、车辆估值、风险折扣等参数计算。
- 推荐出让价格区间。
- 推荐出让中位价。
- 可交易性评分与等级。
- 风险提示。
- 参数输入校验，例如负数折扣率拦截、非正数 AI 建议价拦截。
- 定价结果持久化到资产包结果。

### 2.4 买方报价反推

- 输入买方报价。
- 计算相对系统建议价的差额。
- 计算报价折扣率。
- 判断报价是否偏离内部建议区间。
- 生成谈判建议。
- 保持“AI 不自动接受买方报价”的安全边界。

### 2.5 资产包报告

- 资产包定价报告。
- 转让合规清单。
- PDF 报告增强。
- 导出水印。
- 导出能力受 `audit.export` 权益控制。

## 3. 单车库存决策沙盘

### 3.1 单车五路径沙盘

- 单车库存资产处置路径模拟。
- 路径净回收比较。
- 法律路径分析。
- 市场流动性风险分析。
- 新能源车辆专项风险分析。
- 策略偏好输入。
- 沙盘结果生成任务入口。

### 3.2 沙盘输出与权限

- 沙盘报告预览。
- 打印/保存 PDF 能力。
- 打印/保存 PDF 受 `audit.export` 权益控制。
- 未开通能力时展示升级提示，不影响报告预览主链路。

## 4. 组合经营驾驶舱

### 4.1 组合总览

- 组合资产概览。
- 资产规模、风险分布和经营指标展示。
- 组合驾驶舱页面入口：`/portfolio/overview`。

### 4.2 分层分析

- 资产分层。
- 分层指标展示。
- 分层风险识别。
- 页面入口：`/portfolio/segmentation`。

### 4.3 路径模拟

- 组合层处置路径模拟。
- 不同处置策略对比。
- 页面入口：`/portfolio/strategies`。

### 4.4 现金回流

- 现金回流预测。
- 未来现金流关注指标。
- 页面入口：`/portfolio/cashflow`。

### 4.5 高阶管理页面

- 高管驾驶页：`/portfolio/executive`。
- 经理作战手册：`/portfolio/manager`。
- 主管控制台：`/portfolio/supervisor`。
- 动作中心：`/portfolio/actions`。
- 高阶页面受角色和 `portfolio.advanced_pages` 能力控制。

### 4.6 产能计划

- 页面入口：`/portfolio/capacity-plan`。
- 基于真实组合快照和分层指标生成产能计划。
- 支持产能设置持久化。
- 输出当前月执行计划。
- 输出分层任务建议。
- 当无真实组合数据时返回明确空状态，不静默回退 mock。
- `capacity-plan` API 不再静默回退 mock。

## 5. 任务闭环

### 5.1 任务中心

- 页面入口：`/tasks`。
- 基于 `work_orders` 的任务列表。
- 任务状态、优先级、负责人、创建时间展示。
- 真实租户成员选择。
- 任务分配校验租户成员，防止跨租户派单。
- 前端不再硬编码 `owner_user_id=1`。

### 5.2 任务详情

- 页面入口：`/tasks/[id]`。
- 任务基本信息展示。
- 任务关联对象展示。
- 任务 evidence 展示。
- 任务状态流转。
- 完成任务时写入 `completed_at`。
- 完成后详情页稳定展示完成时间。

### 5.3 证据上传

- PDF 证据上传。
- 图片证据上传。
- 上传后刷新详情页仍可见。
- 非法文件类型拒绝。
- 超过大小限制的文件拒绝。
- 证据上传闭环可用于客户演示。

### 5.4 AI 任务草稿确认链路

- `task_generation_agent` 可生成 `agent_tasks` 任务草稿。
- 任务草稿状态为 `draft`。
- 草稿进入“待确认队列”。
- manager/admin 可确认或驳回。
- high 优先级任务需 admin 确认。
- 确认后创建正式 `work_orders`，状态为 `pending`。
- 确认和驳回写入 `decision_audit_logs`。
- Agent 不自动派发、不自动审批、不自动导出、不自动接受报价、不提供最终法律结论。

## 6. AI 指挥中心

页面入口：`/ai-command-center`

### 6.1 页面信息架构

- 客户视图。
- 内部工作台。
- 顶部 AI 今日判断。
- 当前整体风险等级。
- AI 今日一句话判断。
- 关键发现。
- 主要建议动作。
- 4 个核心业务指标：
  - 待人工确认
  - 高风险资产
  - 本周建议处置
  - 成本/额度预警
- AI 建议你优先处理。
- 需要你确认。
- 快捷分析入口：
  - 分析资产包
  - 判断买方报价
  - 生成本周作战计划
  - 生成报告草稿
- 本周作战计划卡片。
- 任务草稿区域。
- 报告草稿区域。
- 最近 AI 分析记录。
- Agent 工作台。
- 错误状态、空状态和 loading 状态。

### 6.2 Agent Orchestrator

- 前端不直接调用 LLM。
- 所有 Agent 通过后端 Orchestrator 发起。
- 每次 Agent run 写入 `agent_runs`。
- 输出建议写入 `agent_recommendations`。
- 任务草稿写入 `agent_tasks`。
- 人工确认、驳回、规则调整和 Agent 完成写入 `decision_audit_logs`。
- 每次运行记录：
  - `tenant_id`
  - `agent_type`
  - `input_json`
  - `output_json`
  - `status`
  - `created_by`
  - `started_at`
  - `finished_at`
  - `requires_human_review`

### 6.3 统一 Agent 输出结构

每个 Agent 输出包含：

- `summary`
- `key_findings`
- `recommended_actions`
- `risk_warnings`
- `confidence_score`
- `evidence`
- `requires_human_review`
- `agent_status`

### 6.4 当前 8 个 Agent

| Agent | 中文名称 | 当前状态 | 最小角色 | 当前能力 |
|---|---|---:|---:|---|
| `asset_package_diagnosis_agent` | 资产包解读 Agent | `rules_based` | operator | 解读资产包、识别资料缺口和基础风险 |
| `valuation_analysis_agent` | 估值分析 Agent | `rules_based` | operator | 分析估值覆盖率、抵押物价值覆盖和估值风险 |
| `pricing_strategy_agent` | 定价策略 Agent | `rules_based` | manager | 基于资产包定价结果生成价格策略草案 |
| `buyer_offer_analysis_agent` | 买方报价反推 Agent | `rules_based` | operator | 反推买方报价偏离、折扣和谈判建议 |
| `operation_planning_agent` | 运营计划 Agent | `rules_based` | manager | 生成本周/月处置作战计划和分组资产池 |
| `task_generation_agent` | 任务生成 Agent | `rules_based` | manager | 生成待人工确认的任务草稿 |
| `report_generation_agent` | 报告生成 Agent | `rules_based` | manager | 生成报告草稿，不自动下载或外发 |
| `cost_control_agent` | 成本控制 Agent | `rules_based` | admin | 估算成本、额度剩余、预算预警和审批建议 |

### 6.5 运营计划 Agent

- 生成本周/月处置作战计划草稿。
- 输出本周作战重点。
- 输出高优先级资产池。
- 输出快速竞拍池。
- 输出法务推进池。
- 输出补资料/估值复核池。
- 输出债权转让池。
- 输出暂缓观察池。
- 输出报价复核池。
- 输出产能/预算约束。
- 输出 `missing_data`、`data_quality_notes`、`limited_data_reason`。
- 保持 `requires_human_review=true`。
- 不自动派发任务、不审批、不导出、不接受报价。
- 如需落地，只引导 `task_generation_agent` 生成 draft 任务草稿。

### 6.6 任务生成 Agent

- 基于 Agent recommendation、资产包、估值、定价、买方报价和产能上下文生成任务草稿。
- 任务类型：
  - `data_completion`
  - `valuation_review`
  - `auction_preparation`
  - `legal_material_review`
  - `collection_follow_up`
  - `buyer_offer_review`
  - `report_review`
  - `cost_approval`
- 任务草稿字段：
  - title
  - description
  - task_type
  - priority
  - suggested_owner_role
  - deadline_suggestion
  - related_object_type
  - related_object_id
  - required_documents
  - expected_result
  - evidence
  - confidence_score
  - requires_human_review
  - status=draft

### 6.7 报告生成 Agent

- 支持报告类型：
  - `executive_summary`
  - `asset_package_brief`
  - `buyer_offer_memo`
  - `weekly_operation_report`
- 输出报告草稿：
  - `status=draft`
  - `distribution=draft_only`
  - `review_checklist`
  - `missing_data`
  - `data_quality_notes`
  - `source_context`
  - `confidence_score`
  - `allowed_actions`
  - `forbidden_actions`
- 前端展示：
  - 草稿状态
  - 置信度
  - 复核清单
  - 缺失数据
  - 数据说明
  - 来源上下文
- 明确禁止自动下载、自动外发、自动审批出让、接受报价、替代法律结论。

### 6.8 成本控制 Agent

- 输入预计 VIN 调用量。
- 输入高级车况调用量。
- 输入 AI 报告数量。
- 输入单次预算。
- 读取当前租户套餐额度和月度使用量。
- 输出：
  - `estimated_cost`
  - `requested_usage`
  - `quota_remaining`
  - `budget_warning`
  - `approval_required`
  - `downgrade_suggestion`
  - `recommended_action`
- 不会自动批准高成本估值或消耗额度。

### 6.9 AI 审计日志

页面入口：`/admin/ai-audit-logs`

- admin-only。
- 查看 Agent run 审计记录。
- 查看 decision_type。
- 查看 action。
- 查看 actor。
- 查看 agent_run_id。
- 查看 tenant_id。
- 查看是否需要人工复核。
- 支持客户展示“谁发起了分析、用了什么数据、输出了什么建议、是否需要人工复核”。

### 6.10 AI 治理与复盘

- Agent 输出需人工复核提示。
- Agent 状态标签：
  - `rules_based`
  - `mock`
  - `fallback`
  - `llm_assisted`
- confidence_score 展示。
- evidence 展示和 viewer 脱敏。
- 最近 Agent run 列表。
- Agent 规则阈值配置。
- 规则 profile、场景、版本记录。
- 人工复盘记录。
- 复盘洞察。
- 复盘结果不自动反哺模型权重，保持半自动可复核边界。

## 7. 商业化控制中台

### 7.1 套餐与订阅

页面入口：

- `/admin/settings`
- `/admin/billing`

能力：

- 套餐管理。
- 订阅管理。
- 默认套餐种子：
  - `trial_poc`
  - `standard`
  - `pro_manager`
  - `enterprise_private`
- 席位限制 `seat_limit`。
- 套餐能力开关。
- 租户订阅更新。

### 7.2 功能开关

页面入口：`/admin/feature-flags`

- 统一功能目录。
- 套餐默认能力配置。
- 租户级 override。
- 三态能力：
  - 继承套餐
  - 强制开启
  - 强制关闭
- 登录态 capability snapshot。
- 侧边栏和页面级 gating。

### 7.3 成本中心

页面入口：`/admin/cost-center`

- 成本总览。
- 租户成本列表。
- usage event 查询。
- cost snapshot。
- 成本导出。
- 成本中心导出受 `audit.export` 权益控制。
- 成本中心页面受 `dashboard.advanced` 权益控制。

### 7.4 模型路由

页面入口：`/admin/model-routing`

- LLM 模型路由规则。
- preferred model。
- fallback model。
- 按 task_type 配置。
- 预算不足时 fallback。
- API 受 `routing.model_control` 权益控制。

### 7.5 估值规则

页面入口：`/admin/valuation-rules`

- 车300 高级车况定价触发规则。
- 高成本估值审批阈值。
- 规则更新审计。

### 7.6 审批请求

页面入口：`/admin/approval-requests`

- 审批请求列表。
- 业务页发起高成本能力审批。
- 审批通过。
- 审批驳回。
- 审批通过后带审批单重试业务动作。
- 审批单消费记录。

### 7.7 价值中心与价值看板

页面入口：

- `/admin/value-center`
- `/admin/value-dashboard`

能力：

- 租户价值看板。
- 套餐/租户权益下的价值指标展示。
- 适合销售演示和运营驾驶舱一期。
- 受 `tenant.value_dashboard` 权益控制。

### 7.8 用户管理

页面入口：`/admin/users`

- 用户列表。
- 角色展示。
- 登录时间展示。
- 租户成员管理能力基础。
- 席位限制校验。

### 7.9 通用审计日志

页面入口：`/admin/audit-logs`

- 登录审计。
- 操作审计。
- 导出审计。
- 审批审计。
- 配置变更审计。

## 8. 运维与部署能力

### 8.1 技术栈

- 后端：FastAPI。
- ORM：SQLAlchemy。
- 迁移：Alembic。
- 前端：Next.js 16 + React 19。
- 数据库：PostgreSQL-only。
- 对象存储：S3/OSS 兼容抽象，本地可用 MinIO。
- 部署：Docker Compose。

### 8.2 配置与环境变量

- 后端配置入口：`backend/config.py`。
- 后端读取仓库根目录 `.env`。
- 前端读取 `frontend/.env` 和 `frontend/.env.local`。
- 前端不读取仓库根目录 `.env`。
- 生产环境变量矩阵见 `docs/ops/env-matrix.md`。

### 8.3 数据库迁移

- PostgreSQL 运行时策略。
- Alembic 管理 schema。
- 应用启动不再自动创建旧 SQLite 表。
- `alembic upgrade head` 是部署前后必查项。

### 8.4 对象存储与上传

- 上传文件走存储抽象。
- 支持本地/对象存储后端切换。
- 避免基于用户文件名的本地路径拼接。

### 8.5 部署脚本与冒烟

- `deploy/docker-compose.yml`。
- 后端 Dockerfile 支持镜像源配置。
- 前端 Dockerfile 支持 npm registry 配置。
- `deploy/smoke-check.sh`：
  - compose 服务状态
  - backend import
  - Alembic current=head
  - `/api/health`
  - 前端首页
- 生产域名：`https://zhefenglin.com`。

### 8.6 备份与回滚

- 部署前配置备份。
- 部署前数据库备份。
- postgres-backup 容器自动备份。
- 已验证数据库备份恢复链路。
- 回退可使用配置备份、数据库备份和上一提交。

### 8.7 可观测性

- `/api/health` 健康检查。
- `/metrics` 指标接口。
- 请求上下文中间件。
- metrics 中间件。
- 结构化错误响应。
- Docker 容器健康检查。

## 9. 前端页面清单

### 9.1 公开与认证页面

- `/login`：登录。
- `/register`：注册。
- `/legal/terms`：服务条款。
- `/legal/notice`：法律声明。

### 9.2 资产处置页面

- `/`：首页。
- `/asset-pricing`：资产包定价。
- `/inventory-sandbox`：库存决策沙盘。

### 9.3 经营驾驶舱页面

- `/portfolio/overview`：组合总览。
- `/portfolio/segmentation`：分层分析。
- `/portfolio/strategies`：路径模拟。
- `/portfolio/cashflow`：现金回流。
- `/portfolio/executive`：高管驾驶页。
- `/portfolio/manager`：经理作战手册。
- `/portfolio/supervisor`：主管控制台。
- `/portfolio/actions`：动作中心。
- `/portfolio/capacity-plan`：产能计划。

### 9.4 任务页面

- `/tasks`：任务中心。
- `/tasks/[id]`：任务详情。

### 9.5 AI 页面

- `/ai-command-center`：AI 指挥中心。
- `/admin/ai-audit-logs`：AI 审计日志。

### 9.6 管理后台页面

- `/admin/settings`：系统设置。
- `/admin/billing`：套餐计费。
- `/admin/feature-flags`：功能开关。
- `/admin/cost-center`：成本中心。
- `/admin/model-routing`：模型路由。
- `/admin/valuation-rules`：估值规则。
- `/admin/approval-requests`：审批请求。
- `/admin/value-center`：价值中心。
- `/admin/value-dashboard`：价值看板。
- `/admin/users`：用户管理。
- `/admin/audit-logs`：通用审计日志。

## 10. 后端 API 模块清单

- `/api/health`：健康检查。
- `/api/auth/*`：登录、注册、登出、当前用户、访问申请。
- `/api/car-valuation/*`：车辆估值。
- `/api/asset-packages/*`：资产包上传、解析、定价、报告。
- `/api/inventory-sandbox/*`：库存沙盘。
- `/api/portfolio/*`：组合驾驶舱、分层、现金流、产能计划。
- `/api/tasks/*`：任务中心、任务详情、分配、完成、证据上传。
- `/api/jobs/*`：后台任务查询。
- `/metrics`：运维指标。
- `/api/ai-command-center/*`：AI 指挥中心、Agent run、任务草稿、复盘、规则配置、AI 审计。
- `/api/admin/settings/*`：套餐、订阅、系统商业化设置。
- `/api/admin/cost-center/*`：成本中心。
- `/api/admin/feature-flags/*`：功能开关。
- `/api/admin/model-routing/*`：模型路由。
- `/api/admin/valuation-rules/*`：估值触发规则。
- `/api/admin/approval-requests/*`：审批请求。
- `/api/admin/audit-logs/*`：通用审计。
- `/api/admin/*`：用户等管理能力。

## 11. 当前明确边界

- 系统已具备可演示、可审计、可部署的半自动 Agent 工作台能力。
- 当前 Agent 仍以规则化输出为主，不追求全自动自主规划。
- 关键数值由规则、公式和服务层计算，LLM 不直接生成最终价格、折扣、回收率、法律结论或审批结论。
- report draft 仍是草稿，不是正式报告。
- task draft 仍需人工确认后才进入正式 `work_orders`。
- operation plan 仍是作战计划草稿，不自动派发任务。
- cost control 只做预估和审批建议，不自动消耗额度或批准高成本估值。
- 所有高影响动作必须保留 `requires_human_review=true`。

## 12. 下一阶段建议

- 推进 `cost_control_agent` 规则化增强和线上登录态冒烟。
- 建立独立报告草稿生命周期，而不仅保存在 Agent run payload 中。
- 推进 Tool Registry 基础版，但工具调用仍需权限和审计边界。
- 推进 AgentContextBuilder，统一资产包、估值、定价、组合、任务、成本、审计、复盘上下文。
- 完善复盘闭环，将 adopted、rejected、overridden 和 variance_reason 用于规则治理建议，但不自动改模型或规则。
- 持续准备脱敏演示数据集，避免客户演示时临时生成不可控生产数据。
