"use client";

import { Building2, LayoutDashboard, LogOut } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import type { User } from "@2ajar/contracts";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { api } from "@/lib/api-client";
import { Button, buttonVariants } from "./ui/button";

export function Header() {
  const t = useTranslations("nav");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null | undefined>(undefined);

  useEffect(() => {
    api<User>("/me")
      .then(setUser)
      .catch(() => setUser(null));
  }, [pathname]);

  async function logout() {
    await api("/auth/logout", { method: "POST" }).catch(() => undefined);
    setUser(null);
    router.push("/");
    router.refresh();
  }

  const otherLocale = locale === "ar" ? "en" : "ar";

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between gap-2 px-4">
        <Link href="/" className="flex items-center gap-2 font-bold text-primary" aria-label="2ajar home">
          <Building2 className="size-6" aria-hidden />
          <span className="text-lg">{locale === "ar" ? "إيجار" : "2ajar"}</span>
        </Link>
        <nav className="flex items-center gap-1 text-sm">
          <Link href="/listings" className={buttonVariants({ variant: "ghost", size: "sm" })}>
            {t("browse")}
          </Link>
          {user ? (
            <>
              <Link
                href="/dashboard"
                className={buttonVariants({ variant: "ghost", size: "sm" })}
                data-testid="nav-dashboard"
              >
                <LayoutDashboard className="size-4" aria-hidden />
                <span className="hidden sm:inline">{t("dashboard")}</span>
              </Link>
              <Button variant="ghost" size="sm" onClick={logout} aria-label={t("logout")}>
                <LogOut className="size-4" aria-hidden />
              </Button>
            </>
          ) : user === null ? (
            <>
              <Link href="/login" className={buttonVariants({ variant: "ghost", size: "sm" })}>
                {t("login")}
              </Link>
              <Link href="/register" className={buttonVariants({ size: "sm" }) + " hidden sm:inline-flex"}>
                {t("register")}
              </Link>
            </>
          ) : null}
          <Link
            href={pathname}
            locale={otherLocale}
            className={buttonVariants({ variant: "outline", size: "sm" })}
            data-testid="locale-switch"
          >
            {t("language")}
          </Link>
        </nav>
      </div>
    </header>
  );
}
