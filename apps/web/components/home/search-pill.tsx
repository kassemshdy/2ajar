import { Search } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { Location } from "@2ajar/contracts";

/**
 * Airbnb-style "Where · When · Who" pill. A plain GET form to the results page, so it works without JavaScript.
 * "When" is the length of stay (by the hour / nights / months), since 2ajar rents from an hour to years.
 */
export function SearchPill({ locations }: { locations: Location[] }) {
  const t = useTranslations("discover");
  const tStay = useTranslations("stay");
  const locale = useLocale();
  const name = (l: Location) => (locale === "ar" ? l.name_ar : l.name_en);
  const tops = locations.filter((l) => !l.parent_id);
  const under = (id: string) => locations.filter((l) => l.parent_id === id);
  const cell = "flex min-w-0 flex-1 flex-col rounded-full px-6 py-3 transition hover:bg-muted focus-within:bg-white focus-within:shadow-lg";
  const select = "w-full cursor-pointer appearance-none truncate bg-transparent text-sm text-muted-foreground outline-none";

  return (
    <form
      action={`/${locale}/listings`}
      method="get"
      role="search"
      data-testid="search-pill"
      className="mx-auto flex w-full max-w-4xl flex-col gap-1 rounded-3xl border border-border bg-white p-2 shadow-[0_3px_12px_rgba(0,0,0,0.08)] sm:flex-row sm:items-center sm:rounded-full"
    >
      <label className={cell}>
        <span className="text-xs font-semibold">{t("where")}</span>
        <select name="location" defaultValue="" className={select} aria-label={t("where")}>
          <option value="">{t("whereAny")}</option>
          {tops.map((g) => (
            <optgroup key={g.id} label={name(g)}>
              <option value={g.slug}>{name(g)}</option>
              {under(g.id).flatMap((d) => [d, ...under(d.id)]).map((l) => (
                <option key={l.id} value={l.slug}>
                  {l.level === "area" && l.path.split("/").length > 2 ? `  ${name(l)}` : name(l)}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      <span className="hidden h-8 w-px bg-border sm:block" aria-hidden />
      <label className={cell}>
        <span className="text-xs font-semibold">{t("when")}</span>
        <select name="stay" defaultValue="" className={select} aria-label={t("when")}>
          <option value="">{t("whenAny")}</option>
          {(["hours", "nights", "months"] as const).map((s) => (
            <option key={s} value={s}>
              {tStay(s)}
            </option>
          ))}
        </select>
      </label>
      <span className="hidden h-8 w-px bg-border sm:block" aria-hidden />
      <label className={cell}>
        <span className="text-xs font-semibold">{t("who")}</span>
        <select name="guests_min" defaultValue="" className={select} aria-label={t("who")}>
          <option value="">{t("whoAny")}</option>
          {[1, 2, 3, 4, 5, 6, 8, 10, 12, 15, 20].map((n) => (
            <option key={n} value={n}>
              {n}+
            </option>
          ))}
        </select>
      </label>
      <button
        type="submit"
        aria-label={t("search")}
        className="flex h-12 shrink-0 items-center justify-center gap-2 rounded-full bg-primary px-4 text-primary-foreground transition hover:brightness-110 sm:size-12 sm:px-0"
      >
        <Search className="size-5" strokeWidth={2.5} aria-hidden />
        <span className="sm:sr-only">{t("search")}</span>
      </button>
    </form>
  );
}
