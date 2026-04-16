"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminAccess } from "@/components/admin/admin-access";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { listValuationRules, upsertValuationRule, type ValuationRule } from "@/lib/api";
import { useSession } from "@/components/auth/session-provider";

export default function AdminValuationRulesPage() {
  const { user } = useSession();
  const [rules, setRules] = useState<ValuationRule[]>([]);
  const [form, setForm] = useState({
    scope: "global",
    enabled: true,
    trigger_type: "profit_margin_threshold",
    trigger_config: "{\"margin_lower_bound\":0.03,\"margin_upper_bound\":0.08}",
  });

  async function refresh() {
    setRules(await listValuationRules());
  }

  useEffect(() => {
    let cancelled = false;
    void listValuationRules().then((data) => {
      if (!cancelled) {
        setRules(data);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await upsertValuationRule({
        scope: form.scope,
        enabled: form.enabled,
        trigger_type: form.trigger_type,
        trigger_config: JSON.parse(form.trigger_config),
      });
      await refresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "保存失败，请检查 JSON 配置");
    }
  }

  return (
    <AdminAccess minRole="manager">
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">估值触发规则</h1>
          <p className="text-sm text-gray-500 mt-1">控制哪些场景允许触发高级车况定价。</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>规则列表</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="pb-3 font-medium">触发器</th>
                    <th className="pb-3 font-medium">作用域</th>
                    <th className="pb-3 font-medium">状态</th>
                    <th className="pb-3 font-medium">配置</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => (
                    <tr key={rule.id} className="border-b last:border-0">
                      <td className="py-3">{rule.trigger_type}</td>
                      <td className="py-3">{rule.scope}</td>
                      <td className="py-3">{rule.enabled ? "启用" : "停用"}</td>
                      <td className="py-3 text-xs text-gray-500">{JSON.stringify(rule.trigger_config)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>

        {user?.role === "admin" && (
          <Card>
            <CardHeader>
              <CardTitle>新增 / 覆盖规则</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="trigger-type">触发类型</Label>
                  <Input id="trigger-type" value={form.trigger_type} onChange={(event) => setForm((prev) => ({ ...prev, trigger_type: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="trigger-scope">作用域</Label>
                  <Input id="trigger-scope" value={form.scope} onChange={(event) => setForm((prev) => ({ ...prev, scope: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="trigger-enabled">状态</Label>
                  <Input id="trigger-enabled" value={form.enabled ? "enabled" : "disabled"} onChange={(event) => setForm((prev) => ({ ...prev, enabled: event.target.value === "enabled" }))} />
                </div>
                <div className="space-y-2 md:col-span-3">
                  <Label htmlFor="trigger-config">JSON 配置</Label>
                  <Input id="trigger-config" value={form.trigger_config} onChange={(event) => setForm((prev) => ({ ...prev, trigger_config: event.target.value }))} />
                </div>
                <div className="md:col-span-3">
                  <Button type="submit">保存规则</Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </AdminAccess>
  );
}
