import { Search, Sparkles } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { Suggestion } from "@2ajar/contracts";
import { cn } from "@/lib/utils";
import { Button } from "../ui/button";

/** Plain-text search box. A GET form, so it works without JavaScript and answers have shareable URLs. */
export function AskBox({
  suggestions = [],
  defaultQuery = "",
  autoFocus = false,
  slim = false,
}: {
  suggestions?: Suggestion[];
  defaultQuery?: string;
  autoFocus?: boolean;
  /** One-line bar on a light background (home page under the search pill). */
  slim?: boolean;
}) {
  const t = useTranslations("ask");
  const tDiscover = useTranslations("discover");
  const locale = useLocale();
  const askHref = (q: string) => `/${locale}/ask?q=${encodeURIComponent(q)}`;

  return (
    <div className="flex flex-col gap-3" data-testid="ask-box">
      <form action={`/${locale}/ask`} method="get" role="search" className="flex flex-col gap-2 sm:flex-row">
        <label htmlFor="ask-q" className="sr-only">
          {t("label")}
        </label>
        <div className="relative flex-1">
          <Sparkles className="pointer-events-none absolute start-3 top-3 size-5 text-primary" aria-hidden />
          <textarea
            id="ask-q"
            name="q"
            required
            maxLength={300}
            rows={slim ? 1 : 2}
            dir="auto"
            autoFocus={autoFocus}
            defaultValue={defaultQuery}
            placeholder={slim ? `${tDiscover("orAsk")}: ${t("placeholder")}` : t("placeholder")}
            className={cn(
              "block w-full resize-none border border-border bg-background py-2.5 pe-3 ps-10 text-base text-foreground shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              slim ? "rounded-full py-3 placeholder:truncate" : "rounded-xl",
            )}
          />
        </div>
        <Button
          type="submit"
          variant={slim ? "outline" : "default"}
          className={cn("h-auto min-h-11 gap-2 sm:px-6", slim && "rounded-full")}
        >
          <Search className="size-4" aria-hidden />
          {t("submit")}
        </Button>
      </form>
      {suggestions.length ? (
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="opacity-80">{t("tryThese")}</span>
          {suggestions.map((s) => {
            const text = locale === "ar" ? s.text_ar : s.text_en;
            return (
              <a
                key={s.id}
                href={askHref(text)}
                className={
                  slim
                    ? "rounded-full border border-border bg-white px-3 py-1 leading-snug text-foreground hover:border-foreground"
                    : "rounded-full border border-current/30 bg-white/10 px-3 py-1 leading-snug hover:bg-white/20"
                }
                data-testid="ask-suggestion"
              >
                {text}
              </a>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
