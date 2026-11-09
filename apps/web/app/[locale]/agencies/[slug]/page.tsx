import { BadgeCheck } from "lucide-react";
import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import type { AgencyPage } from "@2ajar/contracts";
import { CopyLinkButton } from "@/components/copy-link-button";
import { DemoBanner } from "@/components/demo-banner";
import { ListingTile } from "@/components/listing-tile";
import { apiGet } from "@/lib/api-server";
import { formatDate } from "@/lib/format";

export const dynamic = "force-dynamic";

const SLUG_RE = /^[a-z0-9-]{1,80}$/;

async function load(slug: string) {
  if (!SLUG_RE.test(slug)) return null;
  return apiGet<AgencyPage>(`/agencies/${slug}`);
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ locale: string; slug: string }>;
}): Promise<Metadata> {
  const { locale, slug } = await params;
  const agency = await load(slug);
  if (!agency) return {};
  const t = await getTranslations({ locale, namespace: "agency" });
  return {
    title: agency.name,
    description: t("homes", { count: agency.listings.length }),
    robots: agency.is_demo ? { index: false } : undefined,
  };
}

/** Public page for one agency: every home it currently rents out on 2ajar, shareable as a link. */
export default async function AgencyPageView({ params }: { params: Promise<{ locale: string; slug: string }> }) {
  const { locale, slug } = await params;
  setRequestLocale(locale);
  const agency = await load(slug);
  if (!agency) notFound();
  const t = await getTranslations("agency");
  const tp = await getTranslations("publisher");

  return (
    <div className="flex flex-col gap-8" data-testid="agency-page">
      <DemoBanner show={agency.is_demo} />
      <header className="flex flex-wrap items-center gap-5">
        <span className="flex size-20 items-center justify-center rounded-full bg-foreground text-3xl font-semibold text-background">
          {agency.name.trim().charAt(0).toUpperCase()}
        </span>
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <p className="text-sm text-muted-foreground">{tp("agency")}</p>
          <h1 className="flex flex-wrap items-center gap-2 text-3xl font-semibold tracking-tight">
            {agency.name}
            {agency.verified ? (
              <BadgeCheck className="size-7 text-primary" aria-label={t("verifiedLong")} data-testid="agency-verified" />
            ) : null}
          </h1>
          <p className="text-muted-foreground">
            {t("since", { date: formatDate(agency.on_2ajar_since, locale) })} · {t("members", { count: agency.members })}
          </p>
          {agency.verified ? <p className="text-sm text-primary">{t("verifiedLong")}</p> : null}
        </div>
        <CopyLinkButton label={t("share")} copiedLabel={t("copied")} />
      </header>

      <section className="flex flex-col gap-4">
        <h2 className="text-xl font-semibold">{t("homes", { count: agency.listings.length })}</h2>
        {agency.listings.length ? (
          <div className="grid grid-cols-1 gap-x-6 gap-y-8 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {agency.listings.map((l) => (
              <ListingTile key={l.id} listing={l} />
            ))}
          </div>
        ) : null}
      </section>
    </div>
  );
}
