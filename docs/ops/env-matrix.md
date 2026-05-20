# Environment Variable Matrix

所有环境变量及其来源、默认值、适用范围。

## 后端 (backend/)

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DATABASE_URL` | 是 | `postgresql+psycopg://app:app@localhost:5432/auto_finance` | 生产用 PostgreSQL 连接串 |
| `APP_ENV` | 否 | `development` | 运行环境，`production/staging` 会启用更严格安全校验 |
| `REDIS_URL` | 否 | `redis://localhost:6379/0` | 异步任务队列（Task 8 起需要） |
| `JWT_SECRET` | 是 | — | JWT 签名密钥，生产必须设置 |
| `JWT_REFRESH_SECRET` | 是 | — | Refresh Token 签名密钥 |
| `DEFAULT_REGISTRATION_TENANT_CODE` | 否 | `default` | 公开注册开启时，新用户自动归属的默认租户 code |
| `DEFAULT_REGISTRATION_TENANT_NAME` | 否 | `默认租户` | 默认注册租户不存在时自动创建使用的名称 |
| `CORS_ORIGINS` | 否 | `http://localhost:3000,http://127.0.0.1:3000` | 允许的前端来源，逗号分隔 |
| `CORS_ALLOW_METHODS` | 否 | `GET,POST,PUT,DELETE,OPTIONS` | 显式允许的 CORS 方法列表 |
| `STORAGE_BACKEND` | 否 | `local` | 文件存储后端：`local` / `s3` |
| `S3_ENDPOINT` | 否 | — | S3/MinIO 端点地址 |
| `S3_PUBLIC_BASE_URL` | 否 | — | 对象存储公网下载基址；留空时下载由后端代理 |
| `S3_BUCKET` | 否 | `auto-finance` | S3 桶名 |
| `S3_ACCESS_KEY` | 否 | — | S3 访问密钥 |
| `S3_SECRET_KEY` | 否 | — | S3 私密密钥 |
| `CHE300_ACCESS_KEY` | 否 | — | 车300 API Key |
| `CHE300_ACCESS_SECRET` | 否 | — | 车300 API Secret |
| `CHE300_API_BASE` | 否 | `https://cloud-api.che300.com` | 车300 API 地址 |
| `DEFAULT_CITY_CODE` | 否 | `320100` | 默认城市编码（南京） |
| `DEFAULT_CITY_NAME` | 否 | `南京` | 默认城市名称 |
| `DEEPSEEK_API_KEY` | 否 | — | DeepSeek LLM API Key |
| `DEEPSEEK_BASE_URL` | 否 | `https://api.deepseek.com` | DeepSeek API 地址 |
| `UPLOAD_DIR` | 否 | `backend/data/uploads` | 本地上传目录（local 模式） |
| `RATE_LIMIT_ENABLED` | 否 | `true` | 是否启用关键接口限流 |
| `RATE_LIMIT_WINDOW_SECONDS` | 否 | `60` | 限流统计窗口秒数 |
| `RATE_LIMIT_LOGIN_MAX_REQUESTS` | 否 | `10` | 单 IP 登录接口窗口内最大请求数 |
| `RATE_LIMIT_REGISTER_MAX_REQUESTS` | 否 | `5` | 单 IP 注册接口窗口内最大请求数 |
| `RATE_LIMIT_WRITE_MAX_REQUESTS` | 否 | `30` | 单 IP 关键写接口窗口内最大请求数 |

## 部署构建变量 (deploy/)

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `BACKEND_APT_MIRROR_HOST` | 否 | — | 后端 Docker 构建时替换 Debian apt 源的 host，例如中国大陆 ECS 可设为 `mirrors.aliyun.com` |
| `BACKEND_PIP_INDEX_URL` | 否 | `https://pypi.org/simple` | 后端 Docker 构建安装 Python 依赖时使用的 PyPI 源 |
| `BACKEND_PIP_TRUSTED_HOST` | 否 | — | 私有源或内网镜像需要 `--trusted-host` 时填写；官方 PyPI 留空 |
| `FRONTEND_NPM_REGISTRY` | 否 | — | 前端 Docker 构建时使用的 npm registry，例如 `https://registry.npmmirror.com` |

## 前端 (frontend/)

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `NEXT_PUBLIC_API_BASE` | 否 | `http://127.0.0.1:8000` | 后端 API 地址 |

## 环境文件层级

```
.env.example          ← 共享示例说明（不被运行时加载）
backend/.env.example  ← 后端示例变量
frontend/.env.example ← 前端示例变量
frontend/.env         ← 前端默认值（已提交）
.env                  ← 本地开发实际值（.gitignore 排除）
frontend/.env.local   ← 前端本地覆盖（.gitignore 排除）
```

## 数据库策略说明

- 应用运行时只支持 `DATABASE_URL`
- 本地和生产都应通过 `alembic upgrade head` 管理 schema
- `backend/data/npl.db` 属于历史遗留 SQLite 文件，不代表当前运行时基线
- `DATABASE_PATH` 不再作为应用启动入口，最多只用于手工排查旧数据文件
