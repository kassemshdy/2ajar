import { setRequestLocale } from "next-intl/server";
import { LoginForm } from "@/components/auth-forms";

export default async function LoginPage({ params }: { params: Promise<{ locale: string }> }) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <LoginForm />;
}
