"use client";

import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { listUsers, updateUserRole, toggleUserActive, type UserInfo } from "@/lib/api";
import { useSession } from "@/components/auth/session-provider";

const ROLE_OPTIONS = [
  { value: "viewer", label: "查看者", color: "bg-gray-100 text-gray-700" },
  { value: "operator", label: "操作员", color: "bg-blue-100 text-blue-700" },
  { value: "manager", label: "经理", color: "bg-purple-100 text-purple-700" },
  { value: "admin", label: "管理员", color: "bg-red-100 text-red-700" },
];

function roleBadge(role: string) {
  const opt = ROLE_OPTIONS.find((r) => r.value === role);
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${opt?.color || "bg-gray-100 text-gray-700"}`}>
      {opt?.label || role}
    </span>
  );
}

export default function AdminUsersPage() {
  const { user: currentUser } = useSession();
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updating, setUpdating] = useState<number | null>(null);

  useEffect(() => {
    loadUsers();
  }, []);

  async function loadUsers() {
    setLoading(true);
    setError(null);
    try {
      const data = await listUsers();
      setUsers(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleRoleChange(userId: number, newRole: string) {
    setUpdating(userId);
    try {
      const updated = await updateUserRole(userId, newRole);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
    } catch (err) {
      alert(err instanceof Error ? err.message : "更新失败");
    } finally {
      setUpdating(null);
    }
  }

  async function handleToggleActive(userId: number, isActive: boolean) {
    setUpdating(userId);
    try {
      const updated = await toggleUserActive(userId, isActive);
      setUsers((prev) => prev.map((u) => (u.id === userId ? updated : u)));
    } catch (err) {
      alert(err instanceof Error ? err.message : "更新失败");
    } finally {
      setUpdating(null);
    }
  }

  if (currentUser?.role !== "admin") {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <p className="text-gray-500">仅管理员可访问此页面</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">用户管理</h1>
        <p className="text-sm text-gray-500 mt-1">管理系统用户角色和状态</p>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>全部用户（{users.length}）</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-gray-500 py-8 text-center">加载中...</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="pb-3 font-medium">ID</th>
                    <th className="pb-3 font-medium">邮箱</th>
                    <th className="pb-3 font-medium">昵称</th>
                    <th className="pb-3 font-medium">角色</th>
                    <th className="pb-3 font-medium">状态</th>
                    <th className="pb-3 font-medium">注册时间</th>
                    <th className="pb-3 font-medium">最后登录</th>
                    <th className="pb-3 font-medium">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id} className="border-b last:border-0">
                      <td className="py-3 text-gray-600">{u.id}</td>
                      <td className="py-3">{u.email}</td>
                      <td className="py-3 text-gray-600">{u.display_name || "-"}</td>
                      <td className="py-3">
                        <select
                          value={u.role}
                          onChange={(e) => handleRoleChange(u.id, e.target.value)}
                          disabled={updating === u.id || u.id === currentUser?.id}
                          className="border rounded px-2 py-1 text-sm bg-white disabled:opacity-50"
                        >
                          {ROLE_OPTIONS.map((opt) => (
                            <option key={opt.value} value={opt.value}>
                              {opt.label}
                            </option>
                          ))}
                        </select>
                      </td>
                      <td className="py-3">
                        {u.is_active ? (
                          <Badge className="bg-green-100 text-green-700 hover:bg-green-100">正常</Badge>
                        ) : (
                          <Badge className="bg-red-100 text-red-700 hover:bg-red-100">已禁用</Badge>
                        )}
                      </td>
                      <td className="py-3 text-gray-500 text-xs">
                        {u.created_at ? new Date(u.created_at).toLocaleDateString("zh-CN") : "-"}
                      </td>
                      <td className="py-3 text-gray-500 text-xs">
                        {u.last_login_at ? new Date(u.last_login_at).toLocaleDateString("zh-CN") : "-"}
                      </td>
                      <td className="py-3">
                        {u.id !== currentUser?.id && (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleToggleActive(u.id, !u.is_active)}
                            disabled={updating === u.id}
                            className={u.is_active ? "text-red-600 hover:text-red-700" : "text-green-600 hover:text-green-700"}
                          >
                            {u.is_active ? "禁用" : "启用"}
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>角色权限说明</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="p-3 rounded-lg bg-gray-50">
              <div className="font-medium mb-1">{roleBadge("viewer")} 查看者</div>
              <p className="text-gray-500">可查看首页、资产包定价、库存沙盘</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-50">
              <div className="font-medium mb-1">{roleBadge("operator")} 操作员</div>
              <p className="text-gray-500">查看者权限 + 主管控制台、动作中心</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-50">
              <div className="font-medium mb-1">{roleBadge("manager")} 经理</div>
              <p className="text-gray-500">操作员权限 + 高管驾驶页、经理作战手册</p>
            </div>
            <div className="p-3 rounded-lg bg-gray-50">
              <div className="font-medium mb-1">{roleBadge("admin")} 管理员</div>
              <p className="text-gray-500">全部权限 + 用户管理</p>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
