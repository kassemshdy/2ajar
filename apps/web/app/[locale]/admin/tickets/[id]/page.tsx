import { setRequestLocale } from "next-intl/server";
import { AdminShell } from "@/components/admin/admin-shell";
import { AdminTicketDetail } from "@/components/admin/admin-tickets";

export default async function Page({ params }: { params: Promise<{ locale: string; id: string }> }) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  return (
    <AdminShell need="tickets.read">
      <AdminTicketDetail id={id} />
    </AdminShell>
  );
}
