# 汽车金融 AI 平台系统知识文档

更新时间：2026-05-13
用途：供 ChatGPT 或其他大模型学习本系统的功能边界、业务逻辑、数据分析逻辑和核心公式。

## 1. 系统定位

本系统是一个面向汽车金融不良资产处置场景的 AI 决策平台。核心目标不是替代业务人员做最终决策，而是把资产台账、车300估值、处置路径模拟、组合风险分层、AI 报告生成和商用化管控串成一套可审计、可复核、可部署的工作流。

系统的主要使用对象包括：

- 资产包出让方：金融公司、融资租赁公司、汽车金融机构。
- 处置运营人员：负责上传台账、补录字段、发起定价或路径模拟。
- 业务经理：查看组合分层、现金回流、路径策略和团队任务。
- 高管或风控负责人：关注损失率、拨备压力、资本释放和高风险资产。
- 平台管理员：管理用户、租户、套餐、功能开关、成本中心、模型路由、估值规则和审批请求。

系统当前的技术架构是：

- 后端：FastAPI、SQLAlchemy、Alembic、PostgreSQL。
- 前端：Next.js 16、React、TypeScript。
- 存储：通过存储抽象处理上传文件和报告文件，生产环境避免直接依赖用户文件名拼本地路径。
- 外部能力：车300估值接口、DeepSeek/OpenAI 兼容 LLM 接口、对象存储或 MinIO。
- 部署：Docker Compose，生产运行时以 PostgreSQL 为唯一数据库入口。

## 2. 总体功能地图

### 2.1 资产包出让定价分析

入口页面：`/asset-pricing`

核心功能：

- 上传资产包 Excel 台账。
- 自动识别车型、VIN、上牌日期、里程、本金、GPS、保险、过户等字段。
- 明确忽略 Excel 中的买断价、收购价、转让价等价格列，避免把买方报价误当作出让方定价锚点。
- 区分在库车资产包和非在库车资产包。
- 批量调用车300估值，支持 VIN 优先、车型与登记日期兜底。
- 根据资产包类型、本金、车辆估值、风险标签生成推荐出让价区间。
- 调用大模型生成出让方视角分析报告。
- 生成报告后支持 PDF 下载。
- 对因字段缺失触发风险预警的车辆，支持批量补录和单台编辑补录。
- 补录后可重新生成报告，补录字段不改写原始 Excel，只作为本次重算覆盖值。

### 2.2 单车库存决策沙盘

入口页面：`/inventory-sandbox`

核心功能：

- 输入单台车的逾期金额、车300估值、入库日期、逾期阶段、车辆是否已收回、是否已入库等信息。
- 模拟五条处置路径：
  - 路径 A：继续等待赎车。
  - 路径 B：常规诉讼。
  - 路径 C：立即上架竞拍。
  - 路径 D：实现担保物权特别程序。
  - 路径 E：分期重组或和解。
- 计算各路径净回收、时间成本、停车费、资金成本、贬值损失、法律费用。
- 自动判断路径 C、路径 D 是否具备硬前提。
- 输出系统推荐路径和可下载报告。

### 2.3 组合驾驶舱

入口页面包括：

- `/portfolio/overview`
- `/portfolio/segmentation`
- `/portfolio/strategies`
- `/portfolio/cashflow`
- `/portfolio/executive`
- `/portfolio/manager`
- `/portfolio/supervisor`
- `/portfolio/actions`

核心功能：

- 组合总览：存量不良余额、资产笔数、预计损失、现金回流、收车率、入库率。
- 分层分析：按逾期阶段、收车状态、库存状态等维度切分风险。
- 策略对比：对每个分层模拟催收、重组、竞拍、诉讼、债权转让、车辆转让、批量清收等策略。
- 现金流预测：按 7、30、60、90、180、360 天现金流桶估算回款。
- 高管驾驶页：月度判断、风险贡献、资源建议、审批事项。
- 经理作战手册：本月目标、重点分层、周节奏、团队任务。
- 主管控制台：高优先级资产池和执行动作。
- 行动中心：生成拍卖、拖车、法务、催收等执行任务建议。

### 2.4 用户、租户和权限

核心功能：

- 注册、登录、登出、当前用户信息。
- HttpOnly Cookie 保存访问令牌。
- JWT 中包含会话标识 `jti`，后端会校验会话是否仍有效。
- 用户角色包括 viewer、operator、manager、admin 等。
- 多租户数据通过 `tenant_id` 进行隔离。
- 后台管理页支持用户管理、角色调整、启停用户。

### 2.5 商用化和成本控制

核心功能：

- 套餐管理：月费、年费、部署费、席位数、包含资源量、超额单价、功能开关。
- 订阅管理：租户套餐、状态、月度预算上限、预警阈值。
- 功能开关：按套餐和租户控制高级页面、审计导出、私有化配置、模型路由等。
- 成本中心：统计 VIN 调用、高级车况估值、LLM 调用、总成本、预估收入、毛利。
- 模型路由：不同任务可配置首选模型、兜底模型、是否允许高成本模式。
- 高成本估值规则：按利润率、车辆价值、风险标签、人工选择、审批模式触发高级车况定价。
- 审批请求：创建、批准、拒绝、执行前校验、执行后消费审批额度。

## 3. 主要 API 地图

### 3.1 健康检查

- `GET /api/health`：检查后端服务状态。

### 3.2 认证与用户

- `POST /api/auth/register`：注册。
- `POST /api/auth/login`：登录。
- `POST /api/auth/logout`：登出。
- `GET /api/auth/me`：当前用户信息和功能能力。
- `POST /api/auth/access-request`：提交访问申请。
- `GET /api/admin/users`：管理员查看用户。
- `PATCH /api/admin/users/{id}/role`：修改角色。
- `PATCH /api/admin/users/{id}/active`：启用或停用用户。

### 3.3 车价估值

- `POST /api/valuation/single`：单车估值。
- `POST /api/valuation/batch`：批量估值。

### 3.4 资产包出让分析

- `POST /api/asset-package/upload`：上传资产包 Excel。
- `POST /api/asset-package/calculate`：创建异步计算任务。
- `GET /api/asset-package/{package_id}`：读取资产包结果。
- `GET /api/asset-package/{package_id}/report.pdf`：下载资产包出让分析 PDF。
- `GET /api/asset-package/{package_id}/download`：下载原始上传文件。
- `GET /api/asset-package/list/all`：查看资产包列表。

### 3.5 库存决策沙盘

- `POST /api/sandbox/simulate`：运行单车五路径模拟。
- `GET /api/sandbox/{result_id}`：读取模拟结果。
- `GET /api/sandbox/{result_id}/report`：读取报告 HTML。
- `GET /api/sandbox/{result_id}/report/download`：下载报告。
- `GET /api/sandbox/list/all`：查看模拟历史。

