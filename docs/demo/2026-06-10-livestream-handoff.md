# 2026-06-10 直播日 Handoff 文档

> **你在读这份文档说明:用户开了新对话,需要你立刻接手 6/10 直播日的最后冲刺**。
> 直播时间:**2026-06-10(周三)20:00**。本文档把所有必要上下文一次性给你,**不要重新探索代码、不要做新功能**。
>
> 用户名:藏晖 / canghui。项目路径:`/Users/canghui/Desktop/汽车金融ai平台/`。

---

## 1. 一句话产品定位

汽车金融不良资产处置的 **AI 工作台**(SaaS + 私有化双形态)。不是估值工具,也不是聊天机器人。AI 给草稿,人工拍板,边界明确(`requires_human_review=true` / `agent_status=rules_based`)。

## 2. 项目状态(2026-06-09 22:00 北京时间)

- **生产环境**: https://zhefenglin.com,smoke 全绿,env_drift 6/6
- **本地 mac**: `/Users/canghui/Desktop/汽车金融ai平台/`
- **服务器**: 阿里云 ECS,SSH 用 `ssh ecs-user@<ip>`,目录 `/opt/auto-finance/`
- **当前分支**: `codex/asset-pricing-hardening-handoff`,**领先 main ~75 commit**
- **最新 commit**: `38be8a9`(等明天上午可能彩排再加 1-2 个)
- **已 push 全部到 origin** → 服务器 `git pull` 即可

## 3. 已完成的关键工作(从 2026-05-29 算起)

### 代码 / 架构
- **B1**: Agent 真消费 `overdue_days/in_storage/storage_days`,M3/M6/M12 自动分层,演示亮点
- **B2**: Agent 评测体系 v1(`backend/evals/`)+ 11 golden case 基线 100%
- **B3**: 报告草稿独立生命周期(`report_drafts` 表 + 状态机 + 4 API + 前端 `/admin/report-drafts`)
- **B4**: `env_drift_check.py` 6 项主动检测,集成到 `deploy/smoke-check.sh`
- **B5**: CHE300 `disabled_for_demo` magic string → 显式 `CHE300_MODE` 开关
- **B6**: PII 脱敏(VIN/手机/身份证/邮箱)+ 跨租户回归 5 测试

### task #5 SaaS 试用上线
- 注册后端 `trial_onboarding.py`:每用户独立 tenant + 自动订阅 trial_poc 30 天
- `user.role=operator` for trial users(让上传/Agent 可用,但 admin 仍需 admin)
- `/register` 加 hero(🎯 30 天 / 🤖 AI 识别 / 🔒 独立空间)
- 首页 onboarding 卡片(空状态显示 4 步流程)
- `ALLOW_PUBLIC_REGISTRATION=true` 已在生产 .env 打开

### task #4 演示脚本
- 路径:`docs/demo/livestream-script-2026-06-10.md`
- 主线 9 个 Step,约 10 分钟
- 客户问答 8 题预案
- 应急话术

### task #7 彩排 #1 已跑完
- 3 个翻车点都修了(见第 5 节"今天 6/9 修了什么")
- 演示数据就位:**演示包-标准包 2026Q2 (id=20)** 和 **演示包-问题包 2026Q2 (id=21)**
- 17 个老包已加 `[已归档]` 前缀

### 演示数据画像
**问题包(id=21)**:30 台车,M12+ **19 台** / M6-M12 **11 台** / 缺 VIN **3 台** / 在库超 90 天 **8 台** / 估值覆盖 100% / 推荐出让区间 ¥1,661,454-2,027,054 / 可交易性 C 64 分

## 4. 关键文件路径(避免新对话重新探索)

