import { Check, HelpCircle, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { AskReason } from "@2ajar/contracts";
import { cn } from "@/lib/utils";

const ICONS = { match: Check, miss: X, unknown: HelpCircle } as const;
const TONES = {
  match: "text-emerald-700",
  miss: "text-red-700",
  unknown: "text-muted-foreground",
} as const;
const SOURCE_KEY = { filter: "sourceFilter", listing: "sourceListing", area: "sourceArea" } as const;

/** Why a result was ranked where it is. Every line states its status and where the fact came from. */
export function ReasonList({ reasons }: { reasons: AskReason[] }) {
  const t = useTranslations("ask");
  const locale = useLocale();
  if (!reasons.length) return null;
  return (
    <ul className="flex flex-col gap-1 text-sm" aria-label={t("why")} data-testid="reasons">
      {reasons.map((r) => {
        const Icon = ICONS[r.status];
        return (
          <li key={r.key} className="flex items-start gap-2" data-status={r.status}>
            <Icon className={cn("mt-0.5 size-4 shrink-0", TONES[r.status])} aria-hidden />
            <span>
              <span className="font-medium">{locale === "ar" ? r.label_ar : r.label_en}</span>
              <span className="sr-only"> — {t(r.status)}</span>
              {r.status === "unknown" ? <span className="text-muted-foreground"> · {t("unknown")}</span> : null}
              <span className="block text-xs text-muted-foreground">{t(SOURCE_KEY[r.source])}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