### 3.6 组合驾驶舱

- `GET /api/portfolio/overview`：组合总览。
- `GET /api/portfolio/segmentation`：风险分层。
- `GET /api/portfolio/strategies`：策略模拟。
- `GET /api/portfolio/cashflow`：现金流预测。
- `GET /api/portfolio/executive`：高管驾驶页。
- `GET /api/portfolio/manager-playbook`：经理作战手册。
- `GET /api/portfolio/supervisor-console`：主管控制台。
- `GET /api/portfolio/action-center`：行动中心。

### 3.7 异步任务和指标

- `GET /api/jobs/list`：任务列表。
- `GET /api/jobs/{job_id}`：任务状态。
- `GET /api/metrics`：Prometheus 指标。

### 3.8 管理后台

- `GET/POST /api/admin/settings/plans`：套餐列表和新增。
- `PUT /api/admin/settings/plans/{id}`：更新套餐。
- `GET/PUT /api/admin/settings/subscriptions`：订阅管理。
- `GET/PUT /api/admin/settings/deployment-profiles`：私有化部署配置。
- `GET /api/admin/cost-center/overview`：成本中心总览。
- `GET /api/admin/cost-center/tenants`：租户成本明细。
- `GET /api/admin/cost-center/export`：成本 CSV 导出。
- `GET /api/admin/cost-center/value-dashboard`：租户价值看板。
- `GET/PUT /api/admin/feature-flags`：功能开关。
- `GET/PUT /api/admin/model-routing`：模型路由。
- `GET/PUT /api/admin/valuation-rules`：估值规则。
- `GET/POST /api/admin/approval-requests`：审批请求。
- `POST /api/admin/approval-requests/{id}/approve`：审批通过。
- `POST /api/admin/approval-requests/{id}/reject`：审批拒绝。

## 4. 资产包出让分析逻辑

### 4.1 Excel 字段识别

系统会扫描 Excel 列名，并按关键词映射到内部字段。

| 内部字段 | 含义 | 关键词示例 |
| --- | --- | --- |
| `car_description` | 车型描述 | 车型、品牌型号、车辆、品牌、车名、车辆信息、车辆描述 |
| `vin` | VIN 或车架号 | vin、VIN、车架号、车架、识别代码、识别码 |
| `first_registration` | 首次登记或上牌日期 | 首次登记、上牌日期、登记日期、注册日期、首次上牌、上牌时间 |
| `mileage` | 表显里程，单位万公里 | 里程、公里、表显、行驶里程、km、KM、万公里 |
| `gps_online` | GPS 是否在线 | gps、GPS、定位 |
| `insurance_lapsed` | 是否脱保 | 脱保、保险、交强险 |
| `ownership_transferred` | 是否过户 | 过户、转移 |
| `loan_principal` | 本金或债权金额 | 本金、债权、贷款金额、剩余本金、贷款余额、欠款、欠息 |

识别规则：

- `car_description` 是必需字段。缺少车型描述的行会被跳过并记录解析错误。
- 日期支持 `YYYY-MM-DD`、`YYYY/MM/DD`、`YYYY年MM月DD日`、`YYYY.MM.DD`、`YYYYMMDD` 等格式。
- 布尔字段中，`是`、`在线`、`正常`、`1`、`true`、`yes`、`有` 视为真。
- 布尔字段中，`否`、`离线`、`异常`、`0`、`false`、`no`、`无` 视为假。
- 金额字段会清洗逗号、人民币符号、`元` 和空格。
- 如果金额或里程带 `万`、`万元`、`w`，系统按乘以 10000 处理。
- 里程如果原始数值大于 100，系统认为它是公里数，并转换成万公里：`里程万公里 = 公里数 / 10000`。
- 当前资产包出让模块不再把 Excel 中的买断价、收购价、转让价当作定价依据。

### 4.2 资产包上传流程

上传流程如下：

1. 前端选择 Excel 文件。
2. 后端校验文件扩展名和文件头。
3. 校验上传大小是否超过配置上限。
4. 文件通过存储抽象保存。
5. Excel 被解析成资产列表、错误列表、列映射结果和未识别列列表。
6. 后端创建资产包记录。
7. 前端展示解析成功行数、列识别结果和未识别列。

### 4.3 计算流程

资产包计算是异步任务。

流程如下：

1. 前端发送 `package_id` 和 `PricingParameters`。
2. 后端创建 job。
3. job 重新读取原始 Excel 并重新解析，避免只依赖前端状态。
4. 如果请求中包含 `asset_overrides`，系统按 Excel 行号覆盖字段。
5. 系统构建估值请求列表。
6. 批量调用车300估值。
7. 对每台车执行出让定价算法。
8. 汇总资产包层面的推荐区间、风险预警和方法说明。
9. 调用 LLM 生成分析报告。
10. 如果 LLM 未配置、额度不足或调用失败，使用模板报告兜底。
11. 计算结果保存到资产包记录中。
12. 前端轮询 job 状态，成功后读取最新资产包结果。

### 4.4 补录与重新生成

补录机制用于解决报告生成后发现字段缺失的问题。

可补录字段：

- 车型描述。
- VIN。
- 上牌日期。
- 里程。
- GPS 是否在线。
- 是否脱保。
- 是否过户。
- 本金或债权金额。

补录方式：

- 批量补录：可应用到全部风险预警行、本金缺失行、估值缺失行或全部车辆。
- 单台编辑：逐车修改字段。

补录数据结构：

```json
{
  "asset_overrides": {
    "2": {
      "vin": "LHGCM82633A004352",
      "first_registration": "2021-03-15",
      "mileage": 4.8,
      "loan_principal": 86000
    }
  }
}
```

重要边界：

- 补录字段不会改写原始 Excel 文件。
- 补录只在重新计算时覆盖内存中的资产字段。
- 重新生成报告会重新估值、重新计算风险预警、重新生成分析报告。

## 5. 车300估值逻辑

### 5.1 调用优先级

估值优先级：

1. 如果 VIN 合法且长度为 17 位，优先使用 VIN 估值接口。
2. 如果 VIN 不可用，则使用车型、登记日期、里程等信息兜底。
3. 如果未配置车300密钥，或外部服务不可用，则使用 mock 估值。

### 5.2 车300签名逻辑

真实车300调用的签名逻辑：

```text
1. 收集业务参数和 access_key。
2. 按参数名 ASCII 升序排序。
3. 拼接为 k=v&k=v 形式。
4. sign_string = timestamp + param_string + secret
5. sign = md5(sign_string).hexdigest().lower()
```

### 5.3 真实估值字段

VIN 估值会请求：

- `vin`
- `city_name`
- `condition`
- `reg_date`
- `mile_age`
- `all_level=1`

车况映射：

