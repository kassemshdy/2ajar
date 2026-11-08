import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import type { AskResponse } from "@2ajar/contracts";
import { AskBox } from "@/components/ask/ask-box";
import { ReasonList } from "@/components/ask/reason-list";
import { Understood } from "@/components/ask/understood";
import { DemoBanner } from "@/components/demo-banner";
import { ListingCard } from "@/components/listing-card";
import { Alert, Card } from "@/components/ui/card";
import { apiPost, getPublicConfig, getSuggestions } from "@/lib/api-server";

export const dynamic = "force-dynamic";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "ask" });
  // Answers depend on free text: keep them out of search engines.
  return { title: t("title"), robots: { index: false } };
}

export default async function AskPage({
  params,
  searchParams,
}: {
  params: Promise<{ locale: string }>;
  searchParams: Promise<{ q?: string | string[] }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const raw = (await searchParams).q;
  const query = (Array.isArray(raw) ? raw[0] : (raw ?? "")).trim().slice(0, 300);
  const t = await getTranslations("ask");
  const [config, suggestions] = await Promise.all([getPublicConfig(), getSuggestions()]);

  let answer: AskResponse | null = null;
  let failed = false;
  if (query) {
    try {
      answer = await apiPost<AskResponse>("/search/ask", { query, locale: locale === "ar" ? "ar" : "en" });
    } catch {
      failed = true;
    }
  }

  return (
    <div className="flex flex-col gap-6" data-testid="ask-page">
      <DemoBanner show={config.demo_mode} />
      <h1 className="text-2xl font-bold">{t("title")}</h1>
      <Card className="p-4">
        <AskBox defaultQuery={query} suggestions={query ? [] : (suggestions ?? [])} autoFocus={!query} />
      </Card>

      {failed ? <Alert tone="error">{t("error")}</Alert> : null}

      {answer ? (
        <>
          <Card className="p-4">
            <Understood answer={answer} />
          </Card>
          <section className="flex flex-col gap-4">
            <h2 className="text-xl font-semibold" data-testid="ask-count">
              {t("results", { count: answer.total })}
              {answer.total > answer.results.length && answer.results.length ? (
                <span className="ms-2 text-sm font-normal text-muted-foreground">
                  {t("showing", { shown: answer.results.length, total: answer.total })}
                </span>
              ) : null}
            </h2>
            {answer.results.length ? (
              <ol className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {answer.results.map((hit) => (
                  <li key={hit.listing.id} className="flex flex-col gap-3" data-testid="ask-result">
                    <ListingCard listing={hit.listing} />
                    <ReasonList reasons={hit.reasons} />
                  </li>
                ))}
              </ol>
            ) : (
              <p className="text-muted-foreground">{t("noResults")}</p>
            )}
            <p className="text-xs text-muted-foreground">{t("howItWorks")}</p>
          </section>
        </>
      ) : null}
    </div>
  );
}
