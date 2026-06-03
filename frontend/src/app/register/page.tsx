"use client";

import { Suspense, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

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
import { register } from "@/lib/auth";
import { ApiError } from "@/lib/api";

/**
 * /register —— SaaS 公开试用快速注册。
 *
 * 行为(2026-06-03 改造):
 *   注册成功 → 后端 trial_onboarding 自动创建独立 tenant + trial_poc 30 天
 *               + operator 角色 + 自动登录 → 跳到 / 首页(有 onboarding 卡片)
 *
 * 企业内测申请审核流程已移至 /access-request(本页面底部链接)。
 */
export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <QuickTrialRegisterForm />
    </Suspense>
  );
}

function QuickTrialRegisterForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!agreed) {
      setError("请先阅读并同意《服务使用须知》");
      return;
    }
    if (password.length < 10) {
      setError("密码至少 10 位,需包含字母 + 数字 + 特殊字符");
      return;
    }

    setSubmitting(true);
    try {
      await register({
        email,
        password,
        displayName: displayName || undefined,
        agreedToTerms: true,
      });
      // 注册成功 → 后端已自动登录 + 创建独立试用 tenant + 订阅 trial_poc
      router.push("/");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("注册失败,请稍后再试");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-[calc(100vh-4rem)] flex items-center justify-center px-4 py-8">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>开通试用账号</CardTitle>
          <CardDescription>
            30 天 trial 试用 / 独立工作空间 / 数据互不可见
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
              <Label htmlFor="password">设置密码 *</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="至少 10 位,含字母 + 数字 + 特殊字符"
                required
                autoComplete="new-password"
              />
              <p className="text-xs text-muted-foreground">
                例: <span className="font-mono">Trial2026!Auto</span>
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="display_name">显示名(选填)</Label>
              <Input
                id="display_name"
                type="text"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                placeholder="您的姓名"
                autoComplete="name"
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
                ,理解平台提供的定价建议与决策报告仅供参考,所有 AI
                输出需人工复核。
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
              disabled={submitting || !email || !password || !agreed}
            >
              {submitting ? "正在创建试用空间..." : "创建试用账号 →"}
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
              企业 / 内测客户请走人工审核流程?{" "}
              <Link
                href="/access-request"
                className="text-blue-600 hover:underline"
              >
                提交申请
              </Link>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
