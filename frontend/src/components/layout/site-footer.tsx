import Link from "next/link";

/**
 * 全站 Footer —— 包含主体信息与合规链接。
 *
 * 上线前请将 COMPANY_NAME / ICP_NUMBER 替换为真实值；
 * ICP 备案完成前可保留"备案申请中"占位，但不要长期保留。
 */
const COMPANY_NAME = "【公司全称】";
const ICP_NUMBER = "浙ICP备XXXXXXXX号";

export function SiteFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="mt-auto border-t bg-white/40 backdrop-blur-sm text-xs text-muted-foreground">
      <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col sm:flex-row gap-2 items-center justify-between">
        <div className="space-x-2">
          <span>© {year} {COMPANY_NAME}</span>
          <span className="hidden sm:inline">·</span>
          <a
            href="https://beian.miit.gov.cn/"
            target="_blank"
            rel="noreferrer noopener"
            className="hover:underline"
          >
            {ICP_NUMBER}
          </a>
        </div>
        <div className="space-x-3">
          <Link href="/legal/notice" className="hover:underline">
            服务使用须知
          </Link>
          <Link href="/legal/terms" className="hover:underline">
            用户协议
          </Link>
        </div>
      </div>
    </footer>
  );
}
