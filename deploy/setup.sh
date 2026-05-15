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

WWW_DOMAIN="${WWW_DOMAIN:-www.$DOMAIN}"
APP_CONF_PATH="nginx/conf.d/app.conf"
HTTP_TEMPLATE_PATH="nginx/templates/app.http.conf.template"
HTTPS_TEMPLATE_PATH="nginx/templates/app.https.conf.template"

# 检查关键变量
[ "${DOMAIN:-}" = "your-domain.com" ] && error "请在 .env 中设置真实域名 DOMAIN"

# ── 占位符检查 ──
check_placeholder() {
    local name="$1"; local val="${2:-}"
    [ -z "$val" ] && error "$name 未配置"
    case "$(echo "$val" | tr '[:upper:]' '[:lower:]')" in
        *change_me*|*change-me*|*changeme*|*your-*|*your_*|*placeholder*|*example*|*xxx*|*todo*)
            error "$name 仍是占位符，请修改"
            ;;
    esac
}

check_placeholder "DB_PASSWORD" "${DB_PASSWORD:-}"
check_placeholder "JWT_SECRET" "${JWT_SECRET:-}"
check_placeholder "JWT_REFRESH_SECRET" "${JWT_REFRESH_SECRET:-}"
check_placeholder "S3_ACCESS_KEY" "${S3_ACCESS_KEY:-}"
check_placeholder "S3_SECRET_KEY" "${S3_SECRET_KEY:-}"

# ── 长度检查（与 runtime_security 对齐） ──
if [ "${#JWT_SECRET}" -lt 64 ]; then
    error "JWT_SECRET 长度 ${#JWT_SECRET} 不足 64 字符，请用 openssl rand -hex 48 重新生成"
fi
if [ "${#JWT_REFRESH_SECRET}" -lt 64 ]; then
    error "JWT_REFRESH_SECRET 长度 ${#JWT_REFRESH_SECRET} 不足 64 字符，请用 openssl rand -hex 48 重新生成"
fi
if [ "$JWT_SECRET" = "$JWT_REFRESH_SECRET" ]; then
    error "JWT_SECRET 与 JWT_REFRESH_SECRET 不能相同"
fi
if [ "${#DB_PASSWORD}" -lt 16 ]; then
    error "DB_PASSWORD 长度 ${#DB_PASSWORD} 不足 16 字符，请用 openssl rand -base64 24 重新生成"
fi

info "配置检查通过 — 域名: $DOMAIN"

render_nginx_conf() {
    local template_path="$1"
    sed \
        -e "s/DOMAIN_PLACEHOLDER/$DOMAIN/g" \
        -e "s/WWW_DOMAIN_PLACEHOLDER/$WWW_DOMAIN/g" \
        "$template_path" > "$APP_CONF_PATH"
}

# ── Step 2: 生成 HTTP 引导配置 ──
render_nginx_conf "$HTTP_TEMPLATE_PATH"
info "Nginx HTTP 引导配置已生成: $DOMAIN + $WWW_DOMAIN"

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
info "启动 Nginx (HTTP only) 用于证书验证 ..."
docker compose up -d nginx

info "申请 Let's Encrypt SSL 证书（裸域 + www）..."
docker compose run --rm certbot certonly \
    --webroot \
    --webroot-path=/var/www/certbot \
    --email "admin@$DOMAIN" \
    --agree-tos \
    --no-eff-email \
    -d "$DOMAIN" \
    -d "$WWW_DOMAIN"

render_nginx_conf "$HTTPS_TEMPLATE_PATH"
info "HTTPS 主站配置已生成：裸域主站，www 自动回跳"
info "SSL 证书申请成功"

# ── Step 7: 全部启动 ──
info "启动全部服务 ..."
docker compose up -d --build

# ── Step 8: 创建管理员账号 ──
echo ""
warn "正在创建管理员账号 ..."

# 生成随机初始密码（16 字节 base64，保证大小写+数字+符号熵足够）
ADMIN_INIT_PASSWORD="$(openssl rand -base64 18 | tr -d '=+/' | cut -c1-20)Aa1!"
ADMIN_CREATED=false

if docker compose exec -T backend python3 scripts/create_admin.py \
    --email "admin@$DOMAIN" \
    --password "$ADMIN_INIT_PASSWORD" \
    --role admin \
    --tenant-code default >/dev/null 2>&1; then
    ADMIN_CREATED=true
else
    warn "管理员账号可能已存在，未覆盖；如需重置请手动运行 scripts/create_admin.py"
fi

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
if [ "$ADMIN_CREATED" = "true" ]; then
    echo ""
    echo "  ┌──────────────────────────────────────────────────────────────┐"
    echo "  │ 初始密码（仅本次显示，请立即记录并首次登录后修改）             │"
    echo "  │ $ADMIN_INIT_PASSWORD"
    echo "  └──────────────────────────────────────────────────────────────┘"
    echo ""
else
    echo "  初始密码:   （管理员已存在，未重置）"
fi
echo ""
echo "  常用命令:"
echo "    查看日志:    docker compose logs -f backend"
echo "    重启服务:    docker compose restart"
echo "    停止服务:    docker compose down"
echo "    数据库备份:  docker compose exec postgres pg_dump -U app auto_finance > backup.sql"
echo ""
