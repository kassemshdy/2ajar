"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { Ticket, TicketSummary } from "@2ajar/contracts";
import { Link, useRouter } from "@/i18n/navigation";
import { api, ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import { StatusBadge, TicketThread } from "./ticket-thread";
import { Alert, Card } from "./ui/card";

function useRequireLogin() {
  const router = useRouter();
  return useCallback(
    (e: unknown) => {
      if (e instanceof ApiError && e.status === 401) router.replace("/login");
    },
    [router],
  );
}

export function MyTickets() {
  const t = useTranslations("tickets");
  const locale = useLocale();
  const onError = useRequireLogin();
  const [items, setItems] = useState<TicketSummary[] | null>(null);

  useEffect(() => {
    api<TicketSummary[]>("/me/tickets").then(setItems).catch(onError);
  }, [onError]);

  if (items === null) return null;
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4" data-testid="my-tickets">
      <h1 className="text-2xl font-bold">{t("title")}</h1>
      {items.length === 0 ? <p className="text-muted-foreground">{t("empty")}</p> : null}
      <ul className="flex flex-col gap-2">
        {items.map((x) => (
          <li key={x.id}>
            <Link href={`/tickets/${x.id}`}>
              <Card className="flex items-center justify-between gap-3 p-4 hover:shadow-md">
                <div className="min-w-0">
                  <p className="truncate font-medium" dir="auto">
                    <span className="me-2 font-mono text-sm text-muted-foreground">#{x.number}</span>
                    {x.title}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {formatDate(x.created_at, locale)} · {t("comments", { count: x.comment_count })}
                  </p>
                </div>
                <StatusBadge status={x.status} />
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function TicketDetail({ id }: { id: string }) {
  const t = useTranslations("tickets");
  const onError = useRequireLogin();
  const { user, can } = useSession();
  const [ticket, setTicket] = useState<Ticket | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    api<Ticket>(`/tickets/${id}`)
      .then(setTicket)
      .catch((e) => {
        onError(e);
        setMissing(true);
      });
  }, [id, onError]);

  if (missing) return <Alert tone="error">{t("notFound")}</Alert>;
  if (!ticket) return null;
  return (
    <div className="mx-auto max-w-3xl">
      <TicketThread ticket={ticket} staff={can("tickets.manage")} currentUserId={user?.id} onChange={setTicket} />
    </div>
  );
}
