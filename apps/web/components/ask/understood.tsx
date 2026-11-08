import { SlidersHorizontal } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { AskResponse } from "@2ajar/contracts";

/** Classic-filter query equivalent to what the parser understood, so people can fine-tune by hand. */
export function filtersHref(u: AskResponse["understood"], locale: string): string {
  const params = new URLSearchParams();
  const set = (k: string, v: string | number | null | undefined) => {
    if (v !== null && v !== undefined && v !== "") params.set(k, String(v));
  };
  set("transaction_type", u.transaction_type);
  set("location", u.location_slug);
  set("price_min", u.price_min);
  set("price_max", u.price_max);
  set("bedrooms_min", u.bedrooms_min || null);
  set("furnished", u.furnished);
  set("property_type", u.property_type);
  if (u.sort !== "newest") set("sort", u.sort);
  const qs = params.toString();
  return `/${locale}/listings${qs ? `?${qs}` : ""}`;
}

export function Understood({ answer }: { answer: AskResponse }) {
  const t = useTranslations("ask");
  const locale = useLocale();
  const ar = locale === "ar";
  return (
    <div className="flex flex-col gap-3" data-testid="ask-understood">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">{t("understood")}</p>
        <p className="text-lg font-medium" dir="auto">
          {ar ? answer.summary_ar : answer.summary_en}
        </p>
      </div>
      {answer.understood.preferences.length ? (
        <ul className="flex flex-wrap gap-2">
          {answer.understood.preferences.map((p) => (
            <li key={p.key} className="rounded-full bg-primary/10 px-3 py-1 text-sm text-primary">
              {ar ? p.label_ar : p.label_en}
            </li>
          ))}
        </ul>
      ) : null}
      {answer.clarification_en ? (
        <p className="rounded-lg bg-sky-50 px-3 py-2 text-sm text-sky-900" data-testid="ask-clarification">
          {ar ? answer.clarification_ar : answer.clarification_en}
        </p>
      ) : null}
      {answer.relaxed.length ? (
        <div className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900" data-testid="ask-relaxed">
          <p className="font-medium">{t("relaxed")}</p>
          <ul className="list-inside list-disc">
            {answer.relaxed.map((r) => (
              <li key={r.key}>{ar ? r.label_ar : r.label_en}</li>
            ))}
          </ul>
        </div>
      ) : null}
      <a
        href={filtersHref(answer.understood, locale)}
        className="inline-flex items-center gap-1 self-start text-sm font-medium text-primary hover:underline"
      >
        <SlidersHorizontal className="size-4" aria-hidden />
        {t("refine")}
      </a>
    </div>
  );
}
