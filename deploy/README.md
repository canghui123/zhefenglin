# 汽车金融 AI 平台 — 部署指南

> 📋 **上线前请先阅读** [COMPLIANCE.md](./COMPLIANCE.md) — 含等保二级控制清单、
> 备份/容灾策略、ICP 备案、DPA 模板要点、应急预案 Runbook。

## 服务器要求

- **系统**: Ubuntu 22.04 / CentOS 8+ / Debian 12+
- **配置**: 4 核 8G 内存, 50G+ 磁盘
- **网络**: 开放 80 和 443 端口
- **域名**: 已完成 ICP 备案并解析到服务器 IP

## 部署步骤

### 第一步：服务器装 Docker

```bash
# Ubuntu / Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# 退出重新登录使 docker 组生效
```

### 第二步：上传代码到服务器

```bash
# 方式一：git clone（推荐）
git clone <你的仓库地址> /opt/auto-finance
cd /opt/auto-finance/deploy

# 方式二：本地打包上传
# 本地执行:
tar czf auto-finance.tar.gz --exclude='node_modules' --exclude='.next' --exclude='__pycache__' .
scp auto-finance.tar.gz root@你的服务器IP:/opt/
# 服务器上执行:
cd /opt && tar xzf auto-finance.tar.gz -C auto-finance && cd auto-finance/deploy
```

### 第三步：配置环境变量

```bash
cd /opt/auto-finance/deploy
cp .env.production .env
nano .env
```

**必须修改的项：**

| 变量 | 说明 | 生成方式 |
|------|------|----------|
| `DOMAIN` | 你的域名（不带 https） | 直接填写 |
| `DB_PASSWORD` | 数据库密码 | `openssl rand -base64 24` |
| `JWT_SECRET` | JWT 签名密钥 | `openssl rand -hex 48` |
| `JWT_REFRESH_SECRET` | JWT 刷新密钥 | `openssl rand -hex 48` |
| `S3_ACCESS_KEY` | MinIO 用户名 | 自定义，至少 8 位 |
| `S3_SECRET_KEY` | MinIO 密码 | `openssl rand -base64 36` |
| `CHE300_ACCESS_KEY` | 车300 API Key | 从车300后台获取 |
| `CHE300_ACCESS_SECRET` | 车300 API Secret | 从车300后台获取 |

说明：

- 系统会把 `DOMAIN` 作为唯一对外主域名，例如 `zhefenglin.com`
- 部署脚本会自动为 `DOMAIN` 和 `www.DOMAIN` 同时申请证书
- `https://www.DOMAIN` 会统一 301 跳转到 `https://DOMAIN`
- 中国大陆 ECS 可保留 `BACKEND_APT_MIRROR_HOST=mirrors.aliyun.com`、`BACKEND_PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/`、`BACKEND_PIP_TRUSTED_HOST=mirrors.aliyun.com` 和 `FRONTEND_NPM_REGISTRY=https://registry.npmmirror.com`；海外 / CI 环境可清空 apt/npm 镜像，并把 PyPI 改回官方源
- `DEFAULT_REGISTRATION_TENANT_CODE` / `DEFAULT_REGISTRATION_TENANT_NAME` 控制公开注册用户进入哪个默认租户；内测期建议继续保持 `ALLOW_PUBLIC_REGISTRATION=false`
- 后端镜像已把 `boto3` 作为正式依赖，用于 `STORAGE_BACKEND=s3` 的 MinIO / S3 存储

### 第四步：确认域名解析

确保域名已解析到服务器 IP：

```bash
ping your-domain.com
# 应该返回你服务器的 IP 地址
ping www.your-domain.com
# 应该同样返回你服务器的 IP 地址
```

### 第五步：一键部署

```bash
bash setup.sh
```

脚本会自动完成：
1. 检查 Docker 环境
2. 启动 PostgreSQL + MinIO
3. 构建后端/前端镜像
4. 运行数据库迁移（alembic upgrade head）
5. 创建 MinIO 存储桶
6. 申请 Let's Encrypt SSL 证书
7. 启动 Nginx 反向代理
8. 创建默认管理员账号

### 第六步：验证

```bash
# 一键 smoke check：容器状态、后端 import、Alembic head、健康检查、前端页面
bash smoke-check.sh

# 检查所有服务状态
docker compose ps

# 应该看到 7 个服务全部 running：
# af_postgres, af_minio, af_backend, af_frontend, af_nginx, af_certbot, af_postgres_backup
```

打开浏览器访问 `https://你的域名`，用管理员账号登录：
- 邮箱: `admin@你的域名`
- 密码: 部署脚本在终端"部署完成"卡片里一次性打印的随机初始密码，
  生成规则见 `setup.sh` 第 140 行。**该密码仅显示一次，务必立即记录并首次登录后修改。**

> 若遗失该密码，可重新执行 `bash setup.sh`（管理员若已存在不会覆盖），或改用
> `docker compose exec backend python3 scripts/create_admin.py` 手动创建新管理员。

