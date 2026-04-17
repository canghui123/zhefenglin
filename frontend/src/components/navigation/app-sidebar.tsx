"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useSession } from "@/components/auth/session-provider";
import { UserMenu } from "@/components/auth/user-menu";
import { hasFeature, hasRole, type Role } from "@/lib/auth";

type NavItem = {
  href: string;
  label: string;
  minRole?: Role;
  featureKey?: string;
};

const PUBLIC_PATHS = new Set(["/login", "/register"]);

const navSections: Array<{ title: string; items: NavItem[] }> = [
  {
    title: "资产处置",
    items: [
      { href: "/", label: "首页" },
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
      {
        href: "/portfolio/executive",
        label: "高管驾驶页",
        minRole: "manager",
        featureKey: "portfolio.advanced_pages",
      },
      {
        href: "/portfolio/manager",
        label: "经理作战手册",
        minRole: "manager",
        featureKey: "portfolio.advanced_pages",
      },
      { href: "/portfolio/supervisor", label: "主管控制台", minRole: "operator" },
      { href: "/portfolio/actions", label: "动作中心", minRole: "operator" },
    ],
  },
  {
    title: "系统管理",
    items: [
      { href: "/admin/settings", label: "系统设置", minRole: "manager" },
      { href: "/admin/billing", label: "套餐计费", minRole: "manager" },
      {
        href: "/admin/cost-center",
        label: "成本中心",
        minRole: "manager",
        featureKey: "dashboard.advanced",
      },
      {
        href: "/admin/model-routing",
        label: "模型路由",
        minRole: "manager",
        featureKey: "routing.model_control",
      },
      { href: "/admin/valuation-rules", label: "估值规则", minRole: "manager" },
      { href: "/admin/approval-requests", label: "审批请求", minRole: "manager" },
      {
        href: "/admin/value-dashboard",
        label: "价值看板",
        minRole: "manager",
        featureKey: "tenant.value_dashboard",
      },
      { href: "/admin/users", label: "用户管理", minRole: "admin" },
    ],
  },
];

export function AppSidebar() {
  const { user, loading } = useSession();
  const pathname = usePathname();

  if (PUBLIC_PATHS.has(pathname)) {
    return null;
  }

  const visibleSections = navSections
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => {
        if (item.minRole && !hasRole(user, item.minRole)) {
          return false;
        }
        if (item.featureKey && !hasFeature(user, item.featureKey)) {
          return false;
        }
        return true;
      }),
    }))
    .filter((section) => section.items.length > 0);

  return (
    <aside className="w-64 bg-slate-900 text-white flex flex-col shrink-0">
      <div className="p-6 border-b border-slate-700">
        <h1 className="text-lg font-bold">汽车金融资产处置经营决策系统</h1>
        <p className="text-xs text-slate-400 mt-1">汽车金融不良资产处置</p>
      </div>
      <nav className="flex-1 p-4 space-y-4 overflow-y-auto">
        {loading ? (
          <div className="px-4 py-2 text-sm text-slate-400">加载导航中...</div>
        ) : (
          visibleSections.map((section) => (
            <div key={section.title}>
              <div className="px-4 py-1 text-xs font-semibold text-slate-500 uppercase tracking-wider">
                {section.title}
              </div>
              <div className="space-y-0.5 mt-1">
                {section.items.map((item) => {
                  const isActive = pathname === item.href;
                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      className={`block px-4 py-2 rounded-lg text-sm transition-colors ${
                        isActive
                          ? "bg-slate-800 text-white"
                          : "text-slate-300 hover:bg-slate-800 hover:text-white"
                      }`}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </nav>
      <UserMenu />
    </aside>
  );
}