- `excellent`：优秀车况。
- `good`：良好车况。
- `normal`：一般车况。

车300接口价格通常以万元表示，系统换算为元：

```text
价格元 = 接口价格万元 * 10000
```

### 5.4 Mock 估值公式

当无法调用真实车300时，系统使用 mock 估值。

基础参数：

```text
base_price = 150000
age = 当前年份 - 上牌年份
基础折旧值 = base_price * 0.88 ^ age
```

里程调整：

```text
expected_mileage = age * 2.0
excess_mileage = max(实际里程万公里 - expected_mileage, 0)
里程调整系数 = max(1 - excess_mileage * 0.015, 0.5)
```

最终中等车况估值：

```text
medium_price = round(基础折旧值 * 里程调整系数 * random(0.92, 1.08), -2)
```

车况价格：

```text
excellent_price = medium_price * 1.15
good_price = medium_price * 1.08
fair_price = medium_price * 0.85
dealer_buy_price = medium_price * 0.90
dealer_sell_price = medium_price * 1.05
```

### 5.5 估值缓存

系统会缓存估值结果。缓存 key 通常包含：

- VIN 或车型标识。
- 登记日期。
- 里程。
- 车况。
- 估值等级。

缓存的目的是降低外部接口成本和提升响应速度。

## 6. 资产包出让定价公式

### 6.1 资产包类型

系统当前有两种资产包类型：

| 类型 | 内部值 | 定价锚点 |
| --- | --- | --- |
| 在库车资产包 | `inventory` | 车300车辆估值 |
| 非在库车资产包 | `non_inventory` | 债权本金 |

在库车通常代表车辆已入库或可实际控制，因此估值可作为主要锚点。非在库车资产包通常代表车辆尚未入库，系统以本金为主要锚点，并用车辆估值校验抵押物支撑。

### 6.2 车况价格选择

系统根据用户选择的车况选择估值价格。

```text
如果 vehicle_condition = excellent:
    valuation_price = excellent_price 或 good_price 或 medium_price

如果 vehicle_condition = normal:
    valuation_price = medium_price 或 fair_price 或 good_price

其他情况:
    valuation_price = good_price 或 medium_price 或 excellent_price
```

### 6.3 风险调整项

逐车风险调整 `risk_adjustment`：

| 风险 | 调整 | 风险标签 |
| --- | ---: | --- |
| 已过户或权属异常 | -0.06 | 权属瑕疵，建议调低出让价或剔除 |
| 脱保 | -0.02 | 车辆脱保，需在谈判中预留修复成本 |
| GPS 离线，在库车 | -0.02 | GPS 离线，库存控制稳定性下降 |
| GPS 离线，非在库车 | -0.04 | GPS 离线，非在库追车难度上升 |

### 6.4 本金覆盖调整项

覆盖率公式：

```text
coverage = valuation_price / loan_principal
exposure_gap = loan_principal - valuation_price
```

如果本金或估值为 0，则覆盖调整为 0。

在库车覆盖调整：

| 覆盖率 | 调整 |
| ---: | ---: |
| coverage >= 0.95 | +0.03 |
| 0.75 <= coverage < 0.95 | +0.01 |
| coverage < 0.45 | -0.05 |
| 0.45 <= coverage < 0.60 | -0.03 |
| 其他 | 0 |

非在库车覆盖调整：

| 覆盖率 | 调整 |
| ---: | ---: |
| coverage >= 0.90 | +0.08 |
| 0.65 <= coverage < 0.90 | +0.05 |
| 0.45 <= coverage < 0.65 | +0.02 |
| coverage < 0.25 | -0.08 |
| 其他 | -0.04 |

### 6.5 在库车定价

基础逻辑：

```text
basis_amount = valuation_price or loan_principal
basis_label = 车300车辆评估价
base_discount = 0.78
strategy = inventory_valuation_discount
```

如果估值缺失：

```text
base_discount = base_discount - 0.06
risk = 车辆估值缺失，暂以本金辅助定价
```

如果本金缺失：

```text
risk = 本金缺失，无法评估债权覆盖缺口
```

### 6.6 非在库车定价

基础逻辑：

```text
basis_amount = loan_principal or valuation_price
basis_label = 债权本金
base_discount = 0.36
strategy = non_inventory_principal_discount
```

如果本金缺失：

```text
base_discount = 0.42
risk = 本金缺失，暂以车辆估值辅助定价
```

如果估值缺失：

```text
base_discount = base_discount - 0.05
risk = 车辆估值缺失，非在库资产缺少抵押物价值校验
```

### 6.7 推荐折扣和价格区间

中位折扣：

```text
mid_discount = clamp(base_discount + coverage_adjustment + risk_adjustment, 0.08, 0.95)
```

在库车区间：

```text
spread = 0.07
discount_low = clamp(mid_discount - spread, 0.52, 0.92)
discount_high = clamp(mid_discount + spread, 0.52, 0.92)
```

非在库车区间：

```text
spread = 0.08
discount_low = clamp(mid_discount - spread, 0.12, 0.68)
discount_high = clamp(mid_discount + spread, 0.12, 0.68)
```

推荐出让价：

```text
transfer_price_low = basis_amount * discount_low
transfer_price_mid = basis_amount * mid_discount
transfer_price_high = basis_amount * discount_high
```

本金回收率：

```text
principal_recovery_rate = transfer_price / loan_principal
```

估值变现率：

```text
valuation_realization_rate = transfer_price / valuation_price
```

### 6.8 逐车风险标签

系统会增加以下类型的风险标签：

- 车辆估值缺失。
- 本金缺失。
- 权属瑕疵。
- 脱保。
- GPS 离线。
- 车辆估值对本金覆盖偏低。
- 抵押物覆盖较强，出让方议价能力较好。
- 基础字段完整，可进入买方询价。

覆盖率相关标签：

```text
如果 coverage < 0.35:
    risk = 车辆估值对本金覆盖偏低

如果 coverage >= 0.90:
    risk = 抵押物覆盖较强，出让方议价能力较好
```

如果没有其他风险：

```text
risk = 基础字段完整，可进入买方询价
```

### 6.9 逐车结果字段

每台车会输出：

- 行号。
- 车型。
- 本金。
- 车300估值。
- 定价基准。
- 推荐出让价低、中、高。
- 推荐折扣低、中、高。
- 本金折扣低、中、高。
- 估值折扣低、中、高。
- 抵押物覆盖率。
- 本金缺口。
- 风险标签。

兼容字段：

- `buyout_price`：历史买断价字段，当前出让定价逻辑不再从 Excel 识别或使用买断价。
- `net_profit = recommended_transfer_price_mid - loan_principal`。
- `profit_margin = recommended_transfer_price_mid / loan_principal * 100`。

### 6.10 资产包汇总公式

