"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { Ticket, TicketPage, TicketPriority, TicketStatus } from "@2ajar/contracts";
import { Link } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import { PriorityBadge, StatusBadge, TicketThread } from "../ticket-thread";
import { Button } from "../ui/button";
import { Alert, Card } from "../ui/card";
import { Input, Select } from "../ui/input";

const STATUSES: TicketStatus[] = ["open", "in_progress", "resolved", "closed"];
const PRIORITIES: TicketPriority[] = ["low", "normal", "high", "urgent"];

export function AdminTickets() {
  const t = useTranslations("admin");
  const tt = useTranslations("tickets");
  const locale = useLocale();
  const [status, setStatus] = useState("open");
  const [priority, setPriority] = useState("");
  const [q, setQ] = useState("");
  const [page, setPage] = useState<TicketPage | null>(null);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page_size: "50" });
    if (status) params.set("status", status);
    if (priority) params.set("priority", priority);
    if (q) params.set("q", q);
    setPage(await api<TicketPage>(`/admin/tickets?${params}`));
  }, [status, priority, q]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  return (
    <div className="flex flex-col gap-3" data-testid="admin-tickets">
      <form
        className="flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setQ(String(new FormData(e.currentTarget).get("q") ?? ""));
        }}
      >
        <Select aria-label={t("status")} value={status} onChange={(e) => setStatus(e.target.value)} className="max-w-44">
          <option value="">{t("allStatuses")}</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {tt(`status_${s}`)}
            </option>
          ))}
        </Select>
        <Select aria-label={t("priority")} value={priority} onChange={(e) => setPriority(e.target.value)} className="max-w-44">
          <option value="">{t("allPriorities")}</option>
          {PRIORITIES.map((p) => (
            <option key={p} value={p}>
              {tt(`priority_${p}`)}
            </option>
          ))}
        </Select>
        <Input name="q" aria-label={t("search")} placeholder={t("search")} className="max-w-xs" />
        <Button type="submit" variant="outline">
          {t("search")}
        </Button>
      </form>
      {page ? <p className="text-sm text-muted-foreground">{t("total", { count: page.total })}</p> : null}
      <ul className="flex flex-col gap-2">
        {page?.items.map((x) => (
          <li key={x.id}>
            <Link href={`/admin/tickets/${x.id}`}>
              <Card className="flex flex-wrap items-center justify-between gap-2 p-3 hover:shadow-md" data-testid="admin-ticket-row">
                <div className="min-w-0">
                  <p className="truncate font-medium" dir="auto">
                    <span className="me-2 font-mono text-sm text-muted-foreground">#{x.number}</span>
                    {x.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {x.reporter.name} · {formatDate(x.created_at, locale)} · {tt("comments", { count: x.comment_count })}
                    {x.assignee ? ` · ${x.assignee.name}` : ""}
                  </p>
                </div>
                <div className="flex gap-1">
                  <PriorityBadge priority={x.priority} />
                  <StatusBadge status={x.status} />
                </div>
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function AdminTicketDetail({ id }: { id: string }) {
  const t = useTranslations("admin");
  const tt = useTranslations("tickets");
  const { user, can } = useSession();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<Ticket>(`/tickets/${id}`)
      .then(setTicket)
      .catch((e) => setError(e instanceof ApiError ? e.message : String(e)));
  }, [id]);

  async function patch(changes: Record<string, unknown>) {
    setError(null);
    try {
      setTicket(await api<Ticket>(`/admin/tickets/${id}`, { method: "PATCH", json: changes }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    }
  }

  if (!ticket) return error ? <Alert tone="error">{error}</Alert> : null;
  const manage = can("tickets.manage");
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_18rem]">
      <TicketThread ticket={ticket} staff={manage} currentUserId={user?.id} onChange={setTicket} />
      <aside className="flex flex-col gap-3">
        <Card className="flex flex-col gap-3 p-4" data-testid="triage-panel">
          <label className="flex flex-col gap-1 text-sm">
            {t("status")}
            <Select value={ticket.status} disabled={!manage} onChange={(e) => patch({ status: e.target.value })} aria-label={t("status")}>
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {tt(`status_${s}`)}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex flex-col gap-1 text-sm">
            {t("priority")}
            <Select value={ticket.priority} disabled={!manage} onChange={(e) => patch({ priority: e.target.value })} aria-label={t("priority")}>
              {PRIORITIES.map((p) => (
                <option key={p} value={p}>
                  {tt(`priority_${p}`)}
                </option>
              ))}
            </Select>
          </label>
          <div className="text-sm">
            <p className="text-muted-foreground">{t("assignee")}</p>
            <p>{ticket.assignee?.name ?? t("unassigned")}</p>
            {manage && ticket.assignee?.id !== user?.id ? (
              <Button size="sm" variant="outline" className="mt-1" onClick={() => patch({ assignee_user_id: user?.id })}>
                {t("assignMe")}
              </Button>
            ) : null}
          </div>
          {error ? <Alert tone="error">{error}</Alert> : null}
        </Card>
        <Card className="flex flex-col gap-1 p-4 text-sm">
          <p className="text-muted-foreground">{t("reporter")}</p>
          <p>{ticket.reporter.name}</p>
          <p className="text-muted-foreground" dir="ltr">
            {ticket.reporter.email}
          </p>
          <p className="mt-2 text-muted-foreground">{t("context")}</p>
          <dl className="grid grid-cols-[auto_1fr] gap-x-2 text-xs" dir="ltr">
            {Object.entries(ticket.context).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="font-medium">{k}</dt>
                <dd className="truncate">{String(v)}</dd>
              </div>
            ))}
          </dl>
        </Card>
      </aside>
    </div>
  );
}
