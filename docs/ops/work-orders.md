# 执行工单系统说明

本轮完成模块四 4.2 的最小执行闭环。系统先不直连拖车公司、拍卖平台或法务文档供应商，而是把业务动作沉淀为可审计、可流转、可后续对接外部系统的工单。

## 工单类型

- `towing`：委外拖车/收车工单。
- `auction_push`：拍卖平台推送/上架工单。
- `legal_document`：法务材料生成/提交工单，当前先预留数据结构。

## 状态流转

- `pending`：待处理。
- `in_progress`：处理中。
- `completed`：已完成。
- `cancelled`：已取消。

允许流转：

- `pending -> in_progress/completed/cancelled`
- `in_progress -> completed/cancelled`
- `completed/cancelled` 为终态，不能重新打开。

## API

- `GET /api/work-orders`：按当前租户查看工单，可用 `status` 和 `order_type` 过滤。
- `POST /api/work-orders`：创建工单，最低 `operator` 权限。
- `GET /api/work-orders/{id}`：读取单个工单，强制租户隔离。
- `PUT /api/work-orders/{id}/status`：更新工单状态，最低 `operator` 权限。

## 前端入口

动作中心 `/portfolio/actions` 已支持：

- 从“竞拍/处置就绪清单”一键生成拍卖推送工单。
- 从“收车推进清单”一键生成委外拖车工单。
- 查看最近工单，并执行“开始/完成”状态流转。

## 后续接入方向

- 拖车供应商 API：在 `towing` 工单完成外部派单后回写供应商单号。
- 拍卖平台 API：在 `auction_push` 工单完成上架后回写平台、场次、链接。
- 法务材料生成器：基于 `legal_document` 工单的 payload 自动生成起诉状、保全申请书或特别程序申请书。
