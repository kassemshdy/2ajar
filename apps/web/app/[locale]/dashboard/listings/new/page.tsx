import { setRequestLocale } from "next-intl/server";
import { ListingForm } from "@/components/listing-form";
import { getLocations } from "@/lib/api-server";

export const dynamic = "force-dynamic";

export default async function NewListingPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const locations = (await getLocations()) ?? [];
  return <ListingForm locations={locations} />;
}
