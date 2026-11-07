import { setRequestLocale } from "next-intl/server";
import { ApiTokens } from "@/components/api-tokens";

export default async function Page({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <ApiTokens />;
}
