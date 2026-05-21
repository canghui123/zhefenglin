"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { getDisposalTask, uploadTaskEvidence, type DisposalTask } from "@/lib/api";

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

const PRIORITY_LABELS: Record<string, string> = {
  high: "高优先级",
  medium: "中优先级",
  normal: "普通",
  low: "低优先级",
};

const SOURCE_LABELS: Record<string, string> = {
  manual: "手动创建",
  portfolio_capacity_plan: "组合产能计划",
  sandbox: "处置沙盘",
};

function fmtMoney(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) return "未填写";
  return `¥${value.toLocaleString("zh-CN", { maximumFractionDigits: 0 })}`;
}

function fmtText(value: string | number | null | undefined) {
  if (value === null || value === undefined || value === "") return "未填写";
  return String(value);
}

function fmtDate(value: string | null | undefined) {
  if (!value) return "未填写";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function detailFromResult(task: DisposalTask, key: string) {
  const value = task.result[key];
  if (typeof value === "string" || typeof value === "number") return String(value);
  return "未填写";
}

function evidenceName(storageKey: string) {
  const rawName = storageKey.split("/").pop() || storageKey;
  return rawName.replace(/^[0-9a-fA-F-]{36}-/, "") || rawName;
}

function ownerDisplay(task: DisposalTask) {
  if (task.owner_display_name && task.owner_user_email) {
    return `${task.owner_display_name}（${task.owner_user_email}）`;
  }
  if (task.owner_display_name) return task.owner_display_name;
  if (task.owner_user_email) return task.owner_user_email;
  if (task.owner_user_id) return `用户 ID：${task.owner_user_id}`;
  return "未分配";
}

function FieldRow({ label, value }: { label: string; value: string | number | null | undefined }) {
  return (
    <div className="grid gap-1 border-t border-gray-100 py-3 md:grid-cols-[180px_1fr]">
      <dt className="text-sm text-gray-500">{label}</dt>
      <dd className="text-sm font-medium text-gray-900">{fmtText(value)}</dd>
    </div>
  );
}

export default function TaskDetailPage() {
  const params = useParams<{ id: string }>();
  const taskId = useMemo(() => Number(params.id), [params.id]);
  const [task, setTask] = useState<DisposalTask | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [uploadMessage, setUploadMessage] = useState("");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(async (showPageLoading = true) => {
    if (!Number.isFinite(taskId) || taskId <= 0) {
      setError("任务 ID 无效");
      setLoading(false);
      return;
    }
    if (showPageLoading) setLoading(true);
    setError("");
    try {
      setTask(await getDisposalTask(taskId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "无法加载任务详情，请确认任务存在且你有访问权限。");
    } finally {
      if (showPageLoading) setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    void load();
  }, [load]);

  async function uploadEvidence() {
    if (!selectedFile) return;
    setUploading(true);
    setUploadError("");
    setUploadMessage("");
    try {
      await uploadTaskEvidence(taskId, selectedFile);
      setSelectedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setUploadMessage("证据文件已上传");
      await load(false);
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "证据上传失败");
    } finally {
      setUploading(false);
    }
  }

  async function refreshDetail() {
    setRefreshing(true);
    try {
      await load(false);
    } finally {
      setRefreshing(false);
    }
  }

  if (loading) return <div className="py-20 text-center text-gray-500">加载中...</div>;

  if (error || !task) {
    return (
      <div className="space-y-4">
        <Link href="/tasks" className="text-sm text-slate-700 hover:text-slate-950">
          返回任务列表
        </Link>
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          {error || "任务不存在"}
        </div>
      </div>
    );
  }

  const evidenceFiles = Array.isArray(task.evidence_files) ? task.evidence_files : [];
  const source = [
    task.source_type ? SOURCE_LABELS[task.source_type] || task.source_type : "",
    task.source_id ? `#${task.source_id}` : "",
  ].filter(Boolean).join(" ");

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <Link href="/tasks" className="text-sm text-slate-700 hover:text-slate-950">
            返回任务列表
          </Link>
          <h1 className="mt-2 text-2xl font-bold text-gray-900">{task.title}</h1>
          <p className="mt-1 text-sm text-gray-500">任务 ID：{task.id}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={refreshDetail}
            disabled={refreshing}
            className="rounded-lg border px-3 py-2 text-sm text-gray-700 disabled:text-gray-400"
          >
            {refreshing ? "刷新中..." : "刷新"}
          </button>
          <span className="inline-flex w-fit rounded-full border border-gray-200 px-3 py-1 text-sm text-gray-700">
            {STATUS_LABELS[task.status] || task.status}
          </span>
        </div>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <section className="rounded-xl border bg-white p-5">
        <h2 className="text-sm font-semibold text-gray-800">基础信息</h2>
        <dl className="mt-3">
          <FieldRow label="任务 ID" value={task.id} />
          <FieldRow label="任务标题" value={task.title} />
          <FieldRow label="任务状态" value={STATUS_LABELS[task.status] || task.status} />
          <FieldRow label="任务类型" value={TYPE_LABELS[task.task_type] || task.task_type} />
          <FieldRow label="优先级" value={PRIORITY_LABELS[task.priority] || task.priority} />
          <FieldRow label="分配人" value={ownerDisplay(task)} />
          <FieldRow label="来源" value={source || "未填写"} />
          <FieldRow label="截止时间" value={fmtDate(task.deadline)} />
          <FieldRow label="完成时间" value={fmtDate(detailFromResult(task, "completed_at"))} />
          <FieldRow label="创建时间" value={fmtDate(task.created_at)} />
          <FieldRow label="更新时间" value={fmtDate(task.updated_at)} />
        </dl>
      </section>

      <section className="rounded-xl border bg-white p-5">
        <h2 className="text-sm font-semibold text-gray-800">处置结果</h2>
        <dl className="mt-3">
          <FieldRow label="预计回款" value={fmtMoney(task.expected_recovery)} />
          <FieldRow label="实际回款" value={fmtMoney(task.actual_recovery)} />
          <FieldRow label="处理结果摘要" value={task.result_note || "暂无"} />
          <FieldRow label="偏差原因" value={task.variance_reason || "暂无"} />
        </dl>
      </section>

      <section className="rounded-xl border bg-white p-5">
        <div className="flex flex-col gap-1 md:flex-row md:items-start md:justify-between">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">证据文件</h2>
            <p className="mt-1 text-xs text-gray-500">支持 PDF、JPG、PNG、WEBP，单个文件不超过 10MB。</p>
          </div>
          <span className="text-xs text-gray-500">{evidenceFiles.length} 个文件</span>
        </div>

        <div className="mt-4 rounded-lg border border-dashed border-gray-300 bg-gray-50 p-4">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div className="text-sm font-medium text-gray-800">
                {selectedFile ? selectedFile.name : "选择一个证据文件"}
              </div>
              <div className="mt-1 text-xs text-gray-500">
                上传后会写入任务证据清单，刷新页面后仍可见。
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              <label className="cursor-pointer rounded-lg border bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-100">
                选择文件
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="application/pdf,image/jpeg,image/png,image/webp"
                  className="hidden"
                  onChange={(event) => {
                    setSelectedFile(event.target.files?.[0] || null);
                    setUploadError("");
                    setUploadMessage("");
                  }}
                />
              </label>
              <button
                type="button"
                onClick={uploadEvidence}
                disabled={!selectedFile || uploading}
                className="rounded-lg bg-slate-900 px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:bg-gray-300"
              >
                {uploading ? "上传中..." : "上传证据"}
              </button>
            </div>
          </div>
          {uploadError && <div className="mt-3 rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">{uploadError}</div>}
          {uploadMessage && <div className="mt-3 rounded-md bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{uploadMessage}</div>}
        </div>

        {evidenceFiles.length === 0 ? (
          <p className="mt-3 text-sm text-gray-400">暂无证据文件</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {evidenceFiles.map((file, index) => (
              <li key={`${file}-${index}`} className="rounded-lg border border-gray-100 bg-gray-50 px-3 py-2">
                <div className="flex flex-col gap-1 md:flex-row md:items-center md:justify-between">
                  <div className="text-sm font-medium text-gray-800">{evidenceName(file)}</div>
                  <div className="text-xs text-gray-500">已归档</div>
                </div>
                <div className="mt-1 break-all text-xs text-gray-400">归档路径：{file}</div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
