"use client";

import { Building2, Heart, LayoutDashboard, LifeBuoy, LogOut, Shield } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useSession } from "@/lib/session";
import { Button, buttonVariants } from "./ui/button";

export function Header() {
  const t = useTranslations("nav");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const { user, signOut, can } = useSession();
  const isBackOffice = can("users.read") || can("tickets.read");

  async function logout() {
    await signOut();
    router.push("/");
    router.refresh();
  }

  const otherLocale = locale === "ar" ? "en" : "ar";

  return (
    <header className="sticky top-0 z-20 border-b border-border bg-background/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between gap-2 px-4 sm:px-6">
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
              {isBackOffice ? (
                <Link href="/admin" className={buttonVariants({ variant: "ghost", size: "sm" })} data-testid="nav-admin">
                  <Shield className="size-4" aria-hidden />
                  <span className="hidden sm:inline">{t("admin")}</span>
                </Link>
              ) : null}
              <Link
                href="/saved"
                className={buttonVariants({ variant: "ghost", size: "sm" })}
                aria-label={t("saved")}
                data-testid="nav-saved"
              >
                <Heart className="size-4" aria-hidden />
                <span className="hidden md:inline">{t("saved")}</span>
              </Link>
              <Link href="/tickets" className={buttonVariants({ variant: "ghost", size: "sm" })} aria-label={t("tickets")}>
                <LifeBuoy className="size-4" aria-hidden />
              </Link>
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
