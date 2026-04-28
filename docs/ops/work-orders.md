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
- `GET /api/portfolio/action-center/candidates`：按动作中心分层展开候选车辆，用于批量编排 `towing` / `auction_push` 工单。

## 前端入口

动作中心 `/portfolio/actions` 已支持：

- 从“竞拍/处置就绪清单”进入拍卖工单编排页。
- 从“收车推进清单”进入拖车工单编排页。
- 在编排页查看具体车辆、合同、债务人、逾期、估值、定位线索等明细。
- 支持筛选、单选/批量选择车辆，并逐台或批量设置拖车佣金、工单周期、供应商、起拍价、保留价、拍卖起止时间和拍卖渠道。
- 发布后会把所选车辆及逐台参数写入工单 `payload.line_items`，便于后续对接拖车供应商或拍卖平台。
- 查看最近工单，并执行“开始/完成”状态流转。

## 后续接入方向

- 拖车供应商 API：在 `towing` 工单完成外部派单后回写供应商单号。
- 拍卖平台 API：在 `auction_push` 工单完成上架后回写平台、场次、链接。
- 法务材料生成器：基于 `legal_document` 工单的 payload 自动生成起诉状、保全申请书或特别程序申请书。
