import { redirect } from "next/navigation";

export default function LegalTermsPage() {
  // 内测期服务条款与隐私须知合并为《服务使用须知》单页维护，
  // 访问 /legal/terms 时直接跳转，避免两处文本不同步。
  redirect("/legal/notice");
}
