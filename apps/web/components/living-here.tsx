import { Car, Droplets, Flame, Info, Leaf, ShieldCheck, Snowflake, Sparkles, Sun, Waves, Zap } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { AreaProfile, LivingFactors } from "@2ajar/contracts";
import { formatDate, formatUsd } from "@/lib/format";
import { Badge } from "./ui/card";

type Row = { icon: typeof Zap; label: string; value: string };

/** Publisher-reported running costs and comfort ("Living here"). Hidden when nothing was reported. */
export function LivingHere({ living }: { living: LivingFactors }) {
  const t = useTranslations("living");
  const locale = useLocale();
  const rows: Row[] = [];
  if (living.electricity_supply || living.electricity_usd_month != null) {
    const parts = [
      living.electricity_supply ? t(`electricitySupply.${living.electricity_supply}`) : null,
      living.generator_amps ? t("amps", { amps: living.generator_amps }) : null,
      living.electricity_usd_month != null
        ? t("electricityBill", { amount: formatUsd(living.electricity_usd_month, locale) })
        : null,
    ];
    rows.push({ icon: Zap, label: t("electricity"), value: parts.filter(Boolean).join(" · ") });
  }
  if (living.water_source || living.water_usd_month != null) {
    const parts = [
      living.water_source ? t(`waterSource.${living.water_source}`) : null,
      living.water_usd_month != null ? t("waterBill", { amount: formatUsd(living.water_usd_month, locale) }) : null,
    ];
    rows.push({ icon: Droplets, label: t("water"), value: parts.filter(Boolean).join(" · ") });
  }
  if (living.sewage) rows.push({ icon: Waves, label: t("sewage"), value: t(`sewageKind.${living.sewage}`) });
  if (living.winter_comfort)
    rows.push({ icon: Flame, label: t("winter"), value: t(`winterComfort.${living.winter_comfort}`) });
  if (living.summer_comfort)
    rows.push({ icon: Snowflake, label: t("summer"), value: t(`summerComfort.${living.summer_comfort}`) });

  const flags: { icon: typeof Zap; text: string }[] = [];
  if (living.parking_spots != null) flags.push({ icon: Car, text: t("parking", { count: living.parking_spots }) });
  if (living.solar_ready != null) flags.push({ icon: Sun, text: living.solar_ready ? t("solarReady") : t("notSolarReady") });
  if (living.elevator_backup != null)
    flags.push({ icon: Leaf, text: living.elevator_backup ? t("elevatorBackup") : t("noElevatorBackup") });

  const highlights = living.highlights ?? [];
  const thingsToKnow = living.things_to_know ?? [];
  if (!rows.length && !flags.length && !highlights.length && !thingsToKnow.length) return null;

  return (
    <section className="flex flex-col gap-3" data-testid="living-here">
      <div>
        <h2 className="font-semibold">{t("title")}</h2>
        <p className="text-xs text-muted-foreground">{t("reported")}</p>
      </div>
      {rows.length ? (
        <dl className="grid gap-2 sm:grid-cols-2">
          {rows.map(({ icon: Icon, label, value }) => (
            <div key={label} className="flex items-start gap-2 rounded-lg bg-muted px-3 py-2 text-sm">
              <Icon className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden />
              <div>
                <dt className="font-medium">{label}</dt>
                <dd className="text-muted-foreground">{value}</dd>
              </div>
            </div>
          ))}
        </dl>
      ) : null}
      {flags.length ? (
        <ul className="flex flex-wrap gap-2">
          {flags.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-1 rounded-full bg-muted px-3 py-1 text-sm">
              <Icon className="size-4 text-primary" aria-hidden />
              {text}
            </li>
          ))}
        </ul>
      ) : null}
      {/* Highlights and notes are publisher text: rendered as plain text (React escapes it). */}
      {highlights.length ? (
        <div>
          <h3 className="mb-1 flex items-center gap-1 text-sm font-semibold">
            <Sparkles className="size-4 text-primary" aria-hidden />
            {t("highlights")}
          </h3>
          <ul className="list-inside list-disc text-sm" dir="auto">
            {highlights.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </div>
      ) : null}
      {thingsToKnow.length ? (
        <div>
          <h3 className="mb-1 flex items-center gap-1 text-sm font-semibold">
            <Info className="size-4 text-primary" aria-hidden />
            {t("thingsToKnow")}
          </h3>
          <ul className="list-inside list-disc text-sm" dir="auto">
            {thingsToKnow.map((h) => (
              <li key={h}>{h}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
}

/** Staff-curated neighbourhood facts, with date and source. */
export function AreaInfo({ area }: { area: AreaProfile }) {
  const t = useTranslations("area");
  const locale = useLocale();
  const ar = locale === "ar";
  const rows: { label: string; value: string }[] = [];
  if (area.safety_score != null) rows.push({ label: t("safety"), value: t("score", { score: area.safety_score }) });
  if (area.quiet_score != null) rows.push({ label: t("quiet"), value: t("score", { score: area.quiet_score }) });
  if (area.garbage_collection)
    rows.push({ label: t("garbage"), value: t(`garbageKind.${area.garbage_collection}`) });
  if (area.flood_risk) rows.push({ label: t("flood"), value: t(`floodKind.${area.flood_risk}`) });
  const summary = ar ? area.summary_ar || area.summary_en : area.summary_en || area.summary_ar;
  const noise = ar ? area.noise_notes_ar || area.noise_notes_en : area.noise_notes_en || area.noise_notes_ar;

  return (
    <section className="flex flex-col gap-3" data-testid="area-info">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="flex items-center gap-1 font-semibold">
          <ShieldCheck className="size-5 text-primary" aria-hidden />
          {t("title")} · {ar ? area.location_name_ar : area.location_name_en}
        </h2>
        {area.is_demo ? <Badge tone="demo">{t("demo")}</Badge> : null}
      </div>
      <p className="text-xs text-muted-foreground">{t("curated", { date: formatDate(area.updated_at, locale) })}</p>
      {summary ? (
        <p className="text-sm leading-relaxed" dir="auto">
          {summary}
        </p>
      ) : null}
      {rows.length ? (
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {rows.map((r) => (
            <div key={r.label} className="rounded-lg bg-muted px-3 py-2 text-sm">
              <dt className="text-muted-foreground">{r.label}</dt>
              <dd className="font-semibold">{r.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {area.theft_reports_12m != null ? <p className="text-sm">{t("thefts", { count: area.theft_reports_12m })}</p> : null}
      {noise ? (
        <p className="text-sm" dir="auto">
          <span className="font-medium">{t("noise")}: </span>
          {noise}
        </p>
      ) : null}
      {area.source_note ? (
        <p className="text-xs text-muted-foreground">{t("source", { source: area.source_note })}</p>
      ) : null}
    </section>
  );
}
