import { setRequestLocale } from "next-intl/server";
import { TicketDetail } from "@/components/my-tickets";

export default async function Page({ params }: { params: Promise<{ locale: string; id: string }> }) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  return <TicketDetail id={id} />;
}
