"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { healthCheck, listPackages } from "@/lib/api";

// task #5: 试用 onboarding 卡片 —— 仅在资产包为 0 时显示
const ONBOARDING_STEPS = [
  { num: 1, title: "上传资产包 Excel", desc: "30 秒识别 18 个业务字段,100% 自动映射列名" },
  { num: 2, title: "AI 自动诊断", desc: "M3/M6/M12 分层 · 缺 VIN 识别 · 长期在库聚合" },
  { num: 3, title: "处置建议草稿", desc: "出让区间 · 法务推进 · 债权转让 · 补资料任务" },
  { num: 4, title: "任务确认闭环", desc: "人工 review · 落正式 work_orders · 全链路审计" },
];

export default function HomePage() {
  const [status, setStatus] = useState<string>("checking");
  const [packagesCount, setPackagesCount] = useState<number | null>(null);

  useEffect(() => {
    healthCheck()
      .then(() => setStatus("connected"))
      .catch(() => setStatus("disconnected"));

    listPackages()
      .then((pkgs) => setPackagesCount(pkgs.length))
      .catch(() => setPackagesCount(null));
  }, []);

  const showOnboarding = packagesCount === 0;

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">汽车金融资产处置经营决策系统</h1>
          <p className="text-gray-500 mt-2">汽车金融不良资产处置 -- 内部MVP</p>
        </div>
        <Badge variant={status === "connected" ? "default" : "destructive"}>
          {status === "connected" ? "后端已连接" : status === "checking" ? "连接中..." : "后端未连接"}
        </Badge>
      </div>

      {/* task #5: 试用 onboarding 卡片 —— 资产包为 0 时显示
          设计语言:浅色金融专业版,克制留白,不渐变不花哨 */}
      {showOnboarding && (
        <div className="mb-8 rounded-md border border-slate-200 bg-slate-50 p-6">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr,1.6fr] gap-6">
            <div>
              <div className="text-xs font-medium uppercase tracking-wider text-slate-500 mb-2">
                试用环境 · 快速开始
              </div>
              <h2 className="text-xl font-semibold text-slate-900 mb-2 leading-snug">
                上传第一份资产包,开始你的 AI 处置体验
              </h2>
              <p className="text-sm text-slate-600 mb-4 leading-relaxed">
                系统会自动识别 18 个业务字段、按 M3/M6/M12 分层逾期资产、识别缺 VIN 和在库异常,
                生成可人工确认的处置任务草稿。试用期 30 天,3 席位。
              </p>
              <Link href="/asset-pricing">
                <Button>立即上传资产包 Excel →</Button>
              </Link>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {ONBOARDING_STEPS.map((step) => (
                <div
                  key={step.num}
                  className="rounded border border-slate-200 bg-white p-3"
                >
                  <div className="flex items-baseline gap-2 mb-1">
                    <span className="text-xs font-mono text-slate-400">
                      0{step.num}
                    </span>
                    <span className="text-sm font-medium text-slate-900">
                      {step.title}
                    </span>
                  </div>
                  <div className="text-xs text-slate-500 leading-relaxed">
                    {step.desc}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="mt-5 pt-4 border-t border-slate-200 flex items-center justify-between flex-wrap gap-3 text-xs text-slate-500">
            <div className="flex items-center gap-4">
              <span>
                <span className="font-medium text-slate-700">AI 边界:</span>{" "}
                所有 Agent 输出标注 requires_human_review,不替你做出让/法律结论
              </span>
            </div>
            <span className="text-slate-400">
              数据隔离:你的试用空间独立 tenant,看不到其他用户数据
            </span>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Link href="/asset-pricing">
          <Card className="hover:shadow-lg transition-shadow cursor-pointer h-full">
            <CardHeader>
              <CardTitle>资产包出让定价分析</CardTitle>
              <CardDescription>上传资产包台账，生成出让折扣区间与分析报告</CardDescription>
            </CardHeader>
            <CardContent>
              <ul className="text-sm text-gray-600 space-y-2">
                <li>- 批量车300估值查询</li>
                <li>- 在库/非在库资产包区分定价</li>
                <li>- 千问大模型生成出让分析报告</li>
                <li>- 风险预警与推荐出让折扣区间</li>
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
