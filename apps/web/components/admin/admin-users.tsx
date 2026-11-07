"use client";

import { useLocale, useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import type { AdminUser, AdminUserPage, Permission, PermissionInfo, UserRole } from "@2ajar/contracts";
import { api, ApiError } from "@/lib/api-client";
import { formatDate } from "@/lib/format";
import { useSession } from "@/lib/session";
import { Button } from "../ui/button";
import { Alert, Badge, Card } from "../ui/card";
import { Input, Select } from "../ui/input";

const ROLES: UserRole[] = ["seeker", "owner", "broker", "staff", "platform_admin"];

export function AdminUsers() {
  const t = useTranslations("admin");
  const locale = useLocale();
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState<AdminUserPage | null>(null);
  const [catalog, setCatalog] = useState<PermissionInfo[]>([]);
  const [editing, setEditing] = useState<string | null>(null);

  const load = useCallback(async () => {
    const params = new URLSearchParams({ page_size: "50" });
    if (q) params.set("q", q);
    if (role) params.set("role", role);
    setPage(await api<AdminUserPage>(`/admin/users?${params}`));
  }, [q, role]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);
  useEffect(() => {
    api<PermissionInfo[]>("/admin/permissions").then(setCatalog).catch(() => undefined);
  }, []);

  return (
    <div className="flex flex-col gap-3" data-testid="admin-users">
      <form
        className="flex flex-wrap gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget);
          setQ(String(fd.get("q") ?? ""));
        }}
      >
        <Input name="q" placeholder={t("searchUsers")} aria-label={t("searchUsers")} className="max-w-xs" />
        <Select aria-label={t("role")} value={role} onChange={(e) => setRole(e.target.value)} className="max-w-48">
          <option value="">{t("allRoles")}</option>
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {t(`role_${r}`)}
            </option>
          ))}
        </Select>
        <Button type="submit" variant="outline">
          {t("search")}
        </Button>
      </form>
      {page ? <p className="text-sm text-muted-foreground">{t("total", { count: page.total })}</p> : null}
      <ul className="flex flex-col gap-2">
        {page?.items.map((u) => (
          <li key={u.id}>
            <Card className="p-3" data-testid="admin-user-row">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="font-medium">
                    {u.full_name} <span className="text-sm font-normal text-muted-foreground">{u.email}</span>
                  </p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    <Badge>{t(`role_${u.role}`)}</Badge>
                    <Badge tone={u.is_active ? "success" : "muted"}>{u.is_active ? t("active") : t("inactive")}</Badge>
                    {u.is_demo ? <Badge tone="demo">DEMO</Badge> : null}
                    {u.memberships.map((m) => (
                      <Badge key={m.organization_id} tone="muted">
                        {m.organization_name}
                      </Badge>
                    ))}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {t("lastLogin")}: {u.last_login_at ? formatDate(u.last_login_at, locale) : t("never")}
                  </p>
                </div>
                <Button size="sm" variant="outline" onClick={() => setEditing(editing === u.id ? null : u.id)}>
                  {t("edit")}
                </Button>
              </div>
              {editing === u.id ? (
                <UserEditor
                  user={u}
                  catalog={catalog}
                  onSaved={(saved) =>
                    setPage((p) => (p ? { ...p, items: p.items.map((x) => (x.id === saved.id ? saved : x)) } : p))
                  }
                />
              ) : null}
            </Card>
          </li>
        ))}
      </ul>
    </div>
  );
}

function UserEditor({
  user,
  catalog,
  onSaved,
}: {
  user: AdminUser;
  catalog: PermissionInfo[];
  onSaved: (u: AdminUser) => void;
}) {
  const t = useTranslations("admin");
  const { user: me, can } = useSession();
  const [role, setRole] = useState<UserRole>(user.role);
  const [active, setActive] = useState(user.is_active);
  const [extra, setExtra] = useState<Permission[]>(user.extra_permissions);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);
  const isSelf = me?.id === user.id;
  const readOnly = !can("users.manage");

  async function save() {
    setMessage(null);
    try {
      const saved = await api<AdminUser>(`/admin/users/${user.id}`, {
        method: "PATCH",
        json: { role, is_active: active, extra_permissions: extra },
      });
      onSaved(saved);
      setMessage({ tone: "success", text: t("saved") });
    } catch (e) {
      setMessage({ tone: "error", text: e instanceof ApiError ? e.message : String(e) });
    }
  }

  return (
    <div className="mt-3 flex flex-col gap-3 border-t border-border pt-3" data-testid="user-editor">
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          {t("role")}
          <Select
            value={role}
            onChange={(e) => setRole(e.target.value as UserRole)}
            disabled={readOnly || isSelf}
            className="w-44"
            aria-label={t("role")}
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {t(`role_${r}`)}
              </option>
            ))}
          </Select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={active}
            onChange={(e) => setActive(e.target.checked)}
            disabled={readOnly || isSelf}
            className="size-4"
          />
          {t("active")}
        </label>
      </div>
      <fieldset className="flex flex-col gap-1">
        <legend className="mb-1 text-sm font-medium">{t("permissions")}</legend>
        <div className="grid gap-1 sm:grid-cols-2">
          {catalog
            .filter((p) => p.grantable)
            .map((p) => (
              <label key={p.key} className="flex items-center gap-2 text-sm" dir="ltr">
                <input
                  type="checkbox"
                  className="size-4"
                  // Role defaults are implied and cannot be removed here; change the role instead.
                  disabled={readOnly || p.roles.includes(role)}
                  checked={extra.includes(p.key) || p.roles.includes(role)}
                  onChange={(e) =>
                    setExtra((cur) => (e.target.checked ? [...cur, p.key] : cur.filter((x) => x !== p.key)))
                  }
                />
                <code>{p.key}</code>
                {p.roles.includes(role) ? <span className="text-xs text-muted-foreground">({t(`role_${role}`)})</span> : null}
              </label>
            ))}
        </div>
      </fieldset>
      <p className="text-xs text-muted-foreground" dir="ltr">
        {t("effective")}: {user.permissions.join(", ") || "—"}
      </p>
      {message ? <Alert tone={message.tone}>{message.text}</Alert> : null}
      {!readOnly ? (
        <Button size="sm" onClick={save} className="self-start" data-testid="user-save">
          {t("save")}
        </Button>
      ) : null}
    </div>
  );
}
