import type { ListingPublic, Location, PricePeriod } from "@2ajar/contracts";

const numberLocale = (locale: string) => (locale === "ar" ? "ar-LB-u-nu-latn" : "en-US");

/**
 * "$1,500" in every language. Lebanon writes dollar prices this way in Arabic too; "US$ 1.500" (ar-LB) gets
 * reordered to "$US 1.500" inside right-to-left text. The Unicode LTR isolate keeps "$1,500" intact in Arabic.
 */
export function formatUsd(amount: number, locale: string) {
  const text = new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);
  return locale === "ar" ? `\u2066${text}\u2069` : text;
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

const PERIOD_SUFFIX: Record<PricePeriod, string | null> = {
  hourly: "perHour",
  daily: "perDay",
  nightly: "perNight",
  weekly: "perWeek",
  monthly: "perMonth",
  yearly: "perYear",
  total: null,
};

/** Message key (in the "listing" namespace) for the price suffix, e.g. "/night". */
export function periodSuffixKey(period: PricePeriod): string | null {
  return PERIOD_SUFFIX[period] ?? null;
}

export type StayKind = "hours" | "nights" | "months";

/** Which kind of stay a price period belongs to (mirrors the API's STAY_PERIODS). */
export function stayOf(period: PricePeriod): StayKind {
  if (period === "hourly" || period === "daily") return "hours";
  if (period === "nightly" || period === "weekly") return "nights";
  return "months";
}
