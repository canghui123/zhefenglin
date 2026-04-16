"use client";

import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  uploadExcel,
  calculatePackage,
  getPackage,
  suggestBuyout,
  type PricingParameters,
  type PackageCalculationResult,
  type BuyoutSuggestion,
} from "@/lib/api";
import { pollJob } from "@/lib/jobs";

function formatMoney(n: number) {
  return n.toLocaleString("zh-CN", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

type Strategy = "direct" | "discount" | "ai_suggest";

const FIELD_LABELS: Record<string, string> = {
  car_description: "车型",
  vin: "VIN",
  first_registration: "上牌日期",
  mileage: "里程",
  gps_online: "GPS",
  insurance_lapsed: "脱保",
  ownership_transferred: "过户",
  loan_principal: "本金/债权",
  buyout_price: "买断价",
};

export default function AssetPricingPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [suggesting, setSuggesting] = useState(false);
  const [packageId, setPackageId] = useState<number | null>(null);
  const [parseInfo, setParseInfo] = useState<{
    total_rows: number;
    success_rows: number;
    errors: Array<{ row_number: number; field: string; message: string }>;
    column_mapping: Record<string, string>;
    unmapped_columns: string[];
    suggested_strategy: Strategy;
    strategy_message: string;
  } | null>(null);
  const [strategy, setStrategy] = useState<Strategy>("direct");
  const [discountRate, setDiscountRate] = useState<number>(0.3);
  const [aiSuggestions, setAiSuggestions] = useState<BuyoutSuggestion[] | null>(null);
  const [aiComment, setAiComment] = useState<string>("");
  const [aiOverrides, setAiOverrides] = useState<Record<number, number>>({});
  const [result, setResult] = useState<PackageCalculationResult | null>(null);
  const [error, setError] = useState("");

  const [params, setParams] = useState<PricingParameters>({
    towing_cost: 1500,
    daily_parking: 30,
    capital_rate: 8,
    disposal_period: 45,
    vehicle_condition: "good",
  });

  function clearAiState() {
    setAiSuggestions(null);
    setAiOverrides({});
    setAiComment("");
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError("");
    setResult(null);
    clearAiState();
    try {
      const res = await uploadExcel(file);
      setPackageId(res.package_id);
      setParseInfo({
        total_rows: res.parse_result.total_rows,
        success_rows: res.parse_result.success_rows,
        errors: res.parse_result.errors,
        column_mapping: res.parse_result.column_mapping || {},
        unmapped_columns: res.parse_result.unmapped_columns || [],
        suggested_strategy: res.parse_result.suggested_strategy || "direct",
        strategy_message: res.parse_result.strategy_message || "",
      });
      setStrategy(res.parse_result.suggested_strategy || "direct");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }

  async function handleAiSuggest() {
    if (!packageId) return;
    setSuggesting(true);
    setError("");
    try {
      const res = await suggestBuyout(packageId, params.vehicle_condition || "good");
      setAiSuggestions(res.suggestions);
      setAiComment(res.ai_comment);
      const overrides: Record<number, number> = {};
      res.suggestions.forEach((s) => {
        overrides[s.row_number] = s.suggested_buyout_mid;
      });
      setAiOverrides(overrides);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "AI建议失败");
    } finally {
      setSuggesting(false);
    }
  }

  async function handleCalculate() {
    if (!packageId) return;

    // 策略校验
    if (strategy === "discount" && (!discountRate || discountRate <= 0 || discountRate > 1)) {
      setError("请输入有效的折扣率（0-1 之间，如 0.3 表示按本金30%买断）");
      return;
    }
    if (strategy === "ai_suggest" && !aiSuggestions) {
      setError('请先点击"获取 AI 建议"生成买断价建议');
      return;
    }

    setCalculating(true);
    setError("");
    try {
      const finalParams: PricingParameters = {
        ...params,
        buyout_strategy: strategy,
        discount_rate: strategy === "discount" ? discountRate : null,
      };
      const overrides = strategy === "ai_suggest" ? aiOverrides : undefined;
      const { job_id } = await calculatePackage(packageId, finalParams, overrides);
      const job = await pollJob(job_id);
      if (job.status === "failed") {
        throw new Error(job.error_message || "计算失败");
      }
      const pkg = await getPackage(packageId);
      if (pkg.results) {
        setResult(pkg.results);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "计算失败");
    } finally {
      setCalculating(false);
    }
  }

  const hasBuyoutPrice = parseInfo && Object.values(parseInfo.column_mapping).includes("buyout_price");
  const hasPrincipal = parseInfo && Object.values(parseInfo.column_mapping).includes("loan_principal");

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">资产包买断AI定价</h1>
        <p className="text-gray-500 mt-1">上传甲方Excel资产包，AI自动计算利润与风险</p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Step 1: Upload */}
      <Card>
        <CardHeader>
          <CardTitle>第一步：上传Excel资产包</CardTitle>
          <CardDescription>
            支持 .xlsx 格式。系统会自动识别 车型、VIN、上牌日期、里程、本金、买断价等字段。
            <span className="text-orange-600">为保证估值准确，强烈建议表格中包含 上牌日期 和 里程 两列。</span>
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Input
              type="file"
              accept=".xlsx,.xls"
              onChange={(e) => setFile(e.target.files?.[0] || null)}
              className="max-w-md"
            />
            <Button onClick={handleUpload} disabled={!file || uploading}>
              {uploading ? "解析中..." : "上传并解析"}
            </Button>
          </div>

          {parseInfo && (
            <div className="mt-4 text-sm space-y-3">
              <Badge variant="default">
                成功解析 {parseInfo.success_rows}/{parseInfo.total_rows} 行
              </Badge>

              {/* 列识别结果 */}
              <div className="bg-gray-50 rounded-lg p-3">
                <div className="font-medium text-gray-700 mb-2">列识别结果：</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(parseInfo.column_mapping).map(([excelCol, field]) => (
                    <span key={excelCol} className="inline-flex items-center px-2 py-1 rounded bg-green-100 text-green-700 text-xs">
                      {excelCol} → {FIELD_LABELS[field] || field}
                    </span>
                  ))}
                </div>
                {parseInfo.unmapped_columns.length > 0 && (
                  <div className="mt-2">
                    <span className="text-gray-500">未识别的列：</span>
                    {parseInfo.unmapped_columns.map((col, i) => (
                      <span key={i} className="inline-flex items-center px-2 py-1 ml-1 rounded bg-yellow-100 text-yellow-700 text-xs">
                        {col}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* 策略提示 */}
              <Alert>
                <AlertDescription>
                  <strong>建议策略：</strong>{parseInfo.strategy_message}
                </AlertDescription>
              </Alert>

              {parseInfo.errors.length > 0 && (
                <div className="text-orange-600">
                  {parseInfo.errors.slice(0, 5).map((err, i) => (
                    <div key={i}>
                      第{err.row_number}行 [{err.field}]: {err.message}
                    </div>
                  ))}
                  {parseInfo.errors.length > 5 && (
                    <div>...还有{parseInfo.errors.length - 5}个错误</div>
                  )}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Step 2: Strategy + Parameters */}
      {packageId && parseInfo && (
        <Card>
          <CardHeader>
            <CardTitle>第二步：选择买断价策略 & 调整参数</CardTitle>
            <CardDescription>根据Excel内容选择买断价计算方式，并设置车况与成本参数</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* 买断价策略选择 */}
            <div>
              <Label className="text-base font-medium mb-3 block">买断价计算策略</Label>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setStrategy("direct");
                    clearAiState();
                  }}
                  disabled={!hasBuyoutPrice}
                  className={`text-left p-4 rounded-lg border-2 transition ${
                    strategy === "direct" ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
                  } ${!hasBuyoutPrice ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  <div className="font-medium">① 使用 Excel 买断价</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {hasBuyoutPrice ? "已识别到买断价列，直接使用" : "未识别到买断价列，不可选"}
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setStrategy("discount");
                    clearAiState();
                  }}
                  disabled={!hasPrincipal}
                  className={`text-left p-4 rounded-lg border-2 transition ${
                    strategy === "discount" ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
                  } ${!hasPrincipal ? "opacity-50 cursor-not-allowed" : ""}`}
                >
                  <div className="font-medium">② 本金 × 折扣率</div>
                  <div className="text-xs text-gray-500 mt-1">
                    {hasPrincipal ? "按本金的指定折扣计算买断价" : "未识别到本金列，不可选"}
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => {
                    setStrategy("ai_suggest");
                    clearAiState();
                  }}
                  className={`text-left p-4 rounded-lg border-2 transition ${
                    strategy === "ai_suggest" ? "border-blue-500 bg-blue-50" : "border-gray-200 hover:border-gray-300"
                  }`}
                >
                  <div className="font-medium">③ AI 智能建议</div>
                  <div className="text-xs text-gray-500 mt-1">
                    结合车300估值、车况、里程给出建议价格区间
                  </div>
                </button>
              </div>
            </div>

            {/* 折扣率输入 */}
            {strategy === "discount" && (
              <div className="bg-blue-50 p-4 rounded-lg">
                <Label>买断折扣率（本金的百分比）</Label>
                <div className="flex items-center gap-3 mt-2">
                  <Input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={discountRate}
                    onChange={(e) => setDiscountRate(Number(e.target.value))}
                    className="max-w-xs"
                  />
                  <span className="text-sm text-gray-600">
                    = {(discountRate * 100).toFixed(0)}% （即按本金的 {(discountRate * 100).toFixed(0)}% 买断）
                  </span>
                </div>
              </div>
            )}

            {/* AI 建议面板 */}
            {strategy === "ai_suggest" && (
              <div className="bg-blue-50 p-4 rounded-lg space-y-3">
                <div className="flex items-center gap-3">
                  <Button onClick={handleAiSuggest} disabled={suggesting} variant="secondary">
                    {suggesting ? "AI 分析中..." : aiSuggestions ? "重新获取AI建议" : "获取 AI 建议"}
                  </Button>
                  {aiSuggestions && (
                    <span className="text-sm text-gray-600">
                      已生成 {aiSuggestions.length} 条建议，总建议买断成本 {formatMoney(
                        aiSuggestions.reduce((s, x) => s + (aiOverrides[x.row_number] || x.suggested_buyout_mid), 0)
                      )} 元
                    </span>
                  )}
                </div>
                {aiComment && (
                  <Alert>
                    <AlertDescription>
                      <div className="font-medium mb-1">AI 综合评价：</div>
                      <div className="whitespace-pre-wrap text-sm">{aiComment}</div>
                    </AlertDescription>
                  </Alert>
                )}
                {aiSuggestions && aiSuggestions.length > 0 && (
                  <div className="overflow-x-auto max-h-96 overflow-y-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>行号</TableHead>
                          <TableHead>车型</TableHead>
                          <TableHead className="text-right">车300估值</TableHead>
                          <TableHead className="text-right">建议区间</TableHead>
                          <TableHead className="text-right">采用买断价（可编辑）</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {aiSuggestions.map((s) => (
                          <TableRow key={s.row_number}>
                            <TableCell>{s.row_number}</TableCell>
                            <TableCell className="max-w-[200px] truncate">{s.car_description}</TableCell>
                            <TableCell className="text-right">
                              {s.che300_valuation ? formatMoney(s.che300_valuation) : "-"}
                            </TableCell>
                            <TableCell className="text-right text-xs text-gray-500">
                              {formatMoney(s.suggested_buyout_low)} ~ {formatMoney(s.suggested_buyout_high)}
                            </TableCell>
                            <TableCell className="text-right">
                              <Input
                                type="number"
                                value={aiOverrides[s.row_number] ?? s.suggested_buyout_mid}
                                onChange={(e) =>
                                  setAiOverrides({ ...aiOverrides, [s.row_number]: Number(e.target.value) })
                                }
                                className="w-28 ml-auto text-right"
                              />
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </div>
            )}

            {/* 车况选择器 */}
            <div>
              <Label className="text-base font-medium mb-2 block">预期车况（影响车300估值取价）</Label>
              <div className="flex gap-3">
                {[
                  { value: "excellent", label: "车况优秀", desc: "个人车、少事故、维保齐全" },
                  { value: "good", label: "车况良好 (默认)", desc: "正常磨损、无重大事故" },
                  { value: "normal", label: "车况一般", desc: "有维修记录/外观瑕疵" },
                ].map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => {
                      if (params.vehicle_condition !== opt.value) {
                        setParams({ ...params, vehicle_condition: opt.value as "excellent" | "good" | "normal" });
                        clearAiState();
                      }
                    }}
                    className={`flex-1 p-3 rounded-lg border-2 text-left transition ${
                      params.vehicle_condition === opt.value
                        ? "border-blue-500 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="font-medium">{opt.label}</div>
                    <div className="text-xs text-gray-500 mt-1">{opt.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            {/* 成本参数 */}
            <div>
              <Label className="text-base font-medium mb-3 block">成本参数</Label>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
                <div>
                  <Label>单台拖车费 (元)</Label>
                  <Input
                    type="number"
                    value={params.towing_cost}
                    onChange={(e) => setParams({ ...params, towing_cost: Number(e.target.value) })}
                  />
                </div>
                <div>
                  <Label>日停车费 (元/天)</Label>
                  <Input
                    type="number"
                    value={params.daily_parking}
                    onChange={(e) => setParams({ ...params, daily_parking: Number(e.target.value) })}
                  />
                </div>
                <div>
                  <Label>资金成本年化率 (%)</Label>
                  <Input
                    type="number"
                    value={params.capital_rate}
                    onChange={(e) => setParams({ ...params, capital_rate: Number(e.target.value) })}
                  />
                </div>
                <div>
                  <Label>预期处置周期 (天)</Label>
                  <Input
                    type="number"
                    value={params.disposal_period}
                    onChange={(e) => setParams({ ...params, disposal_period: Number(e.target.value) })}
                  />
                </div>
              </div>
            </div>

            <Button onClick={handleCalculate} disabled={calculating} size="lg">
              {calculating ? "计算中..." : "运行定价计算"}
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Step 3: Results */}
      {result && (
        <>
          {/* Summary cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500">总包买断成本</div>
                <div className="text-2xl font-bold">
                  {formatMoney(result.summary.total_buyout_cost)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500">预期总收入</div>
                <div className="text-2xl font-bold text-blue-600">
                  {formatMoney(result.summary.total_expected_revenue)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500">预期净利润</div>
                <div
                  className={`text-2xl font-bold ${
                    result.summary.total_net_profit >= 0 ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {formatMoney(result.summary.total_net_profit)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500">整体ROI</div>
                <div className="text-2xl font-bold">{result.summary.overall_roi}%</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500">建议最高折扣</div>
                <div className="text-2xl font-bold text-orange-600">
                  {(result.summary.recommended_max_discount * 100).toFixed(1)}%
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Risk alerts */}
          {result.summary.risk_alerts.length > 0 && (
            <Alert variant="destructive">
              <AlertDescription>
                <div className="font-semibold mb-1">风险预警</div>
                {result.summary.risk_alerts.map((alert, i) => (
                  <div key={i}>- {alert}</div>
                ))}
              </AlertDescription>
            </Alert>
          )}

          {/* Detail table */}
          <Card>
            <CardHeader>
              <CardTitle>逐车明细 ({result.assets.length}台)</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>行号</TableHead>
                    <TableHead>车型</TableHead>
                    <TableHead className="text-right">买断价</TableHead>
                    <TableHead className="text-right">车300估值</TableHead>
                    <TableHead className="text-right">总成本</TableHead>
                    <TableHead className="text-right">预期收入</TableHead>
                    <TableHead className="text-right">净利润</TableHead>
                    <TableHead className="text-right">利润率</TableHead>
                    <TableHead>风险标签</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.assets.map((asset) => (
                    <TableRow
                      key={asset.row_number}
                      className={asset.net_profit < 0 ? "bg-red-50" : ""}
                    >
                      <TableCell>{asset.row_number}</TableCell>
                      <TableCell className="max-w-[200px] truncate">
                        {asset.car_description}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatMoney(asset.buyout_price)}
                      </TableCell>
                      <TableCell className="text-right">
                        {asset.che300_valuation
                          ? formatMoney(asset.che300_valuation)
                          : "-"}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatMoney(asset.total_cost)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatMoney(asset.expected_revenue)}
                      </TableCell>
                      <TableCell
                        className={`text-right font-medium ${
                          asset.net_profit >= 0 ? "text-green-600" : "text-red-600"
                        }`}
                      >
                        {formatMoney(asset.net_profit)}
                      </TableCell>
                      <TableCell className="text-right">{asset.profit_margin}%</TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {asset.risk_flags.map((flag, i) => (
                            <Badge key={i} variant="destructive" className="text-xs">
                              {flag}
                            </Badge>
                          ))}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