```
docs/demo/livestream-script-2026-06-10.md           演示脚本(主线 + Q&A + 应急)
docs/demo/2026-06-10-livestream-handoff.md          ← 你正在读
backend/api/auth.py                                  register endpoint(trial mode 分支)
backend/api/report_drafts.py                         B3 4 endpoint
backend/api/asset_package.py                         上传/定价
backend/api/ai_command_center.py                     Agent 入口
backend/services/agent_orchestrator.py               8 个 Agent 实现
backend/services/trial_onboarding.py                 SaaS 试用创建独立 tenant + 订阅
backend/services/data_masking.py                     B6 PII 脱敏(4 正则)
backend/services/audit_service.py                    audit log + PII 脱敏接入
backend/services/overdue_segmentation.py             B1 M3/M6/M12 边界
backend/scripts/env_drift_check.py                   B4 部署后必跑
backend/scripts/production_smoke_test.py             生产 9 步主路径 API 测试
backend/evals/run.py                                 B2 评测 runner(python3 -m evals.run)
backend/alembic/versions/20260604_0017_report_drafts.py  B3 schema
frontend/src/app/register/page.tsx                   注册页(window.location.href reload)
frontend/src/app/admin/report-drafts/                B3 前端列表/详情
frontend/src/lib/api.ts                              request<T> 自动 Content-Type
tools/demo_data/gen_demo_packages.py                 生成 demo Excel
tools/demo_data/reset_demo_state.sh                  彩排重置脚本
tools/demo_data/demo_*_package.xlsx                  演示用 Excel(gitignored)
```

## 5. 今天 6/9 修了什么(彩排 #1 产出)

3 个直播阻断的 fix:

| commit | 修了什么 | 为什么 |
|---|---|---|
| `61ca278` | `request<T>` 自动加 `Content-Type: application/json` | B3 报告草稿"提交复核"显示"请求失败" |
| `61ca278` | `register` 改用 `window.location.href = "/"` | 注册后跳 `/login?next=/`,session-provider 时序问题 |
| `38be8a9` | trial mode 注册 `user.role=operator` | trial 用户 viewer 角色上传 Excel 会 403 |

**已知但不修(演示话术化解)**:
- `/asset-pricing` 默认不显示资产包列表(架构缺列表入口),演示时直接打开演示包-问题包 2026Q2 链接,不展示列表

## 6. 6/10 周三直播日 timeline(用户的工作)

| 时间 | 工作 |
|---|---|
| **上午 10:00** | 跑冒烟:`bash /opt/auto-finance/deploy/smoke-check.sh` + 在生产无痕窗口走一遍 Step A-G(主线脚本)|
| **下午 14:00** | 最后彩排 1 遍,记录翻车点 |
| **17:00-19:00** | 静默休息,不动代码 |
| **19:00** | 提前进直播间,测推流 + 屏幕共享 + 备用视频就位 |
| **19:55** | 切到演示数据快照、关无关 tab、清空浏览器历史 |
| **20:00** | **直播 + Q&A** |

## 7. 应急方案

### 演示主线翻车

| 症状 | 应急话术 |
|---|---|
| 502 / 加载慢 | "网络稍微卡一下,我先放一段我之前录的演示给大家看" → 切预录视频 |
| Agent 输出空 / 异常 | "这条 case 我们 retry 一下,先看一下数据怎么过来的" → 切下个 step |
| 截图 / 数据看着不对 | "这是 Mock 数据,真实生产数据接入车300 后会更准" → 转移注意 |
| 被问 LLM 准确率 | "演示这套全部是 rules_based 规则化,没用 LLM" |
| 被问竞品对比 | "不去做竞品对比,我们做的是业内人需要的工具,大家试用就知道" |

### 部署回滚(直播前 1 小时内不要部署)

```bash
# 旧 backend IMAGE 已 tag 为 deploy-backend:rollback-20260529
cd /opt/auto-finance/deploy
sudo docker tag deploy-backend:rollback-20260529 deploy-backend:latest
sudo docker compose up -d --no-deps backend
```

### 数据回滚

最近备份:`~/predeploy_b3_20260604_1023.sql.gz`(B3 部署前)。如需恢复:

```bash
gunzip -c ~/predeploy_b3_20260604_1023.sql.gz | \
  sudo docker compose exec -T postgres psql -U app auto_finance
```

## 8. 服务器常用命令

