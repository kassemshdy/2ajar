"use client";

import { ArrowRight, ChevronLeft, ChevronRight } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef } from "react";

/** A titled, horizontally scrolling row (swipe on phones, arrow buttons on desktop). Hidden when empty. */
export function Row({
  title,
  subtitle,
  href,
  children,
  testId,
}: {
  title: string;
  subtitle?: string;
  href?: string;
  children: React.ReactNode[];
  testId?: string;
}) {
  const t = useTranslations("discover");
  const scroller = useRef<HTMLDivElement>(null);
  if (!children.length) return null;

  const scroll = (direction: 1 | -1) => {
    const el = scroller.current;
    if (!el) return;
    // In RTL the scroll axis is mirrored, so "next" moves towards negative scrollLeft.
    const rtl = getComputedStyle(el).direction === "rtl";
    el.scrollBy({ left: direction * (rtl ? -1 : 1) * el.clientWidth * 0.9, behavior: "smooth" });
  };

  return (
    <section className="flex flex-col gap-3" data-testid={testId}>
      <div className="flex items-end justify-between gap-3">
        <div className="min-w-0">
          <h2 className="flex items-center gap-2 text-[22px] font-semibold tracking-tight">
            {href ? (
              <a href={href} className="group/title flex items-center gap-2 hover:underline">
                {title}
                <span className="flex size-7 items-center justify-center rounded-full bg-muted transition group-hover/title:bg-border">
                  <ArrowRight className="size-4 rtl:rotate-180" aria-hidden />
                  <span className="sr-only">{t("seeAll")}</span>
                </span>
              </a>
            ) : (
              title
            )}
          </h2>
          {subtitle ? <p className="text-muted-foreground">{subtitle}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <div className="hidden gap-1 sm:flex">
            <button
              type="button"
              onClick={() => scroll(-1)}
              aria-label={t("scrollPrev")}
              className="rounded-full bg-muted p-2 transition hover:bg-border"
            >
              <ChevronLeft className="size-4 rtl:rotate-180" aria-hidden />
            </button>
            <button
              type="button"
              onClick={() => scroll(1)}
              aria-label={t("scrollNext")}
              className="rounded-full bg-muted p-2 transition hover:bg-border"
            >
              <ChevronRight className="size-4 rtl:rotate-180" aria-hidden />
            </button>
          </div>
        </div>
      </div>
      <div
        ref={scroller}
        className="-mx-4 flex snap-x snap-mandatory gap-4 overflow-x-auto scroll-smooth px-4 pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {children.map((child, i) => (
          <div key={i} className="w-[70%] shrink-0 snap-start sm:w-[40%] md:w-[28%] lg:w-[18.5%]">
            {child}
          </div>
        ))}
      </div>
    </section>
  );
}
