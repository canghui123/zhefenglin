"use client";

import { FormEvent, useEffect, useState } from "react";

import { AdminAccess } from "@/components/admin/admin-access";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  createCommercialPlan,
  listCommercialPlans,
  listSubscriptions,
  updateSubscription,
  type CommercialPlan,
  type TenantSubscriptionInfo,
} from "@/lib/api";
import { useSession } from "@/components/auth/session-provider";

const EMPTY_PLAN = {
  code: "",
  name: "",
  billing_cycle_supported: "monthly,yearly",
  monthly_price: 0,
  yearly_price: 0,
  setup_fee: 0,
  private_deploy_fee: 0,
  seat_limit: 5,
  included_vin_calls: 100,
  included_condition_pricing_points: 5,
  included_ai_reports: 50,
  included_asset_packages: 20,
  included_sandbox_runs: 40,
  overage_vin_unit_price: 2,
  overage_condition_pricing_unit_price: 40,
  feature_flags: { "dashboard.advanced": true },
  is_active: true,
};

export default function AdminSettingsPage() {
  const { user } = useSession();
  const [plans, setPlans] = useState<CommercialPlan[]>([]);
  const [subscriptions, setSubscriptions] = useState<TenantSubscriptionInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [planForm, setPlanForm] = useState(EMPTY_PLAN);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [planRows, subscriptionRows] = await Promise.all([
        listCommercialPlans(),
        listSubscriptions(),
      ]);
      setPlans(planRows);
      setSubscriptions(subscriptionRows);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleCreatePlan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    try {
      await createCommercialPlan(planForm);
      setPlanForm(EMPTY_PLAN);
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "创建套餐失败");
    } finally {
      setSaving(false);
    }
  }

  async function handleQuickUpgrade(subscription: TenantSubscriptionInfo, planCode: string) {
    try {
      await updateSubscription(subscription.tenant_id, {
        plan_code: planCode,
        status: subscription.status,
        monthly_budget_limit: subscription.monthly_budget_limit,
        alert_threshold_percent: subscription.alert_threshold_percent,
      });
      await load();
    } catch (err) {
      alert(err instanceof Error ? err.message : "更新订阅失败");
    }
  }

  return (
    <AdminAccess minRole="manager">
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">系统设置中心</h1>
          <p className="text-sm text-gray-500 mt-1">
            管理套餐、租户订阅、预算和商业化基础配置。
          </p>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <Card>
          <CardHeader>
            <CardTitle>套餐目录</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-gray-500">加载中...</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-500">
                      <th className="pb-3 font-medium">套餐</th>
                      <th className="pb-3 font-medium">月费</th>
                      <th className="pb-3 font-medium">年费</th>
                      <th className="pb-3 font-medium">VIN配额</th>
                      <th className="pb-3 font-medium">车况点数</th>
                      <th className="pb-3 font-medium">AI报告</th>
                      <th className="pb-3 font-medium">席位</th>
                    </tr>
                  </thead>
                  <tbody>
                    {plans.map((plan) => (
                      <tr key={plan.id} className="border-b last:border-0">
                        <td className="py-3">
                          <div className="font-medium">{plan.name}</div>
                          <div className="text-xs text-gray-500">{plan.code}</div>
                        </td>
                        <td className="py-3">¥{plan.monthly_price.toLocaleString("zh-CN")}</td>
                        <td className="py-3">¥{plan.yearly_price.toLocaleString("zh-CN")}</td>
                        <td className="py-3">{plan.included_vin_calls}</td>
                        <td className="py-3">{plan.included_condition_pricing_points}</td>
                        <td className="py-3">{plan.included_ai_reports}</td>
                        <td className="py-3">{plan.seat_limit}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>

        {user?.role === "admin" && (
          <Card>
            <CardHeader>
              <CardTitle>新增套餐</CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleCreatePlan} className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="plan-code">套餐编码</Label>
                  <Input
                    id="plan-code"
                    value={planForm.code}
                    onChange={(event) => setPlanForm((prev) => ({ ...prev, code: event.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="plan-name">套餐名称</Label>
                  <Input
                    id="plan-name"
                    value={planForm.name}
                    onChange={(event) => setPlanForm((prev) => ({ ...prev, name: event.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="plan-monthly">月费</Label>
                  <Input
                    id="plan-monthly"
                    type="number"
                    value={planForm.monthly_price}
                    onChange={(event) =>
                      setPlanForm((prev) => ({ ...prev, monthly_price: Number(event.target.value) }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="plan-yearly">年费</Label>
                  <Input
                    id="plan-yearly"
                    type="number"
                    value={planForm.yearly_price}
                    onChange={(event) =>
                      setPlanForm((prev) => ({ ...prev, yearly_price: Number(event.target.value) }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="plan-vin">VIN配额</Label>
                  <Input
                    id="plan-vin"
                    type="number"
                    value={planForm.included_vin_calls}
                    onChange={(event) =>
                      setPlanForm((prev) => ({ ...prev, included_vin_calls: Number(event.target.value) }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="plan-condition">车况点数</Label>
                  <Input
                    id="plan-condition"
                    type="number"
                    value={planForm.included_condition_pricing_points}
                    onChange={(event) =>
                      setPlanForm((prev) => ({
                        ...prev,
                        included_condition_pricing_points: Number(event.target.value),
                      }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="plan-reports">AI报告次数</Label>
                  <Input
                    id="plan-reports"
                    type="number"
                    value={planForm.included_ai_reports}
                    onChange={(event) =>
                      setPlanForm((prev) => ({ ...prev, included_ai_reports: Number(event.target.value) }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="plan-seats">席位数</Label>
                  <Input
                    id="plan-seats"
                    type="number"
                    value={planForm.seat_limit}
                    onChange={(event) => setPlanForm((prev) => ({ ...prev, seat_limit: Number(event.target.value) }))}
                  />
                </div>
                <div className="md:col-span-4">
                  <Button type="submit" disabled={saving}>
                    {saving ? "创建中..." : "创建套餐"}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle>租户订阅</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-gray-500">加载中...</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b text-left text-gray-500">
                      <th className="pb-3 font-medium">租户</th>
                      <th className="pb-3 font-medium">套餐</th>
                      <th className="pb-3 font-medium">状态</th>
                      <th className="pb-3 font-medium">预算上限</th>
                      <th className="pb-3 font-medium">告警阈值</th>
                      <th className="pb-3 font-medium">快捷切换</th>
                    </tr>
                  </thead>
                  <tbody>
                    {subscriptions.map((subscription) => (
                      <tr key={subscription.id} className="border-b last:border-0">
                        <td className="py-3">
                          <div className="font-medium">{subscription.tenant_name || subscription.tenant_code}</div>
                          <div className="text-xs text-gray-500">#{subscription.tenant_id}</div>
                        </td>
                        <td className="py-3">{subscription.plan_name || "-"}</td>
                        <td className="py-3">{subscription.status}</td>
                        <td className="py-3">¥{subscription.monthly_budget_limit.toLocaleString("zh-CN")}</td>
                        <td className="py-3">{subscription.alert_threshold_percent}%</td>
                        <td className="py-3">
                          {user?.role === "admin" ? (
                            <div className="flex gap-2">
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleQuickUpgrade(subscription, "pro_manager")}
                              >
                                升到 Pro
                              </Button>
                              <Button
                                size="sm"
                                variant="outline"
                                onClick={() => handleQuickUpgrade(subscription, "enterprise_private")}
                              >
                                升到 Enterprise
                              </Button>
                            </div>
                          ) : (
                            <span className="text-xs text-gray-500">仅管理员可调整</span>
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
      </div>
    </AdminAccess>
  );
}