---

## 日常运维

### 查看日志

```bash
cd /opt/auto-finance/deploy

# 后端日志（JSON 格式）
docker compose logs -f backend

# 所有服务日志
docker compose logs -f

# 最近 100 行
docker compose logs --tail=100 backend
```

### 重启服务

```bash
# 重启单个服务
docker compose restart backend

# 重启全部
docker compose restart

# 完全停止再启动
docker compose down && docker compose up -d
```

### 更新代码

```bash
cd /opt/auto-finance
git pull

cd deploy
docker compose build backend frontend
docker compose run --rm backend alembic upgrade head
docker compose up -d
bash smoke-check.sh
```

### 数据库备份与恢复

系统自带一个独立的 `postgres-backup` 备份容器，默认每天凌晨 3 点做一次 gzip 压缩
的全量 dump，写入 `postgres_backup` 数据卷。保留策略：

- 最近 14 份日备份
- 最近 8 份周备份
- 最近 6 份月备份
- 最近 2 份年备份

**查看已生成的备份：**

```bash
docker compose exec postgres-backup ls -lh /backups/daily
docker compose exec postgres-backup ls -lh /backups/weekly
```

**手动触发一次备份：**

```bash
docker compose exec postgres-backup /backup.sh
```

**手动做一份临时备份到宿主机：**

```bash
docker compose exec -T postgres pg_dump -U app auto_finance \
    | gzip > backup_$(date +%Y%m%d_%H%M).sql.gz
```

**从备份恢复：**

```bash
# 1) 把备份拷到宿主机（或直接在容器内操作）
docker compose cp postgres-backup:/backups/daily/auto_finance-xxxxxxxx.sql.gz ./restore.sql.gz

# 2) 停掉后端避免并发写入
docker compose stop backend

# 3) 恢复（会覆盖已有数据，谨慎）
gunzip -c restore.sql.gz | docker compose exec -T postgres psql -U app auto_finance

# 4) 重启后端
docker compose up -d backend
```

**把备份同步到异地（强烈建议，生产必做）：**

```bash
# 示例：每天凌晨 4 点用 rclone 同步到阿里云 OSS
0 4 * * * rclone sync /var/lib/docker/volumes/deploy_postgres_backup/_data/ \
          ali-oss:my-backup-bucket/pg/ --log-file /var/log/pg_backup_sync.log
```

### SSL 证书

证书由 certbot 容器自动续期（每 12 小时检查一次）。手动续期：

```bash
docker compose run --rm certbot renew
docker compose restart nginx
```

默认会同时续期裸域和 `www` 域名证书；对外访问统一建议使用裸域。

### 对象存储下载地址

默认情况下，报告预览和资产包下载统一经后端代理返回，这样即使 MinIO 只暴露在容器内网，也不会触发浏览器 mixed content。

只有当你额外提供公网对象存储下载地址时，才需要在 `.env` 里配置：

```bash
S3_PUBLIC_BASE_URL=https://files.your-domain.com
```

若未配置该变量，留空即可。

### 创建新用户

```bash
docker compose exec backend python3 scripts/create_admin.py \
    --email user@example.com \
    --password 'SecurePass123!' \
    --role operator \
    --tenant-code default
```

角色说明：`admin` > `manager` > `operator` > `viewer`

---

## 架构图

```
                    ┌─────────────┐
    用户浏览器 ────▶│   Nginx     │
                    │  :80 → :443 │
                    └──────┬──────┘
                           │
               ┌───────────┼───────────┐
               │                       │
        /api/* │                  其他  │
               ▼                       ▼
        ┌──────────┐           ┌──────────┐
        │ FastAPI  │           │ Next.js  │
        │ Backend  │           │ Frontend │
        │  :8000   │           │  :3000   │
        └────┬─────┘           └──────────┘
             │
     ┌───────┼───────┐
     │               │
     ▼               ▼
┌──────────┐  ┌──────────┐
│PostgreSQL│  │  MinIO   │
│  :5432   │  │  :9000   │
└──────────┘  └──────────┘
```

## 常见问题

### Q: 502 Bad Gateway
后端还没启动完成。等待 30 秒后重试，或检查后端日志：
```bash
docker compose logs backend
```

### Q: SSL 证书申请失败
1. 确认域名已解析到服务器 IP
2. 确认 `www.your-domain.com` 也已解析到服务器 IP
3. 确认 80 端口已开放（`ufw allow 80`）
4. 手动重试：
```bash
docker compose run --rm certbot certonly --webroot --webroot-path=/var/www/certbot -d your-domain.com -d www.your-domain.com
```

### Q: 数据库连接失败
```bash
# 检查 postgres 是否在运行
docker compose ps postgres
# 检查日志
docker compose logs postgres
```

### Q: 上传文件失败
检查 MinIO 是否正常：
```bash
docker compose logs minio
# 确认存储桶存在
docker compose exec minio mc ls local/
```
