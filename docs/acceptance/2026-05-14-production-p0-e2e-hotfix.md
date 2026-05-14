# P0 生产端到端验收与热修复记录

日期：2026-05-14
环境：ECS 生产环境 `https://zhefenglin.com`
验收方式：API 端到端脚本 + 生产容器健康检查

## 结论

P0 生产主链路已通过端到端验收：

- 资产包上传、解析、计算、估值可信度、交易适配度、买方报价反推、PDF 下载链路可用。
- 库存沙盘模拟、法律材料输入、B/D 法律评分、综合推荐评分、HTML 报告生成与下载链路可用。
- 临时验收管理员账号已在验收后停用，并撤销活跃会话。

## 本次生产热修复

验收过程中发现并修复了 3 个生产漂移/兼容问题：

- 沙盘 HTML 模板引用 `auction_discount_rate`，但报告上下文未传入该变量，导致报告任务失败。
- S3/MinIO 报告下载在 `S3_PUBLIC_BASE_URL` 为空时仍跳转到内部预签名地址，公网访问返回 502。
- 生产 `config.py` 缺少 `s3_public_base_url` 字段，导致后端代理下载路径触发 `AttributeError`。

本地保留的代码修复点：

- `backend/services/pdf_generator.py`：为沙盘报告注入安全的路径 C 竞拍折扣，缺显式字段时按 `path_c.sale_price / input.che300_value` 回推。
- `backend/templates/vehicle_report.html`：合并展示“综合推荐评分”“常规诉讼法律可行性”“特别程序法律可行性”和“竞拍折扣”。
- `backend/services/storage/s3.py`：`S3_PUBLIC_BASE_URL` 为空时返回 `None`，让下载接口走后端代理读取对象。
- `backend/config.py`：新增 `s3_public_base_url` 配置字段。
- `backend/tests/services/test_pdf_generator.py`：覆盖路径 C 竞拍折扣显式值和回退值。

## 生产验收结果

端到端产物：

- 本地：`/Users/canghui/Desktop/汽车金融ai平台/data/acceptance-artifacts/prod-p0-e2e-20260514_153215`
- ECS：`/home/ecs-user/deploy_backups/20260514_153215_p0_prod_e2e_full`

验收摘要：

```text
login ok: codex-acceptance-20260514_151712@zhefenglin.com role=admin
asset upload ok: package_id=15 rows=10/10
asset calculate ok: job=17 status=succeeded
asset result ok: assets=10 tradeability=C/60 first_confidence=cache/30
buyer offer ok: price=505840.68 gap_rate=-0.08 assessment=买方报价高于或等于系统中位建议，可关注付款条件和履约风险
asset pdf ok: bytes=7079 content_type=application/pdf
sandbox ok: result_id=14 best_path=C path_scores=5
legal assessment ok: B=100 D=100 gapsD=0
sandbox report ok: bytes=13016 content_type=text/html; charset=utf-8 regenerated_job=19 status=succeeded
P0 production E2E PASS: package_id=15 sandbox_result_id=14
```

生产健康检查：

- `GET https://zhefenglin.com/api/health` 返回 `{"status":"ok","service":"汽车金融不良资产AI平台"}`。
- `af_backend` 容器状态为 `healthy`。
- `af_frontend` 与 `af_nginx` 均保持运行。

## 一致性核对

已核对本地与 ECS 关键文件：

- `backend/services/pdf_generator.py`：本地与 ECS SHA-256 一致。
- `backend/templates/vehicle_report.html`：本地与 ECS SHA-256 一致。
- `backend/services/storage/s3.py`：本地与 ECS SHA-256 一致。
- `backend/config.py`：整文件不一致，属预期；生产文件保留旧兼容结构，但已确认包含 `s3_public_base_url`。

生产关键文本确认：

- `/opt/app/backend/config.py` 包含 `s3_public_base_url`。
- `/opt/app/backend/services/pdf_generator.py` 包含 `_get_path_c_auction_discount_rate` 和 `auction_discount_rate` 上下文注入。
- `/opt/app/backend/services/storage/s3.py` 按 `s3_public_base_url` 决定是否生成公网下载地址。
- `/opt/app/backend/templates/vehicle_report.html` 包含“综合推荐评分”“法律可行性”和“竞拍折扣”。

## 完整验证

本地完整验证已在热修复后重跑：

```bash
cd /Users/canghui/Desktop/汽车金融ai平台/backend
python3 -m pytest -q
python3 -m compileall .

cd /Users/canghui/Desktop/汽车金融ai平台/frontend
npm run lint
npm run build
```

验证结果：

- `python3 -m pytest -q`：通过，`166 passed in 82.92s`
- `python3 -m compileall .`：通过
- `npm run lint`：通过
- `npm run build`：通过，Next.js 生产构建成功生成 27 个静态页面

## 收尾动作

- 生产临时验收管理员 `codex-acceptance-20260514_151712@zhefenglin.com` 已停用。
- 已撤销该账号 8 个活跃会话。
- 停用后登录复测返回 `401 UNAUTHORIZED`。

## 后续建议

- 不要执行 `git add .`，当前工作区仍包含大量无关未提交改动。
- 若要提交本次热修复，建议只选择本记录中列出的相关文件，并单独 review `backend/config.py` 中非本次修复的既有改动。
- 下一轮可以继续推进 P1，但进入新功能前建议先把 P0 生产热修复形成独立提交或补丁包。
