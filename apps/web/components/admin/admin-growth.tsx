"use client";

import { CheckCircle2, Circle, Gauge, Lightbulb, Map, Rocket, Target, TrendingUp } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { GrowthDashboard } from "@2ajar/contracts";
import { api, ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";
import { Alert, Badge, Card } from "../ui/card";
import { Input } from "../ui/input";
import { InfoTip, type GlossaryKey } from "../info-tip";

type Tab = "dashboard" | "steps" | "playbook" | "business";
type Factor = GrowthDashboard["renters"]["factors"][number];

const pct = (x: number | null | undefined) => (x == null ? null : `${Math.round(x * 100)}%`);
const LEVER_TERM: Record<string, GlossaryKey> = {
  dream: "dream",
  likelihood: "likelihood",
  time: "time",
  effort: "effort",
  leads: "leads",
};
const CHANNEL_TERM: Record<string, GlossaryKey> = {
  warm_cold_outreach: "coreFour",
  warm_outreach: "warm",
  cold_outreach: "cold",
  content: "content",
  paid_ads: "paidAds",
};
const STEP_TERM: Record<string, GlossaryKey> = {
  offer_defined: "grandSlam",
  warm_list_100: "warm",
  daily_outreach: "rule100",
  lead_magnet: "leadMagnet",
  double_best_channel: "moreBetterNew",
  paid_ads: "paidAds",
  daily_content: "content",
};
const PHASE_TERM: Record<number, GlossaryKey> = { 1: "dontScale", 2: "coreFour", 3: "moreBetterNew" };
const usd = (n: number) => `$${Math.round(n).toLocaleString("en-US")}`;

function Bar({ value, tone = "primary" }: { value: number | null | undefined; tone?: "primary" | "warn" }) {
  const v = Math.max(0, Math.min(1, value ?? 0));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-muted" role="presentation">
      <div
        className={cn("h-full rounded-full", tone === "warn" ? "bg-amber-500" : "bg-primary")}
        style={{ width: `${v * 100}%` }}
      />
    </div>
  );
}

/**
 * Admin → Growth: Hormozi's value equation and the marketing playbook measured on 2ajar's data, data-driven next
 * steps, and the business model (canvas, revenue streams, revenue calculator).
 */
