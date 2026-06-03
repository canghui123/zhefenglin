"use client";

import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { submitAccessRequest } from "@/lib/auth";

/**
 * /access-request —— 企业内测审核流程。
 *
 * 2026-06-03 改造前,这个表单原来挂在 /register 上。
 * 改造后 /register 改成 SaaS 公开试用快速注册;企业审核流程独立到本路由。
 *
 * 使用场景:大客户希望走人工审核 / 销售对接,而不是自助注册。
 */
export default function AccessRequestPage() {
  return (
    <Suspense fallback={null}>
      <AccessRequestForm />
    </Suspense>
  );
}

function AccessRequestForm() {
  const [email, setEmail] = useState("");
  const [company, setCompany] = useState("");
  const [contactName, setContactName] = useState("");
  const [phone, setPhone] = useState("");
  const [scenario, setScenario] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!agreed) {
      setError("请先阅读并同意《服务使用须知》");
      return;
    }

    setSubmitting(true);
    try {
      await submitAccessRequest({
        email,
        company,
        contact_name: contactName,
        phone: phone || undefined,
        scenario: scenario || undefined,
        source: "web",
        agreed_to_terms: true,
      });
      setDone(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败，请稍后再试");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-8">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>申请已提交</CardTitle>
            <CardDescription>
              我们将在 2 个工作日内通过邮件或电话与您联系。
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted-foreground">
            <p>
              感谢您对汽车金融资产处置经营决策系统的关注。我们正在内测阶段，
              每一位申请者都会被人工审核后开通账号。
            </p>
            <p>如需加急或补充信息，可直接回复我们发送的确认邮件。</p>
            <Link href="/login" className="text-blue-600 hover:underline block">
              返回登录页
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>申请内测访问</CardTitle>
          <CardDescription>
            本平台目前处于邀请内测阶段。请提交以下信息，我们人工审核后开通账号。
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">企业邮箱 *</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="your-name@company.com"
                required
                autoComplete="email"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="company">公司名称 *</Label>
              <Input
                id="company"
                type="text"
                value={company}
                onChange={(e) => setCompany(e.target.value)}
                placeholder="如:XX 资产管理有限公司"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="contact_name">联系人 *</Label>
              <Input
                id="contact_name"
                type="text"
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
                placeholder="您的姓名"
                required
                autoComplete="name"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="phone">手机号(选填)</Label>
              <Input
                id="phone"
                type="tel"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="138 0000 0000"
                autoComplete="tel"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="scenario">使用场景(选填)</Label>
              <textarea
                id="scenario"
                value={scenario}
                onChange={(e) => setScenario(e.target.value)}
                placeholder="简单描述您希望用本平台解决的业务问题,如:月均处置 100 台车,希望辅助买断定价。"
                className="w-full min-h-[80px] rounded-md border border-input bg-background px-3 py-2 text-sm"
              />
            </div>

            <label className="flex items-start gap-2 text-sm cursor-pointer">
              <input
                type="checkbox"
                checked={agreed}
                onChange={(e) => setAgreed(e.target.checked)}
                className="mt-0.5"
              />
              <span className="text-slate-700 leading-relaxed">
                我已阅读并同意{" "}
                <Link
                  href="/legal/terms"
                  className="text-blue-600 hover:underline"
                  target="_blank"
                >
                  《服务使用须知》
                </Link>
                ,理解平台提供的定价建议与决策报告仅供参考。
              </span>
            </label>

            {error && (
              <div className="p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                {error}
              </div>
            )}

            <Button
              type="submit"
              className="w-full"
              disabled={submitting || !email || !company || !contactName || !agreed}
            >
              {submitting ? "正在提交..." : "提交申请"}
            </Button>
          </form>

          <div className="mt-5 pt-4 border-t border-slate-200 text-xs text-slate-500 space-y-2">
            <p>
              已有账号?{" "}
              <Link href="/login" className="text-blue-600 hover:underline">
                直接登录
              </Link>
            </p>
            <p>
              想立即试用 (30 天)?{" "}
              <Link href="/register" className="text-blue-600 hover:underline">
                创建试用账号
              </Link>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
