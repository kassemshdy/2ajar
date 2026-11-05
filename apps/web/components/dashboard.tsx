"use client";

import { FileUp, MessageCircle, Phone, Plus } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { LeadWithListing, ListingPrivate, User } from "@2ajar/contracts";
import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api-client";
import { formatDate, formatUsd, listingTitle } from "@/lib/format";
import { Button, buttonVariants } from "./ui/button";
import { Alert, Badge, Card } from "./ui/card";

const STATUS_TONE = { published: "success", draft: "muted", paused: "warning" } as const;

export function Dashboard() {
  const t = useTranslations("dashboard");
  const tImport = useTranslations("import");
  const locale = useLocale();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [listings, setListings] = useState<ListingPrivate[]>([]);
  const [leads, setLeads] = useState<LeadWithListing[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const me = await api<User>("/me");
      setUser(me);
      if (me.role !== "seeker") {
        const [ls, ld] = await Promise.all([
          api<ListingPrivate[]>("/me/listings"),
          api<LeadWithListing[]>("/me/leads"),
        ]);
        setListings(ls);
        setLeads(ld);
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
      else setError(e instanceof Error ? e.message : String(e));
    }
  }, [router]);

  useEffect(() => {
    load();
  }, [load]);

  async function action(id: string, verb: "publish" | "pause" | "confirm") {
    setError(null);
    try {
      await api(`/listings/${id}/${verb}`, { method: "POST" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  if (!user) return error ? <Alert tone="error">{error}</Alert> : null;

  if (user.role === "seeker") {
    return (
      <div className="flex flex-col gap-4">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <Alert>{t("seekerNote")}</Alert>
      </div>
    );
  }

  const now = Date.now();

  return (
    <div className="flex flex-col gap-8" data-testid="dashboard">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold">{t("title")}</h1>
          <p className="text-sm text-muted-foreground">
            {user.full_name}
            {user.memberships[0] ? ` · ${user.memberships[0].organization_name}` : ""}
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/dashboard/import" className={buttonVariants({ variant: "outline" })} data-testid="import-csv">
            <FileUp className="size-4" aria-hidden />
            {tImport("importCsv")}
          </Link>
          <Link href="/dashboard/listings/new" className={buttonVariants()} data-testid="new-listing">
            <Plus className="size-4" aria-hidden />
            {t("newListing")}
          </Link>
        </div>
      </div>
      {error ? <Alert tone="error">{error}</Alert> : null}

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">{t("myListings")}</h2>
        {listings.length === 0 ? <p className="text-muted-foreground">{t("noListings")}</p> : null}
        <ul className="flex flex-col gap-3">
          {listings.map((l) => {
            const expired = l.status === "published" && l.expires_at && new Date(l.expires_at).getTime() < now;
            return (
              <li key={l.id}>
                <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center" data-testid="dashboard-listing">
                  <div className="h-20 w-full shrink-0 overflow-hidden rounded-lg bg-muted sm:w-28">
                    {l.media[0] ? <img src={l.media[0].url} alt="" className="size-full object-cover" /> : null}
                  </div>
                  <div className="flex min-w-0 flex-1 flex-col gap-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone={STATUS_TONE[l.status as keyof typeof STATUS_TONE] ?? "muted"}>
                        {t(`status_${l.status}`)}
                      </Badge>
                      {l.is_demo ? <Badge tone="demo">DEMO</Badge> : null}
                      <span className="text-sm text-muted-foreground">
                        {t("leadsCount", { count: l.lead_count })}
                      </span>
                    </div>
                    <p className="truncate font-medium">{listingTitle(l, locale) || "—"}</p>
                    <p className="text-sm text-muted-foreground">
                      {formatUsd(l.price_usd, locale)}
                      {l.status === "published" && l.expires_at
                        ? " · " + (expired ? t("expired") : t("expires", { date: formatDate(l.expires_at, locale) }))
                        : ""}
                    </p>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <Link href={`/dashboard/listings/${l.id}/edit`} className={buttonVariants({ variant: "outline", size: "sm" })}>
                      {t("edit")}
                    </Link>
                    <Link href={`/listings/${l.id}`} className={buttonVariants({ variant: "ghost", size: "sm" })}>
                      {t("view")}
                    </Link>
                    {l.status === "published" ? (
                      <>
                        <Button size="sm" variant="outline" onClick={() => action(l.id, "confirm")}>
                          {t("confirm")}
                        </Button>
                        <Button size="sm" variant="outline" onClick={() => action(l.id, "pause")}>
                          {t("pause")}
                        </Button>
                      </>
                    ) : (
                      <Button size="sm" onClick={() => action(l.id, "publish")}>
                        {t("publish")}
                      </Button>
                    )}
                  </div>
                </Card>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-semibold">{t("leads")}</h2>
        {leads.length === 0 ? <p className="text-muted-foreground">{t("noLeads")}</p> : null}
        <ul className="flex flex-col gap-3" data-testid="leads-list">
          {leads.map((lead) => (
            <li key={lead.id}>
              <Card className="flex flex-col gap-2 p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="font-semibold">
                    {lead.name}{" "}
                    <span className="text-xs font-normal text-muted-foreground">
                      {t("contacts", { count: lead.duplicate_count })}
                    </span>
                  </p>
                  <span className="text-xs text-muted-foreground">{formatDate(lead.last_contact_at, locale)}</span>
                </div>
                <p className="text-sm text-muted-foreground">{lead.listing_title}</p>
                {lead.message ? (
                  <p className="whitespace-pre-line text-sm" dir="auto">
                    {lead.message}
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-2">
                  <a href={`tel:${lead.phone_e164}`} className={buttonVariants({ variant: "outline", size: "sm" })} dir="ltr">
                    <Phone className="size-4" aria-hidden />
                    {lead.phone_e164}
                  </a>
                  <a
                    href={`https://wa.me/${lead.phone_e164.replace("+", "")}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className={buttonVariants({ variant: "whatsapp", size: "sm" })}
                  >
                    <MessageCircle className="size-4" aria-hidden />
                    WhatsApp
                  </a>
                </div>
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
