import { setRequestLocale } from "next-intl/server";
import { RegisterForm } from "@/components/auth-forms";

export default async function RegisterPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <RegisterForm locale={locale} />;
}
