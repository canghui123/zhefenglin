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
  type PricingParameters,
  type PackageCalculationResult,
} from "@/lib/api";

function formatMoney(n: number) {
  return n.toLocaleString("zh-CN", { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

export default function AssetPricingPage() {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [calculating, setCalculating] = useState(false);
  const [packageId, setPackageId] = useState<number | null>(null);
  const [parseInfo, setParseInfo] = useState<{
    total_rows: number;
    success_rows: number;
    errors: Array<{ row_number: number; field: string; message: string }>;
  } | null>(null);
  const [result, setResult] = useState<PackageCalculationResult | null>(null);
  const [error, setError] = useState("");

  const [params, setParams] = useState<PricingParameters>({
    towing_cost: 1500,
    daily_parking: 30,
    capital_rate: 8,
    disposal_period: 45,
  });

  async function handleUpload() {
    if (!file) return;
    setUploading(true);
    setError("");
    setResult(null);
    try {
      const res = await uploadExcel(file);
      setPackageId(res.package_id);
      setParseInfo({
        total_rows: res.parse_result.total_rows,
        success_rows: res.parse_result.success_rows,
        errors: res.parse_result.errors,
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "上传失败");
    } finally {
      setUploading(false);
    }
  }

  async function handleCalculate() {
    if (!packageId) return;
    setCalculating(true);
    setError("");
    try {
      const res = await calculatePackage(packageId, params);
      setResult(res);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "计算失败");
    } finally {
      setCalculating(false);
    }
  }

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
          <CardDescription>支持.xlsx格式，系统自动识别车型、本金、买断价等字段</CardDescription>
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
            <div className="mt-4 text-sm">
              <Badge variant="default">
                成功解析 {parseInfo.success_rows}/{parseInfo.total_rows} 行
              </Badge>
              {parseInfo.errors.length > 0 && (
                <div className="mt-2 text-orange-600">
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

      {/* Step 2: Parameters */}
      {packageId && (
        <Card>
          <CardHeader>
            <CardTitle>第二步：调整计算参数</CardTitle>
            <CardDescription>根据实际业务情况调整以下参数</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
              <div>
                <Label>单台拖车费 (元)</Label>
                <Input
                  type="number"
                  value={params.towing_cost}
                  onChange={(e) =>
                    setParams({ ...params, towing_cost: Number(e.target.value) })
                  }
                />
              </div>
              <div>
                <Label>日停车费 (元/天)</Label>
                <Input
                  type="number"
                  value={params.daily_parking}
                  onChange={(e) =>
                    setParams({ ...params, daily_parking: Number(e.target.value) })
                  }
                />
              </div>
              <div>
                <Label>资金成本年化率 (%)</Label>
                <Input
                  type="number"
                  value={params.capital_rate}
                  onChange={(e) =>
                    setParams({ ...params, capital_rate: Number(e.target.value) })
                  }
                />
              </div>
              <div>
                <Label>预期处置周期 (天)</Label>
                <Input
                  type="number"
                  value={params.disposal_period}
                  onChange={(e) =>
                    setParams({ ...params, disposal_period: Number(e.target.value) })
                  }
                />
              </div>
            </div>
            <Button className="mt-6" onClick={handleCalculate} disabled={calculating}>
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
