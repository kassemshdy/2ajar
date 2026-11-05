import { getTranslations, setRequestLocale } from "next-intl/server";
import type { ListingPage } from "@2ajar/contracts";
import { DemoBanner } from "@/components/demo-banner";
import { ListingCard } from "@/components/listing-card";
import { SearchFilters, type SearchState } from "@/components/search-filters";
import { Card } from "@/components/ui/card";
import { apiGet, getLocations, getPublicConfig } from "@/lib/api-server";

export const dynamic = "force-dynamic";

const KEYS = [
  "transaction_type", "location", "price_min", "price_max", "bedrooms_min", "furnished", "property_type", "sort",
] as const;
const PAGE_SIZE = 12;

export default async function ListingsPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const sp = await searchParams;
  const t = await getTranslations("results");

  const state: SearchState = {};
  const query = new URLSearchParams();
  for (const key of KEYS) {
    const v = sp[key];
    if (typeof v === "string" && v !== "") {
      state[key] = v;
      query.set(key, v);
    }
  }
  if (!state.transaction_type) {
    state.transaction_type = "rent";
    query.set("transaction_type", "rent");
  }
  const page = Math.max(1, Number(sp.page) || 1);
  query.set("page", String(page));
  query.set("page_size", String(PAGE_SIZE));

  const [config, locations, results] = await Promise.all([
    getPublicConfig(),
    getLocations(),
    apiGet<ListingPage>(`/listings?${query.toString()}`).catch(() => null),
  ]);
  const total = results?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const pageHref = (p: number) => {
    const q = new URLSearchParams(query);
    q.delete("page_size");
    q.set("page", String(p));
    return `/${locale}/listings?${q.toString()}`;
  };

  return (
    <div className="flex flex-col gap-4">
      <DemoBanner show={config.demo_mode} />
      <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
        <aside>
          <Card className="p-4 lg:sticky lg:top-20">
            <SearchFilters locations={locations ?? []} state={state} />
          </Card>
        </aside>
        <section className="flex flex-col gap-4">
          <h1 className="text-xl font-semibold" data-testid="results-count">
            {t("count", { count: total })}
          </h1>
          {total === 0 ? (
            <p className="text-muted-foreground">{t("empty")}</p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {results!.items.map((l) => (
                <ListingCard key={l.id} listing={l} />
              ))}
            </div>
          )}
          {pages > 1 ? (
            <nav className="flex items-center justify-between text-sm" aria-label="pagination">
              {page > 1 ? <a className="text-primary" href={pageHref(page - 1)}>{t("previous")}</a> : <span />}
              <span className="text-muted-foreground">{t("page", { page, pages })}</span>
              {page < pages ? <a className="text-primary" href={pageHref(page + 1)}>{t("next")}</a> : <span />}
            </nav>
          ) : null}
        </section>
      </div>
    </div>
  );
}
