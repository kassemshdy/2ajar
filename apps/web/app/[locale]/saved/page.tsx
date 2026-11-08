import type { Metadata } from "next";
import { getTranslations, setRequestLocale } from "next-intl/server";
import { SavedListings } from "@/components/saved-listings";

export async function generateMetadata({ params }: { params: Promise<{ locale: string }> }): Promise<Metadata> {
  const { locale } = await params;
  const t = await getTranslations({ locale, namespace: "saved" });
  return { title: t("title"), robots: { index: false } };
}

export default async function SavedPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("saved");
  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-3xl font-semibold tracking-tight">{t("title")}</h1>
      <SavedListings />
    </div>
  );
}
