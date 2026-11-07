"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import type { Ticket, TicketPriority, TicketStatus } from "@2ajar/contracts";
import { api, ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import { Button } from "./ui/button";
import { Alert, Badge, Card } from "./ui/card";
import { Textarea } from "./ui/input";

const STATUS_TONE: Record<TicketStatus, "warning" | "default" | "success" | "muted"> = {
  open: "warning",
  in_progress: "default",
  resolved: "success",
  closed: "muted",
};

export function StatusBadge({ status }: { status: TicketStatus }) {
  const t = useTranslations("tickets");
  return <Badge tone={STATUS_TONE[status]}>{t(`status_${status}`)}</Badge>;
}

export function PriorityBadge({ priority }: { priority: TicketPriority }) {
  const t = useTranslations("tickets");
  return <Badge tone={priority === "urgent" || priority === "high" ? "warning" : "muted"}>{t(`priority_${priority}`)}</Badge>;
}

/**
 * A ticket and its conversation. User-written text is rendered as plain text (React escapes it).
 * In staff mode internal notes are shown (highlighted) and can be written.
 */
export function TicketThread({
  ticket,
  staff = false,
  currentUserId,
  onChange,
}: {
  ticket: Ticket;
  staff?: boolean;
  currentUserId?: string;
  onChange: (t: Ticket) => void;
}) {
  const t = useTranslations("tickets");
  const tErr = useTranslations("errors");
  const locale = useLocale();
  const [body, setBody] = useState("");
  const [internal, setInternal] = useState(staff);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      onChange(await api<Ticket>(`/tickets/${ticket.id}/comments`, { json: { body, is_internal: staff && internal } }));
      setBody("");
    } catch (err) {
      setError(err instanceof ApiError && err.status ? err.message : tErr("network"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4" data-testid="ticket-thread">
      <Card className="flex flex-col gap-3 p-4">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-mono text-sm text-muted-foreground">#{ticket.number}</span>
          <StatusBadge status={ticket.status} />
          <PriorityBadge priority={ticket.priority} />
        </div>
        <h1 className="text-xl font-bold" dir="auto">
          {ticket.title}
        </h1>
        <p className="text-sm text-muted-foreground">{t("reported", { date: formatDate(ticket.created_at, locale) })}</p>
        <p className="whitespace-pre-line" dir="auto">
          {ticket.description}
        </p>
        {ticket.page_url ? (
          <p className="truncate text-sm" dir="ltr">
            <span className="text-muted-foreground">{t("page")}: </span>
            {ticket.page_url}
          </p>
        ) : null}
        {ticket.has_attachment ? (
          <a href={`/api/v1/tickets/${ticket.id}/attachment`} target="_blank" rel="noreferrer" className="self-start">
            <img
              src={`/api/v1/tickets/${ticket.id}/attachment`}
              alt={t("screenshot")}
              className="max-h-64 rounded-lg border border-border"
            />
          </a>
        ) : null}
      </Card>

      <ol className="flex flex-col gap-3" data-testid="ticket-comments">
        {ticket.comments.map((c) => {
          const mine = c.author?.id === currentUserId;
          return (
            <li key={c.id}>
              <Card className={`p-3 ${c.is_internal ? "border-amber-300 bg-amber-50" : ""}`}>
                <div className="mb-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">
                    {mine ? t("you") : c.author_is_staff ? t("staff") : (c.author?.name ?? "—")}
                  </span>
                  {staff && c.author?.name && c.author_is_staff ? <span>({c.author.name})</span> : null}
                  {c.is_internal ? <Badge tone="demo">{t("internal")}</Badge> : null}
                  {c.via === "mcp" ? <Badge tone="muted">MCP</Badge> : null}
                  <span>{formatDate(c.created_at, locale)}</span>
                </div>
                <p className="whitespace-pre-line text-sm" dir="auto">
                  {c.body}
                </p>
              </Card>
            </li>
          );
        })}
      </ol>

      <form onSubmit={send} className="flex flex-col gap-2" data-testid="ticket-reply">
        <Textarea
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={t("replyPlaceholder")}
          aria-label={t("reply")}
          required
          maxLength={5000}
          dir="auto"
        />
        {staff ? (
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={internal} onChange={(e) => setInternal(e.target.checked)} className="size-4" />
            {t("internal")}
          </label>
        ) : null}
        {error ? <Alert tone="error">{error}</Alert> : null}
        <Button type="submit" disabled={busy || !body.trim()} className="self-end">
          {t("send")}
        </Button>
      </form>
    </div>
  );
}
