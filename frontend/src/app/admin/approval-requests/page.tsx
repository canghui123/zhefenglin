"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminAccess } from "@/components/admin/admin-access";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  approveApprovalRequest,
  createApprovalRequest,
  listApprovalRequests,
  rejectApprovalRequest,
  type ApprovalRequestInfo,
} from "@/lib/api";
import { useSession } from "@/components/auth/session-provider";

export default function AdminApprovalRequestsPage() {
  const { user } = useSession();
  const [rows, setRows] = useState<ApprovalRequestInfo[]>([]);
  const [form, setForm] = useState({
    type: "condition_pricing",
    reason: "",
    related_object_type: "vehicle",
    related_object_id: "",
    estimated_cost: 36,
  });

  async function refresh() {
    setRows(await listApprovalRequests());
  }

  useEffect(() => {
    let cancelled = false;
    void listApprovalRequests().then((data) => {
      if (!cancelled) {
        setRows(data);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await createApprovalRequest(form);
      setForm({ type: "condition_pricing", reason: "", related_object_type: "vehicle", related_object_id: "", estimated_cost: 36 });
      await refresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "创建失败");
    }
  }

  return (
    <AdminAccess minRole="manager">
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">审批请求</h1>
          <p className="text-sm text-gray-500 mt-1">对高级车况定价等高成本动作执行申请、审批和追踪。</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>发起审批</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreate} className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="space-y-2">
                <Label htmlFor="approval-type">类型</Label>
                <Input id="approval-type" value={form.type} onChange={(event) => setForm((prev) => ({ ...prev, type: event.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="approval-object">对象ID</Label>
                <Input id="approval-object" value={form.related_object_id} onChange={(event) => setForm((prev) => ({ ...prev, related_object_id: event.target.value }))} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="approval-cost">预计成本</Label>
                <Input id="approval-cost" type="number" value={form.estimated_cost} onChange={(event) => setForm((prev) => ({ ...prev, estimated_cost: Number(event.target.value) }))} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="approval-reason">原因</Label>
                <Input id="approval-reason" value={form.reason} onChange={(event) => setForm((prev) => ({ ...prev, reason: event.target.value }))} />
              </div>
              <div className="md:col-span-4">
                <Button type="submit">提交审批</Button>
              </div>
            </form>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>审批历史</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="pb-3 font-medium">ID</th>
                    <th className="pb-3 font-medium">类型</th>
                    <th className="pb-3 font-medium">关联对象</th>
                    <th className="pb-3 font-medium">原因</th>
                    <th className="pb-3 font-medium">状态</th>
                    <th className="pb-3 font-medium">消费情况</th>
                    <th className="pb-3 font-medium">预计成本</th>
                    <th className="pb-3 font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-b last:border-0">
                      <td className="py-3">#{row.id}</td>
                      <td className="py-3">{row.type}</td>
                      <td className="py-3 text-xs text-gray-500">
                        {(row.related_object_type || "-")}/{row.related_object_id || "-"}
                      </td>
                      <td className="py-3">{row.reason}</td>
                      <td className="py-3">{row.status}</td>
                      <td className="py-3 text-xs text-gray-500">
                        {row.is_consumed && row.consumed_at ? `已消费 ${row.consumed_at}` : "未消费"}
                      </td>
                      <td className="py-3">¥{row.estimated_cost}</td>
                      <td className="py-3">
                        {user?.role === "admin" && row.status === "pending" ? (
                          <div className="flex gap-2">
                            <Button size="sm" variant="outline" onClick={async () => { await approveApprovalRequest(row.id, row.estimated_cost); await refresh(); }}>
                              通过
                            </Button>
                            <Button size="sm" variant="outline" onClick={async () => { await rejectApprovalRequest(row.id, 0); await refresh(); }}>
                              拒绝
                            </Button>
                          </div>
                        ) : (
                          <span className="text-xs text-gray-500">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </AdminAccess>
  );
}
