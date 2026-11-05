"use client";

import { MessageCircle } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { LeadReceipt } from "@2ajar/contracts";
import { api, ApiError } from "@/lib/api-client";
import { Button } from "./ui/button";
import { Alert, Card } from "./ui/card";
import { Field, Input, Textarea } from "./ui/input";

export function ContactPanel({ listingId, consentVersion }: { listingId: string; consentVersion: string }) {
  const t = useTranslations("contact");
  const tErr = useTranslations("errors");
  const locale = useLocale();
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | "duplicate">("idle");
  const [error, setError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);

  useEffect(() => {
    api(`/listings/${listingId}/view`, { method: "POST" }).catch(() => undefined);
  }, [listingId]);

  async function openWhatsApp() {
    setOpening(true);
    try {
      const { url } = await api<{ url: string }>(`/listings/${listingId}/contact/whatsapp?locale=${locale}`, {
        method: "POST",
      });
      window.location.href = url;
    } catch (e) {
      setError(e instanceof ApiError && e.status ? e.message : tErr("network"));
    } finally {
      setOpening(false);
    }
  }

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setError(null);
    setStatus("sending");
    try {
      const res = await api<LeadReceipt>(`/listings/${listingId}/leads`, {
        json: {
          name: fd.get("name"),
          phone: fd.get("phone"),
          email: fd.get("email") || null,
          message: fd.get("message") || null,
          consent: fd.get("consent") === "on",
          consent_text_version: consentVersion,
        },
      });
      setStatus(res.deduplicated ? "duplicate" : "sent");
    } catch (err) {
      setStatus("idle");
      setError(err instanceof ApiError && err.status ? err.message : tErr("network"));
    }
  }

  return (
    <Card className="flex flex-col gap-4 p-4" data-testid="contact-panel">
      <h2 className="font-semibold">{t("title")}</h2>
      <Button variant="whatsapp" size="lg" onClick={openWhatsApp} disabled={opening} data-testid="whatsapp-button">
        <MessageCircle className="size-5" aria-hidden />
        {t("whatsapp")}
      </Button>
      <p className="text-center text-xs text-muted-foreground">{t("or")}</p>
      {status === "sent" || status === "duplicate" ? (
        <Alert tone="success" data-testid="lead-success">
          {status === "sent" ? t("sent") : t("duplicate")}
        </Alert>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-3" data-testid="lead-form">
          <Field label={t("name")} htmlFor="lead-name">
            <Input id="lead-name" name="name" required minLength={2} maxLength={100} autoComplete="name" />
          </Field>
          <Field label={t("phone")} htmlFor="lead-phone">
            <Input id="lead-phone" name="phone" type="tel" required dir="ltr" autoComplete="tel" placeholder="+961 …" />
          </Field>
          <Field label={t("email")} htmlFor="lead-email">
            <Input id="lead-email" name="email" type="email" dir="ltr" autoComplete="email" />
          </Field>
          <Field label={t("message")} htmlFor="lead-message">
            <Textarea id="lead-message" name="message" maxLength={1000} />
          </Field>
          <label className="flex items-start gap-2 text-xs leading-relaxed">
            <input type="checkbox" name="consent" required className="mt-0.5 size-4 shrink-0" data-testid="lead-consent" />
            <span>{t("consent")}</span>
          </label>
          {error ? <Alert tone="error">{error}</Alert> : null}
          <Button type="submit" disabled={status === "sending"}>
            {t("submit")}
          </Button>
        </form>
      )}
    </Card>
  );
}
