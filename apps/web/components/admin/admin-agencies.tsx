"use client";

import { BadgeCheck } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { AdminAgency } from "@2ajar/contracts";
import { api, ApiError } from "@/lib/api-client";
import { Button } from "../ui/button";
import { Alert, Badge, Card } from "../ui/card";

/** Staff check an agency's identity off-platform, then switch on its badge here. Unverified agencies come first. */
export function AdminAgencies() {
  const t = useTranslations("adminAgencies");
  const locale = useLocale();
  const [rows, setRows] = useState<AdminAgency[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setRows(await api<AdminAgency[]>("/admin/agencies"));
  }, []);

  useEffect(() => {
    load().catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [load]);

  async function toggle(a: AdminAgency) {
    setBusy(a.id);
    setError(null);
    try {
      const saved = await api<AdminAgency>(`/admin/agencies/${a.id}`, {
        method: "PATCH",
        json: { is_verified: !a.is_verified },
      });
      setRows((prev) => prev?.map((x) => (x.id === saved.id ? saved : x)) ?? null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-3" data-testid="admin-agencies">
      <p className="text-sm text-muted-foreground">{t("intro")}</p>
      {error ? <Alert tone="error">{error}</Alert> : null}
      <Card className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border text-muted-foreground">
              <th className="px-3 py-2 text-start font-medium">{t("name")}</th>
              <th className="px-3 py-2 text-start font-medium">{t("members")}</th>
              <th className="px-3 py-2 text-start font-medium">{t("live")}</th>
              <th className="px-3 py-2 text-start font-medium">{t("verified")}</th>
              <th className="px-3 py-2" />
            </tr>
          </thead>
          <tbody>
            {(rows ?? []).map((a) => (
              <tr key={a.id} className="border-b border-border last:border-0" data-testid="agency-row">
                <td className="px-3 py-2">
                  <a href={`/${locale}/agencies/${a.slug}`} className="font-medium underline" target="_blank" rel="noreferrer">
                    {a.name}
                  </a>
                  {a.is_demo ? (
                    <Badge tone="demo" className="ms-2">
                      {t("demo")}
                    </Badge>
                  ) : null}
                </td>
                <td className="px-3 py-2">{a.members}</td>
                <td className="px-3 py-2">{a.live_listings}</td>
                <td className="px-3 py-2">
                  {a.is_verified ? <BadgeCheck className="size-5 text-primary" aria-label={t("verified")} /> : "–"}
                </td>
                <td className="px-3 py-2 text-end">
                  <Button
                    size="sm"
                    variant={a.is_verified ? "outline" : "default"}
                    disabled={busy === a.id}
                    onClick={() => toggle(a)}
                    data-testid="agency-toggle"
                  >
                    {a.is_verified ? t("unverify") : t("verify")}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
