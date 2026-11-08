import { ShieldCheck, Volume1 } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { DiscoverOut } from "@2ajar/contracts";

const TINTS = ["from-teal-600 to-emerald-800", "from-sky-600 to-indigo-800", "from-amber-500 to-rose-700",
  "from-fuchsia-600 to-purple-800", "from-lime-600 to-green-800", "from-cyan-600 to-blue-800"];

/** "Top-rated neighbourhoods": staff-curated safety and quiet scores (never visitor ratings we don't have). */
export function TopAreas({ areas }: { areas: DiscoverOut["top_areas"] }) {
  const t = useTranslations("discover");
  const ta = useTranslations("area");
  const tDemo = useTranslations("demo");
  const locale = useLocale();
  if (!areas.length) return null;
  return (
    <section className="flex flex-col gap-3" data-testid="row-top-areas">
      <div>
        <h2 className="text-xl font-semibold tracking-tight">{t("topAreas")}</h2>
        <p className="text-sm text-muted-foreground">{t("topAreasHint")}</p>
      </div>
      <ul className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {areas.map(({ area, listing_count }, i) => (
          <li key={area.location_slug}>
            <a
              href={`/${locale}/listings?location=${area.location_slug}`}
              className={`flex h-full flex-col justify-between gap-6 rounded-2xl bg-gradient-to-br p-4 text-white shadow-sm transition hover:shadow-lg ${TINTS[i % TINTS.length]}`}
            >
              <div className="flex items-start justify-between gap-2">
                <p className="text-lg font-semibold leading-tight">
                  {locale === "ar" ? area.location_name_ar : area.location_name_en}
                </p>
                {area.is_demo ? (
                  <span className="rounded-full bg-white/90 px-2 py-0.5 text-[10px] font-bold text-amber-900">
                    {tDemo("badge")}
                  </span>
                ) : null}
              </div>
              <div className="flex flex-col gap-1 text-sm">
                <div className="flex flex-wrap gap-x-3 gap-y-1">
                  {area.safety_score != null ? (
                    <span className="flex items-center gap-1">
                      <ShieldCheck className="size-4" aria-hidden />
                      {ta("safety")} {ta("score", { score: area.safety_score })}
                    </span>
                  ) : null}
                  {area.quiet_score != null ? (
                    <span className="flex items-center gap-1">
                      <Volume1 className="size-4" aria-hidden />
                      {ta("quiet")} {ta("score", { score: area.quiet_score })}
                    </span>
                  ) : null}
                </div>
                <span className="text-white/80">{t("homes", { count: listing_count })}</span>
              </div>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}
