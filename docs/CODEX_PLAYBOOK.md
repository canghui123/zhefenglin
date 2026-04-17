# Codex 接手 Playbook

最后更新：2026-04-17

## 目标

这份文档是给后续 Codex 会话的固定接手入口，目标是减少重复解释背景、降低上下文丢失风险，并保持提交历史清晰可追溯。

## 首次进入仓库时必须做的事

按下面顺序建立上下文：

1. 阅读 [README.md](/Users/canghui/Desktop/汽车金融ai平台/README.md)
2. 阅读 [AGENTS.md](/Users/canghui/Desktop/汽车金融ai平台/AGENTS.md)
3. 阅读 [docs/HANDOFF.md](/Users/canghui/Desktop/汽车金融ai平台/docs/HANDOFF.md)
4. 阅读 [docs/ops/env-matrix.md](/Users/canghui/Desktop/汽车金融ai平台/docs/ops/env-matrix.md)
5. 如果涉及商业化控制中台，阅读 [docs/commercial-controls.md](/Users/canghui/Desktop/汽车金融ai平台/docs/commercial-controls.md)
6. 如果会修改前端，再阅读 [frontend/AGENTS.md](/Users/canghui/Desktop/汽车金融ai平台/frontend/AGENTS.md)

## 进入任何新任务前的基线命令

后端：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 -m pytest -q
python3 -m compileall .
```

前端：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/frontend
npm run lint
npm run build
```

如果不是修复构建或测试问题，不要跳过这些基线验证。

## 当前项目关键事实

- 运行时数据库策略是 PostgreSQL-only
- 数据库 schema 统一由 Alembic 管理
- `backend/data/npl.db` 只是历史遗留文件，不是当前运行时基线
- 商业化控制中台第一阶段已经落地：套餐、订阅、额度守门、模型路由、估值规则、审批请求、成本中心、价值看板
- 当前最适合继续迭代的是“把中台控制能力和业务页面真正闭环”，而不是继续堆新后台页面

## 推荐开发节奏

每一轮任务都按下面顺序推进：

1. 先扫描相关文件，确认影响范围
2. 如果是新功能或行为改动，先写设计和实施计划
3. 优先补或扩展测试
4. 做最小实现，不额外引入无关重构
5. 跑本轮相关验证
6. 只提交当前主题相关的改动
7. 在结束时说明验证结果、剩余风险和未覆盖项

## 提交粒度规范

强烈建议一轮只做一个主题，并拆成边界明确的 commit。推荐粒度：

- 数据库 / 迁移
- 后端业务逻辑
- 前端交互
- 文档 / 交接

不要把以下内容混进同一笔提交：

- 老遗留改动和新功能
- 运行策略变更和品牌文案改动
- 页面展示调整和底层权限/数据库改动

## 商业化控制中台的继续推进顺序

推荐顺序：

1. 审批闭环
2. 配置治理与审计增强
3. 套餐执行力与 feature entitlement 强校验
4. 前端自动化测试
5. 运维与告警增强

## 做商业化相关改动时要优先复用的能力

- RBAC：`dependencies/auth.py`
- tenant 隔离：`services/tenant_context.py`
- 审计日志：`services/audit_service.py`
- usage/cost 沉淀：`services/cost_metering_service.py`
- 配额与预算校验：`services/quota_service.py`
- 模型路由：`services/model_routing_service.py`
- 高成本守门：`services/commercial_policy_service.py`

## 本项目里最容易被误伤的地方

- `backend/main.py` 同时容易承载品牌文案、路由注册和运行时策略，不要混改
- `frontend/src/lib/api.ts` 是前端统一 API 契约层，改动要和后端返回结构同步
- `backend/services/che300_client.py` 同时承担估值、守门和 usage_event 沉淀，任何改动都要补测试
- 资产包页已有较多状态，新增审批交互时要避免把旧错误提示、AI 建议和新审批状态混成一团

## 建议的 Codex 开场提示词

如果以后你直接开一个新 Codex 会话，最省心的开场方式是：

```text
先阅读 README.md、AGENTS.md、docs/HANDOFF.md、docs/ops/env-matrix.md、docs/CODEX_PLAYBOOK.md，
如果涉及商业化控制中台，再阅读 docs/commercial-controls.md 和最新相关 plan。
然后运行 backend 的 pytest/compileall 和 frontend 的 lint/build 建立基线，
只修改当前任务相关文件，结束前汇报验证结果、剩余风险和未覆盖项，并保持单主题提交。
```

## 当前推荐恢复点

如果是继续本轮工作，优先从下面文档恢复：

- [docs/plans/2026-04-17-approval-closure-design.md](/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-17-approval-closure-design.md)
- [docs/plans/2026-04-17-approval-closure-implementation.md](/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-17-approval-closure-implementation.md)