```text
total_principal = sum(asset.loan_principal)
total_vehicle_valuation = sum(asset.che300_valuation)
recommended_transfer_price_low = sum(asset.low_price)
recommended_transfer_price_mid = sum(asset.mid_price)
recommended_transfer_price_high = sum(asset.high_price)
valued_count = count(asset.che300_valuation > 0)
valuation_coverage_rate = valued_count / total_assets * 100
```

汇总折扣的分母：

```text
如果 asset_package_type = inventory:
    discount_denominator = total_vehicle_valuation
否则:
    discount_denominator = total_principal
```

推荐折扣：

```text
recommended_discount_low = recommended_transfer_price_low / discount_denominator
recommended_discount_mid = recommended_transfer_price_mid / discount_denominator
recommended_discount_high = recommended_transfer_price_high / discount_denominator
```

本金回收率：

```text
principal_recovery_rate = recommended_transfer_price / total_principal
```

估值变现率：

```text
valuation_realization_rate = recommended_transfer_price / total_vehicle_valuation
```

抵押物覆盖率：

```text
collateral_coverage_ratio = total_vehicle_valuation / total_principal
```

历史兼容指标：

```text
total_net_profit = recommended_transfer_price_mid - total_principal
overall_roi = recommended_transfer_price_mid / total_principal * 100
```

### 6.11 资产包级风险预警

资产包层面会生成风险预警，例如：

- 存在本金缺失资产。
- 存在估值缺失资产。
- 整体抵押物覆盖率低于 35%。
- 存在权属瑕疵或过户风险。
- 估值覆盖率不足。

高风险数量：

```text
high_risk_count = low_coverage_asset_count + title_risk_asset_count
```

## 7. 资产包 PDF 报告逻辑

资产包 PDF 由后端 `asset_package_pdf` 服务生成。

技术逻辑：

- 使用 ReportLab。
- 使用 `STSong-Light` CID 字体保证中文可读。
- PDF 不依赖浏览器自动化。
- 如果 ReportLab 未安装，接口会提示安装 `reportlab`。

PDF 内容：

- 报告标题：资产包出让定价分析报告。
- 摘要表：资产数量、资产包类型、本金合计、车300估值合计、推荐出让价、中位折扣、本金中位回收率、估值覆盖率。
- 风险预警。
- 分析报告正文。
- 逐车定价明细。

下载逻辑：

1. 前端点击“下载PDF”。
2. 调用 `GET /api/asset-package/{package_id}/report.pdf`。
3. 后端读取最新计算结果。
4. 生成 PDF bytes。
5. 前端创建 Blob URL 并触发浏览器下载。

## 8. 大模型报告逻辑

### 8.1 资产包报告

资产包报告从出让方视角生成，重点回答：

- 资产包适合按什么定价基准出让。
- 推荐出让价区间是否具备估值和本金支撑。
- 关键风险在哪里。
- 哪些字段缺失会影响报价可信度。
- 给买方沟通时应强调哪些议价点。

如果 LLM 不可用，系统生成模板报告兜底。

### 8.2 沙盘报告

沙盘报告从单车处置专家视角生成，重点比较：

- 等待赎车。
- 常规诉讼。
- 立即竞拍。
- 实现担保物权特别程序。
- 分期重组或和解。

报告会输出推荐路径和原因。

### 8.3 LLM 安全护栏

系统对进入 prompt 的用户文本做防注入处理。

措施包括：

- 清理控制字符。
- 替换常见 prompt injection 关键词。
- 截断超长字段。
- 把用户数据包裹在 `<user_data>` 或类似标签中。
- 系统提示明确要求模型把标签内容当作数据，而不是指令。

### 8.4 LLM 成本控制

LLM 调用会经过商业策略预检：

- 检查租户是否有订阅。
- 检查是否有 `ai_report` 额度。
- 检查月度预算是否超限。
- 检查单次任务预算是否超限。
- 根据任务类型解析模型路由。
- 如果首选模型不可用或高成本受限，尝试兜底模型。
- 如果仍受限，返回模板化输出。

LLM 单次成本按模型估算：

```text
如果模型名包含 turbo:
    unit_cost = llm_turbo_unit_cost
如果模型名包含 long:
    unit_cost = llm_long_unit_cost
其他:
    unit_cost = llm_plus_unit_cost
```

## 9. 单车库存决策沙盘逻辑

### 9.1 输入字段

主要输入：

- 车辆描述。
- 入库日期。
- 逾期阶段。
- 逾期金额。
- 当前车300估值。
- 车辆类型。
- 车龄。
- 日停车费。
- 收车成本。
- 年化资金成本或逾期利率。
- 是否已收回。
- 是否已入库。
- 预计成交天数。
- 竞拍佣金率。
- 常规诉讼律师费。
- 特别程序律师费。
- 分期重组月还款额、期数、再违约率。

### 9.2 车辆类型识别

如果用户选择自动识别，系统通过关键词识别车辆类型。

| 类型 | 关键词示例 |
| --- | --- |
| 豪华品牌 | 宝马、奔驰、奥迪、保时捷、路虎、捷豹、雷克萨斯、凯迪拉克 |
| 日系 | 丰田、本田、日产、马自达、铃木、斯巴鲁、三菱 |
| 德系非豪华 | 大众、斯柯达 |
| 新能源 | 特斯拉、比亚迪、蔚来、小鹏、理想、零跑、哪吒、极氪、EV、PHEV |
| 国产品牌 | 默认类型 |

### 9.3 贬值率模型

系统按车辆类型和车龄使用月贬值率。

| 类型 | 0 到 3 年 | 3 到 5 年 | 5 到 8 年 | 8 年以上 |
| --- | ---: | ---: | ---: | ---: |
| 豪华品牌 | 2.5% | 1.8% | 1.2% | 0.8% |
| 日系 | 1.2% | 1.0% | 0.8% | 0.5% |
| 德系非豪华 | 1.8% | 1.4% | 1.0% | 0.7% |
| 国产品牌 | 2.0% | 1.6% | 1.2% | 0.8% |
| 新能源 | 2.8% | 2.2% | 1.5% | 1.0% |

累计贬值公式：

```text
months = days / 30
cumulative_depreciation = 1 - (1 - monthly_rate) ^ months
cumulative_depreciation = min(cumulative_depreciation, 0.80)
depreciated_value = che300_value * (1 - cumulative_depreciation)
depreciation_amount = che300_value - depreciated_value
```

### 9.4 路径 A：继续等待赎车

模拟时间点：

- 15 天。
- 30 天。
- 60 天。
- 90 天。

公式：

