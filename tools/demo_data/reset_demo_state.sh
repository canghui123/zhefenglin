#!/usr/bin/env bash
# 演示数据重置脚本 —— 把"演示包-*"相关的衍生数据(定价结果、Agent 运行、
# 任务草稿、审计日志)清空,回到"刚上传完未定价"的干净起点,以便彩排重跑。
#
# 不会删除:
#   - asset_packages 行本身(包还在,只清 results_json)
#   - 正式 work_orders(非 demo 衍生)
#   - tenants / users / 套餐 / 权益等基础数据
#
# 用法(在服务器 /opt/auto-finance/deploy 目录下跑):
#   bash /opt/auto-finance/tools/demo_data/reset_demo_state.sh           # dry-run, 只 print
#   bash /opt/auto-finance/tools/demo_data/reset_demo_state.sh --apply   # 真正执行
#
# 安全:
#   - 默认 dry-run, 不带 --apply 只显示要做什么
#   - 用 WHERE name LIKE '演示包-%' 精确锁定 demo 包,不误伤其他
#   - 跑前先做一次 pg_dump 备份

set -euo pipefail

APPLY=0
if [ "${1:-}" = "--apply" ]; then
    APPLY=1
fi

COMPOSE_DIR="${COMPOSE_DIR:-/opt/auto-finance/deploy}"
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
fi

run_psql() {
    $SUDO docker compose -f "$COMPOSE_DIR/docker-compose.yml" exec -T postgres \
        psql -U app auto_finance -v ON_ERROR_STOP=1 -c "$1"
}

echo "=== Demo 数据重置 ==="
echo "Apply: $([ $APPLY -eq 1 ] && echo 'YES (真执行)' || echo 'NO (dry-run)')"
echo "Compose dir: $COMPOSE_DIR"
echo

echo "--- Step 1: 备份 ---"
if [ $APPLY -eq 1 ]; then
    BACKUP_FILE="$HOME/demo_reset_backup_$(date +%Y%m%d_%H%M).sql.gz"
    $SUDO docker compose -f "$COMPOSE_DIR/docker-compose.yml" exec -T postgres \
        pg_dump -U app auto_finance | gzip > "$BACKUP_FILE"
    echo "备份已写到: $BACKUP_FILE"
else
    echo "dry-run: 跳过备份"
fi
echo

echo "--- Step 2: 当前 demo 包识别 ---"
run_psql "
SELECT id, name, total_assets,
       CASE WHEN results_json IS NULL THEN '未定价' ELSE '已定价' END AS status,
       to_char(created_at, 'YYYY-MM-DD HH24:MI') AS created_at
FROM asset_packages
WHERE name LIKE '演示包-%'
ORDER BY id;
"
echo

echo "--- Step 3: 关联 agent_runs / agent_tasks / decision_audit_logs 计数 ---"
run_psql "
WITH demo_pkgs AS (SELECT id FROM asset_packages WHERE name LIKE '演示包-%')
SELECT 'agent_runs (demo 包相关)' AS source, COUNT(*) AS rows
  FROM agent_runs WHERE input_json::jsonb @> ANY(
       (SELECT array_agg(jsonb_build_object('asset_package_id', id)) FROM demo_pkgs)
  )
UNION ALL
SELECT 'agent_runs (所有 tenant_id=1)', COUNT(*) FROM agent_runs WHERE tenant_id = 1
UNION ALL
SELECT 'agent_tasks (demo 相关 — 通过 agent_run 间接)', COUNT(*) FROM agent_tasks
UNION ALL
SELECT 'decision_audit_logs (所有 tenant_id=1)', COUNT(*) FROM decision_audit_logs WHERE tenant_id = 1;
"
echo

if [ $APPLY -eq 0 ]; then
    echo "=== Dry-run 完成 ==="
    echo "如要真执行: 加 --apply 参数"
    echo "DELETE 操作会清空:"
    echo "  - demo 包的 results_json / parameters_json"
    echo "  - tenant_id=1 的所有 agent_runs / agent_tasks / agent_recommendations / decision_audit_logs"
    echo "  - 即:重置回'刚上传完未定价'状态,所有 AI 衍生数据清零"
    exit 0
fi

echo "--- Step 4: 清空 demo 包的 results_json / parameters_json ---"
run_psql "
UPDATE asset_packages
SET results_json = NULL, parameters_json = NULL
WHERE name LIKE '演示包-%';
"

echo "--- Step 5: 清空 demo 租户的 Agent 衍生表 ---"
# tenant_id=1 是 default 租户;如有其他 demo 租户,在这里加 WHERE in (...)
run_psql "
BEGIN;
  DELETE FROM agent_run_reviews     WHERE tenant_id = 1;
  DELETE FROM decision_audit_logs   WHERE tenant_id = 1;
  DELETE FROM agent_tasks           WHERE tenant_id = 1;
  DELETE FROM agent_recommendations WHERE tenant_id = 1;
  DELETE FROM agent_runs            WHERE tenant_id = 1;
COMMIT;
"

echo "--- Step 6: 验证 ---"
run_psql "
SELECT
  (SELECT COUNT(*) FROM asset_packages WHERE name LIKE '演示包-%' AND results_json IS NULL) AS demo_packages_reset,
  (SELECT COUNT(*) FROM agent_runs WHERE tenant_id = 1) AS agent_runs_left,
  (SELECT COUNT(*) FROM agent_tasks WHERE tenant_id = 1) AS agent_tasks_left,
  (SELECT COUNT(*) FROM decision_audit_logs WHERE tenant_id = 1) AS audit_logs_left;
"

echo
echo "=== 重置完成 ==="
echo "演示包已回到'未定价'状态,Agent 衍生数据清零"
echo "可以重新触发定价 + Agent 跑全流程"
