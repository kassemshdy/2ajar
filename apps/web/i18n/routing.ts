import { defineRouting } from "next-intl/routing";

// Arabic is the primary language: "/" always opens /ar (no browser-language guessing); English stays one click
// away via the language switch and at /en.
export const routing = defineRouting({
  locales: ["ar", "en"],
  defaultLocale: "ar",
  localeDetection: false,
});

export type Locale = (typeof routing.locales)[number];

export const isRtl = (locale: string) => locale === "ar";
