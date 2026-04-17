"use client";

import { useState } from "react";
import { useSession } from "@/components/auth/session-provider";
import { simulateSandbox, generateReport, downloadReport, type SandboxResult, type TimePoint, type LitigationScenario, type AuctionRound } from "@/lib/api";
import { hasFeature } from "@/lib/auth";
import { pollJob } from "@/lib/jobs";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

interface FormState {
  car_description: string;
  entry_date: string;
  overdue_amount: number;
  che300_value: number;
  vehicle_type: string;
  vehicle_age_years: number;
  daily_parking: number;
  recovery_cost: number;
  annual_interest_rate: number;
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
  const { user } = useSession();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [result, setResult] = useState<SandboxResult | null>(null);
  const [reportHtml, setReportHtml] = useState("");
  const canExportAudit = hasFeature(user, "audit.export");

  const [form, setForm] = useState<FormState>({
    car_description: "",
    entry_date: "",
    overdue_amount: 0,
    che300_value: 0,
    vehicle_type: "auto",
    vehicle_age_years: 3,
    daily_parking: 30,
    recovery_cost: 0,
    annual_interest_rate: 24,
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
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleSimulate() {
    if (!form.car_description || !form.entry_date || !form.che300_value) {
      setError("请填写车辆描述、入库日期和车300估值");
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
    if (!canExportAudit) {
      setError("当前套餐未开通审计导出能力，暂不支持打印或保存 PDF");
      return;
    }
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
          <Field label="入库日期">
            <input className="inp" type="date" value={form.entry_date} onChange={(e) => upd("entry_date", e.target.value)} />
          </Field>
          <Field label="逾期金额 (元)">
            <input className="inp" type="number" value={form.overdue_amount || ""} onChange={(e) => upd("overdue_amount", +e.target.value)} />
          </Field>
          <Field label="当前车300估值 (元)">
            <input className="inp" type="number" value={form.che300_value || ""} onChange={(e) => upd("che300_value", +e.target.value)} />
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
          <Field label="日停车费 (元)">
            <input className="inp" type="number" value={form.daily_parking} onChange={(e) => upd("daily_parking", +e.target.value)} />
          </Field>
        </div>

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
            <PathCard title="路径A：等待赎车" best={result.best_path === "A"}>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-gray-500 text-xs">
                    <th className="text-left py-1">天数</th>
                    <th className="text-right py-1">贬值</th>
                    <th className="text-right py-1">持有成本</th>
                    <th className="text-right py-1">净头寸</th>
                  </tr>
                </thead>
                <tbody>
                  {result.path_a.timepoints.map((tp: TimePoint) => (
                    <tr key={tp.days} className="border-t">
                      <td className="py-1.5">{tp.days}天</td>
                      <td className="text-right text-red-500">-{fmt(tp.depreciation_amount)}</td>
                      <td className="text-right text-red-500">-{fmt(tp.total_holding_cost)}</td>
                      <td className={`text-right font-medium ${tp.net_position >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                        {fmt(tp.net_position)}
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
                    <th className="text-right py-1">净回收</th>
                  </tr>
                </thead>
                <tbody>
                  {result.path_b.scenarios.map((s: LitigationScenario) => (
                    <tr key={s.label} className="border-t">
                      <td className="py-1.5 text-xs">{s.label}</td>
                      <td className="text-right">{fmt(s.expected_auction_price)}</td>
                      <td className="text-right text-red-500">-{fmt(s.total_cost)}</td>
                      <td className={`text-right font-medium ${s.net_recovery >= 0 ? "text-emerald-600" : "text-red-600"}`}>
                        {fmt(s.net_recovery)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </PathCard>

            {/* C: 立即竞拍 */}
            <PathCard title="路径C：立即竞拍" best={result.best_path === "C"}>
              <div className="space-y-2 text-sm">
                <Row label="预计成交天数" value={`${result.path_c.expected_sale_days}天`} />
                <Row label="成交价" value={`¥${fmt(result.path_c.sale_price)}`} />
                <Row label="佣金" value={`-¥${fmt(result.path_c.commission)}`} red />
                <Row label="停车费" value={`-¥${fmt(result.path_c.parking_during_sale)}`} red />
                {result.path_c.recovery_cost > 0 && (
                  <Row label="收车成本" value={`-¥${fmt(result.path_c.recovery_cost)}`} red />
                )}
                <div className="border-t pt-2">
                  <Row label="净回款" value={`¥${fmt(result.path_c.net_recovery)}`} bold green />
                </div>
              </div>
            </PathCard>

            {/* D: 担保物权特别程序 */}
            <PathCard title="路径D：担保物权特别程序" best={result.best_path === "D"}>
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
                <div className="border-t pt-2">
                  <Row label="净回收" value={`¥${fmt(result.path_d.net_recovery)}`} bold green />
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
                <div className="border-t pt-2">
                  <Row label="净回收" value={`¥${fmt(result.path_e.net_recovery)}`} bold green />
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
              <div className="space-y-2">
                <button
                  className="px-4 py-2 border rounded-lg hover:bg-gray-50 text-sm disabled:opacity-50 disabled:cursor-not-allowed"
                  onClick={printReport}
                  disabled={!canExportAudit}
                >
                  {canExportAudit ? "打印/保存PDF" : "打印/保存PDF未开通"}
                </button>
                {!canExportAudit && (
                  <p className="text-xs text-gray-500">
                    当前套餐未开通审计导出能力，如需打印或保存 PDF，请升级到支持 `audit.export` 的套餐。
                  </p>
                )}
              </div>
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

function PathCard({ title, best, children }: { title: string; best: boolean; children: React.ReactNode }) {
  return (
    <div className={`bg-white border rounded-xl p-4 ${best ? "ring-2 ring-green-400 border-green-300" : ""}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold text-sm text-gray-900">{title}</h3>
        {best && <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded-full font-medium">推荐</span>}
      </div>
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
