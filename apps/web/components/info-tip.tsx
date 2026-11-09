"use client";

import { Info, X } from "lucide-react";
import { useTranslations } from "next-intl";
import { useEffect, useId, useRef, useState } from "react";
import { cn } from "@/lib/utils";

export type GlossaryKey =
  | "valueEquation"
  | "dream"
  | "likelihood"
  | "time"
  | "effort"
  | "northStar"
  | "coreFour"
  | "warm"
  | "cold"
  | "content"
  | "paidAds"
  | "leads"
  | "rule100"
  | "moreBetterNew"
  | "leadMagnet"
  | "grandSlam"
  | "dontScale"
  | "funnel"
  | "playbook"
  | "canvas";

/**
 * Small ⓘ button that opens a plain-language explanation of a growth term (Hormozi vocabulary).
 * Click or Enter toggles it; Escape or a click outside closes it.
 */
export function InfoTip({ term, className }: { term: GlossaryKey; className?: string }) {
  const t = useTranslations("glossary");
  const ti = useTranslations("info");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span ref={ref} className={cn("relative inline-flex align-middle", className)}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={id}
        aria-label={`${ti("open")} ${t(`${term}.t`)}`}
        className="inline-flex size-5 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground"
        data-testid={`info-${term}`}
      >
        <Info className="size-4" aria-hidden />
      </button>
      {open ? (
        <span
          id={id}
          role="dialog"
          aria-label={t(`${term}.t`)}
          className="absolute start-0 top-6 z-30 flex w-72 max-w-[80vw] flex-col gap-1 rounded-xl border border-border bg-card p-3 text-start text-sm font-normal text-foreground shadow-lg"
        >
          <span className="flex items-start justify-between gap-2">
            <span className="font-semibold">{t(`${term}.t`)}</span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label={ti("close")}
              className="text-muted-foreground hover:text-foreground"
            >
              <X className="size-4" aria-hidden />
            </button>
          </span>
          <span className="leading-relaxed text-muted-foreground">{t(`${term}.d`)}</span>
        </span>
      ) : null}
    </span>
  );
}