```text
parking_cost = daily_parking * days
interest_cost = overdue_amount * annual_interest_rate / 100 * days / 365
depreciated_value = che300_value * (1 - depreciation_rate)
depreciation_amount = che300_value - depreciated_value
holding_cost = parking_cost + interest_cost + recovery_cost
total_shrinkage = holding_cost + depreciation_amount
net_position = depreciated_value - overdue_amount - holding_cost
```

路径 A 的代表值通常取各时间点中 `net_position` 最大的一项。

### 9.5 路径 B：常规诉讼

系统模拟三个场景：

| 场景 | 周期 | 拍卖折扣 | 成功率 |
| --- | ---: | ---: | ---: |
| 乐观 | 6 个月 | 80% | 70% |
| 预期 | 9 个月 | 56% | 85% |
| 悲观 | 14 个月 | 45% | 50% |

公式：

```text
duration_days = duration_months * 30
parking_cost = daily_parking * duration_days
interest_cost = overdue_amount * annual_interest_rate / 100 * duration_days / 365
depreciated_value = che300_value * (1 - depreciation_rate)
auction_price = depreciated_value * auction_discount
lawyer_recovery_fee = auction_price * litigation_recovery_fee_rate
total_cost = legal_cost + parking_cost + interest_cost + recovery_cost
net_recovery = auction_price - total_cost
```

### 9.6 法律费用公式

诉讼费：

| 标的金额 | 公式 |
| ---: | --- |
| <= 10,000 | 50 |
| <= 100,000 | amount * 0.025 - 200 |
| <= 200,000 | amount * 0.02 + 300 |
| <= 500,000 | amount * 0.015 + 1300 |
| <= 1,000,000 | amount * 0.01 + 3800 |
| <= 2,000,000 | amount * 0.009 + 4800 |
| <= 5,000,000 | amount * 0.008 + 6800 |
| <= 10,000,000 | amount * 0.007 + 11800 |
| <= 20,000,000 | amount * 0.006 + 21800 |
| > 20,000,000 | amount * 0.005 + 41800 |

执行费：

| 标的金额 | 公式 |
| ---: | --- |
| <= 10,000 | 50 |
| <= 500,000 | amount * 0.015 - 100 |
| <= 5,000,000 | amount * 0.01 + 2400 |
| <= 10,000,000 | amount * 0.005 + 27400 |
| > 10,000,000 | amount * 0.001 + 67400 |

保全费：

| 标的金额 | 公式 |
| ---: | --- |
| <= 1,000 | 30 |
| <= 100,000 | amount * 0.01 + 20 |
| <= 200,000 | amount * 0.005 + 520 |
| > 200,000 | min(amount * 0.001 + 1320, 5000) |

法律费用合计：

```text
total_legal_cost = court_fee + execution_fee + preservation_fee + fixed_lawyer_fee + recovery_fee
```

### 9.7 路径 C：立即上架竞拍

路径 C 只有在车辆已收回时可用。

公式：

```text
sale_price = che300_value * (1 - depreciation_rate) * 0.90
commission = sale_price * commission_rate
parking_during_sale = daily_parking * expected_sale_days
net_recovery = sale_price - commission - parking_during_sale - recovery_cost
```

### 9.8 路径 D：实现担保物权特别程序

路径 D 的硬前提：

- 车辆已收回。
- 车辆已入库。
- 逾期阶段至少 M3。

如果任一条件不满足，路径 D 自动标记为不可用。

公式：

```text
duration_days = 90
depreciated_value = che300_value * (1 - depreciation_rate)
round1_price = depreciated_value * 0.80
round2_price = depreciated_value * 0.56
expected_auction_price = round1_price * 0.70 + round2_price * (1 - 0.70) * 0.85
total_cost = legal_cost + parking_cost + interest_cost + recovery_cost
net_recovery = expected_auction_price - total_cost
```

特别程序法律费用：

```text
court_fee = 500
execution_fee = 按执行费公式计算
preservation_fee = 0
lawyer_fee = special_lawyer_fee + optional_recovery_fee
```

### 9.9 路径 E：分期重组或和解

公式：

```text
monthly_payment = 输入值，如果为空则 overdue_amount / 12
total_expected_recovery = monthly_payment * restructure_months
risk_adjusted_recovery =
    total_expected_recovery * (1 - redefault_rate)
    + monthly_payment * restructure_months * 0.5 * redefault_rate
management_cost = restructure_months * 200
net_recovery = risk_adjusted_recovery - management_cost
```

### 9.10 路径推荐

系统为每条路径取代表值：

```text
path_a_value = max(path_a.timepoints.net_position)
path_b_value = path_b.expected_scenario.net_recovery
path_c_value = path_c.net_recovery if available
path_d_value = path_d.net_recovery if available
path_e_value = path_e.net_recovery
best_path = argmax(path_value)
```

推荐文本会说明哪条路径净回收最高，以及不可用路径的原因。

## 10. 组合驾驶舱数据逻辑

### 10.1 组合模拟数据

在没有真实数据源接入时，系统使用稳定随机种子生成 mock 组合数据，用于演示和测试。

分层维度包括：

- 逾期阶段：M1、M2、M3、M4、M5、M6+。
- 收车状态：未收回、已收回未入库、已入库。
- 库存状态。

### 10.2 EAD 和 LGD

EAD：

```text
segment_ead = asset_count * avg_ead
```

LGD 基础逻辑：

```text
base_lgd = 0.30 + bucket_index * 0.08
如果已入库:
    base_lgd = base_lgd - 0.10
如果未收回:
    base_lgd = base_lgd + 0.10
avg_lgd = clamp(base_lgd + random_adjustment, 0.10, 0.95)
```

预计损失：

```text
expected_loss_amount = segment_ead * avg_lgd
expected_loss_rate = avg_lgd
```

### 10.3 车辆价值

平均车辆价值：

```text
avg_vehicle_value = avg_ead * random(0.5, 0.8) * (1 - bucket_index * 0.06)
```

### 10.4 回收天数

```text
avg_recovery_days = 30 + bucket_index * 20
如果已入库:
    avg_recovery_days = max(avg_recovery_days - 30, 7)
如果未收回:
    avg_recovery_days = avg_recovery_days + 45
```

### 10.5 现金回流

净回收率：

```text
net_recovery_rate = 1 - avg_lgd
```

不同状态下的现金回流系数：

| 状态 | 30 天 | 90 天 | 180 天 |
| --- | ---: | ---: | ---: |
| 已入库 | 50% | 80% | 95% |
| 已收回未入库 | 20% | 55% | 80% |
| 未收回 | 5% | 20% | 50% |

现金回流：

```text
cash_30d = segment_ead * net_recovery_rate * coefficient_30d
cash_90d = segment_ead * net_recovery_rate * coefficient_90d
cash_180d = segment_ead * net_recovery_rate * coefficient_180d
```

### 10.6 推荐策略初始规则

