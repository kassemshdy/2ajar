import {
  Baby, Clock, Dog, Mountain, Sofa, Sparkles, Sun, Tent, Umbrella, Waves, Zap, type LucideIcon,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";

/** Airbnb-style icon strip. Each category is a plain-language smart search, so it needs no extra filters. */
// Apartments by the month first (2ajar's core), then short stays.
export const CATEGORIES: { key: string; icon: LucideIcon }[] = [
  { key: "furnished", icon: Sofa },
  { key: "family", icon: Baby },
  { key: "power", icon: Zap },
  { key: "solar", icon: Sun },
  { key: "beach", icon: Umbrella },
  { key: "mountain", icon: Mountain },
  { key: "pets", icon: Dog },
  { key: "pool", icon: Waves },
  { key: "chalets", icon: Tent },
  { key: "weekend", icon: Sparkles },
  { key: "hourly", icon: Clock },
];

export function CategoryBar() {
  const t = useTranslations("discover");
  const locale = useLocale();
  return (
    <nav aria-label={t("categories")} className="-mx-4 overflow-x-auto px-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
      <ul className="flex gap-6 sm:justify-center sm:gap-9">
        {CATEGORIES.map(({ key, icon: Icon }) => (
          <li key={key} className="shrink-0">
            <a
              href={`/${locale}/ask?q=${encodeURIComponent(t(`q.${key}`))}`}
              className="flex flex-col items-center gap-1.5 border-b-2 border-transparent pb-2 text-xs font-medium text-muted-foreground transition hover:border-border hover:text-foreground"
              data-testid="category"
            >
              <Icon className="size-6" strokeWidth={1.5} aria-hidden />
              <span className="whitespace-nowrap">{t(`cat.${key}`)}</span>
            </a>
          </li>
        ))}
      </ul>
    </nav>
  );
}
