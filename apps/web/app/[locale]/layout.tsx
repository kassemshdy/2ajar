import type { Metadata, Viewport } from "next";
import { hasLocale, NextIntlClientProvider } from "next-intl";
import { getMessages, getTranslations, setRequestLocale } from "next-intl/server";
import { notFound } from "next/navigation";
import { Header } from "@/components/header";
import { isRtl, routing } from "@/i18n/routing";
import "../globals.css";

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }));
}

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "meta" });
  return {
    title: t("title"),
    description: t("description"),
    alternates: { languages: { en: "/en", ar: "/ar" } },
  };
}

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  if (!hasLocale(routing.locales, locale)) notFound();
  setRequestLocale(locale);
  const messages = await getMessages();
  const t = await getTranslations("footer");

  return (
    <html lang={locale} dir={isRtl(locale) ? "rtl" : "ltr"}>
      <body className="min-h-screen antialiased">
        <NextIntlClientProvider locale={locale} messages={messages}>
          <Header />
          <main className="mx-auto w-full max-w-6xl px-4 py-6">{children}</main>
          <footer className="mt-12 border-t border-border py-8 text-center text-sm text-muted-foreground">
            {t("tagline")}
          </footer>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
