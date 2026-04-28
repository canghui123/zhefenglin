"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  createWorkOrder,
  getActionWorkOrderCandidates,
  type ActionWorkOrderCandidateAsset,
  type ActionWorkOrderCandidateData,
} from "@/lib/api";

type BuilderMode = "towing" | "auction";

interface AssetConfig {
  selected: boolean;
  towing_commission: number;
  work_order_days: number;
  towing_vendor: string;
  starting_price: number;
  reserve_price: number;
  auction_start_at: string;
  auction_end_at: string;
  auction_platform: string;
}

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

function defaultConfig(asset: ActionWorkOrderCandidateAsset): AssetConfig {
  return {
    selected: true,
    towing_commission: asset.default_towing_commission,
    work_order_days: asset.default_work_order_days,
    towing_vendor: "默认拖车供应商",
    starting_price: asset.default_starting_price,
    reserve_price: asset.default_reserve_price,
    auction_start_at: asset.default_auction_start_at,
    auction_end_at: asset.default_auction_end_at,
    auction_platform: "主竞拍渠道",
  };
}

export function ActionWorkOrderBuilder({ mode }: { mode: BuilderMode }) {
  const [segmentName, setSegmentName] = useState("");
  const [data, setData] = useState<ActionWorkOrderCandidateData | null>(null);
  const [configs, setConfigs] = useState<Record<string, AssetConfig>>({});
  const [search, setSearch] = useState("");
  const [cityFilter, setCityFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState("");
  const [batchCommission, setBatchCommission] = useState(2500);
  const [batchDays, setBatchDays] = useState(7);
  const [batchVendor, setBatchVendor] = useState("默认拖车供应商");
  const [batchAuctionDiscount, setBatchAuctionDiscount] = useState(0.85);
  const [batchAuctionStart, setBatchAuctionStart] = useState("");
  const [batchAuctionEnd, setBatchAuctionEnd] = useState("");
  const [batchPlatform, setBatchPlatform] = useState("主竞拍渠道");

  const orderType = mode === "towing" ? "towing" : "auction_push";
  const modeTitle = mode === "towing" ? "拖车工单编排" : "拍卖工单编排";

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    setSegmentName(query.get("segment") || "");
  }, []);

  useEffect(() => {
    if (!segmentName) {
      setLoading(false);
      return;
    }
    setLoading(true);
    getActionWorkOrderCandidates(orderType, segmentName)
      .then((nextData) => {
        const nextConfigs: Record<string, AssetConfig> = {};
        nextData.candidates.forEach((asset) => {
          nextConfigs[asset.asset_identifier] = defaultConfig(asset);
        });
        setData(nextData);
        setConfigs(nextConfigs);
        const first = nextData.candidates[0];
        if (first) {
          setBatchCommission(first.default_towing_commission);
          setBatchDays(first.default_work_order_days);
          setBatchAuctionStart(first.default_auction_start_at);
          setBatchAuctionEnd(first.default_auction_end_at);
        }
      })
      .catch((error) => {
        setMessage(error instanceof Error ? error.message : "加载候选资产失败");
      })
      .finally(() => setLoading(false));
  }, [orderType, segmentName]);

  const visibleCandidates = useMemo(() => {
    const keyword = search.trim().toLowerCase();
    return (data?.candidates || []).filter((asset) => {
      const matchesKeyword =
        !keyword ||
        asset.asset_identifier.toLowerCase().includes(keyword) ||
        asset.contract_number.toLowerCase().includes(keyword) ||
        asset.debtor_name.toLowerCase().includes(keyword) ||
        asset.car_description.toLowerCase().includes(keyword) ||
        asset.license_plate.toLowerCase().includes(keyword);
      const matchesCity = !cityFilter || asset.city === cityFilter;
      return matchesKeyword && matchesCity;
    });
  }, [cityFilter, data?.candidates, search]);

  const cities = useMemo(
    () => Array.from(new Set((data?.candidates || []).map((asset) => asset.city))).filter(Boolean),
    [data?.candidates],
  );

  const selectedAssets = useMemo(
    () => (data?.candidates || []).filter((asset) => configs[asset.asset_identifier]?.selected),
    [configs, data?.candidates],
  );

  const visibleAllSelected =
    visibleCandidates.length > 0 &&
    visibleCandidates.every((asset) => configs[asset.asset_identifier]?.selected);

  function updateConfig(assetId: string, patch: Partial<AssetConfig>) {
    setConfigs((prev) => ({
      ...prev,
      [assetId]: {
        ...prev[assetId],
        ...patch,
      },
    }));
  }

  function toggleVisible(checked: boolean) {
    setConfigs((prev) => {
      const next = { ...prev };
      visibleCandidates.forEach((asset) => {
        next[asset.asset_identifier] = {
          ...next[asset.asset_identifier],
          selected: checked,
        };
      });
      return next;
    });
  }

  function applyBatchConfig() {
    setConfigs((prev) => {
      const next = { ...prev };
      selectedAssets.forEach((asset) => {
        const current = next[asset.asset_identifier];
        if (mode === "towing") {
          next[asset.asset_identifier] = {
            ...current,
            towing_commission: batchCommission,
            work_order_days: batchDays,
            towing_vendor: batchVendor,
          };
        } else {
          next[asset.asset_identifier] = {
            ...current,
            starting_price: Math.round(asset.vehicle_value * batchAuctionDiscount),
            reserve_price: Math.round(asset.vehicle_value * Math.max(batchAuctionDiscount - 0.07, 0.5)),
            auction_start_at: batchAuctionStart,
            auction_end_at: batchAuctionEnd,
            auction_platform: batchPlatform,
          };
        }
      });
      return next;
    });
  }

  async function publishWorkOrder() {
    if (!data || selectedAssets.length === 0) {
      setMessage("请至少选择一台车辆");
      return;
    }
    setSubmitting(true);
    setMessage("");
    try {
      const lineItems = selectedAssets.map((asset) => {
        const config = configs[asset.asset_identifier] || defaultConfig(asset);
        return {
          asset_identifier: asset.asset_identifier,
          contract_number: asset.contract_number,
          debtor_name: asset.debtor_name,
          car_description: asset.car_description,
          license_plate: asset.license_plate,
          province: asset.province,
          city: asset.city,
          overdue_bucket: asset.overdue_bucket,
          overdue_days: asset.overdue_days,
          overdue_amount: asset.overdue_amount,
          vehicle_value: asset.vehicle_value,
          recovered_status: asset.recovered_status,
          gps_last_seen: asset.gps_last_seen,
          risk_tags: asset.risk_tags,
          ...(mode === "towing"
            ? {
                towing_commission: config.towing_commission,
                work_order_days: config.work_order_days,
                towing_vendor: config.towing_vendor,
              }
            : {
                starting_price: config.starting_price,
                reserve_price: config.reserve_price,
                auction_start_at: config.auction_start_at,
                auction_end_at: config.auction_end_at,
                auction_platform: config.auction_platform,
              }),
        };
      });
      await createWorkOrder({
        order_type: orderType,
        title: `${mode === "towing" ? "委外拖车" : "拍卖推送"}：${data.segment_name}（${lineItems.length}台）`,
        target_description: `${data.segment_name}，已选择 ${lineItems.length}/${data.segment_count} 台`,
        priority: data.segment_name.includes("M5") || data.segment_name.includes("M6") ? "urgent" : "high",
        source_type: "action_center_batch_builder",
        source_id: data.segment_name,
        payload: {
          workflow: mode === "towing" ? "towing_batch_builder" : "auction_batch_builder",
          segment_name: data.segment_name,
          selected_count: lineItems.length,
          total_candidates: data.segment_count,
          total_selected_overdue_amount: lineItems.reduce((sum, item) => sum + item.overdue_amount, 0),
          line_items: lineItems,
        },
      });
      setMessage(`已发布${mode === "towing" ? "拖车" : "拍卖"}工单，包含 ${lineItems.length} 台车辆`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "发布工单失败");
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <div className="py-20 text-center text-gray-500">加载中...</div>;

  if (!segmentName) {
    return (
      <div className="space-y-4">
        <Link className="text-sm text-blue-600 hover:underline" href="/portfolio/actions">
          返回动作中心
        </Link>
        <div className="rounded-xl border bg-white p-8 text-center text-gray-500">
          请从动作中心的分层清单进入{modeTitle}。
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link className="text-sm text-blue-600 hover:underline" href="/portfolio/actions">
            返回动作中心
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">{modeTitle}</h1>
          <p className="mt-1 text-sm text-gray-500">
            {segmentName}，可单台调整，也可筛选后批量应用参数并发布执行工单。
          </p>
        </div>
        <div className="rounded-xl border bg-white px-4 py-3 text-right">
          <div className="text-xs text-gray-500">已选择</div>
          <div className="text-2xl font-bold text-slate-900">
            {selectedAssets.length}/{data?.segment_count || 0}
          </div>
        </div>
      </div>

      {message && (
        <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          {message}
        </div>
      )}

      <div className="rounded-xl border bg-white p-5">
        <div className="grid gap-3 lg:grid-cols-[1fr_180px_auto]">
          <input
            className="rounded-lg border px-3 py-2 text-sm"
            placeholder="搜索资产编号、合同、债务人、车型、车牌"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <select
            className="rounded-lg border px-3 py-2 text-sm"
            value={cityFilter}
            onChange={(event) => setCityFilter(event.target.value)}
          >
            <option value="">全部城市</option>
            {cities.map((city) => (
              <option key={city} value={city}>
                {city}
              </option>
            ))}
          </select>
          <button
            className="rounded-lg border px-3 py-2 text-sm font-medium hover:bg-gray-50"
            onClick={() => toggleVisible(!visibleAllSelected)}
          >
            {visibleAllSelected ? "取消当前筛选" : "选择当前筛选"}
          </button>
        </div>
      </div>

      <div className="rounded-xl border bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold text-gray-700">批量参数</h3>
        {mode === "towing" ? (
          <div className="grid gap-3 md:grid-cols-4">
            <NumberField label="每台拖车佣金" value={batchCommission} onChange={setBatchCommission} />
            <NumberField label="工单周期(天)" value={batchDays} onChange={setBatchDays} />
            <TextField label="拖车供应商" value={batchVendor} onChange={setBatchVendor} />
            <button className="rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700" onClick={applyBatchConfig}>
              应用到已选车辆
            </button>
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-5">
            <NumberField label="起拍折扣" step="0.01" value={batchAuctionDiscount} onChange={setBatchAuctionDiscount} />
            <TextField label="拍卖开始" type="date" value={batchAuctionStart} onChange={setBatchAuctionStart} />
            <TextField label="拍卖结束" type="date" value={batchAuctionEnd} onChange={setBatchAuctionEnd} />
            <TextField label="拍卖渠道" value={batchPlatform} onChange={setBatchPlatform} />
            <button className="rounded-lg bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700" onClick={applyBatchConfig}>
              应用到已选车辆
            </button>
          </div>
        )}
      </div>

      <div className="overflow-x-auto rounded-xl border bg-white">
        <table className="w-full min-w-[1180px] text-sm">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-3 py-2 text-left">选择</th>
              <th className="px-3 py-2 text-left">车辆/合同</th>
              <th className="px-3 py-2 text-left">逾期信息</th>
              <th className="px-3 py-2 text-right">估值</th>
              <th className="px-3 py-2 text-left">位置/线索</th>
              {mode === "towing" ? (
                <>
                  <th className="px-3 py-2 text-right">佣金</th>
                  <th className="px-3 py-2 text-right">周期</th>
                  <th className="px-3 py-2 text-left">供应商</th>
                </>
              ) : (
                <>
                  <th className="px-3 py-2 text-right">起拍价</th>
                  <th className="px-3 py-2 text-right">保留价</th>
                  <th className="px-3 py-2 text-left">起止时间</th>
                  <th className="px-3 py-2 text-left">渠道</th>
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {visibleCandidates.map((asset) => {
              const config = configs[asset.asset_identifier];
              return (
                <tr key={asset.asset_identifier} className="border-t align-top hover:bg-gray-50">
                  <td className="px-3 py-3">
                    <input
                      type="checkbox"
                      checked={Boolean(config?.selected)}
                      onChange={(event) => updateConfig(asset.asset_identifier, { selected: event.target.checked })}
                    />
                  </td>
                  <td className="px-3 py-3">
                    <div className="font-medium text-gray-900">{asset.asset_identifier}</div>
                    <div className="text-xs text-gray-500">{asset.contract_number} / {asset.debtor_name}</div>
                    <div className="text-xs text-gray-500">{asset.car_description} / {asset.license_plate}</div>
                  </td>
                  <td className="px-3 py-3">
                    <div>{asset.overdue_bucket}</div>
                    <div className="text-xs text-gray-500">逾期 {asset.overdue_days} 天，¥{fmt(asset.overdue_amount)}</div>
                    <div className="mt-1 space-x-1">
                      {asset.risk_tags.map((tag) => (
                        <span key={tag} className="rounded bg-amber-50 px-1.5 py-0.5 text-xs text-amber-700">
                          {tag}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-3 text-right">¥{fmt(asset.vehicle_value)}</td>
                  <td className="px-3 py-3">
                    <div>{asset.province} / {asset.city}</div>
                    <div className="text-xs text-gray-500">GPS最近：{asset.gps_last_seen}</div>
                  </td>
                  {mode === "towing" ? (
                    <>
                      <td className="px-3 py-3">
                        <SmallNumber
                          value={config?.towing_commission || 0}
                          onChange={(value) => updateConfig(asset.asset_identifier, { towing_commission: value })}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <SmallNumber
                          value={config?.work_order_days || 0}
                          onChange={(value) => updateConfig(asset.asset_identifier, { work_order_days: value })}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <input
                          className="w-36 rounded border px-2 py-1 text-xs"
                          value={config?.towing_vendor || ""}
                          onChange={(event) => updateConfig(asset.asset_identifier, { towing_vendor: event.target.value })}
                        />
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="px-3 py-3">
                        <SmallNumber
                          value={config?.starting_price || 0}
                          onChange={(value) => updateConfig(asset.asset_identifier, { starting_price: value })}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <SmallNumber
                          value={config?.reserve_price || 0}
                          onChange={(value) => updateConfig(asset.asset_identifier, { reserve_price: value })}
                        />
                      </td>
                      <td className="px-3 py-3">
                        <div className="flex gap-1">
                          <input
                            className="w-32 rounded border px-2 py-1 text-xs"
                            type="date"
                            value={config?.auction_start_at || ""}
                            onChange={(event) => updateConfig(asset.asset_identifier, { auction_start_at: event.target.value })}
                          />
                          <input
                            className="w-32 rounded border px-2 py-1 text-xs"
                            type="date"
                            value={config?.auction_end_at || ""}
                            onChange={(event) => updateConfig(asset.asset_identifier, { auction_end_at: event.target.value })}
                          />
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <input
                          className="w-36 rounded border px-2 py-1 text-xs"
                          value={config?.auction_platform || ""}
                          onChange={(event) => updateConfig(asset.asset_identifier, { auction_platform: event.target.value })}
                        />
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <div className="sticky bottom-0 flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-white/95 p-4 shadow-lg backdrop-blur">
        <div className="text-sm text-gray-600">
          已选 <span className="font-semibold text-gray-900">{selectedAssets.length}</span> 台，
          合计逾期金额 ¥{fmt(selectedAssets.reduce((sum, asset) => sum + asset.overdue_amount, 0))}
        </div>
        <button
          className="rounded-lg bg-slate-900 px-5 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:opacity-50"
          disabled={submitting || selectedAssets.length === 0}
          onClick={publishWorkOrder}
        >
          {submitting ? "发布中..." : `发布${mode === "towing" ? "拖车" : "拍卖"}工单`}
        </button>
      </div>
    </div>
  );
}

function NumberField({
  label,
  value,
  onChange,
  step = "1",
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  step?: string;
}) {
  return (
    <label className="block text-xs font-medium text-gray-600">
      {label}
      <input
        className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
        type="number"
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value || 0))}
      />
    </label>
  );
}

function TextField({
  label,
  value,
  onChange,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
}) {
  return (
    <label className="block text-xs font-medium text-gray-600">
      {label}
      <input
        className="mt-1 w-full rounded-lg border px-3 py-2 text-sm"
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function SmallNumber({ value, onChange }: { value: number; onChange: (value: number) => void }) {
  return (
    <input
      className="w-28 rounded border px-2 py-1 text-right text-xs"
      type="number"
      value={value}
      onChange={(event) => onChange(Number(event.target.value || 0))}
    />
  );
}
