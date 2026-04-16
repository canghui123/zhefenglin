# Agent Guide

本文件给 Codex、Claude Code 等代码代理使用。目标不是解释业务背景，而是让代理尽快进入正确的工作流。

## 进入仓库后的第一步

按以下顺序读取：

1. [README.md](/Users/canghui/Desktop/汽车金融ai平台/README.md)
2. [docs/HANDOFF.md](/Users/canghui/Desktop/汽车金融ai平台/docs/HANDOFF.md)
3. [docs/ops/env-matrix.md](/Users/canghui/Desktop/汽车金融ai平台/docs/ops/env-matrix.md)
4. 如果要改前端，再读 [frontend/AGENTS.md](/Users/canghui/Desktop/汽车金融ai平台/frontend/AGENTS.md)

## 必跑验证

任何声称“已修复”或“可交付”的结论前，至少跑：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 -m pytest -q
python3 -m compileall .

cd /Users/canghui/Desktop/汽车金融ai平台/frontend
npm run lint
npm run build
```

补充说明：

- 这个环境里不要假设裸 `pytest` 命令存在，请使用 `python3 -m pytest -q`
- 前端项目使用 Next.js 16，触达前端逻辑前先读 `frontend/AGENTS.md`

## 环境与配置边界

- 后端配置入口是 [backend/config.py](/Users/canghui/Desktop/汽车金融ai平台/backend/config.py)
- 后端读取仓库根目录 `.env`
- 前端读取 `frontend/.env` 和 `frontend/.env.local`
- 前端不会自动读取仓库根目录 `.env`
- 生产环境变量说明以 [docs/ops/env-matrix.md](/Users/canghui/Desktop/汽车金融ai平台/docs/ops/env-matrix.md) 为准

## 修改代码时的项目约束

- 涉及数据库时，优先走 SQLAlchemy 模型、仓储层和 Alembic，不要回退到散落的原始 SQL
- 涉及上传、报告、文件落盘时，优先走存储抽象，不要重新引入基于用户文件名的本地路径拼接
- 涉及租户数据时，保持 `tenant_id` 过滤和权限边界，避免跨租户读写
- 涉及资产包定价时，重点关注：
  - [backend/api/asset_package.py](/Users/canghui/Desktop/汽车金融ai平台/backend/api/asset_package.py)
  - [backend/models/asset.py](/Users/canghui/Desktop/汽车金融ai平台/backend/models/asset.py)
  - [backend/services/excel_parser.py](/Users/canghui/Desktop/汽车金融ai平台/backend/services/excel_parser.py)
  - [backend/services/pricing_engine.py](/Users/canghui/Desktop/汽车金融ai平台/backend/services/pricing_engine.py)
- 涉及资产定价前端时，重点关注：
  - [frontend/src/app/asset-pricing/page.tsx](/Users/canghui/Desktop/汽车金融ai平台/frontend/src/app/asset-pricing/page.tsx)
  - [frontend/src/lib/api.ts](/Users/canghui/Desktop/汽车金融ai平台/frontend/src/lib/api.ts)

## 推荐工作流

1. 先 `git status --short`，确认工作区是否已有未提交改动
2. 再读目标文件和相关测试，不要直接改
3. 先写或补回归测试，再做实现
4. 修改完成后跑最小定向验证
5. 最后跑整体验证，再总结风险与未覆盖项

## 当前阶段建议

如果目标是继续把项目推进到更适合商用的状态，请以 [docs/plans/2026-04-03-commercial-readiness.md](/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-03-commercial-readiness.md) 作为主计划，并以 [docs/HANDOFF.md](/Users/canghui/Desktop/汽车金融ai平台/docs/HANDOFF.md) 作为当前落地上下文。
