import type { ListingPublic, Location } from "@2ajar/contracts";

const numberLocale = (locale: string) => (locale === "ar" ? "ar-LB-u-nu-latn" : "en-US");

export function formatUsd(amount: number, locale: string) {
  return new Intl.NumberFormat(numberLocale(locale), {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
}

export function formatDate(iso: string | null | undefined, locale: string) {
  if (!iso) return "";
  return new Intl.DateTimeFormat(numberLocale(locale), { dateStyle: "medium" }).format(new Date(iso));
}

export function localized(text: { en?: string | null; ar?: string | null }, locale: string) {
  return (locale === "ar" ? text.ar || text.en : text.en || text.ar) ?? "";
}

export function locationName(loc: Pick<Location, "name_en" | "name_ar">, locale: string) {
  return locale === "ar" ? loc.name_ar : loc.name_en;
}

export function listingTitle(listing: ListingPublic, locale: string) {
  return localized(listing.title, locale);
}
