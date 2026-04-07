# Claude Execution Brief: Session 0 Preflight

你现在不要直接进入商用化改造的 Task 1。  
先在仓库 `/Users/canghui/Desktop/汽车金融ai平台` 执行一次 **Session 0 / Preflight**，目标是解决版本管理边界和本地运行前置条件。

## 已知事实

你需要基于以下已验证事实工作，不要重复假设：

- 根目录 `/Users/canghui/Desktop/汽车金融ai平台` **不是** git 仓库
- 但存在嵌套 git 仓库：
  - `/Users/canghui/Desktop/汽车金融ai平台/frontend/.git`
  - `/Users/canghui/Desktop/汽车金融ai平台/汽车金融ai决策/.git`
- 当前机器环境：
  - `docker`: missing
  - `brew`: missing
  - `redis-server`: missing
  - `psql`: installed
  - `postgres`: installed
  - `pg_isready`: available
  - `pg_isready` 当前结果：`/tmp:5432 - no response`
  - PostgreSQL 版本：`psql (PostgreSQL) 18.3 (Postgres.app)`

## 本次 Session 0 的目标

1. 明确这个项目应该如何做版本管理。
2. 明确 Task 3 和 Task 8 需要的本地运行环境怎么提供。
3. 输出一份可执行的 Preflight 结论，而不是直接改业务代码。
4. 只有当 Preflight 清楚后，才允许进入：
   - [2026-04-03-commercial-readiness.md](/Users/canghui/Desktop/汽车金融ai平台/docs/plans/2026-04-03-commercial-readiness.md)

## 你的工作边界

- 不要修改任何业务逻辑文件。
- 不要开始 Task 1-10。
- 不要直接执行破坏性的 git 操作。
- 不要删除任何现有 `.git` 目录，除非用户明确批准。
- 不要安装系统软件，除非用户明确批准。

## 你必须完成的步骤

### Step 1: 审计仓库边界

你要确认并汇报：

- 根目录是否应该成为这次商用改造的唯一主仓库
- `frontend/.git` 是否需要保留历史
- `汽车金融ai决策/.git` 是否属于本项目执行范围，还是应被排除

你必须给出 2 个方案并推荐 1 个：

1. 维持现状，多仓库继续并行
2. 建立根目录主仓库，梳理或隔离嵌套仓库

默认推荐方向：

- 以 `/Users/canghui/Desktop/汽车金融ai平台` 作为商用改造主仓库
- `frontend/.git` 先备份历史再处理，不能直接删
- `汽车金融ai决策/` 默认视为独立历史目录，先排除在本轮之外

### Step 2: 给出安全的 git 迁移方案

你必须输出一份“先检查、再确认、后执行”的 git 方案，至少包含：

- 如何备份 `frontend/.git`
- 根目录初始化 git 前需要排除哪些目录
- 是否需要把 `frontend` 变成普通目录
- `node_modules`、`.next`、`backend/data/*.db`、上传文件等是否需要加入根 `.gitignore`

你可以建议执行这些动作，但在用户批准前，不要真的执行：

- `git init`
- 删除或移动 `.git`
- 初始提交

### Step 3: 审计本地基础设施

你必须根据已知事实，输出结论：

- PostgreSQL 二进制已安装，但服务未启动
- Redis 当前不可用
- Docker 不可用
- Homebrew 不可用

### Step 4: 给出运行环境方案

你必须给出 2 个方案并推荐 1 个：

1. **Docker Desktop 方案**
   - 安装 Docker Desktop
   - PostgreSQL 和 Redis 都通过 `docker compose` 提供
   - 优点：后续 Task 3 和 Task 8 一致
   - 缺点：当前机器未安装 Docker，需要额外安装

2. **本机服务方案**
   - PostgreSQL 使用现有 Postgres.app
   - Redis 单独安装和启动
   - 优点：Task 3 可以更快开始
   - 缺点：环境一致性比容器方案差，Redis 仍需额外补齐

默认推荐方向：

- **短期推荐**：先使用 Postgres.app 完成 Task 3-4，不让 Docker 缺失阻塞数据库迁移
- **中期要求**：在进入 Task 8 前，明确 Redis 的安装和启动路径

### Step 5: 明确哪些事情现在必须做，哪些可以延后

你必须把前置条件拆成三层：

- 进入 Task 1-2 前必须完成的事
- 进入 Task 3 前必须完成的事
- 进入 Task 8 前必须完成的事

推荐结论应该接近：

- Task 1-2 前：
  - 明确 git 策略
  - 明确主仓库边界
- Task 3 前：
  - 启动 PostgreSQL
  - 确认数据库连接方式
- Task 8 前：
  - 安装并启动 Redis
  - 验证后台任务依赖可用

### Step 6: 产出文档

你必须输出：

1. 一份简短结论
2. 一份建议执行顺序
3. 一份需要用户确认的清单

如果你选择写文件，建议写到：

- `docs/ops/session-0-preflight-report.md`

## 你最后的回复格式

最后只输出这 4 部分：

1. `现状`
2. `推荐方案`
3. `需要用户确认`
4. `下一步`

`下一步` 必须明确说明：

- 是否可以直接进入 Task 1-2
- 进入 Task 3 前还差什么
- 进入 Task 8 前还差什么

## 推荐开场提示

你可以直接按下面这段开始执行：

```text
请先不要开始 Task 1。

先执行 Session 0 / Preflight，范围只限于：
1. 审计当前仓库的 git 结构
2. 给出根目录主仓库方案
3. 审计 PostgreSQL / Redis / Docker 本地前置条件
4. 给出 Task 1-2、Task 3、Task 8 的分阶段前置建议

要求：
- 不要改业务代码
- 不要直接做破坏性 git 操作
- 不要安装系统软件
- 先输出结论、推荐方案、需要我确认的事项

已知事实：
- 根目录不是 git 仓库
- frontend/.git 存在
- 汽车金融ai决策/.git 存在
- docker missing
- brew missing
- redis-server missing
- Postgres.app 已安装，但数据库服务当前未启动
```