```text
如果逾期阶段 >= M5 且已入库:
    recommended_strategy = bulk_clearance
否则如果状态为已入库或已收回未入库:
    recommended_strategy = retail_auction
否则如果逾期阶段 <= M2:
    recommended_strategy = collection
否则如果逾期阶段 <= M4:
    recommended_strategy = litigation
否则:
    recommended_strategy = debt_transfer
```

### 10.7 组合总览

```text
total_ead = sum(segment_ead)
total_asset_count = sum(asset_count)
total_expected_loss = sum(expected_loss_amount)
total_expected_loss_rate = total_expected_loss / total_ead
cash_30d = sum(segment.cash_30d)
cash_90d = sum(segment.cash_90d)
cash_180d = sum(segment.cash_180d)
high_risk_segment_count = count(segment.expected_loss_rate > 0.60)
provision_impact = total_expected_loss * 0.015
```

## 11. 组合策略模拟公式

### 11.1 策略参数

| 策略 | 成功率 | 平均天数 | 成本率 | 回收率 |
| --- | ---: | ---: | ---: | ---: |
| 催收 | 25% | 45 | 2% | 30% |
| 重组 | 35% | 90 | 3% | 55% |
| 零售竞拍 | 80% | 30 | 15% | 65% |
| 常规诉讼 | 45% | 270 | 12% | 40% |
| 特别程序 | 60% | 120 | 8% | 55% |
| 债权转让 | 95% | 14 | 5% | 25% |
| 车辆转让 | 90% | 14 | 5% | 45% |
| 批量清收 | 95% | 7 | 3% | 20% |

### 11.2 成功率调整

```text
success_rate = base_success_rate

如果逾期阶段 >= M5:
    success_rate = success_rate * 0.7

如果已入库且策略为零售竞拍、车辆转让、批量清收:
    success_rate = min(0.98, success_rate * 1.2)

如果未收回且策略为零售竞拍或车辆转让:
    success_rate = success_rate * 0.5
```

### 11.3 回收和成本

```text
recovery_rate = base_recovery_rate
如果逾期阶段 >= M5:
    recovery_rate = recovery_rate * 0.85

expected_recovery_gross = ead * recovery_rate * success_rate
```

成本项：

```text
towing_cost = ead * 0.02
    if strategy in [retail_auction, vehicle_transfer, bulk_clearance] and status = 未收回
    else 0

inventory_cost = asset_count * 30 * min(avg_days, 90)
    if strategy in [retail_auction, litigation]
    else 0

legal_cost = ead * 0.06
    if strategy in [litigation, special_procedure]
    else 0

channel_cost = expected_recovery_gross * 0.05
    if strategy in [retail_auction, debt_transfer, vehicle_transfer]
    else 0

funding_cost = ead * funding_rate * avg_days / 365
management_cost = ead * 0.01
```

总成本和净回收：

```text
total_cost = towing_cost + inventory_cost + legal_cost + channel_cost + funding_cost + management_cost
net_recovery_pv = expected_recovery_gross - total_cost
expected_loss_amount = ead - net_recovery_pv
expected_loss_rate = expected_loss_amount / ead
```

资本释放评分：

```text
capital_release_score = clamp((1 - expected_loss_rate) * 80 + 1 / avg_days * 2000, 0, 100)
```

### 11.4 现金流预测

现金流桶：

```text
bucket_days = [7, 30, 60, 90, 180, 360]
```

现金流公式：

```text
total_recovery = ead * recovery_rate * success_rate
progress = min(1, bucket_day / (avg_days * 1.5))
gross_cash_in = total_recovery * progress
gross_cash_out = ead * cost_rate * min(1, bucket_day / (avg_days * 0.8))
net_cash_flow = gross_cash_in - gross_cash_out
```

长期占压和回现率：

```text
total_long_tail = max(0, total_ead - cash_360d)
cash_return_rate = cash_360d / total_ead
```

## 12. 角色化建议逻辑

### 12.1 高管驾驶页

月度判断：

```text
如果 total_expected_loss_rate > 50%:
    monthly_judgment = RED
如果 total_expected_loss_rate > 35%:
    monthly_judgment = YELLOW
否则:
    monthly_judgment = GREEN
```

高管建议重点：

- 找出损失贡献最高的分层。
- 如果库存资产过多，建议加速竞拍或批量出清。
- 对 M4+ 长尾资产，建议法务、特别程序或债权转让。
- 输出资源建议和需要审批的事项。

### 12.2 经理作战手册

经理视角输出：

- 本月现金回流目标。
- 已收车率提升目标。
- 库存压降目标。
- 每周节奏。
- 分层作战重点。

示例目标逻辑：

```text
cash_target = cash_30d
recovered_rate_target = current_recovered_rate + 0.05
inventory_reduction_target = 15 vehicles/month
```

### 12.3 主管控制台和行动中心

主管视角：

- 把高损失、高金额、高可执行性的分层放入高优先级池。
- 对已入库资产生成竞拍任务。
- 对未收回资产生成拖车、催收或法务任务。

拍卖底价建议：

```text
auction_floor_price = avg_vehicle_value * 0.85
```

## 13. 权限、租户和功能开关

### 13.1 认证逻辑

注册：

- 必须开启公开注册。
- 必须同意服务条款。
- 密码至少 10 位，并满足字符复杂度。
- 密码不能包含邮箱或显示名中的明显信息。
- 默认创建 viewer 用户。
- 自动加入默认租户。
- 创建会话并写入 HttpOnly Cookie。

登录：

- 校验账号是否存在、是否启用、密码是否正确。
- 触发登录限流和账号锁定策略。
- 创建服务端 session。
- 签发 JWT，JWT 中包含 `jti`。
- 写入 Cookie。

请求认证：

```text
从 Cookie 或 Authorization Header 读取 token
解码 JWT
提取 jti
查询服务端 session
确认 session 未撤销且未过期
加载用户和租户上下文
```

登出：

```text
根据 jti 撤销 session
清除 Cookie
```

### 13.2 权限角色

常见角色：

- `viewer`：只读或基础能力。
- `operator`：可执行资产包、沙盘、组合操作。
- `manager`：可查看高级驾驶舱、成本中心部分能力。
- `admin`：可管理用户、套餐、租户、审批和系统配置。

### 13.3 功能开关目录

| 功能键 | 名称 | 含义 |
| --- | --- | --- |
| `dashboard.advanced` | 高级成本中心 | 开放成本中心总览与经营指标 |
| `audit.export` | 审计导出 | 允许导出 CSV、报告打印和审计留档动作 |
| `deployment.private_config` | 私有化配置 | 管理私有部署、专属交付和环境配置 |
| `portfolio.advanced_pages` | 高级驾驶舱页面 | 开放高管驾驶页和经理作战手册 |
| `routing.model_control` | 模型路由控制 | 查看和调整模型路由和高成本模式 |
| `tenant.value_dashboard` | 租户价值看板 | 面向销售和续费沟通的价值看板 |
| `pricing.custom_quote` | 自定义报价 | 使用私有报价和定制商务配置 |

