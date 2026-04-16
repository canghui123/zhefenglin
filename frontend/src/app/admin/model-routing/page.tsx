"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminAccess } from "@/components/admin/admin-access";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { listModelRoutingRules, upsertModelRoutingRule, type ModelRoutingRule } from "@/lib/api";
import { useSession } from "@/components/auth/session-provider";

export default function AdminModelRoutingPage() {
  const { user } = useSession();
  const [rules, setRules] = useState<ModelRoutingRule[]>([]);
  const [form, setForm] = useState({
    scope: "global",
    task_type: "medium_task",
    preferred_model: "qwen-plus",
    fallback_model: "qwen-turbo",
    allow_batch: false,
    allow_search: false,
    allow_high_cost_mode: false,
    prompt_version: "v1",
    is_active: true,
  });

  async function refresh() {
    setRules(await listModelRoutingRules());
  }

  useEffect(() => {
    let cancelled = false;
    void listModelRoutingRules().then((data) => {
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
      await upsertModelRoutingRule(form);
      await refresh();
    } catch (err) {
      alert(err instanceof Error ? err.message : "保存失败");
    }
  }

  return (
    <AdminAccess minRole="manager">
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">模型路由</h1>
          <p className="text-sm text-gray-500 mt-1">配置轻任务、中任务、长文本和报告生成的模型策略。</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>现有规则</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b text-left text-gray-500">
                    <th className="pb-3 font-medium">任务</th>
                    <th className="pb-3 font-medium">首选模型</th>
                    <th className="pb-3 font-medium">回退模型</th>
                    <th className="pb-3 font-medium">Prompt版本</th>
                  </tr>
                </thead>
                <tbody>
                  {rules.map((rule) => (
                    <tr key={rule.id} className="border-b last:border-0">
                      <td className="py-3">{rule.task_type}</td>
                      <td className="py-3">{rule.preferred_model}</td>
                      <td className="py-3">{rule.fallback_model || "-"}</td>
                      <td className="py-3">{rule.prompt_version}</td>
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
              <form onSubmit={handleSubmit} className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="task-type">任务类型</Label>
                  <Input id="task-type" value={form.task_type} onChange={(event) => setForm((prev) => ({ ...prev, task_type: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="preferred-model">首选模型</Label>
                  <Input id="preferred-model" value={form.preferred_model} onChange={(event) => setForm((prev) => ({ ...prev, preferred_model: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="fallback-model">回退模型</Label>
                  <Input id="fallback-model" value={form.fallback_model} onChange={(event) => setForm((prev) => ({ ...prev, fallback_model: event.target.value }))} />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="prompt-version">Prompt版本</Label>
                  <Input id="prompt-version" value={form.prompt_version} onChange={(event) => setForm((prev) => ({ ...prev, prompt_version: event.target.value }))} />
                </div>
                <div className="md:col-span-4">
                  <Button type="submit">保存路由规则</Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}
      </div>
    </AdminAccess>
  );
}
