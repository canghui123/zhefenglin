# 对象存储运维指南

> Task 7 引入的文件存储抽象层。所有上传文件和生成报告都经过统一的 `StorageBackend` 接口。

## 1. 后端选择

`config.settings.storage_backend` 控制使用哪个后端：

| 值 | 后端 | 依赖 | 适用场景 |
| --- | --- | --- | --- |
| `local` (默认) | 本地文件系统 | 无 | 开发、单机部署 |
| `s3` | S3 兼容 (AWS / MinIO) | `boto3` | 生产、多实例部署 |

## 2. 本地模式

文件写入 `config.settings.upload_dir`（默认 `backend/data/uploads`）。下载由后端代理返回字节流。

无需额外配置。

## 3. MinIO 模式（开发 / 测试用 S3）

```bash
cd infra/minio
docker compose up -d
```

`.env` 中添加：

```dotenv
STORAGE_BACKEND=s3
S3_ENDPOINT=http://localhost:9000
S3_BUCKET=auto-finance
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin
```

MinIO Web 控制台：<http://localhost:9001>（minioadmin / minioadmin）。

首次启动时后端会自动创建 bucket。

## 4. AWS S3 模式

```dotenv
STORAGE_BACKEND=s3
S3_BUCKET=your-bucket-name
S3_ACCESS_KEY=AKIA...
S3_SECRET_KEY=...
# S3_ENDPOINT 留空 = 使用 AWS 默认端点
```

确保 IAM 策略包含 `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:ListBucket`。

## 5. 存储接口

```python
from services.storage.factory import get_storage

store = get_storage()
store.put_bytes("uploads/pkg_42.xlsx", data, content_type="application/...")
data = store.get_bytes("uploads/pkg_42.xlsx")
store.delete_object("uploads/pkg_42.xlsx")
url = store.build_download_url("uploads/pkg_42.xlsx", expires_in=300)  # S3 only
```

## 6. 数据库字段

- `asset_packages.storage_key` — 上传 Excel 的对象 key
- `sandbox_results.report_storage_key` — 生成报告的对象 key

旧字段 `upload_filename` / `report_pdf_path` 保留用于兼容；代码优先读 `storage_key`，回退到旧字段。

## 7. 下载链路

前端不直拼公开路径。所有下载都经过授权端点：

- `GET /api/asset-package/{id}/download` — Excel 下载
- `GET /api/sandbox/{id}/report/download` — 报告下载

S3 模式下返回 pre-signed URL 302 重定向；本地模式下后端直接代理字节流。