功能开关优先级：

```text
租户覆盖 > 套餐权益 > 套餐 JSON feature_flags > 默认关闭
```

如果租户没有订阅，系统保留部分 legacy 能力，避免演示环境完全不可用。

## 14. 商用化计费和额度逻辑

### 14.1 资源类型

| 资源类型 | 套餐字段 |
| --- | --- |
| `vin_call` | `included_vin_calls` |
| `condition_pricing` | `included_condition_pricing_points` |
| `ai_report` | `included_ai_reports` |
| `asset_package_upload` | `included_asset_packages` |
| `sandbox_run` | `included_sandbox_runs` |
| `seat` | `seat_limit` |

### 14.2 月度额度检查

```text
month_start = 当月 1 日 00:00:00
month_end = 下月 1 日 00:00:00
quota_used = sum(usage_events.quantity where resource_type = 当前资源)
quota_remaining = max(quota_limit - quota_used, 0)
```

拒绝条件：

```text
如果没有当前订阅:
    reason = subscription_missing

如果 estimated_internal_cost > single_task_budget:
    reason = single_task_budget_exceeded

如果 quota_used + requested_quantity > quota_limit:
    reason = quota_exceeded

如果 monthly_cost_used + estimated_internal_cost > monthly_budget_limit:
    reason = monthly_budget_exceeded
```

### 14.3 使用量记录

每次外部能力或高成本能力调用会记录 usage event。

成本公式：

```text
estimated_cost_total = quantity * unit_cost_internal
```

月度快照：

```text
total_cost = che300_cost + llm_cost
estimated_gross_profit = estimated_revenue - total_cost
```

VIN 调用：

```text
vin_calls += quantity
che300_cost += estimated_cost_total
```

高级车况估值：

```text
condition_pricing_calls += quantity
che300_cost += estimated_cost_total
```

LLM 调用：

```text
llm_input_tokens += prompt_tokens
llm_output_tokens += completion_tokens
llm_cost += llm_unit_cost
```

### 14.4 成本中心指标

成本中心总览会聚合：

- VIN 调用量。
- 高级车况估值调用量。
- LLM 输入 token。
- LLM 输出 token。
- LLM 成本。
- 车300成本。
- 总成本。
- 预估收入。
- 预估毛利。

租户明细：

```text
avg_cost_per_vehicle = total_cost / max(vin_calls + condition_pricing_calls, 1)
```

价值看板：

```text
estimated_decisions_processed = vin_calls + condition_pricing_calls + sandbox_runs
estimated_hours_saved = vin_calls * 0.12 + ai_report_calls * 0.25 + sandbox_runs * 0.2
recommended_path_coverage =
    min(100, (condition_calls + ai_report_calls) / max(estimated_decisions_processed, 1) * 100)
```

## 15. 高成本估值审批逻辑

### 15.1 触发规则

高级车况估值由估值规则控制。

支持的触发类型：

- `profit_margin_threshold`：利润率落入指定区间。
- `high_asset_value`：车辆价值超过阈值。
- `high_risk_vehicle`：风险标签命中指定集合。
- `manual_request`：人工勾选高成本估值。
- `approval_report_mode`：审批报告模式。

规则匹配：

```text
如果任一启用规则匹配:
    allow_condition_pricing = true
    fallback_level = condition_pricing
否则:
    allow_condition_pricing = false
    fallback_level = basic
```

### 15.2 审批流程

创建审批：

```text
create_request(
    tenant_id,
    applicant_user_id,
    type,
    reason,
    related_object_type,
    related_object_id,
    estimated_cost,
    metadata
)
```

执行前校验：

```text
审批单必须存在
tenant_id 必须匹配
状态必须是 approved
不能已经 consumed
type 必须匹配
related_object_type 和 related_object_id 必须匹配
```

执行后消费：

```text
mark_consumed(approval_request_id, consumed_request_id)
```

### 15.3 降级策略

如果高级车况估值受限：

- 严格模式 `strict_policy=true`：直接报错并返回审批上下文。
- 非严格模式：降级为 basic 估值，并在响应中标记 degraded。

## 16. 模型路由逻辑

模型路由按任务类型和租户解析。

默认路由：

```json
{
  "scope": "fallback",
  "task_type": "light_task",
  "preferred_model": "qwen-turbo",
  "fallback_model": "qwen-plus",
  "allow_batch": false,
  "allow_search": false,
  "allow_high_cost_mode": false,
  "prompt_version": "v1"
}
```

如果存在启用的租户规则或全局规则，使用规则中的：

- 首选模型。
- 兜底模型。
- 是否允许批量。
- 是否允许搜索。
- 是否允许高成本模式。
- prompt 版本。

## 17. 异步任务逻辑

资产包计算等耗时操作通过 job 执行。

任务状态：

- pending。
- running。
- succeeded。
- failed。

任务执行流程：

```text
创建 job_runs 记录
写入 payload_json
调度后台函数
设置 started_at
执行业务逻辑
成功则保存 result_json 并标记 succeeded
失败则保存 error_code、error_message 并标记 failed
设置 finished_at
```

前端轮询：

```text
每 1 秒请求 /api/jobs/{job_id}
最多 120 次
状态为 succeeded 或 failed 时停止
超时则提示任务超时
```

## 18. 环境变量和部署边界

后端读取仓库根目录 `.env`。前端读取 `frontend/.env` 和 `frontend/.env.local`。

关键后端变量：

