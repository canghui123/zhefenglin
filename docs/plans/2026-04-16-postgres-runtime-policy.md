# PostgreSQL Runtime Policy Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 收口运行时数据库策略到 PostgreSQL，移除失真的 SQLite 本地运行入口，并同步统一系统名称文案。

**Architecture:** 后端运行时只认 `DATABASE_URL`，数据库 schema 统一由 Alembic 管理，不再在应用启动时根据 `DATABASE_PATH` 动态创建旧版 SQLite 表。测试继续允许使用临时 SQLite，但仅通过 SQLAlchemy metadata 建表，不再依赖 `backend/database.py`。前端和报告模板的品牌文案统一替换为“汽车金融资产处置经营决策系统”。

**Tech Stack:** FastAPI, SQLAlchemy, Alembic, pytest, Next.js 16, React 19.

---

### Task 1: 锁定运行时数据库策略

**Files:**
- Create: `backend/tests/api/test_runtime_database_policy.py`
- Modify: `backend/main.py`
- Modify: `backend/config.py`
- Modify: `backend/database.py`

**Step 1: 写失败的回归测试**

```python
def test_health_startup_does_not_bootstrap_legacy_sqlite_from_database_path():
    ...
```

**Step 2: 跑测试确认当前会误触发旧 SQLite 引导**

Run: `cd backend && python3 -m pytest -q tests/api/test_runtime_database_policy.py`
Expected: FAIL，因为启动会根据 `DATABASE_PATH` 触发旧 `init_db()`

**Step 3: 最小实现**

- 移除 `main.py` 中基于 `DATABASE_PATH` / sqlite URL 的旧启动分支
- 在 `config.py` 中把 `database_path` 标记为历史兼容，不再作为运行时入口
- 更新 `database.py` 头注释，明确其仅保留给历史迁移/手工排障，不允许新增依赖

**Step 4: 重跑测试**

Run: `cd backend && python3 -m pytest -q tests/api/test_runtime_database_policy.py`
Expected: PASS

### Task 2: 更新配置与文档契约

**Files:**
- Modify: `docs/ops/env-matrix.md`
- Modify: `backend/.env.example`
- Modify: `README.md`
- Modify: `AGENTS.md`
- Modify: `docs/HANDOFF.md`

**Step 1: 文档收口**

- 删除或降级 `DATABASE_PATH` 的本地开发承诺
- 明确“运行时 PostgreSQL-only，schema 由 Alembic 管理”
- 说明 `backend/data/npl.db` 为历史遗留文件，不代表当前运行时基线

**Step 2: 验证**

Run: `cd backend && python3 -m pytest -q tests/api/test_runtime_database_policy.py`
Expected: PASS

### Task 3: 统一系统名称文案

**Files:**
- Modify: `frontend/src/app/layout.tsx`
- Modify: `frontend/src/app/page.tsx`
- Modify: `backend/main.py`
- Modify: `backend/templates/vehicle_report.html`

**Step 1: 替换对外展示文案**

统一替换为：

```text
汽车金融资产处置经营决策系统
```

**Step 2: 验证**

Run: `cd frontend && npm run lint && npm run build`
Expected: PASS

### Task 4: 全量回归

**Step 1: 后端**

Run: `cd backend && python3 -m pytest -q`
Expected: PASS

Run: `cd backend && python3 -m compileall .`
Expected: PASS

**Step 2: 前端**

Run: `cd frontend && npm run lint`
Expected: PASS

Run: `cd frontend && npm run build`
Expected: PASS

**Step 3: Commit**

```bash
git add backend/main.py backend/config.py backend/database.py \
  backend/tests/api/test_runtime_database_policy.py \
  docs/ops/env-matrix.md backend/.env.example README.md AGENTS.md docs/HANDOFF.md \
  frontend/src/app/layout.tsx frontend/src/app/page.tsx backend/templates/vehicle_report.html \
  docs/plans/2026-04-16-postgres-runtime-policy.md
git commit -m "fix: enforce postgres runtime policy"
```
