"use client";

import { useCallback, useEffect, useState } from "react";
import {
  assignDisposalTask,
  completeDisposalTask,
  createDisposalTask,
  generateTasksFromPortfolio,
  listDisposalTasks,
  type DisposalTask,
} from "@/lib/api";

const STATUS_LABELS: Record<string, string> = {
  pending: "待处理",
  assigned: "已分配",
  in_progress: "进行中",
  blocked: "受阻",
  done: "已完成",
  cancelled: "已取消",
};

const TYPE_LABELS: Record<string, string> = {
  towing: "拖车",
  inventory_check: "入库核验",
  valuation: "估值",
  auction: "竞拍",
  litigation: "法务诉讼",
  special_procedure: "特别程序",
  collection: "催收",
  restructure: "重组谈判",
  debt_transfer: "债权转让准备",
  data_supplement: "资料补录",
};

function fmt(n: number | null | undefined) {
  if (n === null || n === undefined || Number.isNaN(n)) return "-";
  return n.toLocaleString("zh-CN", { maximumFractionDigits: 0 });
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<DisposalTask[]>([]);
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [manualTitle, setManualTitle] = useState("");
  const [manualType, setManualType] = useState("auction");
  const [manualRecovery, setManualRecovery] = useState<number | "">("");
  const [completeValues, setCompleteValues] = useState<Record<number, string>>({});

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setTasks(await listDisposalTasks(status ? { status } : undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : "任务加载失败");
    } finally {
      setLoading(false);
    }
  }, [status]);

  useEffect(() => {
    void load();
  }, [load]);

  async function generatePortfolioTasks() {
    setBusy(true);
    setError("");
    try {
      await generateTasksFromPortfolio();
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "生成任务失败");
    } finally {
      setBusy(false);
    }
  }

  async function addManualTask() {
    if (!manualTitle.trim()) {
      setError("请填写任务标题");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await createDisposalTask({
        task_type: manualType,
        title: manualTitle.trim(),
        priority: "medium",
        expected_recovery: manualRecovery === "" ? null : manualRecovery,
        source_type: "manual",
      });
      setManualTitle("");
      setManualRecovery("");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建任务失败");
    } finally {
      setBusy(false);
    }
  }

  async function assignToMe(taskId: number) {
    setBusy(true);
    setError("");
    try {
      await assignDisposalTask(taskId, 1);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "分配失败");
    } finally {
      setBusy(false);
    }
  }

  async function complete(taskId: number) {
    setBusy(true);
    setError("");
    try {
      await completeDisposalTask(taskId, {
        actual_recovery: completeValues[taskId] ? Number(completeValues[taskId]) : null,
        result_note: "前端任务闭环回填",
        evidence_files: [],
      });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "完成任务失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">行动中心任务闭环</h1>
          <p className="mt-1 text-sm text-gray-500">把组合计划和沙盘建议转成可分配、可完成、可回填结果的任务。</p>
        </div>
        <button
          type="button"
          onClick={generatePortfolioTasks}
          disabled={busy}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm text-white disabled:bg-gray-300"
        >
          {busy ? "处理中..." : "从组合产能计划生成任务"}
        </button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="rounded-xl border bg-white p-5">
        <h3 className="mb-3 text-sm font-semibold text-gray-800">手动创建任务</h3>
        <div className="grid gap-3 md:grid-cols-[180px_1fr_180px_auto]">
          <select className="h-9 rounded-lg border border-gray-200 px-3 text-sm" value={manualType} onChange={(event) => setManualType(event.target.value)}>
            {Object.entries(TYPE_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
          <input
            className="h-9 rounded-lg border border-gray-200 px-3 text-sm"
            placeholder="任务标题"
            value={manualTitle}
            onChange={(event) => setManualTitle(event.target.value)}
          />
          <input
            type="number"
            className="h-9 rounded-lg border border-gray-200 px-3 text-sm"
            placeholder="预计回款"
            value={manualRecovery}
            onChange={(event) => setManualRecovery(event.target.value ? Number(event.target.value) : "")}
          />
          <button type="button" onClick={addManualTask} disabled={busy} className="rounded-lg border px-4 py-2 text-sm disabled:text-gray-400">
            创建
          </button>
        </div>
      </div>

      <div className="rounded-xl border bg-white p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-800">任务列表</h3>
          <select className="h-9 rounded-lg border border-gray-200 px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="">全部状态</option>
            {Object.entries(STATUS_LABELS).map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
        </div>

        {loading ? (
          <p className="py-12 text-center text-sm text-gray-500">加载中...</p>
        ) : tasks.length === 0 ? (
          <p className="py-12 text-center text-sm text-gray-400">暂无任务</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-3 py-2 text-left">任务</th>
                  <th className="px-3 py-2 text-left">状态</th>
                  <th className="px-3 py-2 text-right">预计/实际回款</th>
                  <th className="px-3 py-2 text-left">来源</th>
                  <th className="px-3 py-2 text-left">操作</th>
                </tr>
              </thead>
              <tbody>
                {tasks.map((task) => (
                  <tr key={task.id} className="border-t">
                    <td className="px-3 py-2">
                      <div className="font-medium text-gray-900">{task.title}</div>
                      <div className="text-xs text-gray-500">{TYPE_LABELS[task.task_type] || task.task_type} · {task.priority}</div>
                    </td>
                    <td className="px-3 py-2">{STATUS_LABELS[task.status] || task.status}</td>
                    <td className="px-3 py-2 text-right">
                      ¥{fmt(task.expected_recovery)} / ¥{fmt(task.actual_recovery)}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">
                      {task.source_type || "-"} {task.source_id ? `#${task.source_id}` : ""}
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-wrap items-center gap-2">
                        {task.status !== "done" && (
                          <button type="button" onClick={() => assignToMe(task.id)} disabled={busy} className="rounded border px-2 py-1 text-xs">
                            分配
                          </button>
                        )}
                        {task.status !== "done" && (
                          <>
                            <input
                              type="number"
                              className="h-7 w-28 rounded border px-2 text-xs"
                              placeholder="实际回款"
                              value={completeValues[task.id] || ""}
                              onChange={(event) => setCompleteValues({ ...completeValues, [task.id]: event.target.value })}
                            />
                            <button type="button" onClick={() => complete(task.id)} disabled={busy} className="rounded border px-2 py-1 text-xs">
                              完成
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
