# 动态复盘与模型自学习闭环

本模块用于把真实处置结果反哺给决策模型，形成“预测 -> 执行 -> 回款 -> 偏差分析 -> 系数建议”的闭环。

## 数据表

- `disposal_outcomes`：记录真实处置结果，包括资产标识、处置路径、区域、预测回款、实际回款、预测周期、实际周期、预测成功率和实际结果。
- `model_learning_runs`：记录每次学习运行的汇总偏差、成功率修正建议、区域系数调整建议，以及是否已应用。

## API

- `GET /api/model-feedback/outcomes`
- `POST /api/model-feedback/outcomes`
- `GET /api/model-feedback/summary`
- `GET /api/model-feedback/learning-runs`
- `POST /api/model-feedback/learning-runs`

录入和查看需要 `operator` 及以上权限；创建学习运行需要 `manager` 及以上权限。

## 调整策略

默认不自动修改生产模型参数。`POST /api/model-feedback/learning-runs` 可分别控制两类应用：

- `apply_success_adjustment=false`：只记录成功率修正建议，不影响后续沙盘。
- `apply_success_adjustment=true`：把本次 `suggested_success_adjustment` 标记为已应用；后续同租户库存沙盘会读取最近一次已应用值，并对各路径动态成功率做保守校准。
- `apply_region_adjustments=false`：只记录区域建议，不改动区域配置表。
- `apply_region_adjustments=true`：根据样本偏差对已存在的区域系数做保守修正。

调整范围被限制在安全区间：

- 单次区域流通速度建议：`0.75x - 1.25x`
- 单次法务效率建议：`0.85x - 1.15x`
- 落库后的区域系数：`0.60 - 1.60`
- 单次成功率修正建议：`-15pct - +15pct`
- 后续沙盘路径成功率：仍受原有 `0% - 98%` 边界约束；特别程序等硬门禁路径不可用时仍保持 `0%`

## 前端入口

页面路径：`/portfolio/learning`，导航名称为“复盘学习”。

页面支持：

- 录入真实处置结果
- 查看整体预测偏差与成功率差距
- 查看区域维度调整建议
- 生成学习运行记录
- 经理权限下应用成功率修正，使后续库存沙盘按真实处置偏差校准
- 经理权限下应用区域系数调整
