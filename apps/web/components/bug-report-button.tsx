"use client";

import { Bug, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { Ticket, TicketCategory } from "@2ajar/contracts";
import { Link } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api-client";
import { useSession } from "@/lib/session";
import { Button } from "./ui/button";
import { Alert, Card } from "./ui/card";
import { Field, Input, Select, Textarea } from "./ui/input";

const CATEGORIES: TicketCategory[] = ["bug", "feedback", "question"];

/** Browser details attached to every report so the team can reproduce the problem. */
export function captureContext(locale: string): Record<string, string | number | boolean> {
  return {
    locale,
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    user_agent: navigator.userAgent.slice(0, 300),
    language: navigator.language,
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    online: navigator.onLine,
  };
}

/** Floating "Report a bug" button, shown to signed-in users on every page. */
export function BugReportButton() {
  const t = useTranslations("bug");
  const tErr = useTranslations("errors");
  const locale = useLocale();
  const { user } = useSession();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [created, setCreated] = useState<Ticket | null>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (!user) return null;

  function close() {
    setOpen(false);
    setError(null);
    setCreated(null);
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    // Read the file from the input itself: the most reliable source across browsers and test DOMs.
    const screenshot = (form.elements.namedItem("screenshot") as HTMLInputElement | null)?.files?.[0];
    setBusy(true);
    setError(null);
    try {
      let ticket = await api<Ticket>("/tickets", {
        json: {
          category: fd.get("category"),
          title: fd.get("title"),
          description: fd.get("description"),
          page_url: window.location.href.slice(0, 500),
          context: captureContext(locale),
        },
      });
      if (screenshot) {
        const upload = new FormData();
        upload.append("file", screenshot);
        ticket = await api<Ticket>(`/tickets/${ticket.id}/attachment`, { form: upload });
      }
      setCreated(ticket);
    } catch (err) {
      setError(err instanceof ApiError && err.status ? err.message : tErr("network"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="fixed bottom-4 end-4 z-30 flex items-center gap-2 rounded-full bg-foreground px-4 py-3 text-sm font-medium text-background shadow-lg transition hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label={t("open")}
        data-testid="bug-button"
      >
        <Bug className="size-4" aria-hidden />
        <span className="hidden sm:inline">{t("open")}</span>
      </button>
      {open ? (
        <div
          className="fixed inset-0 z-40 flex items-end justify-center bg-black/40 p-0 sm:items-center sm:p-4"
          role="dialog"
          aria-modal="true"
          aria-labelledby="bug-title"
        >
          <Card className="max-h-[90vh] w-full max-w-lg overflow-y-auto rounded-b-none p-5 sm:rounded-xl" data-testid="bug-dialog">
            <div className="mb-3 flex items-start justify-between gap-2">
              <h2 id="bug-title" className="text-lg font-semibold">
                {t("title")}
              </h2>
              <button type="button" onClick={close} aria-label={t("cancel")} className="rounded p-1 hover:bg-muted">
                <X className="size-5" />
              </button>
            </div>
            {created ? (
              <div className="flex flex-col gap-3">
                <Alert tone="success" data-testid="bug-sent">
                  {t("sent", { number: created.number })}
                </Alert>
                <Link href={`/tickets/${created.id}`} className="font-medium text-primary underline" onClick={close}>
                  {t("view")}
                </Link>
              </div>
            ) : (
              <form onSubmit={submit} className="flex flex-col gap-3">
                <p className="text-sm text-muted-foreground">{t("intro")}</p>
                <Field label={t("category")} htmlFor="bug-category">
                  <Select id="bug-category" name="category" defaultValue="bug">
                    {CATEGORIES.map((c) => (
                      <option key={c} value={c}>
                        {t(`cat_${c}`)}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field label={t("summary")} htmlFor="bug-summary">
                  <Input id="bug-summary" name="title" required minLength={3} maxLength={160} dir="auto" autoFocus />
                </Field>
                <Field label={t("details")} htmlFor="bug-details">
                  <Textarea id="bug-details" name="description" required minLength={10} maxLength={5000} dir="auto" />
                </Field>
                <Field label={t("screenshot")} htmlFor="bug-screenshot">
                  <Input id="bug-screenshot" name="screenshot" type="file" accept="image/jpeg,image/png,image/webp" />
                </Field>
                {error ? <Alert tone="error">{error}</Alert> : null}
                <div className="flex justify-end gap-2">
                  <Button type="button" variant="ghost" onClick={close}>
                    {t("cancel")}
                  </Button>
                  <Button type="submit" disabled={busy} data-testid="bug-submit">
                    {t("send")}
                  </Button>
                </div>
              </form>
            )}
          </Card>
        </div>
      ) : null}
    </>
  );
}
