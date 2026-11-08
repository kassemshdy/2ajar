import { setRequestLocale } from "next-intl/server";
import { AdminShell } from "@/components/admin/admin-shell";
import { AdminTickets } from "@/components/admin/admin-tickets";

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <AdminShell need="tickets.read">
      <AdminTickets />
    </AdminShell>
  );
}
