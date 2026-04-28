import type { Metadata } from "next";
import { Geist } from "next/font/google";
import Link from "next/link";
import "./globals.css";
import { SessionProvider } from "@/components/auth/session-provider";
import { UserMenu } from "@/components/auth/user-menu";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "汽车金融不良资产AI平台",
  description: "AI智能定价与库存决策引擎",
};

const navSections = [
  {
    title: "资产处置",
    items: [
      { href: "/", label: "首页" },
      { href: "/data-import", label: "数据接入" },
      { href: "/asset-pricing", label: "资产包定价" },
      { href: "/inventory-sandbox", label: "库存决策沙盘" },
    ],
  },
  {
    title: "经营驾驶舱",
    items: [
      { href: "/portfolio/overview", label: "组合总览" },
      { href: "/portfolio/segmentation", label: "分层分析" },
      { href: "/portfolio/strategies", label: "路径模拟" },
      { href: "/portfolio/cashflow", label: "现金回流" },
    ],
  },
  {
    title: "管理决策",
    items: [
      { href: "/portfolio/executive", label: "高管驾驶页" },
      { href: "/portfolio/manager", label: "经理作战手册" },
      { href: "/portfolio/supervisor", label: "主管控制台" },
      { href: "/portfolio/actions", label: "动作中心" },
      { href: "/portfolio/learning", label: "复盘学习" },
    ],
  },
  {
    title: "系统管理",
    items: [
      { href: "/admin/users", label: "用户管理" },
    ],
  },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className={`${geistSans.variable} h-full`}>
      <body className="min-h-full flex bg-gray-50 antialiased">
        <SessionProvider>
          {/* Sidebar */}
          <aside className="w-64 bg-slate-900 text-white flex flex-col shrink-0">
            <div className="p-6 border-b border-slate-700">
              <h1 className="text-lg font-bold">AI资产决策引擎</h1>
              <p className="text-xs text-slate-400 mt-1">汽车金融不良资产处置</p>
            </div>
            <nav className="flex-1 p-4 space-y-4 overflow-y-auto">
              {navSections.map((section) => (
                <div key={section.title}>
                  <div className="px-4 py-1 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                    {section.title}
                  </div>
                  <div className="space-y-0.5 mt-1">
                    {section.items.map((item) => (
                      <Link
                        key={item.href}
                        href={item.href}
                        className="block px-4 py-2 rounded-lg text-sm hover:bg-slate-800 transition-colors text-slate-300 hover:text-white"
                      >
                        {item.label}
                      </Link>
                    ))}
                  </div>
                </div>
              ))}
            </nav>
            <UserMenu />
          </aside>

          {/* Main content */}
          <main className="flex-1 overflow-auto">
            <div className="p-8">{children}</div>
          </main>
        </SessionProvider>
      </body>
    </html>
  );
}
