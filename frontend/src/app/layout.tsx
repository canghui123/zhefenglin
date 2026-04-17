import type { Metadata } from "next";
import { Geist } from "next/font/google";
import "./globals.css";
import { SessionProvider } from "@/components/auth/session-provider";
import { AppSidebar } from "@/components/navigation/app-sidebar";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

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
    <html lang="zh-CN" className={`${geistSans.variable} h-full`}>
      <body className="min-h-full flex bg-gray-50 antialiased">
        <SessionProvider>
          <AppSidebar />

          {/* Main content */}
          <main className="flex-1 overflow-auto">
            <div className="p-8">{children}</div>
          </main>
        </SessionProvider>
      </body>
    </html>
  );
}
