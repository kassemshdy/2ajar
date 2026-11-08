import { setRequestLocale } from "next-intl/server";
import { AdminAreas } from "@/components/admin/admin-areas";
import { AdminShell } from "@/components/admin/admin-shell";

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <AdminShell need="areas.manage">
      <AdminAreas />
    </AdminShell>
  );
}
