import { setRequestLocale } from "next-intl/server";
import { CsvImport } from "@/components/csv-import";

export default async function ImportPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <CsvImport />;
}
