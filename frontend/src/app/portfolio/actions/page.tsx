"use client";

import { useEffect, useState } from "react";
import {
  createWorkOrder,
  getActionCenter,
  listWorkOrders,
  updateWorkOrderStatus,
  type ActionCenterData,
  type WorkOrderInfo,
} from "@/lib/api";

function fmt(n: number) {
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export default function ActionCenterPage() {
  const [data, setData] = useState<ActionCenterData | null>(null);
  const [workOrders, setWorkOrders] = useState<WorkOrderInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [submittingKey, setSubmittingKey] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    Promise.all([getActionCenter(), listWorkOrders()])
      .then(([actionData, orders]) => {
        setData(actionData);
        setWorkOrders(orders);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  async function refreshWorkOrders() {
    const orders = await listWorkOrders();
    setWorkOrders(orders);
  }

  async function handleCreateAuctionOrder(item: ActionCenterData["auction_ready"][number]) {
    const key = `auction:${item.segment_name}`;
    setSubmittingKey(key);
    setMessage("");
    try {
      await createWorkOrder({
        order_type: "auction_push",
        title: `拍卖推送：${item.segment_name}`,
        target_description: `${item.count}台在库车辆，建议单台底价 ¥${fmt(item.recommended_floor_price)}`,
        priority: item.risk_tags.length > 0 ? "high" : "normal",
        source_type: "portfolio_segment",
        source_id: item.segment_name,
        payload: {
          count: item.count,
          estimated_value: item.estimated_value,
          recommended_floor_price: item.recommended_floor_price,
          risk_tags: item.risk_tags,
        },
      });
      await refreshWorkOrders();
      setMessage("已生成拍卖推送工单");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "生成工单失败");
    } finally {
      setSubmittingKey("");
    }
  }

  async function handleCreateTowingOrder(item: ActionCenterData["recovery_tasks"][number]) {
    const key = `towing:${item.segment_name}`;
    setSubmittingKey(key);
    setMessage("");
    try {
      await createWorkOrder({
        order_type: "towing",
        title: `委外拖车：${item.segment_name}`,
        target_description: `${item.count}台未收回车辆，逾期阶段 ${item.overdue_bucket}`,
        priority: item.overdue_bucket.startsWith("M5") || item.overdue_bucket.startsWith("M6") ? "urgent" : "high",
        source_type: "portfolio_segment",
        source_id: item.segment_name,
        payload: {
          count: item.count,
          overdue_bucket: item.overdue_bucket,
          total_ead: item.total_ead,
        },
      });
      await refreshWorkOrders();
      setMessage("已生成委外拖车工单");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "生成工单失败");
    } finally {
      setSubmittingKey("");
    }
  }

  async function handleStatus(workOrderId: number, status: string) {
    setSubmittingKey(`status:${workOrderId}`);
    setMessage("");
    try {
      await updateWorkOrderStatus(workOrderId, status);
      await refreshWorkOrders();
      setMessage("工单状态已更新");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "更新状态失败");
    } finally {
      setSubmittingKey("");
    }
  }

  if (loading) return <div className="text-center py-20 text-gray-500">加载中...</div>;
  if (!data) return <div className="text-center py-20 text-red-500">加载失败</div>;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">动作中心</h1>
        <p className="text-sm text-gray-500 mt-1">今天具体做什么 — 执行层待办清单</p>
      </div>

      {message && (
        <div className="rounded-lg border border-blue-100 bg-blue-50 px-4 py-3 text-sm text-blue-700">
          {message}
        </div>
      )}

      {/* 今日待办 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">今日重点</h3>
        <div className="space-y-3">
          {data.recommendations.map((rec, i) => (
            <div key={i} className="p-4 border rounded-lg flex items-start gap-3">
              <div className={`w-2 h-2 rounded-full mt-2 shrink-0 ${
                rec.priority === 1 ? "bg-red-500" : "bg-yellow-500"
              }`} />
              <div>
                <div className="font-semibold text-sm text-gray-900">{rec.recommendation_title}</div>
                <p className="text-sm text-gray-600 mt-0.5">{rec.recommendation_text}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 竞拍/处置就绪 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-emerald-600 mb-3">竞拍/处置就绪清单</h3>
        {data.auction_ready.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">分层</th>
                  <th className="text-right px-3 py-2">台数</th>
                  <th className="text-right px-3 py-2">预估总值</th>
                  <th className="text-right px-3 py-2">建议底价(单台)</th>
                  <th className="text-left px-3 py-2">风险标签</th>
                  <th className="text-right px-3 py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {data.auction_ready.map((item) => (
                  <tr key={item.segment_name} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-2 text-xs font-medium">{item.segment_name}</td>
                    <td className="text-right px-3 py-2">{item.count}台</td>
                    <td className="text-right px-3 py-2 text-emerald-600">¥{fmt(item.estimated_value)}</td>
                    <td className="text-right px-3 py-2">¥{fmt(item.recommended_floor_price)}</td>
                    <td className="px-3 py-2">
                      {item.risk_tags.map((tag) => (
                        <span key={tag} className="text-xs bg-yellow-100 text-yellow-700 px-1.5 py-0.5 rounded mr-1">
                          {tag}
                        </span>
                      ))}
                    </td>
                    <td className="text-right px-3 py-2">
                      <button
                        className="rounded border border-emerald-200 px-2.5 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                        disabled={submittingKey === `auction:${item.segment_name}`}
                        onClick={() => handleCreateAuctionOrder(item)}
                      >
                        生成拍卖工单
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-400">暂无就绪资产</p>
        )}
      </div>

      {/* 收车推进 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-blue-600 mb-3">收车推进清单</h3>
        {data.recovery_tasks.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">分层</th>
                  <th className="text-right px-3 py-2">待收车数</th>
                  <th className="text-left px-3 py-2">逾期分段</th>
                  <th className="text-right px-3 py-2">EAD</th>
                  <th className="text-right px-3 py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {data.recovery_tasks.map((item) => (
                  <tr key={item.segment_name} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-2 text-xs font-medium">{item.segment_name}</td>
                    <td className="text-right px-3 py-2 font-semibold">{item.count}台</td>
                    <td className="px-3 py-2 text-xs">{item.overdue_bucket}</td>
                    <td className="text-right px-3 py-2">¥{fmt(item.total_ead)}</td>
                    <td className="text-right px-3 py-2">
                      <button
                        className="rounded border border-blue-200 px-2.5 py-1 text-xs font-medium text-blue-700 hover:bg-blue-50 disabled:opacity-50"
                        disabled={submittingKey === `towing:${item.segment_name}`}
                        onClick={() => handleCreateTowingOrder(item)}
                      >
                        生成拖车工单
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-400">暂无收车任务</p>
        )}
      </div>

      {/* 执行工单 */}
      <div className="bg-white rounded-xl border p-5">
        <h3 className="text-sm font-semibold text-gray-700 mb-3">执行工单</h3>
        {workOrders.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="text-left px-3 py-2">工单</th>
                  <th className="text-left px-3 py-2">类型</th>
                  <th className="text-left px-3 py-2">优先级</th>
                  <th className="text-left px-3 py-2">状态</th>
                  <th className="text-left px-3 py-2">目标</th>
                  <th className="text-right px-3 py-2">操作</th>
                </tr>
              </thead>
              <tbody>
                {workOrders.slice(0, 10).map((order) => (
                  <tr key={order.id} className="border-t hover:bg-gray-50">
                    <td className="px-3 py-2 font-medium">{order.title}</td>
                    <td className="px-3 py-2 text-xs">{orderTypeName(order.order_type)}</td>
                    <td className="px-3 py-2 text-xs">{priorityName(order.priority)}</td>
                    <td className="px-3 py-2">
                      <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-700">
                        {statusName(order.status)}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500 max-w-[280px] truncate">
                      {order.target_description || "-"}
                    </td>
                    <td className="text-right px-3 py-2 space-x-2">
                      {order.status === "pending" && (
                        <button
                          className="rounded border px-2 py-1 text-xs hover:bg-gray-50 disabled:opacity-50"
                          disabled={submittingKey === `status:${order.id}`}
                          onClick={() => handleStatus(order.id, "in_progress")}
                        >
                          开始
                        </button>
                      )}
                      {order.status !== "completed" && order.status !== "cancelled" && (
                        <button
                          className="rounded border border-emerald-200 px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-50 disabled:opacity-50"
                          disabled={submittingKey === `status:${order.id}`}
                          onClick={() => handleStatus(order.id, "completed")}
                        >
                          完成
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-gray-400">暂无执行工单，可从上方清单一键生成。</p>
        )}
      </div>
    </div>
  );
}

function orderTypeName(type: string) {
  const names: Record<string, string> = {
    towing: "委外拖车",
    legal_document: "法务材料",
    auction_push: "拍卖推送",
  };
  return names[type] || type;
}

function priorityName(priority: string) {
  const names: Record<string, string> = {
    low: "低",
    normal: "普通",
    high: "高",
    urgent: "紧急",
  };
  return names[priority] || priority;
}

function statusName(status: string) {
  const names: Record<string, string> = {
    pending: "待处理",
    in_progress: "处理中",
    completed: "已完成",
    cancelled: "已取消",
  };
  return names[status] || status;
}
