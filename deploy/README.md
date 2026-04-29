# 汽车金融 AI 平台 — 部署指南

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
| `DB_PASSWORD` | 数据库密码 | `openssl rand -hex 16` |
| `JWT_SECRET` | JWT 签名密钥 | `openssl rand -hex 32` |
| `JWT_REFRESH_SECRET` | JWT 刷新密钥 | `openssl rand -hex 32` |
| `S3_ACCESS_KEY` | MinIO 用户名 | 自定义，至少 8 位 |
| `S3_SECRET_KEY` | MinIO 密码 | `openssl rand -hex 16` |
| `CHE300_ACCESS_KEY` | 车300 API Key | 从车300后台获取 |
| `CHE300_ACCESS_SECRET` | 车300 API Secret | 从车300后台获取 |
| `QWEN_API_KEY` | 通义千问 / DashScope API Key | 从阿里云 DashScope 控制台获取 |
| `LLM_PROVIDER` | 大模型供应商 | 默认 `qwen` |
| `LLM_MODEL` | 千问模型名称 | 默认 `qwen-plus` |

说明：

- 中国大陆 ECS 可保留 `BACKEND_PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/` 和 `BACKEND_PIP_TRUSTED_HOST=mirrors.aliyun.com`；海外 / CI 环境可改回官方 PyPI 并清空 trusted host
- `DEFAULT_REGISTRATION_TENANT_CODE` / `DEFAULT_REGISTRATION_TENANT_NAME` 控制公开注册用户进入哪个默认租户
- 后端镜像已把 `boto3` 作为正式依赖，用于 `STORAGE_BACKEND=s3` 的 MinIO / S3 存储
- 大模型默认走千问 OpenAI 兼容接口：`QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`

### 第四步：确认域名解析

确保裸域名和 `www` 子域名都已解析到服务器 IP：

```bash
ping your-domain.com
ping www.your-domain.com
# 应该返回你服务器的 IP 地址
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
6. 申请 Let's Encrypt SSL 证书（覆盖裸域名和 `www` 子域名）
7. 启动 Nginx 反向代理
8. 创建默认管理员账号

### 第六步：验证

```bash
# 检查所有服务状态
docker compose ps

# 应该看到 6 个服务全部 running：
# af_postgres, af_minio, af_backend, af_frontend, af_nginx, af_certbot
```

打开浏览器访问 `https://你的域名`，用管理员账号登录：
- 邮箱: `admin@你的域名`
- 密码: `Admin123!`（**请立即修改**）

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
```

### 数据库备份

```bash
# 手动备份
docker compose exec postgres pg_dump -U app auto_finance > backup_$(date +%Y%m%d).sql

# 恢复
docker compose exec -T postgres psql -U app auto_finance < backup_20260413.sql
```

### SSL 证书

生产部署使用主机 `/etc/letsencrypt` 作为证书目录，并挂载到 Nginx / certbot 容器。
证书覆盖裸域名和 `www` 子域名，Nginx 会把 `www` 统一 301 到裸域名。

证书由 certbot 容器通过 webroot 自动续期（每 12 小时检查一次）。手动续期：

```bash
docker compose run --rm certbot renew --webroot -w /var/www/certbot
docker compose restart nginx
```

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
2. 确认 `www` 子域名也已解析到服务器 IP
3. 确认 80 端口已开放（`ufw allow 80`）
4. 手动重试：
```bash
docker run --rm -p 80:80 -v /etc/letsencrypt:/etc/letsencrypt \
  certbot/certbot certonly --standalone \
  --cert-name your-domain.com \
  -d your-domain.com \
  -d www.your-domain.com
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
