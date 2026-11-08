import { Star, Users } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { ListingPublic } from "@2ajar/contracts";
import { formatUsd, listingTitle, locationName, periodSuffixKey } from "@/lib/format";
import { cn } from "@/lib/utils";
import { FavoriteButton } from "./favorite-button";

/**
 * Airbnb-style card: square photo with a heart, "Type · Area", title, guests/bedrooms, bold price per period,
 * and an optional honest note explaining why it is in this row (distance, visitors, value).
 */
export function ListingTile({
  listing,
  note,
  className,
}: {
  listing: ListingPublic;
  note?: string;
  className?: string;
}) {
  const t = useTranslations("listing");
  const te = useTranslations("enums");
  const tDemo = useTranslations("demo");
  const locale = useLocale();
  const cover = listing.media[0];
  const p = listing.property;
  const suffix = periodSuffixKey(listing.price_period);
  const facts = [
    p.max_guests ? t("guests", { count: p.max_guests }) : null,
    p.bedrooms != null ? t("bedrooms", { count: p.bedrooms }) : null,
  ].filter(Boolean);

  return (
    <a
      href={`/${locale}/listings/${listing.id}`}
      className={cn("group flex flex-col gap-2", className)}
      data-testid="listing-tile"
    >
      <div className="relative aspect-square overflow-hidden rounded-2xl bg-muted">
        {cover ? (
          <img
            src={cover.url}
            alt=""
            loading="lazy"
            className="size-full object-cover transition duration-300 group-hover:scale-105"
          />
        ) : (
          <div className="flex size-full items-center justify-center text-sm text-muted-foreground">{t("noPhotos")}</div>
        )}
        {listing.is_demo ? (
          <span className="absolute start-3 top-3 rounded-full bg-white/95 px-2.5 py-1 text-xs font-semibold text-amber-900 shadow-sm">
            {tDemo("badge")}
          </span>
        ) : null}
        <div className="absolute end-2 top-2">
          <FavoriteButton listingId={listing.id} />
        </div>
      </div>
      <div className="flex flex-col gap-0.5 text-[15px] leading-snug">
        <p className="flex items-center justify-between gap-2 font-semibold">
          <span className="truncate">
            {te(p.property_type)} · {locationName(listing.location, locale)}
          </span>
        </p>
        <p className="line-clamp-1 text-muted-foreground" dir="auto">
          {listingTitle(listing, locale)}
        </p>
        {facts.length ? (
          <p className="flex items-center gap-1 text-muted-foreground">
            {p.max_guests ? <Users className="size-3.5" aria-hidden /> : null}
            {facts.join(" · ")}
          </p>
        ) : null}
        {note ? (
          <p className="flex items-center gap-1 text-sm text-primary">
            <Star className="size-3.5" aria-hidden />
            {note}
          </p>
        ) : null}
        <p className="mt-0.5">
          <span className="font-semibold">{formatUsd(listing.price_usd, locale)}</span>
          {suffix ? <span className="text-muted-foreground"> {t(suffix)}</span> : null}
        </p>
      </div>
    </a>
  );
}
