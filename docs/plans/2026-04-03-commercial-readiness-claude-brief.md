# Claude Execution Brief: Commercial Readiness Hardening

你现在要在仓库 `/Users/canghui/Desktop/汽车金融ai平台` 内执行一项“商用化改造”工作。  
但在开始 Task 1 之前，必须先完成一轮 Preflight：

- [2026-04-03-session-0-preflight-claude-brief.md](/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-03-session-0-preflight-claude-brief.md)

Preflight 完成且用户确认后，再完整阅读以下计划文件，并严格按计划逐项执行：

- [2026-04-03-commercial-readiness.md](/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-03-commercial-readiness.md)

## 你的工作方式

1. 必须先完成 Session 0 / Preflight，再进入 Task 1。
2. 必须使用计划文件作为唯一主线，不要自行改范围，不要跳步。
3. 必须按任务顺序推进：
   - Task 1: 测试与 CI 基线
   - Task 2: 架构与环境契约
   - Task 3: PostgreSQL + Alembic
   - Task 4: 仓储层改造
   - Task 5: 认证与 RBAC
   - Task 6: 租户隔离与审计
   - Task 7: 对象存储
   - Task 8: 异步任务
   - Task 9: 第三方调用韧性与可观测性
   - Task 10: 错误码、OpenAPI、备份与数据治理
4. 每个 Task 必须遵守 TDD：
   - 先写失败测试
   - 运行确认失败
   - 写最小实现
   - 运行测试确认通过
   - 再继续下一个步骤
5. 每完成一个 Task，都要运行计划里列出的验证命令。
6. 每完成一个 Task，都要单独提交一次 commit，commit message 优先使用计划中给出的建议。
7. 如果某个 Task 卡住，不要硬扩范围；先根据计划里的 `Explicit Stop Conditions` 停下来并说明阻塞点。

## 明确约束

- 保持“模块化单体”架构，不拆微服务。
- 不要重写前端视觉层，只补登录、权限、任务状态、错误体验。
- 不要继续扩展 SQLite 逻辑；从 Task 3 起要把生产方向切到 PostgreSQL。
- 不要把本地磁盘存储继续当成最终方案；上传和报告最终要走对象存储抽象层。
- 不要一次把所有同步接口都改成异步；只先改“资产包计算”和“报告生成”。
- 不要新增计划外的大型基础设施。

## 关键目标

- 所有核心 API 都需要认证。
- 所有核心业务数据都要支持 `tenant_id` 隔离。
- 所有关键动作都要有审计日志。
- 上传文件和报告不依赖本地磁盘。
- 长耗时任务可以异步执行并查询状态。
- 有统一错误码、OpenAPI 契约、结构化日志、指标、CI、安全扫描和备份恢复文档。

## 执行要求

- 先读代码再改，不要凭空假设。
- 只修改计划明确涉及的文件或为完成任务必须新增的文件。
- 优先复用现有代码结构：
  - 后端入口在 `backend/main.py`
  - 后端配置在 `backend/config.py`
  - 当前数据库初始化在 `backend/database.py`
  - 核心 API 在 `backend/api/`
  - 核心服务在 `backend/services/`
  - 前端 API 封装在 `frontend/src/lib/api.ts`
- 每次改动后都要给出：
  - 改了什么
  - 为什么这样改
  - 跑了哪些验证
  - 是否有剩余风险

## 完成定义

只有同时满足以下条件，才能宣告完成：

- `cd backend && pytest -q` 通过
- `cd backend && python3 -m compileall .` 通过
- `cd frontend && npm run lint` 通过
- `cd frontend && npm run build` 通过
- 计划中的 10 个 Task 都完成
- 文档、环境示例、CI 和 runbook 已同步更新

## 推荐开场提示

可以直接按下面这段开始执行：

```text
请先读取并执行这个 Preflight 文件：
/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-03-session-0-preflight-claude-brief.md

Preflight 完成并得到确认后，再读取并执行这个计划文件：
/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-03-commercial-readiness.md

要求：
1. 先完成 Session 0，并汇报 git 结构和本地环境建议。
2. 得到确认后，再按 Task 1 -> Task 10 的顺序执行。
3. 每个 Task 必须先写失败测试，再做最小实现，再跑验证。
4. 每完成一个 Task 单独提交一次 commit。
5. 不要扩展范围，不要跳步，不要自行拆微服务。
6. 每个阶段结束时汇报：修改文件、验证结果、剩余风险。
```
