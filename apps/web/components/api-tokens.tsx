"use client";

import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { ApiToken, ApiTokenCreated } from "@2ajar/contracts";
import { api, ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import { Button } from "./ui/button";
import { Alert, Badge, Card } from "./ui/card";
import { Field, Input } from "./ui/input";

export function mcpConfig(origin: string, token: string) {
  return JSON.stringify(
    {
      mcpServers: {
        "2ajar": { type: "http", url: `${origin}/api/v1/mcp`, headers: { Authorization: `Bearer ${token}` } },
      },
    },
    null,
    2,
  );
}

export function ApiTokens() {
  const t = useTranslations("tokens");
  const locale = useLocale();
  const { user, can } = useSession();
  const [tokens, setTokens] = useState<ApiToken[]>([]);
  const [created, setCreated] = useState<ApiTokenCreated | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (user && can("mcp.access")) api<ApiToken[]>("/me/api-tokens").then(setTokens).catch(() => undefined);
  }, [user, can]);

  if (user === undefined) return null;
  if (!user || !can("mcp.access")) return <Alert tone="error">{t("noAccess")}</Alert>;

  async function create(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    setError(null);
    try {
      const token = await api<ApiTokenCreated>("/me/api-tokens", {
        json: { name: fd.get("name"), expires_in_days: Number(fd.get("expires_in_days")) || null },
      });
      setCreated(token);
      setCopied(false);
      setTokens((cur) => [token, ...cur]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    }
  }

  async function revoke(id: string) {
    await api(`/me/api-tokens/${id}`, { method: "DELETE" });
    setTokens((cur) => cur.map((x) => (x.id === id ? { ...x, revoked_at: new Date().toISOString() } : x)));
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4" data-testid="api-tokens">
      <h1 className="text-2xl font-bold">{t("title")}</h1>
      <p className="text-sm text-muted-foreground">{t("intro")}</p>
      <Card className="p-4">
        <form onSubmit={create} className="flex flex-wrap items-end gap-3">
          <Field label={t("name")} htmlFor="token-name">
            <Input id="token-name" name="name" required minLength={2} maxLength={80} defaultValue="Claude" />
          </Field>
          <Field label={t("expires")} htmlFor="token-expiry">
            <Input id="token-expiry" name="expires_in_days" type="number" min={1} max={365} defaultValue={90} className="w-28" />
          </Field>
          <Button type="submit" data-testid="token-create">
            {t("create")}
          </Button>
        </form>
        {error ? <Alert tone="error" className="mt-3">{error}</Alert> : null}
      </Card>
      {created ? (
        <Card className="flex flex-col gap-2 border-amber-300 p-4" data-testid="token-created">
          <Alert tone="warning">{t("copyNow")}</Alert>
          <code className="break-all rounded bg-muted p-2 text-sm" dir="ltr" data-testid="token-value">
            {created.token}
          </code>
          <Button
            size="sm"
            variant="outline"
            className="self-start"
            onClick={async () => {
              await navigator.clipboard?.writeText(created.token);
              setCopied(true);
            }}
          >
            {copied ? t("copied") : t("copy")}
          </Button>
          <p className="mt-2 text-sm font-medium">{t("mcpConfig")}</p>
          <pre className="overflow-x-auto rounded bg-muted p-2 text-xs" dir="ltr">
            {mcpConfig(window.location.origin, created.token)}
          </pre>
        </Card>
      ) : null}
      {tokens.length === 0 ? <p className="text-muted-foreground">{t("empty")}</p> : null}
      <ul className="flex flex-col gap-2">
        {tokens.map((x) => (
          <li key={x.id}>
            <Card className="flex flex-wrap items-center justify-between gap-2 p-3" data-testid="token-row">
              <div>
                <p className="font-medium">
                  {x.name} <code className="text-xs text-muted-foreground" dir="ltr">{x.prefix}…</code>
                </p>
                <p className="text-xs text-muted-foreground">
                  {x.last_used_at ? t("lastUsed", { date: formatDate(x.last_used_at, locale) }) : t("neverUsed")}
                </p>
              </div>
              {x.revoked_at ? (
                <Badge tone="muted">{t("revoked")}</Badge>
              ) : (
                <Button size="sm" variant="outline" onClick={() => revoke(x.id)}>
                  {t("revoke")}
                </Button>
              )}
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}
