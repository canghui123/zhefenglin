"use client";

import { useEffect, useState } from "react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ApiError,
  analyzeBuyerOffer,
  calculatePackage,
  createApprovalRequest,
  downloadAssetPackageReportPdf,
  getPackage,
  listApprovalRequests,
  uploadExcel,
  type ApprovalContext,
  type ApprovalRequestInfo,
  type AssetFieldOverride,
  type PackageCalculationResult,
  type ParsedAssetInfo,
  type PricingParameters,
} from "@/lib/api";
import { pollJob } from "@/lib/jobs";

type AssetPackageType = "inventory" | "non_inventory";
type BatchCorrectionTarget = "risk" | "missing_principal" | "missing_valuation" | "all";

const SESSION_KEY = "asset-pricing:seller-transfer:v2";

const FIELD_LABELS: Record<string, string> = {
  car_description: "车型",
  vin: "VIN",
  first_registration: "上牌日期",
  mileage: "里程",
  gps_online: "GPS",
  insurance_lapsed: "脱保",
  ownership_transferred: "过户",
  loan_principal: "本金/债权",
};

const PACKAGE_TYPE_LABELS: Record<AssetPackageType, string> = {
  inventory: "在库车资产包",
  non_inventory: "非在库车资产包",
};

const STRATEGY_LABELS: Record<string, string> = {
  inventory_valuation_discount: "在库车：估值折扣",
  non_inventory_principal_discount: "非在库：本金折扣",
  seller_transfer_analysis: "出让方定价分析",
};

const CONFIDENCE_LABELS: Record<string, string> = {
  high: "高可信",
  medium: "中可信",
  low: "低可信",
  very_low: "极低可信",
  mock: "模拟估值",
  unknown: "未知",
};

const TRADEABILITY_LABELS: Record<string, string> = {
  A: "强适配",
  B: "较好适配",
  C: "需补强",
  D: "交易阻力高",
  E: "暂不适配",
};

function formatMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  });
}

