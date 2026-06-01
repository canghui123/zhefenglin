# backend/scripts

后端运维 / 演示 / 上线工具集。所有脚本都是**独立可跑**的,不属于 FastAPI runtime 依赖。

## 工具一览

| 脚本 | 用途 | 何时跑 |
|---|---|---|
| `create_admin.py` | 创建管理员账号 | 部署后 / 忘记管理员密码 |
| `list_access_requests.py` | 列出待审批的访问申请 | 日常运维 |
| `seed_commercial_defaults.py` | 写入套餐 / 权益默认种子 | 首次部署或恢复默认 |
| `production_smoke_test.py` | 线上主路径 API 回归测试 | 部署后 / 彩排前 / 直播前 |

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
