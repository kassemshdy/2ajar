import { BedDouble, Bath, MapPin, Ruler } from "lucide-react";
import { getLocale, getTranslations } from "next-intl/server";
import type { ListingPublic } from "@2ajar/contracts";
import { Link } from "@/i18n/navigation";
import { formatUsd, listingTitle, locationName } from "@/lib/format";
import { Badge, Card } from "./ui/card";

export async function ListingCard({ listing }: { listing: ListingPublic }) {
  const locale = await getLocale();
  const t = await getTranslations("listing");
  const tDemo = await getTranslations("demo");
  const cover = listing.media[0];
  const p = listing.property;
  const period =
    listing.price_period === "monthly" ? t("perMonth") : listing.price_period === "yearly" ? t("perYear") : "";

  return (
    <Card className="overflow-hidden transition-shadow hover:shadow-md" data-testid="listing-card">
      <Link href={`/listings/${listing.id}`} className="block">
        <div className="relative aspect-[4/3] bg-muted">
          {cover ? (
            <img src={cover.url} alt="" loading="lazy" className="size-full object-cover" />
          ) : (
            <div className="flex size-full items-center justify-center text-sm text-muted-foreground">
              {t("noPhotos")}
            </div>
          )}
          <div className="absolute start-2 top-2 flex gap-1">
            <Badge className="bg-background/90 text-foreground">
              {listing.transaction_type === "rent" ? t("forRent") : t("forSale")}
            </Badge>
            {listing.is_demo ? <Badge tone="demo">{tDemo("badge")}</Badge> : null}
          </div>
        </div>
        <div className="flex flex-col gap-2 p-4">
          <p className="text-lg font-bold">
            {formatUsd(listing.price_usd, locale)}
            <span className="text-sm font-normal text-muted-foreground">{period}</span>
          </p>
          <h3 className="line-clamp-2 font-medium">{listingTitle(listing, locale)}</h3>
          <p className="flex items-center gap-1 text-sm text-muted-foreground">
            <MapPin className="size-4 shrink-0" aria-hidden />
            {locationName(listing.location, locale)}
          </p>
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {p.bedrooms != null ? (
              <span className="flex items-center gap-1">
                <BedDouble className="size-4" aria-hidden />
                {t("bedrooms", { count: p.bedrooms })}
              </span>
            ) : null}
            {p.bathrooms != null ? (
              <span className="flex items-center gap-1">
                <Bath className="size-4" aria-hidden />
                {t("bathrooms", { count: p.bathrooms })}
              </span>
            ) : null}
            {p.area_sqm ? (
              <span className="flex items-center gap-1">
                <Ruler className="size-4" aria-hidden />
                {t("area", { area: p.area_sqm })}
              </span>
            ) : null}
          </div>
        </div>
      </Link>
    </Card>
  );
}
