#!/usr/bin/env bash
# ============================================================
# 汽车金融 AI 平台 — 一键部署脚本
# 使用方式：bash setup.sh
# ============================================================
set -euo pipefail

cd "$(dirname "$0")"

# ── 颜色输出 ──
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── Step 0: 检查前置条件 ──
echo ""
echo "=============================="
echo " 汽车金融 AI 平台 · 部署向导"
echo "=============================="
echo ""

command -v docker >/dev/null 2>&1 || error "请先安装 Docker: https://docs.docker.com/engine/install/"
command -v docker compose >/dev/null 2>&1 || error "请先安装 Docker Compose V2"

# ── Step 1: 加载环境变量 ──
if [ ! -f .env ]; then
    if [ -f .env.production ]; then
        cp .env.production .env
        warn "已从 .env.production 复制为 .env，请编辑填入实际值"
        warn "运行: nano .env"
        exit 0
    else
        error "找不到 .env 文件，请先配置环境变量"
    fi
fi

source .env

# 检查关键变量
[ "${DOMAIN:-}" = "your-domain.com" ] && error "请在 .env 中设置真实域名 DOMAIN"
[[ "${DB_PASSWORD:-}" == *"CHANGE_ME"* ]] && error "请在 .env 中设置数据库密码 DB_PASSWORD"
[[ "${JWT_SECRET:-}" == *"CHANGE_ME"* ]] && error "请在 .env 中设置 JWT_SECRET（用 openssl rand -hex 32 生成）"
[[ "${S3_ACCESS_KEY:-}" == *"CHANGE_ME"* ]] && error "请在 .env 中设置 S3_ACCESS_KEY"

info "配置检查通过 — 域名: $DOMAIN"

# ── Step 2: Nginx 配置模板说明 ──
info "Nginx 将通过模板读取 DOMAIN: $DOMAIN / www.$DOMAIN"

# ── Step 3: 先启动不需要 SSL 的服务 ──
info "启动 PostgreSQL + MinIO + 后端 + 前端 ..."
docker compose up -d postgres minio
sleep 5

# ── Step 4: 运行数据库迁移 ──
info "构建后端镜像并运行数据库迁移 ..."
docker compose build backend
docker compose run --rm backend alembic upgrade head
info "数据库迁移完成"

# ── Step 5: 创建 MinIO bucket ──
info "初始化 MinIO 存储桶 ..."
docker compose exec minio mc alias set local http://localhost:9000 "$S3_ACCESS_KEY" "$S3_SECRET_KEY" 2>/dev/null || true
docker compose exec minio mc mb local/"${S3_BUCKET:-auto-finance}" 2>/dev/null || true
info "存储桶就绪"

# ── Step 6: 申请 SSL 证书 ──
info "申请 Let's Encrypt SSL 证书（覆盖 $DOMAIN 和 www.$DOMAIN）..."

# 首次签发时 nginx 尚无证书无法启动，因此用 certbot standalone 临时占用 80 端口。
# 续期由 compose 中的 certbot 服务走 webroot 模式完成。
docker compose stop nginx >/dev/null 2>&1 || true
docker run --rm \
    -p 80:80 \
    -v /etc/letsencrypt:/etc/letsencrypt \
    certbot/certbot certonly \
    --standalone \
    --cert-name "$DOMAIN" \
    --email "admin@$DOMAIN" \
    --agree-tos \
    --no-eff-email \
    --keep-until-expiring \
    --expand \
    -d "$DOMAIN" \
    -d "www.$DOMAIN"
info "SSL 证书申请成功"

# ── Step 7: 全部启动 ──
info "启动全部服务 ..."
docker compose up -d --build

# ── Step 8: 创建管理员账号 ──
echo ""
warn "正在创建管理员账号 ..."
docker compose exec backend python3 scripts/create_admin.py \
    --email "admin@$DOMAIN" \
    --password "Admin123!" \
    --role admin \
    --tenant-code default 2>/dev/null || warn "管理员可能已存在，跳过"

# ── 完成 ──
echo ""
echo "=============================="
info "部署完成！"
echo "=============================="
echo ""
echo "  访问地址:  https://$DOMAIN"
echo "  API 文档:  https://$DOMAIN/docs"
echo "  监控指标:  https://$DOMAIN/api/metrics"
echo ""
echo "  管理员账号: admin@$DOMAIN"
echo "  初始密码:   Admin123!  ← 请立即修改！"
echo ""
echo "  常用命令:"
echo "    查看日志:    docker compose logs -f backend"
echo "    重启服务:    docker compose restart"
echo "    停止服务:    docker compose down"
echo "    数据库备份:  docker compose exec postgres pg_dump -U app auto_finance > backup.sql"
echo ""