```bash
# SSH
ssh ecs-user@<ip>
cd /opt/auto-finance

# 拉代码 + 重 build + up
cd /opt/auto-finance/deploy
sudo docker compose build backend frontend 2>&1 | tail -8
sudo docker compose up -d --no-deps backend frontend
sleep 20
bash smoke-check.sh

# 看日志
sudo docker compose logs backend --tail 50
sudo docker compose logs frontend --tail 50

# 在 backend 容器跑 python(注意 PYTHONPATH)
sudo docker compose exec -T -e PYTHONPATH=/app backend python3 -c "..."

# 查 DB
sudo docker compose exec -T postgres psql -U app auto_finance -c "..."

# alembic 状态
sudo docker compose run --rm backend alembic current

# 重置演示数据
bash /opt/auto-finance/tools/demo_data/reset_demo_state.sh --apply

# 生产 smoke
python3 backend/scripts/production_smoke_test.py
```

## 9. 用户偏好(藏晖)

读这份文档的 AI,请记住:

- **节奏控制**:藏晖一般每天 5-8h 投入,累的时候说"今天到此为止"。我会主动建议"真·收工"
- **回复风格**:简短、表格化、命令直接给(不要 200 字铺垫)
- **决策方式**:他问"推荐哪个"时希望我直接拍板,不要 4 选 1 让他选
- **沟通风格**:中英混排;关键 commit hash / file path 用反引号包;`🎉` 用于真正的成功节点
- **演示日特别**:**严禁加任何新功能或大改动**。只修阻断 bug。所有 polish 推迟到直播后

## 10. 已知问题(暂不修,直播后处理)

1. **本地 mac 没 pip / bandit** — SAST 扫描推迟到直播后跑
2. **`/asset-pricing` 缺列表入口** — 演示话术化解
3. **alembic 测试本地 fail** — postgres 没启,**正常**,生产 alembic head 在 `20260604_0017`
4. **本地分支领先 main ~75 commit** — 仓库治理在直播后做
5. **数据导入中心 / 法律文书生成** — 在 `codex/data-ingestion-center-20260428` / `codex/legal-doc-generator-v1` 分支,**没合并**,演示中口头预告"v1.5"

## 11. 关键演示数据

**直播必须用的**:
- admin 账号:`<问藏晖>` / 密码:`<问藏晖>`
- 演示包-问题包 2026Q2 id=21 关键指标:
  - 估值覆盖率 100%
  - 推荐出让区间 ¥1,661,454 - ¥2,027,054
  - 可交易性 C(64 分)
  - **M12+ 19 台 / M6-M12 11 台 / 缺 VIN 3 台 / 在库超 90 天 8 台**
- B 线口头预告:数据导入中心 / 法律文书生成 → "v1.5 开放"

## 12. 验收清单(直播前 1 小时,19:00 必跑)

- [ ] `bash /opt/auto-finance/deploy/smoke-check.sh` 全绿(含 env_drift 6/6)
- [ ] `python3 -m evals.run --no-save`(在 backend/ 跑)→ 11/11 = 100%
- [ ] 浏览器无痕窗口:admin 登录 → 演示包-问题包 2026Q2 → 看到完整数据
- [ ] 浏览器无痕窗口:新邮箱注册 → 看到 onboarding + sidebar OPERATOR
- [ ] 直播脚本打印或屏幕另开 tab 备用
- [ ] 备用预录视频(如有)就位

## 13. 接手指令

你读完本文档后,**第一回复直接给用户**:

> 已读 handoff 文档。今天 6/10 直播,我接手 task #8(直播日冒烟 + 19:00 最后冒烟 + Backup plan)。
> 
> 你现在最需要我做的是哪个?
> (a) 上午冒烟跑完贴回结果,我判断有没有问题需要修
> (b) 帮你过一遍演示脚本,润色话术
> (c) 帮你准备 Q&A 应对(8 题之外可能被问的)
> (d) 等到 19:00 一起做最后一次冒烟

**严禁**:
- 不要扫描整个 git log 来"理解项目状态" — 已经在第 3 节列了
- 不要重新 explore 代码结构 — 已经在第 4 节列了
- 不要建议加新功能 — 严禁
- 不要再做"长篇 polish" — 节省 context

---

**编写时间**: 2026-06-09 22:00(彩排 #1 完成后)
**编写人**: Claude(本对话最后一次回复前)
**目的**: 让新对话的 AI 5 分钟内接手 6/10 直播日所有事
