import { getTranslations, setRequestLocale } from "next-intl/server";
import type { DiscoverOut } from "@2ajar/contracts";
import { AskBox } from "@/components/ask/ask-box";
import { DemoBanner } from "@/components/demo-banner";
import { CategoryBar } from "@/components/home/category-bar";
import { NearYou } from "@/components/home/near-you";
import { Row } from "@/components/home/row";
import { SearchPill } from "@/components/home/search-pill";
import { TopAreas } from "@/components/home/top-areas";
import { ListingTile } from "@/components/listing-tile";
import { apiGet, getLocations, getPublicConfig, getSuggestions } from "@/lib/api-server";

export const dynamic = "force-dynamic";

const EMPTY: DiscoverOut = {
  recent: [], nights: [], hours: [], most_viewed: [], great_value: [], top_areas: [], by_area: [],
};

export default async function HomePage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("home");
  const td = await getTranslations("discover");
  const [config, discover, suggestions, locations] = await Promise.all([
    getPublicConfig(),
    apiGet<DiscoverOut>("/discover").catch(() => null),
    getSuggestions().catch(() => null),
    getLocations().catch(() => null),
  ]);
  const d = discover ?? EMPTY;
  const ar = locale === "ar";
  const list = (q: string) => `/${locale}/listings${q}`;

  return (
    <div className="flex flex-col gap-12">
      {/* Search band: Airbnb-style pill, then the plain-language search that is 2ajar's own. */}
      <section className="-mx-4 -mt-6 flex flex-col gap-4 border-b border-border bg-gradient-to-b from-white to-muted/60 px-4 pb-8 pt-6 sm:-mx-6 sm:px-6">
        <h1 className="sr-only">{t("headline")}</h1>
        <SearchPill locations={locations ?? []} />
        <div className="mx-auto w-full max-w-4xl">
          <AskBox slim suggestions={(suggestions ?? []).slice(0, 3)} />
        </div>
        <div className="mx-auto w-full max-w-5xl pt-2">
          <CategoryBar />
        </div>
      </section>

      <DemoBanner show={config.demo_mode} />

      {d.by_area.map((row) => {
        const area = ar ? row.name_ar : row.name_en;
        return (
          <Row
            key={row.slug}
            title={td(row.kind === "stays" ? "staysIn" : "popularIn", { area })}
            subtitle={(ar ? row.parent_ar : row.parent_en) ?? undefined}
            href={list(`?location=${row.slug}`)}
            testId="row-area"
          >
            {row.listings.map((l) => (
              <ListingTile key={l.id} listing={l} />
            ))}
          </Row>
        );
      })}

      <Row title={td("recent")} subtitle={td("recentHint")} href={list("")} testId="row-recent">
        {d.recent.map((l) => (
          <ListingTile key={l.id} listing={l} />
        ))}
      </Row>

      <NearYou />

      <Row title={td("mostViewed")} subtitle={td("mostViewedHint")} testId="row-most-viewed">
        {d.most_viewed.map((x) => (
          <ListingTile key={x.listing.id} listing={x.listing} note={td("visitors", { count: x.visitors_30d })} />
        ))}
      </Row>

      <TopAreas areas={d.top_areas} />

      <Row title={td("greatValue")} subtitle={td("greatValueHint")} testId="row-great-value">
        {d.great_value.map((x) => (
          <ListingTile
            key={x.listing.id}
            listing={x.listing}
            note={td("belowArea", { pct: x.below_area_median_pct })}
          />
        ))}
      </Row>

      <Row title={td("nights")} subtitle={td("nightsHint")} href={list("?stay=nights")} testId="row-nights">
        {d.nights.map((l) => (
          <ListingTile key={l.id} listing={l} />
        ))}
      </Row>

      <Row title={td("hours")} subtitle={td("hoursHint")} href={list("?stay=hours")} testId="row-hours">
        {d.hours.map((l) => (
          <ListingTile key={l.id} listing={l} />
        ))}
      </Row>
    </div>
  );
}
