# backend/scripts

后端运维 / 演示 / 上线工具集。所有脚本都是**独立可跑**的,不属于 FastAPI runtime 依赖。

## 工具一览

| 脚本 | 用途 | 何时跑 |
|---|---|---|
| `create_admin.py` | 创建管理员账号 | 部署后 / 忘记管理员密码 |
| `list_access_requests.py` | 列出待审批的访问申请 | 日常运维 |
| `seed_commercial_defaults.py` | 写入套餐 / 权益默认种子 | 首次部署或恢复默认 |
| `production_smoke_test.py` | 线上主路径 API 回归测试 | 部署后 / 彩排前 / 直播前 |
| `env_drift_check.py` | 环境配置漂移检测(B4) | **每次部署后 / cron 每日** / smoke-check.sh 自动调用 |

---

## `production_smoke_test.py`

**用途**:对生产环境 `https://zhefenglin.com` 跑一遍 9 条主路径 API,验证从登录到 AI 指挥中心闭环全程没有翻车。

### 跑法

```bash
# 1. 准备环境变量(不要让密码进 shell history)
export AF_SMOKE_EMAIL='admin@zhefenglin.com'
read -s AF_SMOKE_PASSWORD          # 输入密码,不显示
export AF_SMOKE_PASSWORD

# 2. 跑
cd /path/to/backend
python3 scripts/production_smoke_test.py

# 报告自动写到 /tmp/smoke_report_YYYYMMDD_HHMM.md
```

### 覆盖的 9 个 Step

| Step | API | 验证 |
|---|---|---|
| 1 | `POST /api/auth/login` | Cookie 登录 + access_token |
| 2 | `GET /api/auth/me` | role / feature_capabilities snapshot |
| 3 | `GET /api/ai-command-center/overview` | 8 agent_workbench / today_overview / suggested_prompts |
| 4 | `POST /api/ai-command-center/runs` (asset_package_diagnosis_agent) | AgentOutput schema 完整 |
| 5 | `POST /api/ai-command-center/runs` (operation_planning_agent) | 6 池子字段全 |
| 6 | `POST /api/ai-command-center/runs` (pricing_strategy_agent) | 中位价 / 区间 / tradeability |
| 7 | `GET /api/tasks` | work_orders 数量没因 smoke 而新增 |
| 8 | `GET /api/asset-package/list/all` | 资产包数量 |
| 9 | `GET /api/ai-command-center/decision-audit-logs` | 审计记录 |

### 严格的安全边界

- ✅ 只读 + 触发 Agent run(预期有 agent_runs / audit_logs 增量,这是 Agent 本质)
- ❌ 不上传文件
- ❌ 不创建用户
- ❌ 不确认任务草稿(不会产生新 work_order)
- ❌ 不修改任何业务数据
- 密码**永不**写入报告或 stdout

### 何时跑

- **每次部署后**:`docker compose up -d` + `bash deploy/smoke-check.sh` 之后立刻跑
- **彩排前**:确认演示主路径不会翻车
- **直播前**:上线最后一道关
- **CI(未来)**:接入 stage 环境后,每次 PR 跑一次

---

## `reset_demo_state.sh`(在 `tools/demo_data/`)

演示数据重置脚本——跑在服务器,把"演示包-*"相关的衍生数据(定价结果 / Agent 运行 / 任务草稿 / 审计)清空,回到"刚上传完未定价"状态,以便彩排重跑。

详见 `tools/demo_data/reset_demo_state.sh` 头部注释。

---

## `env_drift_check.py`

**用途**:防止 `.env` 改了但容器没重启 / postgres / MinIO 等容器仍用旧凭证的**配置漂移**问题。这类问题在 2026-05-30 一天内撞了 3 次(DB_PASSWORD / S3_ACCESS_KEY / CHE300_ACCESS_KEY),从此再也不靠手动诊断。

### 跑法

```bash
# 1. 容器内手动跑(部署后,自动被 deploy/smoke-check.sh 调用)
docker compose exec backend python3 scripts/env_drift_check.py

# 2. cron 每日跑
0 6 * * * docker compose exec -T backend python3 scripts/env_drift_check.py >> /var/log/env_drift.log 2>&1
```

### 检查项(6 个)

| 项 | 含义 |
|---|---|
| `DATABASE_URL → postgres 连接` | 实际跑 SELECT 1,捕获 auth_failed / connection refused |
| `S3_ACCESS_KEY → MinIO/S3 连接` | 实际 list_buckets,捕获 InvalidAccessKeyId |
| `JWT_SECRET 编解码` | encode + decode round-trip |
| `CHE300_MODE 配置` | 报告当前 mode + 占位符识别 |
| `本地存储可写` | upload_dir 写测试文件再删 |
| `CORS 生产模式` | production 时拒绝 localhost / 127.0.0.1 |

### 输出 + 退出码

```
================================================================
Environment Drift Check
================================================================
  ✓ DATABASE_URL → postgres 连接: OK
  ✓ S3_ACCESS_KEY → MinIO/S3 连接: OK
  ✓ JWT_SECRET 编解码: OK
  ✓ CHE300_MODE 配置: auto, 将走 mock fallback
  ✓ 本地存储可写: 跳过(s3 模式)
  ✓ CORS 生产模式: 已收紧

  i 关键 env 变量 sha256: 30d6c726000e4f8d...

=== ✓ 全部 6 项通过 ===
```

- 退出码 0 = 全部通过
- 退出码 1 = 至少一项失败,打印具体哪个变量漂移 + 怎么修

### Env hash 漂移提示

每次跑会把关键 env 变量的 sha256 写到 `/tmp/env_drift_hash.txt`。下次跑时对比上次 hash,变了就提示**可能需要重启相关容器**——尤其是 postgres / MinIO 这类数据卷已 init 的容器,改 .env 不会自动更新密码,需要回滚 .env 或重 init 数据卷。

### 单元测试

11 个测试覆盖纯函数(`compute_env_hash`)+ 各 check 分支:`backend/tests/scripts/test_env_drift_check.py`。
