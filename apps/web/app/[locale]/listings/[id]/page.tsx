import { BedDouble, Bath, Building, CheckCircle2, Layers, MapPin, Ruler, Sofa } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import type { ListingPublic } from "@2ajar/contracts";
import { ContactPanel } from "@/components/contact-panel";
import { DemoBanner } from "@/components/demo-banner";
import { AreaInfo, LivingHere } from "@/components/living-here";
import { Badge, Card } from "@/components/ui/card";
import { apiGet, getPublicConfig } from "@/lib/api-server";
import { formatDate, formatUsd, listingTitle, localized, locationName } from "@/lib/format";

export const dynamic = "force-dynamic";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

async function load(id: string) {
  if (!UUID_RE.test(id)) return null;
  // Forward cookies so publishers can preview their own unpublished listings.
  return apiGet<ListingPublic>(`/listings/${id}`, { forwardCookies: true });
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}): Promise<Metadata> {
  const { locale, id } = await params;
  const listing = await load(id);
  if (!listing) return {};
  return {
    title: `${listingTitle(listing, locale)} — ${formatUsd(listing.price_usd, locale)}`,
    description: localized(listing.description, locale).slice(0, 160),
    robots: listing.is_demo || listing.status !== "published" ? { index: false } : undefined,
  };
}

export default async function ListingDetailPage({ params }: { params: Promise<{ locale: string; id: string }> }) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  const [listing, config] = await Promise.all([load(id), getPublicConfig()]);
  if (!listing) notFound();
  const t = await getTranslations("listing");
  const te = await getTranslations("enums");
  const tDemo = await getTranslations("demo");
  const p = listing.property;
  const period =
    listing.price_period === "monthly" ? t("perMonth") : listing.price_period === "yearly" ? t("perYear") : "";
  const [cover, ...rest] = listing.media;
  const description = localized(listing.description, locale);

  const facts = [
    p.bedrooms != null && { icon: BedDouble, text: t("bedrooms", { count: p.bedrooms }) },
    p.bathrooms != null && { icon: Bath, text: t("bathrooms", { count: p.bathrooms }) },
    p.area_sqm && { icon: Ruler, text: t("area", { area: p.area_sqm }) },
    p.floor != null && { icon: Layers, text: t("floor", { floor: p.floor }) },
    p.furnished && { icon: Sofa, text: te(p.furnished) },
    { icon: Building, text: te(p.property_type) },
  ].filter(Boolean) as { icon: typeof Bath; text: string }[];

  return (
    <article className="flex flex-col gap-6" data-testid="listing-detail">
      <DemoBanner show={listing.is_demo} />
      <div className="grid gap-2 overflow-hidden rounded-2xl sm:grid-cols-[2fr_1fr]">
        <div className="aspect-[4/3] bg-muted sm:row-span-2">
          {cover ? (
            <img src={cover.url} alt={listingTitle(listing, locale)} className="size-full object-cover" />
          ) : (
            <div className="flex size-full items-center justify-center text-muted-foreground">{t("noPhotos")}</div>
          )}
        </div>
        {rest.slice(0, 2).map((m) => (
          <div key={m.id} className="hidden aspect-[4/3] bg-muted sm:block">
            <img src={m.url} alt="" loading="lazy" className="size-full object-cover" />
          </div>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <div className="flex flex-col gap-6">
          <header className="flex flex-col gap-2">
            <div className="flex flex-wrap gap-2">
              <Badge>{listing.transaction_type === "rent" ? t("forRent") : t("forSale")}</Badge>
              {listing.is_demo ? <Badge tone="demo">{tDemo("badge")}</Badge> : null}
            </div>
            <h1 className="text-2xl font-bold sm:text-3xl">{listingTitle(listing, locale)}</h1>
            <p className="flex items-center gap-1 text-muted-foreground">
              <MapPin className="size-4" aria-hidden />
              {locationName(listing.location, locale)}
            </p>
            <p className="text-3xl font-bold text-primary" data-testid="listing-price">
              {formatUsd(listing.price_usd, locale)}
              <span className="text-base font-normal text-muted-foreground">{period}</span>
            </p>
            {listing.last_confirmed_at ? (
              <p className="flex items-center gap-1 text-sm text-emerald-700">
                <CheckCircle2 className="size-4" aria-hidden />
                {t("verifiedFresh", { date: formatDate(listing.last_confirmed_at, locale) })}
              </p>
            ) : null}
          </header>

          <section>
            <h2 className="mb-3 font-semibold">{t("facts")}</h2>
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {facts.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
                  <Icon className="size-4 text-primary" aria-hidden />
                  {text}
                </li>
              ))}
            </ul>
          </section>

          {p.amenities.length ? (
            <section>
              <h2 className="mb-3 font-semibold">{t("amenities")}</h2>
              <ul className="flex flex-wrap gap-2">
                {p.amenities.map((a) => (
                  <li key={a}>
                    <Badge tone="muted">{te(a)}</Badge>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {p.living ? <LivingHere living={p.living} /> : null}

          {listing.area ? <AreaInfo area={listing.area} /> : null}

          {description ? (
            <section>
              <h2 className="mb-3 font-semibold">{t("description")}</h2>
              {/* Untrusted publisher text: rendered as plain text (React escapes it). */}
              <p className="whitespace-pre-line leading-relaxed" dir="auto">
                {description}
              </p>
            </section>
          ) : null}
        </div>

        <aside className="flex flex-col gap-4">
          <Card className="p-4">
            <p className="text-sm text-muted-foreground">{t("publishedBy")}</p>
            <p className="font-semibold">{listing.publisher.display_name}</p>
          </Card>
          {listing.status === "published" ? (
            <ContactPanel listingId={listing.id} consentVersion={config.consent_text_version} />
          ) : null}
        </aside>
      </div>
    </article>
  );
}
