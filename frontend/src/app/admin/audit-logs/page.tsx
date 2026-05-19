"use client";

import { useCallback, useEffect, useState } from "react";
import { exportAuditLogsCsv, listAuditLogs, type AuditLogRow } from "@/lib/api";

export default function AuditLogsPage() {
  const [rows, setRows] = useState<AuditLogRow[]>([]);
  const [action, setAction] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRows(await listAuditLogs(action ? { action } : undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : "审计日志加载失败");
    } finally {
      setLoading(false);
    }
  }, [action]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleExport() {
    setError("");
    try {
      const csv = await exportAuditLogsCsv(action ? { action } : undefined);
      const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "audit-logs.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : "导出失败");
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">审计日志</h1>
          <p className="mt-1 text-sm text-gray-500">查询关键动作留痕，并导出带水印的审计 CSV。</p>
        </div>
        <button type="button" onClick={handleExport} className="rounded-lg border px-4 py-2 text-sm">
          导出 CSV
        </button>
      </div>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">{error}</div>}

      <div className="rounded-xl border bg-white p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-sm font-semibold text-gray-800">日志列表</h3>
          <input
            className="h-9 rounded-lg border border-gray-200 px-3 text-sm"
            placeholder="按 action 过滤，如 task_complete"
            value={action}
            onChange={(event) => setAction(event.target.value)}
          />
        </div>

        {loading ? (
          <p className="py-12 text-center text-sm text-gray-500">加载中...</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-xs text-gray-500">
                <tr>
                  <th className="px-3 py-2 text-left">时间</th>
                  <th className="px-3 py-2 text-left">动作</th>
                  <th className="px-3 py-2 text-left">对象</th>
                  <th className="px-3 py-2 text-left">用户/IP</th>
                  <th className="px-3 py-2 text-left">Request ID</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t">
                    <td className="px-3 py-2 text-xs">{row.created_at || "-"}</td>
                    <td className="px-3 py-2 font-medium">{row.action}</td>
                    <td className="px-3 py-2 text-xs">
                      {row.resource_type || "-"} {row.resource_id ? `#${row.resource_id}` : ""}
                    </td>
                    <td className="px-3 py-2 text-xs">
                      用户 {row.user_id || "-"} / {row.ip || "-"}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500">{row.request_id || "-"}</td>
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
