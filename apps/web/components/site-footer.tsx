import { useTranslations } from "next-intl";

/** Airbnb-style light footer with link columns. */
export function SiteFooter({ locale }: { locale: string }) {
  const t = useTranslations("footer");
  const nav = useTranslations("nav");
  const cols: { title: string; links: [string, string][] }[] = [
    { title: t("support"), links: [[nav("tickets"), "/tickets"], [t("howSearch"), "/ask"]] },
    { title: t("renting"), links: [[t("listProperty"), "/register"], [t("importCsv"), "/dashboard/import"]] },
    { title: t("company"), links: [[nav("explore"), "/listings"], [nav("saved"), "/saved"]] },
  ];
  return (
    <footer className="mt-16 border-t border-border bg-muted pb-20 md:pb-0">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 sm:grid-cols-3 sm:px-6">
        {cols.map((c) => (
          <div key={c.title} className="flex flex-col gap-3 text-sm">
            <h2 className="font-semibold">{c.title}</h2>
            {c.links.map(([label, href]) => (
              <a key={href} href={`/${locale}${href}`} className="hover:underline">
                {label}
              </a>
            ))}
          </div>
        ))}
      </div>
      <div className="mx-auto flex max-w-7xl flex-col gap-1 border-t border-border px-4 py-6 text-sm text-muted-foreground sm:flex-row sm:justify-between sm:px-6">
        <span>{t("rights", { year: new Date().getFullYear() })}</span>
        <span>{t("tagline")}</span>
      </div>
    </footer>
  );
}
