import { BedDouble, Bath, Building, CheckCircle2, Layers, MapPin, Ruler, Sofa, Users } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import type { ListingPublic, NearbyListing } from "@2ajar/contracts";
import { ContactPanel } from "@/components/contact-panel";
import { DemoBanner } from "@/components/demo-banner";
import { FavoriteButton } from "@/components/favorite-button";
import { Row } from "@/components/home/row";
import { ListingTile } from "@/components/listing-tile";
import { AreaInfo, LivingHere } from "@/components/living-here";
import { Badge, Card } from "@/components/ui/card";
import { apiGet, getPublicConfig } from "@/lib/api-server";
import { formatDate, formatUsd, listingTitle, localized, locationName, periodSuffixKey, stayOf } from "@/lib/format";

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
  const tStay = await getTranslations("stay");
  const p = listing.property;
  const period =
    periodSuffixKey(listing.price_period) ? t(periodSuffixKey(listing.price_period)!) : "";
  const description = localized(listing.description, locale);

  const facts = [
    p.max_guests ? { icon: Users, text: t("upToGuests", { count: p.max_guests }) } : null,
    p.bedrooms != null && { icon: BedDouble, text: t("bedrooms", { count: p.bedrooms }) },
    p.bathrooms != null && { icon: Bath, text: t("bathrooms", { count: p.bathrooms }) },
    p.area_sqm && { icon: Ruler, text: t("area", { area: p.area_sqm }) },
    p.floor != null && { icon: Layers, text: t("floor", { floor: p.floor }) },
    p.furnished && { icon: Sofa, text: te(p.furnished) },
  ].filter(Boolean) as { icon: typeof Bath; text: string }[];
  const similar = (await apiGet<NearbyListing[]>(`/listings/${listing.id}/similar`).catch(() => null)) ?? [];
  const photos = listing.media.slice(0, 5);
  const price = (
    <p data-testid="listing-price">
      <span className="text-2xl font-semibold">{formatUsd(listing.price_usd, locale)}</span>
      <span className="text-muted-foreground"> {period}</span>
    </p>
  );

  return (
    <article className="flex flex-col gap-8" data-testid="listing-detail">
      <DemoBanner show={listing.is_demo} />

      <header className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl" dir="auto">
          {listingTitle(listing, locale)}
        </h1>
        <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 font-medium">
            <span className="flex items-center gap-1">
              <MapPin className="size-4" aria-hidden />
              {locationName(listing.location, locale)}
            </span>
            <span aria-hidden>·</span>
            <span>{tStay(stayOf(listing.price_period))}</span>
            {listing.is_demo ? <Badge tone="demo">{tDemo("badge")}</Badge> : null}
          </p>
          <FavoriteButton listingId={listing.id} variant="inline" />
        </div>
      </header>

      <div
        className={`grid gap-2 overflow-hidden rounded-2xl ${photos.length > 1 ? "sm:grid-cols-4 sm:grid-rows-2" : ""}`}
        data-testid="photo-grid"
      >
        {photos.length ? (
          photos.map((m, i) => (
            <div
              key={m.id}
              className={
                i === 0
                  ? `aspect-[4/3] bg-muted ${photos.length > 1 ? "sm:col-span-2 sm:row-span-2 sm:aspect-auto" : "sm:aspect-[2/1] lg:aspect-[5/2]"}`
                  : "hidden aspect-[4/3] bg-muted sm:block"
              }
            >
              <img
                src={m.url}
                alt={i === 0 ? listingTitle(listing, locale) : ""}
                loading={i === 0 ? "eager" : "lazy"}
                className="size-full object-cover"
              />
            </div>
          ))
        ) : (
          <div className="flex aspect-[4/3] items-center justify-center bg-muted text-muted-foreground sm:aspect-[21/9]">
            {t("noPhotos")}
          </div>
        )}
      </div>

      <div className="grid gap-10 lg:grid-cols-[1fr_24rem]">
        <div className="flex flex-col divide-y divide-border">
          <section className="flex flex-col gap-1 pb-6">
            <h2 className="text-xl font-semibold">
              {te(p.property_type)} · {locationName(listing.location, locale)}
            </h2>
            <p className="text-muted-foreground">{facts.map((f) => f.text).join(" · ")}</p>
            <p className="mt-2 text-sm">{t("hostedBy", { name: listing.publisher.display_name })}</p>
            {listing.last_confirmed_at ? (
              <p className="flex items-center gap-1 text-sm text-emerald-700">
                <CheckCircle2 className="size-4" aria-hidden />
                {t("verifiedFresh", { date: formatDate(listing.last_confirmed_at, locale) })}
              </p>
            ) : null}
          </section>

          <section className="py-6">
            <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {facts.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-center gap-3 text-sm">
                  <Icon className="size-5 text-foreground" strokeWidth={1.5} aria-hidden />
                  {text}
                </li>
              ))}
              <li className="flex items-center gap-3 text-sm">
                <Building className="size-5" strokeWidth={1.5} aria-hidden />
                {te(p.property_type)}
              </li>
            </ul>
          </section>

          {description ? (
            <section className="py-6">
              <h2 className="mb-3 text-xl font-semibold">{t("description")}</h2>
              {/* Untrusted publisher text: rendered as plain text (React escapes it). */}
              <p className="whitespace-pre-line leading-relaxed" dir="auto">
                {description}
              </p>
            </section>
          ) : null}

          {p.amenities.length ? (
            <section className="py-6">
              <h2 className="mb-3 text-xl font-semibold">{t("amenities")}</h2>
              <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                {p.amenities.map((a) => (
                  <li key={a} className="flex items-center gap-2 text-sm">
                    <CheckCircle2 className="size-4 text-primary" aria-hidden />
                    {te(a)}
                  </li>
                ))}
              </ul>
            </section>
          ) : null}

          {p.living ? (
            <div className="py-6 empty:hidden">
              <LivingHere living={p.living} />
            </div>
          ) : null}

          {listing.area ? (
            <div className="py-6">
              <AreaInfo area={listing.area} />
            </div>
          ) : null}
        </div>

        <aside className="lg:sticky lg:top-24 lg:self-start">
          {listing.status === "published" ? (
            <ContactPanel listingId={listing.id} consentVersion={config.consent_text_version} header={price} />
          ) : (
            <Card className="rounded-2xl p-6 shadow-lg">{price}</Card>
          )}
        </aside>
      </div>

      {similar.length ? (
        <div className="border-t border-border pt-8">
          <Row title={t("similar")} testId="row-similar">
            {similar.map((h) => (
              <ListingTile key={h.listing.id} listing={h.listing} note={t("kmAway", { km: h.distance_km })} />
            ))}
          </Row>
        </div>
      ) : null}
    </article>
  );
}
