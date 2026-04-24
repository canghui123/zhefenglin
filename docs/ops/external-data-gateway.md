# 外部数据生态网关说明

本轮完成模块四 4.1 的最小可上线骨架，目标是先统一外部数据进入系统后的字段、评分和决策联动方式，后续再替换为真实供应商 API。

## 已预留的数据源

- `gps_trace`：GPS 轨迹、最后出现时间、围栏信号。
- `etc_trace`：高速 ETC 通行线索。
- `traffic_violation`：违章城市和车辆活动线索。
- `judicial_risk`：失信被执行人、限制高消费、涉诉数量。

## API

- `GET /api/external-data/providers`：查看预留供应商能力。
- `POST /api/external-data/find-car-score`：输入 GPS/ETC/违章线索，输出 0-100 寻车评分和派单建议。
- `POST /api/external-data/judicial-risk`：输入司法风险线索，输出风险等级，以及是否否决继续催收等待还款路径。

## 决策联动

- 库存沙盘新增 `debtor_dishonest_enforced` 与 `external_find_car_score` 输入。
- 当 `debtor_dishonest_enforced=true` 时，路径 A“继续等待赎车”成功率强制为 `0`，并从推荐候选中排除。
- 组合策略对比也支持 `debtor_dishonest_enforced` 信号，命中时 `collection` 路径成功率为 `0` 并显示约束原因。

## 后续接入真实供应商

真实供应商接入时优先替换 `backend/services/external_data_gateway.py` 的数据来源，不建议让业务页面直接调用供应商 SDK。所有供应商异常、超时、配额控制和审计应收敛在网关层。
