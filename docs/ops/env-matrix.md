# Environment Variable Matrix

所有环境变量及其来源、默认值、适用范围。

## 后端 (backend/)

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `DATABASE_URL` | 是 | `postgresql+psycopg://app:app@localhost:5432/auto_finance` | 生产用 PostgreSQL 连接串 |
| `DATABASE_PATH` | 否 | `backend/data/npl.db` | SQLite 路径（仅本地开发兼容） |
| `REDIS_URL` | 否 | `redis://localhost:6379/0` | 异步任务队列（Task 8 起需要） |
| `JWT_SECRET` | 是 | — | JWT 签名密钥，生产必须设置 |
| `JWT_REFRESH_SECRET` | 是 | — | Refresh Token 签名密钥 |
| `CORS_ORIGINS` | 否 | `http://localhost:3000,http://127.0.0.1:3000` | 允许的前端来源，逗号分隔 |
| `STORAGE_BACKEND` | 否 | `local` | 文件存储后端：`local` / `s3` |
| `S3_ENDPOINT` | 否 | — | S3/MinIO 端点地址 |
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
