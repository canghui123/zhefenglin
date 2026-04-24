"use client";

import { useState } from "react";
import { simulateSandbox, generateReport, downloadReport, type SandboxResult, type TimePoint, type LitigationScenario, type AuctionRound } from "@/lib/api";
import { pollJob } from "@/lib/jobs";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

interface FormState {
  car_description: string;
  entry_date: string;
  overdue_bucket: string;
  overdue_amount: number;
  che300_value: number;
  province: string;
  city: string;
  vehicle_type: string;
  vehicle_age_years: number;
  daily_parking: number;
  recovery_cost: number;
  sunk_collection_cost: number;
  sunk_legal_cost: number;
  annual_interest_rate: number;
  vehicle_recovered: boolean;
  vehicle_in_inventory: boolean;
  debtor_dishonest_enforced: boolean;
  external_find_car_score: number;
  expected_sale_days: number;
  commission_rate: number;
  litigation_lawyer_fee: number;
  litigation_has_recovery_fee: boolean;
  litigation_recovery_fee_rate: number;
  special_lawyer_fee: number;
  special_has_recovery_fee: boolean;
  special_recovery_fee_rate: number;
  restructure_monthly_payment: number;
  restructure_months: number;
  restructure_redefault_rate: number;
}

export default function InventorySandboxPage() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SandboxResult | null>(null);
  const [reportHtml, setReportHtml] = useState("");

  const [form, setForm] = useState<FormState>({
    car_description: "",
    entry_date: "",
    overdue_bucket: "M3(61-90天)",
    overdue_amount: 0,
    che300_value: 0,
    province: "",
    city: "",
    vehicle_type: "auto",
    vehicle_age_years: 3,
    daily_parking: 30,
    recovery_cost: 0,
    sunk_collection_cost: 0,
    sunk_legal_cost: 0,
    annual_interest_rate: 24,
    vehicle_recovered: true,
    vehicle_in_inventory: true,
    debtor_dishonest_enforced: false,
    external_find_car_score: 0,
    expected_sale_days: 7,
    commission_rate: 0.02,
    litigation_lawyer_fee: 5000,
    litigation_has_recovery_fee: false,
    litigation_recovery_fee_rate: 0.05,
    special_lawyer_fee: 3000,
    special_has_recovery_fee: false,
    special_recovery_fee_rate: 0.03,
    restructure_monthly_payment: 0,
    restructure_months: 12,
    restructure_redefault_rate: 0.30,
  });

  function upd(field: keyof FormState, value: string | number | boolean) {
    if (field === "vehicle_recovered" && value === false) {
      setForm((prev) => ({ ...prev, vehicle_recovered: false, vehicle_in_inventory: false }));
      return;
    }
    if (field === "vehicle_in_inventory" && value === true) {
      setForm((prev) => ({ ...prev, vehicle_recovered: true, vehicle_in_inventory: true }));
      return;
    }
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSimulate() {
    if (!form.car_description || !form.entry_date || !form.che300_value) {
      setError("请填写车辆描述、入库/评估日期和车300估值");
      return;
    }
    setLoading(true);
    setError("");
    setReportHtml("");
    try {
      const res = await simulateSandbox(form);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "模拟失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleReport() {
    if (!result?.id) return;
    try {
      const { job_id } = await generateReport(result.id);
      const job = await pollJob(job_id);
      if (job.status === "failed") {
        throw new Error(job.error_message || "报告生成失败");
      }
      const html = await downloadReport(result.id);
      setReportHtml(html);
    } catch {
      setError("报告生成失败");
    }
  }

  function printReport() {
    const win = window.open("", "_blank");
    if (win) {
      win.document.write(reportHtml);
      win.document.close();
      win.print();
    }
  }

  const pathNames: Record<string, string> = {
    A: "继续等待赎车",
    B: "常规诉讼",
    C: "立即上架竞拍",
    D: "担保物权特别程序",
    E: "分期重组/和解",
  };
  const specialProcedureStageAllowed = !form.overdue_bucket.startsWith("M1") && !form.overdue_bucket.startsWith("M2");
  const specialProcedureBlocked = !form.vehicle_recovered || !form.vehicle_in_inventory || !specialProcedureStageAllowed;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">库存决策沙盘</h1>
        <p className="text-gray-500 mt-1">五路径模拟推演 — 等待/诉讼/竞拍/特别程序/重组</p>
      </div>

      {error && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
      )}

      {/* ====== 输入表单 ====== */}
      <div className="bg-white border rounded-xl p-6 space-y-6">
        <h2 className="font-semibold text-gray-900">车辆基本信息</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Field label="车辆描述">
            <input className="inp" value={form.car_description} onChange={(e) => upd("car_description", e.target.value)} placeholder="如：2021丰田凯美瑞2.0G豪华版" />
          </Field>
          <Field label="入库/评估日期">
            <input className="inp" type="date" value={form.entry_date} onChange={(e) => upd("entry_date", e.target.value)} />
          </Field>
          <Field label="逾期阶段">
            <select className="inp" value={form.overdue_bucket} onChange={(e) => upd("overdue_bucket", e.target.value)}>
              <option value="M1(1-30天)">M1（1-30天）</option>
              <option value="M2(31-60天)">M2（31-60天）</option>
              <option value="M3(61-90天)">M3（61-90天）</option>
              <option value="M4(91-120天)">M4（91-120天）</option>
              <option value="M5(121-150天)">M5（121-150天）</option>
              <option value="M6+(>150天)">M6+（150天以上）</option>
            </select>
          </Field>
          <Field label="逾期金额 (元)">
            <input className="inp" type="number" value={form.overdue_amount || ""} onChange={(e) => upd("overdue_amount", +e.target.value)} />
          </Field>
          <Field label="当前车300估值 (元)">
            <input className="inp" type="number" value={form.che300_value || ""} onChange={(e) => upd("che300_value", +e.target.value)} />
          </Field>
          <Field label="省份">
            <input className="inp" value={form.province} onChange={(e) => upd("province", e.target.value)} placeholder="如：江苏省" />
          </Field>
          <Field label="城市">
            <input className="inp" value={form.city} onChange={(e) => upd("city", e.target.value)} placeholder="如：南京市" />
          </Field>
          <Field label="车辆类型">
            <select className="inp" value={form.vehicle_type} onChange={(e) => upd("vehicle_type", e.target.value)}>
              <option value="auto">自动识别</option>
              <option value="luxury">豪华品牌(BBA/保时捷等)</option>
              <option value="japanese">日系(丰田/本田等)</option>
              <option value="german">德系非豪华(大众等)</option>
              <option value="domestic">国产品牌</option>
              <option value="new_energy">新能源</option>
            </select>
          </Field>
          <Field label="车龄 (年)">
            <input className="inp" type="number" step="0.5" value={form.vehicle_age_years} onChange={(e) => upd("vehicle_age_years", +e.target.value)} />
          </Field>
          <Field label="收车成本 (元)">
            <input className="inp" type="number" value={form.recovery_cost || ""} onChange={(e) => upd("recovery_cost", +e.target.value)} placeholder="含拖车/GPS/人工" />
          </Field>
          <Field label="已发生催收成本 (元)">
            <input className="inp" type="number" value={form.sunk_collection_cost || ""} onChange={(e) => upd("sunk_collection_cost", +e.target.value)} placeholder="沉没成本，仅展示" />
          </Field>
          <Field label="已发生法务成本 (元)">
            <input className="inp" type="number" value={form.sunk_legal_cost || ""} onChange={(e) => upd("sunk_legal_cost", +e.target.value)} placeholder="沉没成本，仅展示" />
          </Field>
          <Field label="日停车费 (元)">
            <input className="inp" type="number" value={form.daily_parking} onChange={(e) => upd("daily_parking", +e.target.value)} />
          </Field>
          <Field label="车辆是否已回收">
            <div className="flex items-center gap-2 h-10">
              <input
                type="checkbox"
                checked={form.vehicle_recovered}
                onChange={(e) => upd("vehicle_recovered", e.target.checked)}
                className="w-4 h-4"
                id="vehicle_recovered"
              />
              <label htmlFor="vehicle_recovered" className="text-sm text-gray-700 cursor-pointer">
                {form.vehicle_recovered ? "已收回" : "未收回（路径C/D将屏蔽）"}
              </label>
            </div>
          </Field>
          <Field label="车辆是否已入库">
            <div className="flex items-center gap-2 h-10">
              <input
                type="checkbox"
                checked={form.vehicle_in_inventory}
                onChange={(e) => upd("vehicle_in_inventory", e.target.checked)}
                className="w-4 h-4 disabled:opacity-50"
                id="vehicle_in_inventory"
                disabled={!form.vehicle_recovered}
              />
              <label htmlFor="vehicle_in_inventory" className="text-sm text-gray-700 cursor-pointer">
                {form.vehicle_in_inventory ? "已入库（可形成特别程序证据链）" : "未入库（路径D将屏蔽）"}
              </label>
            </div>
          </Field>
          <Field label="司法风险：失信被执行人">
            <div className="flex items-center gap-2 h-10">
              <input
                type="checkbox"
                checked={form.debtor_dishonest_enforced}
                onChange={(e) => upd("debtor_dishonest_enforced", e.target.checked)}
                className="w-4 h-4"
                id="debtor_dishonest_enforced"
              />
              <label htmlFor="debtor_dishonest_enforced" className="text-sm text-gray-700 cursor-pointer">
                {form.debtor_dishonest_enforced ? "否决继续等待赎车" : "未命中强司法阻断"}
              </label>
            </div>
          </Field>
          <Field label="寻车线索评分">
            <input
              className="inp"
              type="number"
              min="0"
              max="100"
              value={form.external_find_car_score || ""}
              onChange={(e) => upd("external_find_car_score", +e.target.value)}
              placeholder="0-100，可由外部数据接口生成"
            />
          </Field>
        </div>
        {form.debtor_dishonest_enforced && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            已命中失信被执行人信号，路径A“继续等待赎车”会被系统自动排除，不进入推荐候选。
          </div>
        )}
        {specialProcedureBlocked && (
          <div className="p-3 bg-amber-50 border border-amber-200 rounded-lg text-amber-800 text-sm">
            当前条件下，路径D“实现担保物权特别程序”不会进入推荐候选。硬前提为：车辆已收回、已入库形成证据链，且逾期阶段至少达到 M3。
            {!form.vehicle_recovered && " 当前车辆未收回，请先完成收车。"}
            {form.vehicle_recovered && !form.vehicle_in_inventory && " 当前车辆未入库，请先完成入库登记。"}
            {!specialProcedureStageAllowed && " 当前为 M1/M2，建议优先催收、重组或常规诉讼评估。"}
          </div>
        )}

        <hr className="border-gray-200" />
        <h2 className="font-semibold text-gray-900">竞拍参数</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="预计成交天数">
            <input className="inp" type="number" value={form.expected_sale_days} onChange={(e) => upd("expected_sale_days", +e.target.value)} />
          </Field>
          <Field label="竞拍佣金比例">
            <input className="inp" type="number" step="0.01" value={form.commission_rate} onChange={(e) => upd("commission_rate", +e.target.value)} />
          </Field>
          <Field label="逾期年利率 (%)">
            <input className="inp" type="number" value={form.annual_interest_rate} onChange={(e) => upd("annual_interest_rate", +e.target.value)} />
          </Field>
        </div>

        <hr className="border-gray-200" />
        <h2 className="font-semibold text-gray-900">常规诉讼律师费</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="固定律师费 (元)">
            <input className="inp" type="number" value={form.litigation_lawyer_fee} onChange={(e) => upd("litigation_lawyer_fee", +e.target.value)} />
          </Field>
          <Field label="有回款比例律师费">
            <div className="flex items-center gap-2 h-10">
              <input type="checkbox" checked={form.litigation_has_recovery_fee} onChange={(e) => upd("litigation_has_recovery_fee", e.target.checked)} className="w-4 h-4" />
              <span className="text-sm text-gray-600">启用</span>
            </div>
          </Field>
          {form.litigation_has_recovery_fee && (
            <Field label="回款比例 (%)">
              <input className="inp" type="number" step="0.01" value={form.litigation_recovery_fee_rate} onChange={(e) => upd("litigation_recovery_fee_rate", +e.target.value)} />
            </Field>
          )}
        </div>
        <p className="text-xs text-gray-400">诉讼费、执行费、保全费将根据逾期金额按现行法律标准自动计算</p>

        <hr className="border-gray-200" />
        <h2 className="font-semibold text-gray-900">担保物权特别程序律师费</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="固定律师费 (元)">
            <input className="inp" type="number" value={form.special_lawyer_fee} onChange={(e) => upd("special_lawyer_fee", +e.target.value)} />
          </Field>
          <Field label="有回款比例律师费">
            <div className="flex items-center gap-2 h-10">
              <input type="checkbox" checked={form.special_has_recovery_fee} onChange={(e) => upd("special_has_recovery_fee", e.target.checked)} className="w-4 h-4" />
              <span className="text-sm text-gray-600">启用</span>
            </div>
          </Field>
          {form.special_has_recovery_fee && (
            <Field label="回款比例 (%)">
              <input className="inp" type="number" step="0.01" value={form.special_recovery_fee_rate} onChange={(e) => upd("special_recovery_fee_rate", +e.target.value)} />
            </Field>
          )}
        </div>

        <hr className="border-gray-200" />
        <h2 className="font-semibold text-gray-900">分期重组/和解参数</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Field label="月还款额 (元)">
            <input className="inp" type="number" value={form.restructure_monthly_payment || ""} onChange={(e) => upd("restructure_monthly_payment", +e.target.value)} placeholder="0=按逾期额/12自动" />
          </Field>
          <Field label="重组期数 (月)">
            <input className="inp" type="number" value={form.restructure_months} onChange={(e) => upd("restructure_months", +e.target.value)} />
          </Field>
          <Field label="再违约率">
            <input className="inp" type="number" step="0.05" value={form.restructure_redefault_rate} onChange={(e) => upd("restructure_redefault_rate", +e.target.value)} />
          </Field>
        </div>

        <button
          className="mt-4 px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 font-medium"
          onClick={handleSimulate}
          disabled={loading}
        >
          {loading ? "模拟计算中..." : "开始五路径模拟"}
        </button>
      </div>

      {/* ====== 结果展示 ====== */}
      {result && (
        <>
          {/* 推荐 */}
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-xl">
            <div className="font-bold text-lg text-blue-900 mb-1">
              系统推荐：路径{result.best_path} — {pathNames[result.best_path]}
            </div>
            <div className="text-sm text-gray-700 whitespace-pre-line">{result.recommendation}</div>
          </div>

          {/* 五路径卡片 */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* A: 等待赎车 */}
            <PathCard
              title="路径A：等待赎车"
              best={result.best_path === "A"}
              unavailable={result.path_a.available === false}
              unavailableReason={result.path_a.unavailable_reason || ""}
            >
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs">
                    <th className="text-left py-1">天数</th>
                    <th className="text-right py-1">贬值</th>
                    <th className="text-right py-1">持有成本</th>
                    <th className="text-right py-1">成功率</th>
                    <th className="text-right py-1">边际收益</th>
                  </tr>
                </thead>
                <tbody>
                  {result.path_a.timepoints.map((tp: TimePoint) => (
                    <tr key={tp.days} className="border-t">
                      <td className="py-1.5">{tp.days}天</td>
                      <td className="text-right text-red-500">-{fmt(tp.depreciation_amount)}</td>
                      <td className="text-right text-red-500">-{fmt(tp.total_holding_cost)}</td>
                      <td className="text-right">{(tp.success_probability * 100).toFixed(0)}%</td>
                      <td className={`text-right font-medium ${tp.future_marginal_net_benefit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                        {fmt(tp.future_marginal_net_benefit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </PathCard>

            {/* B: 常规诉讼 */}
            <PathCard title="路径B：常规诉讼" best={result.best_path === "B"}>
              <div className="text-xs text-gray-500 mb-2 space-y-0.5">
                <div>诉讼费: ¥{fmt(result.path_b.legal_cost.court_fee)} | 执行费: ¥{fmt(result.path_b.legal_cost.execution_fee)}</div>
                <div>保全费: ¥{fmt(result.path_b.legal_cost.preservation_fee)} | 律师费: ¥{fmt(result.path_b.legal_cost.lawyer_fee_fixed)}</div>
              </div>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs">
                    <th className="text-left py-1">情景</th>
                    <th className="text-right py-1">拍卖价</th>
                    <th className="text-right py-1">总成本</th>
                    <th className="text-right py-1">成功率</th>
                    <th className="text-right py-1">边际收益</th>
                  </tr>
                </thead>
                <tbody>
                  {result.path_b.scenarios.map((s: LitigationScenario) => (
                    <tr key={s.label} className="border-t">
                      <td className="py-1.5 text-xs">{s.label}</td>
                      <td className="text-right">{fmt(s.expected_auction_price)}</td>
                      <td className="text-right text-red-500">-{fmt(s.total_cost)}</td>
                      <td className="text-right">{(s.success_probability * 100).toFixed(0)}%</td>
                      <td className={`text-right font-medium ${s.future_marginal_net_benefit >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                        {fmt(s.future_marginal_net_benefit)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </PathCard>

            {/* C: 立即竞拍 */}
            <PathCard
              title="路径C：立即竞拍"
              best={result.best_path === "C"}
              unavailable={result.path_c.available === false}
              unavailableReason={result.path_c.unavailable_reason || ""}
            >
              <div className="space-y-2 text-sm">
                <Row label="预计成交天数" value={`${result.path_c.expected_sale_days}天`} />
                <Row label="成交价" value={`¥${fmt(result.path_c.sale_price)}`} />
                <Row label="佣金" value={`-¥${fmt(result.path_c.commission)}`} red />
                <Row label="停车费" value={`-¥${fmt(result.path_c.parking_during_sale)}`} red />
                {result.path_c.recovery_cost > 0 && (
                  <Row label="收车成本" value={`-¥${fmt(result.path_c.recovery_cost)}`} red />
                )}
                <Row label="动态成功率" value={`${(result.path_c.success_probability * 100).toFixed(0)}%`} />
                {result.path_c.sunk_cost_excluded > 0 && (
                  <Row label="已剔除沉没成本" value={`¥${fmt(result.path_c.sunk_cost_excluded)}`} />
                )}
                <div className="border-t pt-2">
                  <Row label="未来边际净收益" value={`¥${fmt(result.path_c.future_marginal_net_benefit)}`} bold green />
                </div>
              </div>
            </PathCard>

            {/* D: 担保物权特别程序 */}
            <PathCard
              title="路径D：担保物权特别程序"
              best={result.best_path === "D"}
              unavailable={result.path_d.available === false}
              unavailableReason={result.path_d.unavailable_reason || ""}
            >
              <div className="text-xs text-gray-500 mb-2 space-y-0.5">
                <div>申请费: ¥{fmt(result.path_d.legal_cost.court_fee)} | 执行费: ¥{fmt(result.path_d.legal_cost.execution_fee)}</div>
                <div>律师费: ¥{fmt(result.path_d.legal_cost.lawyer_fee_fixed)}</div>
              </div>
              <div className="space-y-2 text-sm">
                <Row label="周期" value={`约${result.path_d.duration_months}个月`} />
                {result.path_d.auction_rounds.map((r: AuctionRound) => (
                  <Row key={r.round_name} label={`${r.round_name}(${(r.discount_rate * 100).toFixed(0)}%)`} value={`¥${fmt(r.auction_price)}`} />
                ))}
                <Row label="期望拍卖价" value={`¥${fmt(result.path_d.expected_auction_price)}`} />
                <Row label="法律费用合计" value={`-¥${fmt(result.path_d.legal_cost.total_legal_cost)}`} red />
                <Row label="停车+利息" value={`-¥${fmt(result.path_d.parking_cost + result.path_d.interest_cost)}`} red />
                <Row label="动态成功率" value={`${(result.path_d.success_probability * 100).toFixed(0)}%`} />
                {result.path_d.sunk_cost_excluded > 0 && (
                  <Row label="已剔除沉没成本" value={`¥${fmt(result.path_d.sunk_cost_excluded)}`} />
                )}
                <div className="border-t pt-2">
                  <Row label="未来边际净收益" value={`¥${fmt(result.path_d.future_marginal_net_benefit)}`} bold green />
                </div>
              </div>
            </PathCard>

            {/* E: 分期重组 */}
            <PathCard title="路径E：分期重组/和解" best={result.best_path === "E"}>
              <div className="space-y-2 text-sm">
                <Row label="月还款额" value={`¥${fmt(result.path_e.monthly_payment)}`} />
                <Row label="还款期数" value={`${result.path_e.total_months}个月`} />
                <Row label="预期总回收" value={`¥${fmt(result.path_e.total_expected_recovery)}`} />
                <Row label="再违约率" value={`${(result.path_e.redefault_rate * 100).toFixed(0)}%`} />
                <Row label="风险调整后回收" value={`¥${fmt(result.path_e.risk_adjusted_recovery)}`} />
                <Row label="管理成本" value={`-¥${fmt(result.path_e.holding_cost)}`} red />
                <Row label="动态成功率" value={`${(result.path_e.success_probability * 100).toFixed(0)}%`} />
                <div className="border-t pt-2">
                  <Row label="未来边际净收益" value={`¥${fmt(result.path_e.future_marginal_net_benefit)}`} bold green />
                </div>
              </div>
            </PathCard>
          </div>

          {/* 报告 */}
          <div className="bg-white border rounded-xl p-5 flex items-center gap-4">
            <button className="px-4 py-2 bg-gray-900 text-white rounded-lg hover:bg-gray-800 text-sm" onClick={handleReport}>
              生成报告预览
            </button>
            {reportHtml && (
              <button className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm" onClick={printReport}>
                打印/保存PDF
              </button>
            )}
          </div>
          {reportHtml && (
            <div className="bg-white border rounded-xl p-4">
              <iframe srcDoc={reportHtml} className="w-full h-[800px] border rounded" title="报告预览" />
            </div>
          )}
        </>
      )}

      <style>{`.inp { width: 100%; padding: 0.5rem 0.75rem; border: 1px solid #d1d5db; border-radius: 0.5rem; font-size: 0.875rem; outline: none; } .inp:focus { border-color: #3b82f6; box-shadow: 0 0 0 2px rgba(59,130,246,0.15); }`}</style>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
    </div>
  );
}

function PathCard({
  title,
  best,
  unavailable,
  unavailableReason,
  children,
}: {
  title: string;
  best: boolean;
  unavailable?: boolean;
  unavailableReason?: string;
  children: React.ReactNode;
}) {
  const base = "bg-white border rounded-xl p-4 relative";
  const highlight = best && !unavailable ? "ring-2 ring-green-400 border-green-300" : "";
  const disabled = unavailable ? "opacity-60 grayscale" : "";
  return (
    <div className={`${base} ${highlight} ${disabled}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-sm text-gray-900">{title}</h3>
        {best && !unavailable && (
          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">
            推荐
          </span>
        )}
        {unavailable && (
          <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded-full font-medium">
            不可用
          </span>
        )}
      </div>
      {unavailable && unavailableReason && (
        <div className="mb-3 p-2 bg-amber-50 border border-amber-200 rounded text-xs text-amber-800">
          {unavailableReason}
        </div>
      )}
      {children}
    </div>
  );
}

function Row({ label, value, red, green, bold }: { label: string; value: string; red?: boolean; green?: boolean; bold?: boolean }) {
  return (
    <div className="flex justify-between">
      <span className={`text-gray-500 ${bold ? "font-semibold text-gray-700" : ""}`}>{label}</span>
      <span className={`${bold ? "font-bold text-lg" : "font-medium"} ${red ? "text-red-500" : ""} ${green ? "text-emerald-600" : ""}`}>
        {value}
      </span>
    </div>
  );
}
