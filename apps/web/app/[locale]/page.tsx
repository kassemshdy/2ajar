import { getTranslations, setRequestLocale } from "next-intl/server";
import type { DiscoverOut } from "@2ajar/contracts";
import { AskBox } from "@/components/ask/ask-box";
import { DemoBanner } from "@/components/demo-banner";
import { CategoryBar } from "@/components/home/category-bar";
import { NearYou } from "@/components/home/near-you";
import { Row } from "@/components/home/row";
import { TopAreas } from "@/components/home/top-areas";
import { ListingTile } from "@/components/listing-tile";
import { apiGet, getPublicConfig, getSuggestions } from "@/lib/api-server";

export const dynamic = "force-dynamic";

const EMPTY: DiscoverOut = { recent: [], nights: [], hours: [], most_viewed: [], great_value: [], top_areas: [] };

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");
  const td = await getTranslations("discover");
  const [config, discover, suggestions] = await Promise.all([
    getPublicConfig(),
    apiGet<DiscoverOut>("/discover").catch(() => null),
    getSuggestions().catch(() => null),
  ]);
  const d = discover ?? EMPTY;
  const list = (stay?: string) => `/${locale}/listings${stay ? `?stay=${stay}` : ""}`;

  return (
    <div className="flex flex-col gap-10">
      <DemoBanner show={config.demo_mode} />
      <section className="flex flex-col gap-5 rounded-3xl bg-gradient-to-br from-primary to-teal-900 p-6 text-white sm:p-10">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold leading-tight sm:text-4xl">{t("headline")}</h1>
          <p className="text-white/85">{t("subheadline")}</p>
        </div>
        <AskBox suggestions={(suggestions ?? []).slice(0, 4)} />
      </section>

      <CategoryBar />

      <NearYou />

      <Row title={td("recent")} subtitle={td("recentHint")} href={list()} testId="row-recent">
        {d.recent.map((l) => (
          <ListingTile key={l.id} listing={l} />
        ))}
      </Row>

      <Row title={td("nights")} subtitle={td("nightsHint")} href={list("nights")} testId="row-nights">
        {d.nights.map((l) => (
          <ListingTile key={l.id} listing={l} />
        ))}
      </Row>

      <Row title={td("mostViewed")} subtitle={td("mostViewedHint")} testId="row-most-viewed">
        {d.most_viewed.map((x) => (
          <ListingTile key={x.listing.id} listing={x.listing} note={td("visitors", { count: x.visitors_30d })} />
        ))}
      </Row>

      <TopAreas areas={d.top_areas} />

      <Row title={td("hours")} subtitle={td("hoursHint")} href={list("hours")} testId="row-hours">
        {d.hours.map((l) => (
          <ListingTile key={l.id} listing={l} />
        ))}
      </Row>

      <Row title={td("greatValue")} subtitle={td("greatValueHint")} testId="row-great-value">
        {d.great_value.map((x) => (
          <ListingTile
            key={x.listing.id}
            listing={x.listing}
            note={td("belowArea", { pct: x.below_area_median_pct })}
          />
        ))}
      </Row>
    </div>
  );
}