export function AdminGrowth() {
  const t = useTranslations("growth");
  const locale = useLocale();
  const ar = locale === "ar";
  const [data, setData] = useState<GrowthDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("dashboard");

  const load = useCallback(async () => {
    try {
      setData(await api<GrowthDashboard>("/admin/growth"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "error");
    }
  }, []);
  useEffect(() => {
    load();
  }, [load]);

  if (error) return <Alert tone="error">{error}</Alert>;
  if (!data) return null;
  const m = data.metrics;

  const tabs: { key: Tab; icon: typeof Gauge }[] = [
    { key: "dashboard", icon: Gauge },
    { key: "steps", icon: Lightbulb },
    { key: "playbook", icon: Rocket },
    { key: "business", icon: Map },
  ];

  return (
    <div className="flex flex-col gap-5" data-testid="admin-growth">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm text-muted-foreground">{t("updated", { date: formatDate(data.generated_at, locale) })}</p>
        <div className="flex flex-wrap gap-1 rounded-full bg-muted p-1 text-sm" role="tablist">
          {tabs.map(({ key, icon: Icon }) => (
            <button
              key={key}
              type="button"
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={cn(
                "flex items-center gap-1.5 rounded-full px-3 py-1.5 font-medium",
                tab === key ? "bg-background shadow-sm" : "text-muted-foreground",
              )}
            >
              <Icon className="size-4" aria-hidden />
              {t(`tabs.${key}`)}
            </button>
          ))}
        </div>
      </div>
      {data.demo_mode ? <Alert tone="warning">{t("demoNote")}</Alert> : null}

      {tab === "dashboard" ? <Dashboard data={data} /> : null}
      {tab === "steps" ? <Steps data={data} ar={ar} /> : null}
      {tab === "playbook" ? <Playbook data={data} onChange={load} /> : null}
      {tab === "business" ? <Business metrics={m} targets={data.targets} /> : null}
    </div>
  );
}

function Dashboard({ data }: { data: GrowthDashboard }) {
  const t = useTranslations("growth");
  const locale = useLocale();
  const ar = locale === "ar";
  const m = data.metrics;
  const noData = <span className="text-muted-foreground">{t("noData")}</span>;
  const fmt = (key: string, v: number | null | undefined) =>
    v == null ? null : key === "conversion" || key === "retention_60d" ? pct(v) : String(v);

  const scoreboard = Object.entries(data.targets).map(([key, target]) => {
    const v = m[key] as number | null | undefined;
    return { key, v, target };
  });

  return (
    <div className="flex flex-col gap-5">
      <Card className="flex flex-col gap-3 p-5" data-testid="north-star">
        <div className="flex items-center gap-2 text-primary">
          <Target className="size-5" aria-hidden />
          <h2 className="font-semibold">{t("northStar")}</h2>
          <InfoTip term="northStar" />
        </div>
        <p className="text-4xl font-bold">{m.weekly_inquiries ?? 0}</p>
        <p className="text-sm text-muted-foreground">{t("northStarHint")}</p>
        <Bar value={(m.weekly_inquiries ?? 0) / data.targets.weekly_inquiries.day30} />
        <p className="text-xs text-muted-foreground">
          {t("target30", { n: data.targets.weekly_inquiries.day30 })} · {t("target90", { n: data.targets.weekly_inquiries.day90 })}
        </p>
      </Card>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">{t("scoreboard")}</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" data-testid="scoreboard">
          {scoreboard.map(({ key, v, target }) => (
            <Card key={key} className="flex flex-col gap-2 p-4">
              <p className="text-sm text-muted-foreground">{t(`metric.${key}`)}</p>
              <p className="text-2xl font-semibold">{fmt(key, v) ?? noData}</p>
              <Bar value={v == null ? 0 : v / target.day30} tone={v != null && v >= target.day30 ? "primary" : "warn"} />
              <p className="text-xs text-muted-foreground">
                {t("target30", { n: fmt(key, target.day30) ?? "" })} · {t("target90", { n: fmt(key, target.day90) ?? "" })}
              </p>
            </Card>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="flex items-center gap-1 text-lg font-semibold">
            {t("valueEq")} <InfoTip term="valueEquation" />
          </h2>
          <p className="font-medium text-primary">{t("valueEqFormula")}</p>
          <p className="text-sm text-muted-foreground">{t("valueEqHint")}</p>
        </div>
        <div className="grid gap-3 lg:grid-cols-2">
          {(["renters", "owners"] as const).map((side) => (
            <Card key={side} className="flex flex-col gap-3 p-4" data-testid={`value-${side}`}>
              <div className="flex items-baseline justify-between">
                <h3 className="font-semibold">{t(side)}</h3>
                <p className="text-sm">
                  {t("index")}: <span className="text-xl font-bold">{data[side].index ?? "–"}</span>
                  <span className="text-muted-foreground"> / 100</span>
                </p>
              </div>
              {data[side].factors.map((f: Factor) => (
                <div key={f.key} className="flex flex-col gap-1">
                  <div className="flex items-baseline justify-between gap-2 text-sm">
                    <span className="flex items-center gap-1 font-medium">
                      {t(`factor.${f.key}`)}
                      {LEVER_TERM[f.key] ? <InfoTip term={LEVER_TERM[f.key]} /> : null}
                    </span>
                    <span className="font-semibold">{f.score == null ? t("noData") : f.value}</span>
                  </div>
                  <Bar value={f.score} tone={f.score != null && f.score < 0.5 ? "warn" : "primary"} />
                  <p className="text-xs text-muted-foreground">{t(`factorMetric.${f.metric}`)}</p>
                </div>
              ))}
            </Card>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="flex items-center gap-1 text-lg font-semibold">
          {t("funnel")} <InfoTip term="funnel" />
        </h2>
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4" data-testid="funnel">
          {(["searches", "visitors", "views", "inquiries"] as const).map((k) => {
            const v = data.funnel[k];
            // Only ratios that mean something: visitors per search, inquiries per listing view.
            const base = { searches: null, visitors: data.funnel.searches, views: null, inquiries: data.funnel.views }[k];
            const prev = base || null;
            return (
              <Card key={k} className="p-4">
                <p className="text-sm text-muted-foreground">{t(`funnelStep.${k}`)}</p>
                <p className="text-2xl font-semibold">{v}</p>
                {prev ? <p className="text-xs text-muted-foreground">{pct(v / prev)}</p> : null}
              </Card>
            );
          })}
        </div>
      </section>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-semibold">{t("gaps")}</h2>
        <p className="text-sm text-muted-foreground">{t("gapsHint")}</p>
        {data.area_gaps.length ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm" data-testid="area-gaps">
              <thead>
                <tr className="border-b border-border text-start text-muted-foreground">
                  {(["area", "searches", "zero", "live", "facts"] as const).map((c) => (
                    <th key={c} className="px-2 py-2 text-start font-medium">
                      {t(`gapCols.${c}`)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.area_gaps.map((g) => (
                  <tr key={g.slug} className="border-b border-border">
                    <td className="px-2 py-2 font-medium">{ar ? g.name_ar : g.name_en}</td>
                    <td className="px-2 py-2">{g.searches}</td>
                    <td className={cn("px-2 py-2", g.zero_results ? "font-semibold text-red-700" : "")}>{g.zero_results}</td>
                    <td className={cn("px-2 py-2", g.live_listings < 5 ? "font-semibold text-amber-700" : "")}>{g.live_listings}</td>
                    <td className="px-2 py-2">{g.has_area_facts ? "✓" : "✗"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{t("noData")}</p>
        )}
      </section>

      <div className="grid gap-3 lg:grid-cols-2">
        <Card className="flex flex-col gap-2 p-4" data-testid="wishes">
          <h2 className="font-semibold">{t("wishes")}</h2>
          <p className="text-xs text-muted-foreground">{t("wishesHint")}</p>
          {data.wishes.length ? (
            data.wishes.map((w) => (
              <div key={w.key} className="flex flex-col gap-1">
                <div className="flex justify-between text-sm">
                  <span>
                    {t(`wish.${w.key}`)} <span className="text-muted-foreground">×{w.searches}</span>
                  </span>
                  <span className="text-muted-foreground">
                    {w.data_coverage == null ? t("amenityWish") : t("coverage", { pct: pct(w.data_coverage) ?? "" })}
                  </span>
                </div>
                {w.data_coverage != null ? (
                  <Bar value={w.data_coverage} tone={w.data_coverage < 0.5 ? "warn" : "primary"} />
                ) : null}
              </div>
            ))
          ) : (
            <p className="text-sm text-muted-foreground">{t("noData")}</p>
          )}
        </Card>
        <Card className="flex flex-col gap-2 p-4">
          <h2 className="font-semibold">{t("quiet")}</h2>
          {data.quiet_listings.length ? (
            <ul className="flex flex-col gap-1 text-sm">
              {data.quiet_listings.map((q) => (
                <li key={q.id} className="flex justify-between gap-2">
                  <a href={`/${locale}/listings/${q.id}`} className="truncate text-primary hover:underline" dir="auto">
                    {q.title}
                  </a>
                  <span className="shrink-0 text-muted-foreground">{t("visitors", { n: q.visitors })}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-muted-foreground">{t("noData")}</p>
          )}
          {data.property_types.length ? (
            <>
              <h2 className="mt-2 font-semibold">{t("types")}</h2>
              <p className="text-sm text-muted-foreground">
                {data.property_types.map((p) => `${p.key} ×${p.searches}`).join(" · ")}
              </p>
            </>
          ) : null}
        </Card>
      </div>
    </div>
  );
}

function Steps({ data, ar }: { data: GrowthDashboard; ar: boolean }) {
  const t = useTranslations("growth");
  const params = (p: Record<string, unknown>) => {
    const out: Record<string, string | number> = {};
    for (const [k, v] of Object.entries(p)) {
      if (k.endsWith("_en") || k.endsWith("_ar")) continue;
      out[k] = Array.isArray(v) ? v.map((w) => t(`wish.${w}`)).join(ar ? "، " : ", ") : (v as string | number);
    }
    out.areas = String((ar ? p.areas_ar : p.areas_en) ?? "") || "–";
    return out;
  };
  if (!data.recommendations.length) return <p className="text-muted-foreground">{t("noSteps")}</p>;
  return (
    <div className="flex flex-col gap-3" data-testid="recommendations">
      <p className="text-sm text-muted-foreground">{t("stepsHint")}</p>
      {data.recommendations.map((r) => {
        const p = params(r.params);
        return (
          <Card key={r.key} className="flex gap-3 p-4" data-priority={r.priority}>
            <TrendingUp className={cn("mt-0.5 size-5 shrink-0", r.priority === 1 ? "text-red-600" : "text-primary")} aria-hidden />
            <div className="flex flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone={r.priority === 1 ? "warning" : "muted"}>{t("priority", { n: r.priority })}</Badge>
                <Badge>{t(`lever.${r.lever}`)}</Badge>
                {LEVER_TERM[r.lever] ? <InfoTip term={LEVER_TERM[r.lever]} /> : null}
                {r.channel ? <Badge tone="muted">{t(`channel.${r.channel}`)}</Badge> : null}
                {r.channel && CHANNEL_TERM[r.channel] ? <InfoTip term={CHANNEL_TERM[r.channel]} /> : null}
              </div>
              <h3 className="font-semibold">{t(`rec.${r.key}.t`, p)}</h3>
              <p className="text-sm text-muted-foreground">{t(`rec.${r.key}.d`, p)}</p>
            </div>
          </Card>
        );
      })}
    </div>
  );
}

function Playbook({ data, onChange }: { data: GrowthDashboard; onChange: () => Promise<void> }) {
  const t = useTranslations("growth");
  const [busy, setBusy] = useState<string | null>(null);
  async function toggle(key: string, done: boolean) {
    setBusy(key);
    try {
      await api(`/admin/growth/tasks/${key}`, { method: "PUT", json: { done } });
      await onChange();
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className="flex flex-col gap-4" data-testid="playbook">
      <p className="flex items-center gap-1 text-sm text-muted-foreground">
        {t("playbookHint")} <InfoTip term="playbook" />
      </p>
      {[1, 2, 3].map((phase) => {
        const items = data.playbook.filter((x) => x.phase === phase);
        const done = items.filter((x) => x.done).length;
        return (
          <Card key={phase} className="flex flex-col gap-2 p-4">
            <div className="flex items-center justify-between gap-2">
              <h2 className="flex items-center gap-1 font-semibold">
                {t(`phase.${phase}`)} <InfoTip term={PHASE_TERM[phase]} />
              </h2>
              <span className="text-sm text-muted-foreground">
                {done} / {items.length}
              </span>
            </div>
            <Bar value={done / items.length} />
            <ul className="flex flex-col gap-1">
              {items.map((x) => (
                <li key={x.key} className="flex items-center gap-2 text-sm">
                  {x.auto ? (
                    x.done ? (
                      <CheckCircle2 className="size-5 text-primary" aria-label={t("auto")} />
                    ) : (
                      <Circle className="size-5 text-muted-foreground" aria-label={t("auto")} />
                    )
                  ) : (
                    <input
                      type="checkbox"
                      className="size-4"
                      checked={x.done}
                      disabled={busy === x.key}
                      onChange={(e) => toggle(x.key, e.target.checked)}
                      aria-label={t(`step.${x.key}`)}
                      data-testid={`step-${x.key}`}
                    />
                  )}
                  <span className={cn(x.done && "text-muted-foreground line-through")}>{t(`step.${x.key}`)}</span>
                  {STEP_TERM[x.key] ? <InfoTip term={STEP_TERM[x.key]} /> : null}
                  {x.auto && x.target != null ? (
                    <span className="ms-auto text-xs text-muted-foreground">
                      {t("auto")} · {t("of", { current: x.current ?? 0, target: x.target })}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          </Card>
        );
      })}
    </div>
  );
}

const BLOCKS = ["partners", "activities", "value", "relationships", "segments", "resources", "channels", "costs", "revenue"] as const;

function Business({ metrics, targets }: { metrics: GrowthDashboard["metrics"]; targets: GrowthDashboard["targets"] }) {
  const t = useTranslations("growth.bm");
  const [a, setA] = useState({ proPrice: 15, proAdoption: 30, boostPrice: 5, boostShare: 10, referralFee: 20, closeRate: 5 });
  const today = {
    publishers: Number(metrics.active_publishers ?? 0),
    listings: Number(metrics.live_listings ?? 0),
    inquiries: Number(metrics.weekly_inquiries ?? 0),
  };
  const day90 = {
    publishers: targets.active_publishers.day90,
    listings: targets.live_listings.day90,
    inquiries: targets.weekly_inquiries.day90,
  };
  const revenue = useMemo(() => {
    const calc = (b: typeof today) => {
      const pro = b.publishers * (a.proAdoption / 100) * a.proPrice;
      const boost = b.listings * (a.boostShare / 100) * a.boostPrice * 4.33;
      const referral = b.inquiries * 4.33 * (a.closeRate / 100) * a.referralFee;
      return { pro, boost, referral, total: pro + boost + referral };
    };
    return { today: calc(today), day90: calc(day90) };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [a, today.publishers, today.listings, today.inquiries]);

  const streams = t.raw("streams") as { t: string; d: string; p: string; when: string }[];

  return (
    <div className="flex flex-col gap-6" data-testid="business-model">
      <section className="flex flex-col gap-3">
        <div>
          <h2 className="flex items-center gap-1 text-lg font-semibold">
            {t("canvas")} <InfoTip term="canvas" />
          </h2>
          <p className="text-sm text-muted-foreground">{t("canvasHint")}</p>
        </div>
        <div className="grid gap-2 md:grid-cols-5 md:grid-rows-[auto_auto_auto]" data-testid="canvas">
          {BLOCKS.map((b) => (
            <Card
              key={b}
              className={cn(
                "flex flex-col gap-1 p-3 text-sm",
                b === "partners" && "md:row-span-2",
                b === "value" && "md:row-span-2 border-primary",
                b === "segments" && "md:row-span-2",
                b === "costs" && "md:col-span-2",
                b === "revenue" && "md:col-span-3",
              )}
            >
              <h3 className="font-semibold text-primary">{t(`blocks.${b}.t`)}</h3>
              <ul className="list-disc ps-4">
                {(t.raw(`blocks.${b}.i`) as string[]).map((i) => (
                  <li key={i}>{i}</li>
                ))}
              </ul>
            </Card>
          ))}
        </div>
      </section>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("money")}</h2>
          <p className="text-sm text-muted-foreground">{t("moneyHint")}</p>
        </div>
        <div className="grid gap-3 md:grid-cols-2" data-testid="revenue-streams">
          {streams.map((s) => (
            <Card key={s.t} className="flex flex-col gap-1 p-4">
              <h3 className="font-semibold">{s.t}</h3>
              <p className="text-sm">{s.d}</p>
              <p className="text-sm font-medium text-primary">{s.p}</p>
              <p className="text-xs text-muted-foreground">{s.when}</p>
            </Card>
          ))}
        </div>
        <Alert tone="warning">{t("avoid")}</Alert>
        <Alert tone="info">{t("payments")}</Alert>
      </section>

      <section className="flex flex-col gap-3">
        <div>
          <h2 className="text-lg font-semibold">{t("sim")}</h2>
          <p className="text-sm text-muted-foreground">{t("simHint")}</p>
        </div>
        <div className="grid gap-3 sm:grid-cols-3">
          {(Object.keys(a) as (keyof typeof a)[]).map((k) => (
            <label key={k} className="flex flex-col gap-1 text-sm">
              <span className="font-medium">{t(`simInputs.${k}`)}</span>
              <Input
                type="number"
                min={0}
                value={a[k]}
                onChange={(e) => setA({ ...a, [k]: Number(e.target.value) || 0 })}
                data-testid={`sim-${k}`}
              />
            </label>
          ))}
        </div>
        <table className="w-full text-sm" data-testid="revenue-sim">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="px-2 py-2 text-start font-medium">{t("simCols.stream")}</th>
              <th className="px-2 py-2 text-start font-medium">{t("simCols.today")}</th>
              <th className="px-2 py-2 text-start font-medium">{t("simCols.day90")}</th>
            </tr>
          </thead>
          <tbody>
            {(["pro", "boost", "referral", "total"] as const).map((r) => (
              <tr key={r} className={cn("border-b border-border", r === "total" && "font-semibold")}>
                <td className="px-2 py-2">{t(`simRows.${r}`)}</td>
                <td className="px-2 py-2" data-testid={`sim-today-${r}`}>{usd(revenue.today[r])}</td>
                <td className="px-2 py-2">{usd(revenue.day90[r])}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="text-xs text-muted-foreground">
          {t("simNote", { publishers: today.publishers, listings: today.listings, inquiries: today.inquiries })}
        </p>
      </section>
    </div>
  );
}
