"use client";

import { useTranslations } from "next-intl";
import type { Permission } from "@2ajar/contracts";
import { Link, usePathname } from "@/i18n/navigation";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";
import { Alert } from "../ui/card";

/** Back-office frame: tabs filtered by permission. The API enforces the same permissions server-side. */
export function AdminShell({ need, children }: { need: Permission; children: React.ReactNode }) {
  const t = useTranslations("admin");
  const tNav = useTranslations("nav");
  const pathname = usePathname();
  const { user, can } = useSession();
  if (user === undefined) return null;
  if (!user || !can(need)) return <Alert tone="error">{t("noAccess")}</Alert>;

  const tabs = [
    { href: "/admin/tickets", label: t("tickets"), show: can("tickets.read") },
    { href: "/admin/users", label: t("users"), show: can("users.read") },
    { href: "/settings/tokens", label: tNav("tokens"), show: can("mcp.access") },
  ].filter((x) => x.show);

  return (
    <div className="flex flex-col gap-4" data-testid="admin">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-2xl font-bold">{t("title")}</h1>
        <nav className="flex gap-1 rounded-lg bg-muted p-1 text-sm">
          {tabs.map((tab) => (
            <Link
              key={tab.href}
              href={tab.href}
              className={cn(
                "rounded-md px-3 py-1.5 font-medium",
                pathname.startsWith(tab.href) ? "bg-background shadow-sm" : "text-muted-foreground",
              )}
            >
              {tab.label}
            </Link>
          ))}
        </nav>
      </div>
      {children}
    </div>
  );
}
