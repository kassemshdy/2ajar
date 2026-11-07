import { setRequestLocale } from "next-intl/server";
import { AdminShell } from "@/components/admin/admin-shell";
import { AdminUsers } from "@/components/admin/admin-users";

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return (
    <AdminShell need="users.read">
      <AdminUsers />
    </AdminShell>
  );
}
