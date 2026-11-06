import { setRequestLocale } from "next-intl/server";
import { Dashboard } from "@/components/dashboard";

export default async function DashboardPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <Dashboard />;
}
