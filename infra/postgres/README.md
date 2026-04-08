# 本地 PostgreSQL 启动指南

## 方式 A: Docker Compose（推荐生产/CI）

```bash
cd infra/postgres
docker compose up -d
docker compose ps     # 等到 healthy
```

连接串:
```
postgresql+psycopg://app:app@localhost:5432/auto_finance
```

## 方式 B: Postgres.app（macOS 本地开发）

如果不想装 Docker, 可使用已安装的 Postgres.app:

```bash
# 启动数据集群
~/Applications/Postgres.app/Contents/Versions/18/bin/pg_ctl \
    start -D ~/Library/Application\ Support/Postgres/afterloan-18/ \
    -l ~/Library/Application\ Support/Postgres/afterloan-18/pg.log

# 创建用户和库（首次执行）
~/Applications/Postgres.app/Contents/Versions/18/bin/psql -d postgres -c "CREATE USER app WITH PASSWORD 'app';"
~/Applications/Postgres.app/Contents/Versions/18/bin/psql -d postgres -c "CREATE DATABASE auto_finance OWNER app;"
```

## 应用迁移

```bash
cd backend
alembic upgrade head
```
