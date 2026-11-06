import { getTranslations } from "next-intl/server";
import { Alert } from "./ui/card";

export async function DemoBanner({ show }: { show: boolean }) {
  if (!show) return null;
  const t = await getTranslations("demo");
  return (
    <Alert tone="warning" className="mb-4" data-testid="demo-banner">
      {t("banner")}
    </Alert>
  );
}
