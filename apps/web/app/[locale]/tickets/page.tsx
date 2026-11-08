import { setRequestLocale } from "next-intl/server";
import { MyTickets } from "@/components/my-tickets";

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <MyTickets />;
}