function formatPercent(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${(value * 100).toFixed(1)}%`;
}

function formatPercentPoint(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return `${value.toFixed(1)}%`;
}

function toDateInputValue(value: string | null | undefined) {
  return value ? value.slice(0, 10) : "";
}

function parseOptionalNumber(value: string) {
  if (!value.trim()) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseOptionalBoolean(value: string) {
  if (value === "true") return true;
  if (value === "false") return false;
  return undefined;
}

function booleanInputValue(value: boolean | null | undefined) {
  if (value === true) return "true";
  if (value === false) return "false";
  return "";
}

function cleanSingleOverride(patch: AssetFieldOverride) {
  const cleaned: AssetFieldOverride = {};
  if (patch.car_description?.trim()) cleaned.car_description = patch.car_description.trim();
  if (patch.vin?.trim()) cleaned.vin = patch.vin.trim().toUpperCase();
  if (patch.first_registration?.trim()) {
    cleaned.first_registration = patch.first_registration.trim();
  }
  if (typeof patch.mileage === "number" && Number.isFinite(patch.mileage)) {
    cleaned.mileage = patch.mileage;
  }
  if (typeof patch.gps_online === "boolean") cleaned.gps_online = patch.gps_online;
  if (typeof patch.insurance_lapsed === "boolean") {
    cleaned.insurance_lapsed = patch.insurance_lapsed;
  }
  if (typeof patch.ownership_transferred === "boolean") {
    cleaned.ownership_transferred = patch.ownership_transferred;
  }
  if (typeof patch.loan_principal === "number" && Number.isFinite(patch.loan_principal)) {
    cleaned.loan_principal = patch.loan_principal;
  }
  return cleaned;
}

function cleanFieldOverrides(overrides: Record<number, AssetFieldOverride>) {
  const cleaned: Record<number, AssetFieldOverride> = {};
  for (const [rowNumber, patch] of Object.entries(overrides)) {
    const next = cleanSingleOverride(patch);
    if (Object.keys(next).length > 0) {
      cleaned[Number(rowNumber)] = next;
    }
  }
  return cleaned;
}

export default function AssetPricingPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [packageId, setPackageId] = useState<number | null>(null);
  const [parseInfo, setParseInfo] = useState<{
    assets: ParsedAssetInfo[];
    total_rows: number;
    success_rows: number;
    errors: Array<{ row_number: number; field: string; message: string }>;
    column_mapping: Record<string, string>;
    unmapped_columns: string[];
    suggested_strategy: string;
    strategy_message: string;
  } | null>(null);
  const [assetPackageType, setAssetPackageType] = useState<AssetPackageType>("inventory");
  const [advancedConditionPricing, setAdvancedConditionPricing] = useState(false);
  const [approvalContext, setApprovalContext] = useState<ApprovalContext | null>(null);
  const [approvalRequest, setApprovalRequest] = useState<ApprovalRequestInfo | null>(null);
  const [creatingApproval, setCreatingApproval] = useState(false);
  const [refreshingApproval, setRefreshingApproval] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);
  const [analyzingBuyerOffer, setAnalyzingBuyerOffer] = useState(false);
  const [fieldOverrides, setFieldOverrides] = useState<Record<number, AssetFieldOverride>>({});
  const [batchTarget, setBatchTarget] = useState<BatchCorrectionTarget>("risk");
  const [batchPatch, setBatchPatch] = useState<AssetFieldOverride>({});
  const [buyerOfferPrice, setBuyerOfferPrice] = useState("");
  const [buyerOfferNote, setBuyerOfferNote] = useState("");
  const [params, setParams] = useState<PricingParameters>({
    towing_cost: 1500,
    daily_parking: 30,
    capital_rate: 8,
    disposal_period: 45,
    vehicle_condition: "good",
    asset_package_type: "inventory",
  });
  const [result, setResult] = useState<PackageCalculationResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(SESSION_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw) as {
        packageId?: number | null;
        parseInfo?: typeof parseInfo;
        assetPackageType?: AssetPackageType;
        advancedConditionPricing?: boolean;
        fieldOverrides?: Record<number, AssetFieldOverride>;
        params?: PricingParameters;
        result?: PackageCalculationResult | null;
        buyerOfferPrice?: string;
        buyerOfferNote?: string;
      };
      if (saved.packageId) setPackageId(saved.packageId);
      if (saved.parseInfo) setParseInfo(saved.parseInfo);
      if (saved.assetPackageType) setAssetPackageType(saved.assetPackageType);
      if (typeof saved.advancedConditionPricing === "boolean") {
        setAdvancedConditionPricing(saved.advancedConditionPricing);
      }
      if (saved.fieldOverrides) setFieldOverrides(saved.fieldOverrides);
      if (saved.params) setParams(saved.params);
      if (saved.result) setResult(saved.result);
      if (typeof saved.buyerOfferPrice === "string") setBuyerOfferPrice(saved.buyerOfferPrice);
      if (typeof saved.buyerOfferNote === "string") setBuyerOfferNote(saved.buyerOfferNote);
    } catch {
      sessionStorage.removeItem(SESSION_KEY);
    }
  }, []);

  useEffect(() => {
    try {
      sessionStorage.setItem(
        SESSION_KEY,
        JSON.stringify({
          packageId,
          parseInfo,
          assetPackageType,
          advancedConditionPricing,
          fieldOverrides,
          params,
          result,
          buyerOfferPrice,
          buyerOfferNote,
        }),
      );
    } catch {
      // Ignore sessionStorage quota errors.
    }
  }, [
    packageId,
    parseInfo,
    assetPackageType,
    advancedConditionPricing,
    fieldOverrides,
    params,
    result,
    buyerOfferPrice,
    buyerOfferNote,
  ]);

  useEffect(() => {
    if (!approvalRequest || approvalRequest.status !== "pending") return;
    const timer = window.setInterval(() => {
      void refreshApprovalStatus(approvalRequest.id);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [approvalRequest]);

  function clearApprovalFlow() {
    setApprovalContext(null);
    setApprovalRequest(null);
  }

  function resetAll() {
    setFile(null);
    setPackageId(null);
    setParseInfo(null);
    setAssetPackageType("inventory");
    setAdvancedConditionPricing(false);
    setFieldOverrides({});
    setBatchPatch({});
    setBatchTarget("risk");
    setBuyerOfferPrice("");
    setBuyerOfferNote("");
    setParams({
      towing_cost: 1500,
      daily_parking: 30,
      capital_rate: 8,
      disposal_period: 45,
      vehicle_condition: "good",
      asset_package_type: "inventory",
    });
    clearApprovalFlow();
    setResult(null);
    setError("");
    sessionStorage.removeItem(SESSION_KEY);
  }

  function extractApprovalContext(err: unknown): ApprovalContext | null {
    if (!(err instanceof ApiError) || !err.details || typeof err.details !== "object") {
      return null;
    }
    const maybeContext = (err.details as { approval_context?: ApprovalContext }).approval_context;
    return maybeContext && typeof maybeContext === "object" ? maybeContext : null;
  }

  function updateFieldOverride(rowNumber: number, patch: AssetFieldOverride) {
    setFieldOverrides((current) => {
      const nextPatch = cleanSingleOverride({ ...(current[rowNumber] || {}), ...patch });
      const next = { ...current };
      if (Object.keys(nextPatch).length > 0) {
        next[rowNumber] = nextPatch;
      } else {
        delete next[rowNumber];
      }
      return next;
    });
  }

  function getBatchRows() {
    if (!result) return [];
    return result.assets.filter((asset) => {
      if (batchTarget === "all") return true;
      if (batchTarget === "missing_principal") {
        return asset.loan_principal === null || asset.risk_flags.some((flag) => flag.includes("本金缺失"));
      }
      if (batchTarget === "missing_valuation") {
        return (
          asset.che300_valuation === null ||
          asset.risk_flags.some((flag) => flag.includes("估值缺失") || flag.includes("车辆估值缺失"))
        );
      }
      return asset.risk_flags.some((flag) => flag !== "基础字段完整");
    });
  }

  function handleApplyBatchPatch() {
    const cleanedPatch = cleanSingleOverride(batchPatch);
    if (Object.keys(cleanedPatch).length === 0) {
      setError("请先输入需要批量补录的字段");
      return;
    }
    const rows = getBatchRows();
    if (rows.length === 0) {
      setError("当前范围没有可补录的车辆");
      return;
    }
    setFieldOverrides((current) => {
      const next = { ...current };
      for (const row of rows) {
        next[row.row_number] = cleanSingleOverride({
          ...(next[row.row_number] || {}),
          ...cleanedPatch,
        });
      }
      return next;
    });
    setError("");
  }

  async function handleDownloadPdf() {
    if (!packageId) return;
    setDownloadingPdf(true);
    setError("");
    try {
      const blob = await downloadAssetPackageReportPdf(packageId);
      const url = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `asset-package-${packageId}-transfer-report.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "PDF下载失败");
    } finally {
      setDownloadingPdf(false);
    }
  }

  async function handleBuyerOfferAnalysis() {
    if (!packageId || !result) return;
    const price = Number(buyerOfferPrice);
    if (!Number.isFinite(price) || price <= 0) {
      setError("请输入大于0的买方报价");
      return;
    }
    setAnalyzingBuyerOffer(true);
    setError("");
    try {
      const analysis = await analyzeBuyerOffer(packageId, {
        buyer_offer_price: price,
        buyer_offer_note: buyerOfferNote.trim() || null,
      });
      setResult((current) =>
        current
          ? {
              ...current,
              summary: {
                ...current.summary,
                buyer_offer_analysis: analysis,
              },
            }
          : current,
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "买方报价分析失败");
    } finally {
      setAnalyzingBuyerOffer(false);
    }
  }

  async function refreshApprovalStatus(approvalId: number) {
    setRefreshingApproval(true);
    try {
      const rows = await listApprovalRequests();
      setApprovalRequest(rows.find((row) => row.id === approvalId) || null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "审批状态刷新失败");
    } finally {
      setRefreshingApproval(false);
    }
  }

  async function handleCreateApproval() {
    if (!approvalContext) return;
    setCreatingApproval(true);
    setError("");
    try {
      const created = await createApprovalRequest({
        type: approvalContext.approval_type,
        reason: approvalContext.reason,
        related_object_type: approvalContext.related_object_type || undefined,
        related_object_id: approvalContext.related_object_id || undefined,
        estimated_cost: approvalContext.estimated_cost,
        metadata: approvalContext.metadata,
      });
      setApprovalRequest(created);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "发起审批失败");
    } finally {
      setCreatingApproval(false);
    }
  }

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError("");
    setResult(null);
    clearApprovalFlow();
    try {
      const res = await uploadExcel(file);
      setPackageId(res.package_id);
      setParseInfo({
        assets: res.parse_result.assets || [],
        total_rows: res.parse_result.total_rows,
        success_rows: res.parse_result.success_rows,
        errors: res.parse_result.errors,
        column_mapping: res.parse_result.column_mapping || {},
        unmapped_columns: res.parse_result.unmapped_columns || [],
        suggested_strategy: res.parse_result.suggested_strategy || "seller_transfer_analysis",
        strategy_message: res.parse_result.strategy_message || "",
      });
      setFieldOverrides({});
      setBatchPatch({});
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }

  async function handleCalculate() {
    if (!packageId) return;
    setCalculating(true);
    setError("");
    try {
      const approvalRequestId =
        approvalRequest && approvalRequest.status === "approved" && !approvalRequest.is_consumed
          ? approvalRequest.id
          : null;
      const finalParams: PricingParameters = {
        ...params,
        asset_package_type: assetPackageType,
        advanced_condition_pricing: advancedConditionPricing,
        approval_request_id: approvalRequestId,
        strict_policy: advancedConditionPricing,
      };
      const cleanedOverrides = cleanFieldOverrides(fieldOverrides);
      if (Object.keys(cleanedOverrides).length > 0) {
        finalParams.asset_overrides = cleanedOverrides;
      }
      const { job_id } = await calculatePackage(packageId, finalParams);
      const job = await pollJob(job_id);
      if (job.status === "failed") {
        throw new Error(job.error_message || "计算失败");
      }
      const pkg = await getPackage(packageId);
      if (pkg.results) {
        setResult(pkg.results);
        setApprovalContext(null);
      }
      if (approvalRequestId) {
        await refreshApprovalStatus(approvalRequestId);
      }
    } catch (err: unknown) {
      const nextApprovalContext = extractApprovalContext(err);
      if (nextApprovalContext) setApprovalContext(nextApprovalContext);
      setError(err instanceof Error ? err.message : "计算失败");
    } finally {
      setCalculating(false);
    }
  }

  const ignoredPriceColumns =
    parseInfo?.unmapped_columns.filter((column) => /买断|收购|转让价|折扣价/.test(column)) || [];
  const parsedAssetByRow = new Map((parseInfo?.assets || []).map((asset) => [asset.row_number, asset]));
  const correctionRows =
    result?.assets.filter((asset) => asset.risk_flags.some((flag) => flag !== "基础字段完整")) || [];
  const correctionDisplayRows =
    correctionRows.length > 0 ? correctionRows : result?.assets.slice(0, 20) || [];
  const cleanedOverrideCount = Object.keys(cleanFieldOverrides(fieldOverrides)).length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">资产包出让定价分析</h1>
        <p className="mt-1 text-gray-500">
          站在金融公司出让方角度，先确认资产包是否在库，再调用车300估值和大模型生成推荐出让折扣区间与分析报告。
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Card>
        <CardHeader>
          <CardTitle>第一步：上传资产包台账</CardTitle>
          <CardDescription>
            系统会识别车型、VIN、上牌日期、里程、本金/债权等字段。即使表格包含买断价、收购价或转让价，本模块也不会把它作为定价锚点。
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2 md:max-w-xl">
            <Label htmlFor="asset-package-file">资产包Excel文件</Label>
            <div className="flex items-center gap-3">
              <Input
                id="asset-package-file"
                type="file"
                accept=".xlsx,.xls"
                onChange={(event) => setFile(event.target.files?.[0] || null)}
              />
              <Button onClick={handleUpload} disabled={!file || uploading}>
                {uploading ? "解析中..." : "上传并解析"}
              </Button>
            </div>
          </div>

          {parseInfo && (
            <div className="space-y-3 text-sm">
              <Badge>成功解析 {parseInfo.success_rows}/{parseInfo.total_rows} 行</Badge>
              <div className="rounded-lg bg-gray-50 p-3">
                <div className="mb-2 font-medium text-gray-700">列识别结果</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(parseInfo.column_mapping).map(([excelCol, field]) => (
                    <span
                      key={excelCol}
                      className="inline-flex rounded bg-green-100 px-2 py-1 text-xs text-green-700"
                    >
                      {excelCol} → {FIELD_LABELS[field] || field}
                    </span>
                  ))}
                </div>
                {parseInfo.unmapped_columns.length > 0 && (
                  <div className="mt-2">
                    <span className="text-gray-500">未作为分析字段的列：</span>
                    {parseInfo.unmapped_columns.map((column) => (
                      <span
                        key={column}
                        className="ml-1 inline-flex rounded bg-yellow-100 px-2 py-1 text-xs text-yellow-700"
                      >
                        {column}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <Alert>
                <AlertDescription>
                  <strong>定价逻辑：</strong>{parseInfo.strategy_message}
                  {ignoredPriceColumns.length > 0 && (
                    <span className="ml-1">
                      已忽略价格列：{ignoredPriceColumns.join("、")}。
                    </span>
                  )}
                </AlertDescription>
              </Alert>

              {parseInfo.errors.length > 0 && (
                <div className="text-orange-600">
                  {parseInfo.errors.slice(0, 5).map((err) => (
                    <div key={`${err.row_number}-${err.field}`}>
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

      {packageId && parseInfo && (
        <Card>
          <CardHeader>
            <CardTitle>第二步：确认资产包类型并生成出让分析</CardTitle>
            <CardDescription>
              在库车以车辆估值为主要定价锚点；非在库车以本金为主要定价锚点，并用车辆估值校验可回收支撑。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <Label className="mb-3 block text-base font-medium">资产包类型</Label>
              <div className="grid gap-3 md:grid-cols-2">
                {[
                  {
                    value: "inventory" as const,
                    title: "在库车资产包",
                    desc: "车辆已入库或可实际控制，系统以车300评估价为主锚给出出让折扣区间。",
                  },
                  {
                    value: "non_inventory" as const,
                    title: "非在库车资产包",
                    desc: "车辆尚未入库，系统以债权本金为主锚，并用车辆估值校验收车和处置支撑。",
                  },
                ].map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      setAssetPackageType(option.value);
                      setResult(null);
                    }}
                    className={`rounded-lg border-2 p-4 text-left transition ${
                      assetPackageType === option.value
                        ? "border-blue-500 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="font-medium">{option.title}</div>
                    <div className="mt-1 text-xs text-gray-500">{option.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <Label className="mb-2 block text-base font-medium">车况估值口径</Label>
              <div className="flex flex-col gap-3 md:flex-row">
                {[
                  { value: "excellent", label: "车况优秀", desc: "维保齐全、少事故" },
                  { value: "good", label: "车况良好", desc: "正常磨损、无重大事故" },
                  { value: "normal", label: "车况一般", desc: "外观/维修瑕疵较多" },
                ].map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => {
                      setParams({
                        ...params,
                        vehicle_condition: option.value as "excellent" | "good" | "normal",
                      });
                      setResult(null);
                    }}
                    className={`flex-1 rounded-lg border-2 p-3 text-left transition ${
                      params.vehicle_condition === option.value
                        ? "border-blue-500 bg-blue-50"
                        : "border-gray-200 hover:border-gray-300"
                    }`}
                  >
                    <div className="font-medium">{option.label}</div>
                    <div className="mt-1 text-xs text-gray-500">{option.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            <div className="rounded-lg bg-slate-50 p-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <div className="font-medium">车300估值与大模型报告</div>
                  <p className="mt-1 text-sm text-gray-600">
                    计算时会先批量调用车300估值，再调用大模型生成出让方分析报告。高级车况定价可能触发审批。
                  </p>
                </div>
                <Button
                  type="button"
                  variant={advancedConditionPricing ? "default" : "outline"}
                  onClick={() => {
                    setAdvancedConditionPricing((current) => {
                      const next = !current;
                      if (!next) clearApprovalFlow();
                      return next;
                    });
                  }}
                >
                  {advancedConditionPricing ? "已启用高级车况定价" : "启用高级车况定价"}
                </Button>
              </div>
            </div>

            {(approvalContext || approvalRequest) && (
              <Card className="border-amber-200 bg-amber-50">
                <CardContent className="space-y-4 pt-6">
                  <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-amber-900">高级车况定价审批</span>
                        {approvalRequest && (
                          <Badge variant={approvalRequest.is_consumed ? "secondary" : "default"}>
                            {approvalRequest.is_consumed
                              ? "已消费"
                              : approvalRequest.status === "approved"
                                ? "已通过"
                                : approvalRequest.status === "rejected"
                                  ? "已拒绝"
                                  : "审批中"}
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-amber-900">
                        {approvalContext?.reason || "高级车况定价已进入审批链路。"}
                      </p>
                      <p className="text-xs text-amber-800">
                        关联对象：
                        {approvalContext?.related_object_type || approvalRequest?.related_object_type || "-"}
                        {" / "}
                        {approvalContext?.related_object_id || approvalRequest?.related_object_id || "-"}
                        {" · "}
                        预计成本：¥
                        {approvalContext?.estimated_cost ?? approvalRequest?.estimated_cost ?? 36}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {!approvalRequest && approvalContext && (
                        <Button type="button" onClick={handleCreateApproval} disabled={creatingApproval}>
                          {creatingApproval ? "提交中..." : "发起审批"}
                        </Button>
                      )}
                      {approvalRequest?.status === "pending" && (
                        <Button
                          type="button"
                          variant="outline"
                          onClick={() => void refreshApprovalStatus(approvalRequest.id)}
                          disabled={refreshingApproval}
                        >
                          {refreshingApproval ? "刷新中..." : "刷新审批状态"}
                        </Button>
                      )}
                      {approvalRequest?.status === "approved" && !approvalRequest.is_consumed && (
                        <Button type="button" onClick={handleCalculate} disabled={calculating}>
                          {calculating ? "重试中..." : "使用已审批额度生成分析"}
                        </Button>
                      )}
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            <div className="flex flex-wrap items-center gap-3">
              <Button onClick={handleCalculate} disabled={calculating} size="lg">
                {calculating ? "生成中..." : "生成资产包出让分析"}
              </Button>
              <Button variant="outline" onClick={resetAll}>
                清空重新开始
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {result && (
        <>
          <Alert>
            <AlertDescription>
              <div className="flex flex-wrap items-center gap-3">
                <span className="font-medium">
                  本次分析：{PACKAGE_TYPE_LABELS[result.summary.asset_package_type as AssetPackageType] || "在库车资产包"}
                </span>
                <span className="text-sm text-gray-600">定价基准：{result.summary.discount_basis}</span>
                <span className="text-sm text-gray-600">
                  估值数据覆盖率：{formatPercentPoint(result.summary.valuation_coverage_rate)}
                </span>
              </div>
            </AlertDescription>
          </Alert>

          <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500">资产数量</div>
                <div className="text-2xl font-bold">{result.summary.total_assets}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500">本金合计</div>
                <div className="text-2xl font-bold">{formatMoney(result.summary.total_principal)}</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500">车300估值合计</div>
                <div className="text-2xl font-bold text-blue-600">
                  {formatMoney(result.summary.total_vehicle_valuation)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500">推荐出让价</div>
                <div className="text-xl font-bold text-green-600">
                  {formatMoney(result.summary.recommended_transfer_price_low)} -{" "}
                  {formatMoney(result.summary.recommended_transfer_price_high)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500">中位折扣</div>
                <div className="text-2xl font-bold text-orange-600">
                  {formatPercent(result.summary.recommended_discount_mid)}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-sm text-gray-500">本金中位回收率</div>
                <div className="text-2xl font-bold">
                  {formatPercent(result.summary.principal_recovery_rate_mid)}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="gap-3 md:flex md:flex-row md:items-start md:justify-between">
              <div>
                <CardTitle>交易适配度</CardTitle>
                <CardDescription>
                  综合估值覆盖、本金完整度、权属状态、车辆控制和买方接受度，判断资产包进入询价/竞价流程的成熟度。
                </CardDescription>
              </div>
              <Badge
                variant={
                  result.summary.tradeability_level === "A" || result.summary.tradeability_level === "B"
                    ? "default"
                    : result.summary.tradeability_level === "C"
                      ? "secondary"
                      : "destructive"
                }
              >
                {TRADEABILITY_LABELS[result.summary.tradeability_level || "E"] || "暂不适配"} ·{" "}
                {result.summary.tradeability_score ?? 0}分
              </Badge>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-gray-700">
                {result.summary.tradeability_summary || "系统暂未返回交易适配度摘要。"}
              </p>
              {result.summary.tradeability_breakdown &&
                Object.keys(result.summary.tradeability_breakdown).length > 0 && (
                  <div className="grid gap-2 md:grid-cols-3">
                    {Object.entries(result.summary.tradeability_breakdown).map(([key, value]) => (
                      <div key={key} className="rounded-lg bg-slate-50 p-3">
                        <div className="text-xs text-gray-500">{key}</div>
                        <div className="mt-1 text-lg font-semibold">{value.toFixed(1)}分</div>
                      </div>
                    ))}
                  </div>
                )}
              {(result.summary.tradeability_recommendations || []).length > 0 && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
                  <div className="mb-2 text-sm font-medium text-amber-900">交易前建议补强项</div>
                  <div className="space-y-1 text-sm text-amber-900">
                    {(result.summary.tradeability_recommendations || []).map((item) => (
                      <div key={item}>- {item}</div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {result.summary.pricing_methodology && (
            <Alert>
              <AlertDescription>{result.summary.pricing_methodology}</AlertDescription>
            </Alert>
          )}

          {result.summary.risk_alerts.length > 0 && (
            <Alert variant="destructive">
              <AlertDescription>
                <div className="mb-1 font-semibold">风险预警</div>
                {result.summary.risk_alerts.map((alert) => (
                  <div key={alert}>- {alert}</div>
                ))}
              </AlertDescription>
            </Alert>
          )}

          <Card>
            <CardHeader>
              <CardTitle>字段补录与重新生成</CardTitle>
              <CardDescription>
                如果报告风险预警来自本金、VIN、上牌日期、里程或车辆状态缺失，可以在这里批量补录或逐车编辑，然后重新生成报告。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-5">
              <div className="rounded-lg border bg-slate-50 p-4">
                <div className="mb-3 text-sm font-medium text-gray-700">批量补录</div>
                <div className="grid gap-3 md:grid-cols-4">
                  <div className="grid gap-1">
                    <Label>应用范围</Label>
                    <select
                      value={batchTarget}
                      onChange={(event) => setBatchTarget(event.target.value as BatchCorrectionTarget)}
                      className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
                    >
                      <option value="risk">全部风险预警行</option>
                      <option value="missing_principal">本金缺失行</option>
                      <option value="missing_valuation">估值缺失行</option>
                      <option value="all">全部车辆</option>
                    </select>
                  </div>
                  <div className="grid gap-1">
                    <Label>本金/债权(元)</Label>
                    <Input
                      type="number"
                      value={batchPatch.loan_principal ?? ""}
                      onChange={(event) =>
                        setBatchPatch({
                          ...batchPatch,
                          loan_principal: parseOptionalNumber(event.target.value),
                        })
                      }
                    />
                  </div>
                  <div className="grid gap-1">
                    <Label>VIN</Label>
                    <Input
                      value={batchPatch.vin || ""}
                      onChange={(event) =>
                        setBatchPatch({ ...batchPatch, vin: event.target.value || undefined })
                      }
                    />
                  </div>
                  <div className="grid gap-1">
                    <Label>上牌日期</Label>
                    <Input
                      type="date"
                      value={batchPatch.first_registration || ""}
                      onChange={(event) =>
                        setBatchPatch({
                          ...batchPatch,
                          first_registration: event.target.value || undefined,
                        })
                      }
                    />
                  </div>
                  <div className="grid gap-1">
                    <Label>里程(万公里)</Label>
                    <Input
                      type="number"
                      step="0.01"
                      value={batchPatch.mileage ?? ""}
                      onChange={(event) =>
                        setBatchPatch({
                          ...batchPatch,
                          mileage: parseOptionalNumber(event.target.value),
                        })
                      }
                    />
                  </div>
                  <div className="grid gap-1">
                    <Label>GPS</Label>
                    <select
                      value={booleanInputValue(batchPatch.gps_online)}
                      onChange={(event) =>
                        setBatchPatch({
                          ...batchPatch,
                          gps_online: parseOptionalBoolean(event.target.value),
                        })
                      }
                      className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
                    >
                      <option value="">不批量修改</option>
                      <option value="true">在线</option>
                      <option value="false">离线</option>
                    </select>
                  </div>
                  <div className="grid gap-1">
                    <Label>脱保</Label>
                    <select
                      value={booleanInputValue(batchPatch.insurance_lapsed)}
                      onChange={(event) =>
                        setBatchPatch({
                          ...batchPatch,
                          insurance_lapsed: parseOptionalBoolean(event.target.value),
                        })
                      }
                      className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
                    >
                      <option value="">不批量修改</option>
                      <option value="true">是</option>
                      <option value="false">否</option>
                    </select>
                  </div>
                  <div className="grid gap-1">
                    <Label>过户</Label>
                    <select
                      value={booleanInputValue(batchPatch.ownership_transferred)}
                      onChange={(event) =>
                        setBatchPatch({
                          ...batchPatch,
                          ownership_transferred: parseOptionalBoolean(event.target.value),
                        })
                      }
                      className="h-8 rounded-lg border border-input bg-white px-2 text-sm"
                    >
                      <option value="">不批量修改</option>
                      <option value="true">是</option>
                      <option value="false">否</option>
                    </select>
                  </div>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <Button type="button" onClick={handleApplyBatchPatch}>
                    批量应用
                  </Button>
                  <Button type="button" variant="outline" onClick={() => setBatchPatch({})}>
                    清空批量输入
                  </Button>
                  <span className="text-sm text-gray-500">
                    当前已补录 {cleanedOverrideCount} 行，需重新生成后生效。
                  </span>
                </div>
              </div>

              {cleanedOverrideCount > 0 && (
                <Alert>
                  <AlertDescription>
                    补录字段不会改写原始Excel；点击“使用补录字段重新生成报告”后，系统会按补录值重新估值、重算风险预警并生成新版报告。
                  </AlertDescription>
                </Alert>
              )}

              <div className="flex flex-wrap items-center justify-between gap-3">
                <div className="text-sm text-gray-500">
                  {correctionRows.length > 0
                    ? `已筛出 ${correctionRows.length} 台带风险标签车辆。`
                    : "当前无风险标签，默认展示前20台便于人工修正。"}
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button type="button" onClick={handleCalculate} disabled={calculating || cleanedOverrideCount === 0}>
                    {calculating ? "重新生成中..." : "使用补录字段重新生成报告"}
                  </Button>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => {
                      setFieldOverrides({});
                      setBatchPatch({});
                    }}
                  >
                    清空全部补录
                  </Button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>行号</TableHead>
                      <TableHead>风险标签</TableHead>
                      <TableHead>本金/债权</TableHead>
                      <TableHead>VIN</TableHead>
                      <TableHead>上牌日期</TableHead>
                      <TableHead>里程</TableHead>
                      <TableHead>GPS</TableHead>
                      <TableHead>脱保</TableHead>
                      <TableHead>过户</TableHead>
                      <TableHead>操作</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {correctionDisplayRows.map((asset) => {
                      const source = parsedAssetByRow.get(asset.row_number);
                      const patch = fieldOverrides[asset.row_number] || {};
                      const hasGpsPatch = typeof patch.gps_online === "boolean";
                      const hasInsurancePatch = typeof patch.insurance_lapsed === "boolean";
                      const hasOwnershipPatch = typeof patch.ownership_transferred === "boolean";
                      return (
                        <TableRow key={`edit-${asset.row_number}`}>
                          <TableCell>{asset.row_number}</TableCell>
                          <TableCell className="min-w-[180px]">
                            <div className="flex flex-wrap gap-1">
                              {asset.risk_flags.map((flag) => (
                                <Badge key={flag} variant="secondary" className="text-xs">
                                  {flag}
                                </Badge>
                              ))}
                            </div>
                          </TableCell>
                          <TableCell>
                            <Input
                              type="number"
                              className="w-32"
                              value={patch.loan_principal ?? source?.loan_principal ?? asset.loan_principal ?? ""}
                              onChange={(event) =>
                                updateFieldOverride(asset.row_number, {
                                  loan_principal: parseOptionalNumber(event.target.value),
                                })
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              className="w-44"
                              value={patch.vin ?? source?.vin ?? ""}
                              onChange={(event) =>
                                updateFieldOverride(asset.row_number, {
                                  vin: event.target.value || undefined,
                                })
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              type="date"
                              className="w-36"
                              value={patch.first_registration ?? toDateInputValue(source?.first_registration)}
                              onChange={(event) =>
                                updateFieldOverride(asset.row_number, {
                                  first_registration: event.target.value || undefined,
                                })
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <Input
                              type="number"
                              step="0.01"
                              className="w-28"
                              value={patch.mileage ?? source?.mileage ?? ""}
                              onChange={(event) =>
                                updateFieldOverride(asset.row_number, {
                                  mileage: parseOptionalNumber(event.target.value),
                                })
                              }
                            />
                          </TableCell>
                          <TableCell>
                            <select
                              value={hasGpsPatch ? booleanInputValue(patch.gps_online) : booleanInputValue(source?.gps_online)}
                              onChange={(event) =>
                                updateFieldOverride(asset.row_number, {
                                  gps_online: parseOptionalBoolean(event.target.value),
                                })
                              }
                              className="h-8 w-24 rounded-lg border border-input bg-white px-2 text-sm"
                            >
                              <option value="">未知</option>
                              <option value="true">在线</option>
                              <option value="false">离线</option>
                            </select>
                          </TableCell>
                          <TableCell>
                            <select
                              value={
                                hasInsurancePatch
                                  ? booleanInputValue(patch.insurance_lapsed)
                                  : booleanInputValue(source?.insurance_lapsed)
                              }
                              onChange={(event) =>
                                updateFieldOverride(asset.row_number, {
                                  insurance_lapsed: parseOptionalBoolean(event.target.value),
                                })
                              }
                              className="h-8 w-20 rounded-lg border border-input bg-white px-2 text-sm"
                            >
                              <option value="">未知</option>
                              <option value="true">是</option>
                              <option value="false">否</option>
                            </select>
                          </TableCell>
                          <TableCell>
                            <select
                              value={
                                hasOwnershipPatch
                                  ? booleanInputValue(patch.ownership_transferred)
                                  : booleanInputValue(source?.ownership_transferred)
                              }
                              onChange={(event) =>
                                updateFieldOverride(asset.row_number, {
                                  ownership_transferred: parseOptionalBoolean(event.target.value),
                                })
                              }
                              className="h-8 w-20 rounded-lg border border-input bg-white px-2 text-sm"
                            >
                              <option value="">未知</option>
                              <option value="true">是</option>
                              <option value="false">否</option>
                            </select>
                          </TableCell>
                          <TableCell>
                            <Button
                              type="button"
                              variant="outline"
                              onClick={() =>
                                setFieldOverrides((current) => {
                                  const next = { ...current };
                                  delete next[asset.row_number];
                                  return next;
                                })
                              }
                            >
                              清空本行
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>买方报价对比</CardTitle>
              <CardDescription>
                买方报价只接受手动录入，不读取Excel价格列；系统会反推报价折扣、与推荐中位价差距和谈判建议，并同步写入PDF数据源。
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 md:grid-cols-[220px_1fr_auto] md:items-end">
                <div className="grid gap-1">
                  <Label>买方报价(元)</Label>
                  <Input
                    type="number"
                    value={buyerOfferPrice}
                    onChange={(event) => setBuyerOfferPrice(event.target.value)}
                    placeholder="例如 1500000"
                  />
                </div>
                <div className="grid gap-1">
                  <Label>报价备注</Label>
                  <Input
                    value={buyerOfferNote}
                    onChange={(event) => setBuyerOfferNote(event.target.value)}
                    placeholder="如：买方要求一次性打包、T+3付款"
                  />
                </div>
                <Button
                  type="button"
                  onClick={handleBuyerOfferAnalysis}
                  disabled={analyzingBuyerOffer}
                >
                  {analyzingBuyerOffer ? "分析中..." : "分析买方报价"}
                </Button>
              </div>

              {result.summary.buyer_offer_analysis && (
                <div className="grid gap-3 md:grid-cols-4">
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-xs text-gray-500">买方报价</div>
                    <div className="mt-1 text-lg font-semibold">
                      ¥{formatMoney(result.summary.buyer_offer_analysis.buyer_offer_price)}
                    </div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-xs text-gray-500">报价折扣</div>
                    <div className="mt-1 text-lg font-semibold">
                      {formatPercent(result.summary.buyer_offer_analysis.buyer_offer_discount)}
                    </div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-xs text-gray-500">中位价差额</div>
                    <div className="mt-1 text-lg font-semibold">
                      ¥{formatMoney(result.summary.buyer_offer_analysis.buyer_offer_gap)}
                    </div>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-3">
                    <div className="text-xs text-gray-500">差距率</div>
                    <div className="mt-1 text-lg font-semibold">
                      {formatPercent(result.summary.buyer_offer_analysis.buyer_offer_gap_rate)}
                    </div>
                  </div>
                  <div className="rounded-lg border border-blue-100 bg-blue-50 p-3 md:col-span-4">
                    <div className="mb-1 font-medium text-blue-900">
                      {result.summary.buyer_offer_analysis.buyer_offer_assessment}
                    </div>
                    <div className="space-y-1 text-sm text-blue-900">
                      {result.summary.buyer_offer_analysis.negotiation_suggestions.map((item) => (
                        <div key={item}>- {item}</div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="gap-3 md:flex md:flex-row md:items-start md:justify-between">
              <div>
                <CardTitle>资产包出让分析报告</CardTitle>
                <CardDescription>由系统结合车300估值、本金和资产包类型生成，可作为对外沟通底稿。</CardDescription>
              </div>
              <Button type="button" variant="outline" onClick={handleDownloadPdf} disabled={downloadingPdf}>
                {downloadingPdf ? "下载中..." : "下载PDF"}
              </Button>
            </CardHeader>
            <CardContent>
              <div className="whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-sm leading-7 text-gray-800">
                {result.summary.analysis_report}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>逐车定价明细 ({result.assets.length}台)</CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>行号</TableHead>
                    <TableHead>车型</TableHead>
                    <TableHead className="text-right">本金</TableHead>
                    <TableHead className="text-right">车300估值</TableHead>
                    <TableHead>估值可信度</TableHead>
                    <TableHead>定价基准</TableHead>
                    <TableHead className="text-right">推荐出让价区间</TableHead>
                    <TableHead className="text-right">基准折扣</TableHead>
                    <TableHead className="text-right">本金折扣</TableHead>
                    <TableHead className="text-right">估值折扣</TableHead>
                    <TableHead>风险标签</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {result.assets.map((asset) => (
                    <TableRow key={asset.row_number}>
                      <TableCell>{asset.row_number}</TableCell>
                      <TableCell className="max-w-[220px] truncate">{asset.car_description}</TableCell>
                      <TableCell className="text-right">{formatMoney(asset.loan_principal)}</TableCell>
                      <TableCell className="text-right">{formatMoney(asset.che300_valuation)}</TableCell>
                      <TableCell>
                        <div className="flex min-w-[120px] flex-col gap-1">
                          <Badge
                            variant={
                              asset.valuation_confidence_level === "high" ||
                              asset.valuation_confidence_level === "medium"
                                ? "default"
                                : asset.valuation_confidence_level === "low"
                                  ? "secondary"
                                  : "destructive"
                            }
                            className="w-fit"
                          >
                            {CONFIDENCE_LABELS[asset.valuation_confidence_level || "unknown"] || "未知"} ·{" "}
                            {asset.valuation_confidence_score ?? 0}
                          </Badge>
                          <span className="text-xs text-gray-500">{asset.valuation_source || "-"}</span>
                          {(asset.valuation_anomaly_tags || []).length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {(asset.valuation_anomaly_tags || []).map((tag) => (
                                <Badge key={tag} variant="outline" className="text-xs">
                                  {tag}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="text-sm">{asset.pricing_basis}</div>
                        <div className="text-xs text-gray-500">
                          {STRATEGY_LABELS[asset.applied_strategy || ""] || asset.applied_strategy}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        {formatMoney(asset.recommended_transfer_price_low)} -{" "}
                        {formatMoney(asset.recommended_transfer_price_high)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatPercent(asset.recommended_discount_mid)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatPercent(asset.principal_discount_mid)}
                      </TableCell>
                      <TableCell className="text-right">
                        {formatPercent(asset.valuation_discount_mid)}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {asset.risk_flags.map((flag) => (
                            <Badge key={flag} variant="secondary" className="text-xs">
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
