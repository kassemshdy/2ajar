import { setRequestLocale } from "next-intl/server";
import { AdminGrowth } from "@/components/admin/admin-growth";
import { AdminShell } from "@/components/admin/admin-shell";

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <AdminShell need="analytics.read">
      <AdminGrowth />
    </AdminShell>
  );
}