- `DATABASE_URL`：PostgreSQL 连接串。
- `APP_ENV`：运行环境。
- `REDIS_URL`：Redis。
- `JWT_SECRET_KEY`：JWT 密钥。
- `CORS_ALLOW_ORIGINS`：跨域白名单。
- `STORAGE_BACKEND`：本地、S3 或 MinIO。
- `S3_ENDPOINT_URL`、`S3_ACCESS_KEY_ID`、`S3_SECRET_ACCESS_KEY`、`S3_BUCKET_NAME`：对象存储。
- `CHE300_ACCESS_KEY`、`CHE300_SECRET_KEY`、`CHE300_BASE_URL`、`CHE300_CITY_NAME`：车300。
- `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`LLM_MODEL`：大模型。
- `UPLOAD_DIR`：本地上传目录。
- `RATE_LIMIT_*`：限流配置。

关键前端变量：

- `NEXT_PUBLIC_API_BASE`：浏览器请求后端 API 的基础地址。

生产边界：

- 生产运行时只使用 PostgreSQL。
- 不应把 `DATABASE_PATH` 当作本地运行入口。
- 涉及上传、报告、文件落盘，应优先走存储抽象。
- 涉及租户数据时必须保持 `tenant_id` 过滤。

## 19. 前端页面逻辑

### 19.1 首页

展示平台标题和后端连接状态，并提供主要入口：

- 资产包出让定价分析。
- 库存决策沙盘。

### 19.2 登录注册

负责：

- 登录。
- 注册。
- 保存当前用户状态。
- 获取功能能力。
- 按角色和功能开关显示页面。

### 19.3 资产包出让页

页面状态包括：

- 当前上传文件。
- 上传解析状态。
- 资产包 ID。
- 解析结果。
- 资产包类型。
- 高级车况定价开关。
- 审批上下文。
- 审批单状态。
- 补录字段。
- 批量补录输入。
- 计算结果。
- 错误提示。

主要交互：

- 上传并解析。
- 选择在库车或非在库车。
- 选择车况口径。
- 开启高级车况定价。
- 发起审批或刷新审批。
- 生成资产包出让分析。
- 批量补录。
- 单台编辑补录。
- 使用补录字段重新生成报告。
- 下载 PDF。

### 19.4 组合页面

组合页面围绕后台 `/api/portfolio/*` 数据展示：

- 总览页展示核心经营指标。
- 分层页展示逾期和状态分层。
- 策略页展示不同处置策略对比。
- 现金流页展示未来现金回流。
- 高管、经理、主管和行动中心页面根据角色聚焦不同决策粒度。

### 19.5 管理后台

管理页面包括：

- 用户管理。
- 套餐和订阅管理。
- 成本中心。
- 价值看板。
- 功能开关。
- 模型路由。
- 估值规则。
- 审批请求。
- 私有化部署配置。

## 20. 数据模型摘要

### 20.1 资产包核心模型

`Asset`：

- `row_number`
- `car_description`
- `vin`
- `first_registration`
- `mileage`
- `gps_online`
- `insurance_lapsed`
- `ownership_transferred`
- `loan_principal`
- `buyout_price`

`PricingParameters`：

- 拖车费。
- 日停车费。
- 资金成本。
- 处置周期。
- GPS 在线和离线拖回成功率。
- 车况。
- 资产包类型。
- 高级车况定价开关。
- 审批信息。
- 单次任务预算。
- `asset_overrides`。

`PackageSummary`：

- 总资产数。
- 本金合计。
- 车辆估值合计。
- 估值覆盖率。
- 推荐出让价区间。
- 推荐折扣。
- 本金回收率。
- 估值变现率。
- 抵押物覆盖率。
- 分析报告。
- 定价方法说明。
- 高风险数量。
- 风险预警。

### 20.2 沙盘核心模型

`SandboxInput`：

- 车辆描述。
- 入库日期。
- 逾期阶段。
- 逾期金额。
- 车300估值。
- 车辆类型。
- 车龄。
- 停车费。
- 收车成本。
- 年化利率。
- 车辆回收和入库状态。
- 竞拍参数。
- 法律费用参数。
- 分期重组参数。

`SandboxResult`：

- 输入。
- 路径 A 结果。
- 路径 B 结果。
- 路径 C 结果。
- 路径 D 结果。
- 路径 E 结果。
- 推荐路径。
- 最优路径。

### 20.3 组合核心模型

`PortfolioOverview`：

- 存量不良余额。
- 存量笔数。
- 预计总损失。
- 预计损失率。
- 30/90/180 天现金回流。
- 收车率。
- 入库率。
- 平均库存天数。
- 高风险分层数量。
- 拨备压力。
- 资本释放评分。

`SegmentDetail`：

- 分层名称。
- 逾期阶段。
- 收车状态。
- 库存状态。
- 资产笔数。
- EAD。
- 平均车辆价值。
- 平均 LGD。
- 平均回收天数。
- 预计损失。
- 推荐策略。

`StrategyComparison`：

- 策略类型。
- 成功率。
- 预期毛回收。
- 总成本。
- 净回收现值。
- 预计损失。
- 预计回收天数。
- 资本释放评分。
- 成本拆分。
- 风险备注。
- 不推荐原因。

## 21. 当前系统的重要业务假设

- 资产包出让模块站在金融公司出让方角度，而不是买方买断定价角度。
- 在库车更依赖车辆估值，非在库车更依赖债权本金。
- Excel 中的价格类字段可能是历史买断价、买方报价或转让价，当前模块不将其作为定价锚点。
- 车300估值是核心外部数据源，但系统必须具备 mock 和降级能力。
- LLM 报告是辅助解释，不是唯一计算依据；所有关键价格区间应由规则和公式先算出。
- 字段缺失会降低报告可信度，因此系统允许报告后补录并重新生成。
- 高成本能力必须经过套餐、预算、额度、审批和审计链路。
- 多租户场景中所有读写都必须保持租户隔离。

## 22. 给 ChatGPT 学习时的提示建议

如果要让 ChatGPT 学习并后续辅助讨论本系统，可以使用以下提示词：

```text
请学习下面这份汽车金融 AI 平台系统知识文档。
学习重点：
1. 资产包出让定价分析的完整流程。
2. 在库车和非在库车的定价锚点差异。
3. 车300估值、风险调整、覆盖率调整和推荐出让价公式。
4. 单车库存决策沙盘的五路径模拟公式。
5. 组合驾驶舱的 EAD、LGD、现金流、策略模拟逻辑。
6. 商用化管控，包括套餐、额度、成本中心、模型路由、审批和功能开关。
7. 系统边界：LLM 只生成解释报告，关键数值由规则和公式计算。

之后我会让你基于这份文档，帮我解释系统、设计测试表、写演示话术、拆解产品卖点或检查业务逻辑。
```

## 23. 快速口径总结

一句话介绍：

> 这是一个面向汽车金融不良资产处置的 AI 决策平台，围绕资产包出让定价、单车库存处置、组合风险分层和商用化成本管控，把 Excel 台账、车300估值、规则定价、路径模拟和 AI 报告串成可审计的闭环。

资产包出让定价核心：

> 在库车以车300估值为锚，非在库车以债权本金为锚，再根据抵押物覆盖率、GPS、脱保、过户等风险因素调整折扣，生成推荐出让价区间和分析报告。

库存沙盘核心：

> 对单车在等待赎车、常规诉讼、立即竞拍、特别程序、分期重组五条路径下的净回收进行量化比较，推荐净回收和可执行性最优的路径。

组合驾驶舱核心：

> 将资产按逾期和处置状态分层，估算 EAD、LGD、现金回流和策略净现值，为高管、经理、主管和执行人员提供不同粒度的行动建议。

商用化核心：

> 用套餐、额度、预算、模型路由、审批和成本中心控制外部估值与大模型调用成本，同时保留租户级功能开关和审计能力。
