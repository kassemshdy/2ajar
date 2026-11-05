import { setRequestLocale } from "next-intl/server";
import type { Location } from "@2ajar/contracts";
import { ListingForm } from "@/components/listing-form";
import { apiGet } from "@/lib/api-server";

export const dynamic = "force-dynamic";

export default async function NewListingPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const locations = (await apiGet<Location[]>("/locations")) ?? [];
  return <ListingForm locations={locations} />;
}
