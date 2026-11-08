import { useLocale, useTranslations } from "next-intl";
import type { ListingPublic } from "@2ajar/contracts";
import { formatUsd, locationName } from "@/lib/format";
import { cn } from "@/lib/utils";
import { FavoriteButton } from "./favorite-button";

/**
 * Airbnb-style card: square photo with a heart, then two quiet lines, "Chalet in Faraya" and "$160 night ·
 * 6 guests", plus an optional honest note explaining why it is in this row (distance, visitors, value).
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
  const unit = listing.price_period === "total" ? null : t(`unit_${listing.price_period}`);
  const extra = p.max_guests
    ? t("guests", { count: p.max_guests })
    : p.bedrooms != null
      ? t("bedrooms", { count: p.bedrooms })
      : null;

  return (
    <a
      href={`/${locale}/listings/${listing.id}`}
      className={cn("group flex flex-col gap-2.5", className)}
      data-testid="listing-tile"
    >
      <div className="relative aspect-square overflow-hidden rounded-2xl bg-muted">
        {cover ? (
          <img
            src={cover.url}
            alt=""
            loading="lazy"
            className="size-full object-cover transition duration-300 group-hover:scale-[1.03]"
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
      <div className="flex flex-col text-[15px] leading-5">
        <p className="truncate font-medium">
          {t("typeIn", { type: te(listing.property.property_type), area: locationName(listing.location, locale) })}
        </p>
        <p className="truncate text-muted-foreground">
          <span className="text-foreground">{formatUsd(listing.price_usd, locale)}</span>
          {unit ? ` ${unit}` : null}
          {extra ? ` · ${extra}` : null}
        </p>
        {note ? <p className="truncate text-sm text-primary">{note}</p> : null}
      </div>
    </a>
  );
}
