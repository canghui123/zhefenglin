"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { healthCheck } from "@/lib/api";

export default function HomePage() {
  const [status, setStatus] = useState<string>("checking");

  useEffect(() => {
    healthCheck()
      .then(() => setStatus("connected"))
      .catch(() => setStatus("disconnected"));
  }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">AI智能定价与库存决策引擎</h1>
          <p className="text-gray-500 mt-2">汽车金融不良资产处置 -- 内部MVP</p>
        </div>
        <Badge variant={status === "connected" ? "default" : "destructive"}>
          {status === "connected" ? "后端已连接" : status === "checking" ? "连接中..." : "后端未连接"}
        </Badge>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link href="/asset-pricing">
          <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
            <CardHeader>
              <CardTitle>资产包买断AI定价</CardTitle>
              <CardDescription>上传甲方Excel资产包，一键计算利润与风险</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-gray-600 space-y-2">
                <li>- 批量车300估值查询</li>
                <li>- 多维成本自动测算</li>
                <li>- AI贬值趋势预测</li>
                <li>- 风险预警与建议买断折扣</li>
              </ul>
            </CardContent>
          </Card>
        </Link>

        <Link href="/inventory-sandbox">
          <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
            <CardHeader>
              <CardTitle>甲方库存决策沙盘</CardTitle>
              <CardDescription>三路径模拟，生成专业PDF建议书</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-gray-600 space-y-2">
                <li>- 路径A：继续等待赎车</li>
                <li>- 路径B：司法诉讼流程</li>
                <li>- 路径C：立即上架竞拍</li>
                <li>- 一键生成PDF决策报告</li>
              </ul>
            </CardContent>
          </Card>
        </Link>
      </div>
    </div>
  );
}
