"use client";

import { useEffect, useState } from "react";

import { AdminAccess } from "@/components/admin/admin-access";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listCommercialPlans, listSubscriptions, type CommercialPlan, type TenantSubscriptionInfo } from "@/lib/api";

export default function AdminBillingPage() {
  const [plans, setPlans] = useState<CommercialPlan[]>([]);
  const [subscriptions, setSubscriptions] = useState<TenantSubscriptionInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [planRows, subscriptionRows] = await Promise.all([
          listCommercialPlans(),
          listSubscriptions(),
        ]);
        setPlans(planRows);
        setSubscriptions(subscriptionRows);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const totalMonthlyRevenue = subscriptions.reduce((sum, item) => {
    const plan = plans.find((row) => row.code === item.plan_code);
    return sum + (plan?.monthly_price || 0);
  }, 0);

  return (
    <AdminAccess minRole="manager">
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold">套餐与计费</h1>
          <p className="text-sm text-gray-500 mt-1">查看套餐价格带、订阅结构和本月经常性收入估算。</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardHeader>
              <CardTitle>在售套餐</CardTitle>
            </CardHeader>
            <CardContent className="text-3xl font-semibold">{loading ? "-" : plans.length}</CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>活跃订阅</CardTitle>
            </CardHeader>
            <CardContent className="text-3xl font-semibold">{loading ? "-" : subscriptions.length}</CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>月度收入估算</CardTitle>
            </CardHeader>
            <CardContent className="text-3xl font-semibold">¥{totalMonthlyRevenue.toLocaleString("zh-CN")}</CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>价格带概览</CardTitle>
          </CardHeader>
          <CardContent>
            {loading ? (
              <p className="text-sm text-gray-500">加载中...</p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
                {plans.map((plan) => (
                  <div key={plan.id} className="rounded-xl border bg-white p-4">
                    <div className="text-sm text-gray-500">{plan.code}</div>
                    <div className="text-lg font-semibold mt-1">{plan.name}</div>
                    <div className="text-2xl font-bold mt-3">¥{plan.monthly_price.toLocaleString("zh-CN")}</div>
                    <div className="text-xs text-gray-500 mt-1">年费 ¥{plan.yearly_price.toLocaleString("zh-CN")}</div>
                    <div className="text-xs text-gray-600 mt-4 space-y-1">
                      <div>VIN 配额 {plan.included_vin_calls}</div>
                      <div>高级车况点数 {plan.included_condition_pricing_points}</div>
                      <div>AI 报告 {plan.included_ai_reports}</div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AdminAccess>
  );
}
