import type { Metadata } from "next";
import "./globals.css";
import { SessionProvider } from "@/components/auth/session-provider";
import { AppSidebar } from "@/components/navigation/app-sidebar";
import { SiteFooter } from "@/components/layout/site-footer";

export const metadata: Metadata = {
  title: "汽车金融资产处置经营决策系统",
  description: "汽车金融资产处置经营决策系统",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="zh-CN" className="h-full">
      <body className="min-h-full flex bg-gray-50 antialiased">
        <SessionProvider>
          <AppSidebar />

          {/* Main content */}
          <main className="flex-1 overflow-auto flex flex-col">
            <div className="p-8 flex-1">{children}</div>
            <SiteFooter />
          </main>
        </SessionProvider>
      </body>
    </html>
  );
}
