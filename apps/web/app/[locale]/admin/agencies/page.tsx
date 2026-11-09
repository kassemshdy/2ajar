import { setRequestLocale } from "next-intl/server";
import { AdminShell } from "@/components/admin/admin-shell";
import { AdminAgencies } from "@/components/admin/admin-agencies";

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <AdminShell need="listings.moderate">
      <AdminAgencies />
    </AdminShell>
  );
}
