"use client";

import { Download, FileUp } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { ImportResult } from "@2ajar/contracts";
import { Link } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api-client";
import { Button, buttonVariants } from "./ui/button";
import { Alert, Badge, Card } from "./ui/card";
import { Field, Input } from "./ui/input";

export function CsvImport() {
  const t = useTranslations("import");
  const tErr = useTranslations("errors");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function run(dryRun: boolean) {
    if (!file) return;
    setBusy(true);
    setError(null);
    try {
      const form = new FormData();
      form.append("file", file);
      setResult(await api<ImportResult>(`/listings/import?dry_run=${dryRun}`, { form }));
    } catch (e) {
      setResult(null);
      setError(e instanceof ApiError && e.status ? e.message : tErr("network"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6" data-testid="csv-import">
      <div>
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t("intro")}</p>
      </div>
      <Card className="flex flex-col gap-4 p-4">
        <a href="/api/v1/listings/import/template" className={buttonVariants({ variant: "outline" }) + " self-start"} download>
          <Download className="size-4" aria-hidden />
          {t("template")}
        </a>
        <Field label={t("file")} htmlFor="csv-file">
          <Input
            id="csv-file"
            type="file"
            accept=".csv,text/csv"
            data-testid="csv-input"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setResult(null);
            }}
          />
        </Field>
        <Button type="button" onClick={() => run(true)} disabled={!file || busy} className="self-start" data-testid="csv-preview">
          <FileUp className="size-4" aria-hidden />
          {t("preview")}
        </Button>
      </Card>

      {error ? <Alert tone="error">{error}</Alert> : null}

      {result ? (
        <Card className="flex flex-col gap-4 p-4">
          {result.dry_run ? (
            <p className="font-medium" data-testid="csv-summary">
              {t("summary", { valid: result.valid, total: result.total })}
            </p>
          ) : (
            <Alert tone="success" data-testid="csv-created">
              {t("created", { count: result.created })}
            </Alert>
          )}
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-start text-muted-foreground">
                  <th className="p-2 text-start">{t("row")}</th>
                  <th className="p-2 text-start">{t("status")}</th>
                  <th className="p-2 text-start" />
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r) => (
                  <tr key={r.row} className="border-b border-border align-top" data-testid="csv-row">
                    <td className="p-2">{r.row}</td>
                    <td className="p-2">
                      <Badge tone={r.ok ? "success" : "warning"}>{r.ok ? t("ok") : t("error")}</Badge>
                    </td>
                    <td className="p-2" dir="auto">
                      {r.title ? <p className="font-medium">{r.title}</p> : null}
                      {r.errors.map((e) => (
                        <p key={e} className="text-red-700">
                          {e}
                        </p>
                      ))}
                      {r.listing_id ? (
                        <Link href={`/dashboard/listings/${r.listing_id}/edit`} className="text-primary underline">
                          {t("openDraft")}
                        </Link>
                      ) : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {result.dry_run ? (
            result.valid > 0 ? (
              <Button type="button" onClick={() => run(false)} disabled={busy} className="self-start" data-testid="csv-confirm">
                {t("import", { count: result.valid })}
              </Button>
            ) : (
              <p className="text-muted-foreground">{t("none")}</p>
            )
          ) : null}
        </Card>
      ) : null}
    </div>
  );
}
