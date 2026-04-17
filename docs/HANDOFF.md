# Project Handoff

最后更新：2026-04-16

## 当前状态

这个仓库已经不是“只够演示”的原型状态，当前至少具备：

- 后端 pytest 基线
- 前端 lint/build 基线
- PostgreSQL + Alembic 迁移体系
- 认证、角色与租户相关基础能力
- 资产包上传、解析、估值、定价与报告相关业务链路
- 前后端环境变量配置入口
- Docker 部署说明与基础运维文档

如果后续改动由 Codex 接手，建议先把这里当作“会话恢复点”。

推荐同时阅读：

- [docs/CODEX_PLAYBOOK.md](/Users/canghui/Desktop/汽车金融ai平台/docs/CODEX_PLAYBOOK.md)
- [docs/plans/2026-04-17-approval-closure-design.md](/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-17-approval-closure-design.md)

## 本轮已确认的修复

本次交接前，已经补上的问题包括：

- 资产包计算接口现在会拒绝负数折扣率
- `ai_buyout_overrides` 现在会拒绝非正数价格
- FastAPI 的 422 响应做了 JSON-safe 处理，不会因为 `ValueError` 再次抛 500
- Excel 数值解析现在支持常见中文业务写法，例如 `12.3万`、`12.3万元`、`8.6万公里`、`1.2w`
- Excel 解析不再把 `挂牌价`、`拍卖价`、`成交价`、`报价`、`底价` 这类销售侧价格列误识别成买断成本
- 资产定价前端会在上传、切换策略、切换车况时清理 AI 建议状态，避免沿用旧包或旧车况的建议
- 后端 Dockerfile 不再强依赖单一镜像源，改为通过可选构建参数配置
- 应用运行时数据库策略已明确收口为 PostgreSQL-only，不再支持基于 `DATABASE_PATH` 的 SQLite 启动路径
- 高级车况定价现在支持业务页内发起审批、审批通过后带审批单重试，并记录审批单消费状态

## 本轮新增回归测试

- [backend/tests/api/test_asset_package_input_validation.py](/Users/canghui/Desktop/汽车金融ai平台/backend/tests/api/test_asset_package_input_validation.py)
- [backend/tests/services/test_excel_parser.py](/Users/canghui/Desktop/汽车金融ai平台/backend/tests/services/test_excel_parser.py)

这些测试主要覆盖：

- 负数折扣率拦截
- 非正数 AI 建议价拦截
- 常见中文单位数值解析
- 销售侧价格列不应影响买断策略识别

## 建议的会话恢复步骤

新的 Codex 会话进入后，建议按这个顺序执行：

1. 阅读 [README.md](/Users/canghui/Desktop/汽车金融ai平台/README.md)
2. 阅读 [AGENTS.md](/Users/canghui/Desktop/汽车金融ai平台/AGENTS.md)
3. 阅读 [docs/ops/env-matrix.md](/Users/canghui/Desktop/汽车金融ai平台/docs/ops/env-matrix.md)
4. 如果要碰前端，再阅读 [frontend/AGENTS.md](/Users/canghui/Desktop/汽车金融ai平台/frontend/AGENTS.md)
5. 阅读 [docs/CODEX_PLAYBOOK.md](/Users/canghui/Desktop/汽车金融ai平台/docs/CODEX_PLAYBOOK.md)
6. 运行基线验证命令，确认当前工作区是否仍然健康

推荐验证命令：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 -m pytest -q
python3 -m compileall .

cd /Users/canghui/Desktop/汽车金融ai平台/frontend
npm run lint
npm run build
```

数据库注意事项：

- `backend/data/npl.db` 是历史遗留文件，缺少认证、租户、审计、任务等后续表
- 运行时 schema 以 Alembic 迁移结果为准，不要把旧 SQLite 文件当成真实基线

## 当前仍值得继续完善的点

下面这些不一定是 blocker，但很适合作为下一轮 Codex 任务：

1. 消除 Pydantic v2 的 `class-based Config` 弃用告警，迁移到 `ConfigDict`
2. 为 `pytest-asyncio` 明确 `asyncio_default_fixture_loop_scope`，避免未来版本行为变化
3. 收口 Alembic 与 ORM metadata 的唯一约束漂移，避免 autogenerate 持续报 diff
4. 给前端补自动化测试，至少覆盖资产定价页的关键状态切换与 API 交互
5. 继续按照 [docs/plans/2026-04-03-commercial-readiness.md](/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-03-commercial-readiness.md) 推进商用化收口

## 对 Codex 最友好的提示方式

如果你以后不用 Claude code，而要让 Codex 直接接这个项目，最省心的开场方式是：

```text
先阅读 README.md、AGENTS.md、docs/HANDOFF.md、docs/ops/env-matrix.md 和 frontend/AGENTS.md（如果会改前端），
然后运行 backend 的 pytest/compileall 和 frontend 的 lint/build 建立基线，
再根据当前任务只改相关文件，并在结束前说明验证结果、剩余风险和未覆盖项。
```

如果是继续商用化建设，可以再补一句：

```text
以 docs/plans/2026-04-03-commercial-readiness.md 为主计划，优先完成依赖顺序靠前且能独立验证的任务。
```
