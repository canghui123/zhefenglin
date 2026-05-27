# AI 指挥中心 UI/UX 改版验收记录

## 1. 改版目标

将 `/ai-command-center` 从偏技术化的 Agent 工作台，调整为普通业务用户更容易理解的“汽车金融不良资产 AI 作战台”。

用户进入页面后，应能快速判断：

- 当前最重要的风险是什么
- AI 建议优先做什么
- 哪些事项需要人工确认
- 可以发起哪些常用分析

本次只优化前端 UI/UX，不改变后端核心逻辑、API、权限、tenant 隔离、人工复核和审计机制。

## 2. 改版前问题

- 页面主视觉偏 Agent 技术工作台，业务用户需要理解 `agent_type`、`run_id`、`evidence` 等技术概念。
- 重要结论、风险、建议动作和待确认事项不够集中。
- Agent 工作台、任务、审计、evidence 信息平铺，页面密度偏高。
- mock、fallback、requires_human_review 等技术文案不够业务化。

## 3. 页面结构变化

- 顶部新增“AI 今日判断”主卡片，展示整体风险、今日判断、关键发现、建议动作、置信度和人工复核提示。
- 新增 4 个核心业务指标：待人工确认、高风险资产、本周建议处置、成本/额度预警。
- 新增默认“客户视图”，隐藏 Agent 工作台、审计日志、run 细节和完整分析依据，只展示风险、建议、待确认、本周作战计划和报告草稿。
- 保留“内部工作台”视图，用于发起分析、查看分析依据、任务草稿、最近运行、Agent 状态和管理员审计。
- 新增“AI 建议你优先处理”区域，建议卡片默认展示业务原因、动作、风险等级、置信度和人工复核状态。
- 新增“需要你确认”队列，按报价确认、高成本估值审批、任务草稿确认、报告草稿复核、法务路径复核分组。
- 新增快捷分析入口，用业务按钮替代直接选择 Agent：分析资产包、判断买方报价、生成本周作战计划、生成报告草稿。
- Agent 工作台降级到底部次级区域，用于查看能力状态、最小角色和人工复核边界。
- `evidence` 改为“分析依据”折叠展示；viewer 仍只显示摘要级依据。
- `mock` 显示为“预览能力”，`fallback` 显示为“降级输出”，`requires_human_review` 显示为“需人工复核”。

## 4. operator 冒烟结果

账号：`operator@example.com`

结果：通过。

- `/ai-command-center` 页面可访问。
- 默认进入客户视图，页面只展示风险、建议、待确认、本周作战计划和报告草稿。
- 顶部 AI 今日判断清晰可读，包含整体风险、关键发现、建议动作和置信度。
- 4 个业务指标正常展示。
- “AI 建议你优先处理”区域正常展示。
- “需要你确认”区域正常展示，空状态文案友好且明确不会跨租户读取数据。
- 切换到内部工作台后，快捷分析入口可见。
- 可发起基础 Agent；已通过“分析资产包”入口发起资产包分析，生成新的 AI 分析记录。
- “分析依据”折叠展示正常。
- operator 页面未展示 admin-only 审计入口。
- 直连 `/admin/ai-audit-logs` 时被拦截，显示“仅管理员可访问此页面”。

## 5. admin 冒烟结果

账号：`admin@example.com`

结果：通过。

- `/ai-command-center` 页面可访问。
- 默认客户视图未暴露 Agent 工作台和 AI 审计明细。
- 成本/额度预警指标正常展示。
- 切换到内部工作台后，Agent 工作台位于页面底部次级区域，展示最小角色、规则分析和需人工复核状态。
- 当前真实后端返回的 Agent 状态为规则分析；mock 状态的“预览能力”展示由前端自动化测试覆盖。
- `requires_human_review` 在建议、运行记录和审计区域中显示清楚。
- admin 可以访问 `/admin/ai-audit-logs`；operator 不能访问，审计权限未被误放开。
- 页面未发现明显布局错乱。
- 空状态在待确认、任务草稿等区域显示友好；API 错误状态由前端自动化测试覆盖。

## 6. 前端测试结果

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/frontend
npm run lint
npm test
npm run build
```

结果：

- `npm run lint`：通过
- `npm test`：通过，4 files / 15 tests passed
- `npm run build`：通过，`/ai-command-center` 构建成功

## 7. 后端测试补跑结果

已启动本地 PostgreSQL 后补跑：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 -m pytest -q
python3 -m compileall .
```

结果：

- `python3 -m pytest -q`：通过，204 passed
- `python3 -m compileall .`：通过

## 8. 剩余风险

- 本次只做 UI/UX 业务化改版，没有新增后端能力。
- 当前真实后端环境下 Agent 状态主要为规则分析，未在浏览器真实数据中观察到 mock Agent；mock 文案由前端测试覆盖。
- 生产部署仍需按常规流程执行数据库迁移、构建、部署和线上 smoke check。

## 9. 是否建议提交

建议提交。

建议提交信息：

```text
feat: polish AI command center battle desk UX
```
