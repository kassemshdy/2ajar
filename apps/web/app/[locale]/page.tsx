import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ListingPage } from "@2ajar/contracts";
import { DemoBanner } from "@/components/demo-banner";
import { ListingCard } from "@/components/listing-card";
import { SearchFilters } from "@/components/search-filters";
import { Card } from "@/components/ui/card";
import { Link } from "@/i18n/navigation";
import { apiGet, getLocations, getPublicConfig } from "@/lib/api-server";

export const dynamic = "force-dynamic";

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");
  const [config, locations, latest] = await Promise.all([
    getPublicConfig(),
    getLocations(),
    apiGet<ListingPage>("/listings?transaction_type=rent&page_size=6"),
  ]);

  return (
    <div className="flex flex-col gap-8">
      <DemoBanner show={config.demo_mode} />
      <section className="grid gap-6 rounded-2xl bg-gradient-to-br from-primary to-teal-900 p-6 text-white sm:p-10 lg:grid-cols-[1fr_minmax(0,28rem)]">
        <div className="flex flex-col justify-center gap-3">
          <h1 className="text-3xl font-bold leading-tight sm:text-4xl">{t("headline")}</h1>
          <p className="text-white/85">{t("subheadline")}</p>
        </div>
        <Card className="p-4 text-foreground">
          <SearchFilters locations={locations ?? []} state={{}} compact />
        </Card>
      </section>
      <section className="flex flex-col gap-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-xl font-semibold">{t("latest")}</h2>
          <Link href="/listings" className="text-sm font-medium text-primary hover:underline">
            {t("seeAll")}
          </Link>
        </div>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {(latest?.items ?? []).map((l) => (
            <ListingCard key={l.id} listing={l} />
          ))}
        </div>
      </section>
    </div>
  );
}
