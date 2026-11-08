"use client";

import {
  Building2, Globe, Heart, LayoutDashboard, LifeBuoy, LogIn, LogOut, Menu, Search, Shield, UserRound,
} from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { Link, usePathname, useRouter } from "@/i18n/navigation";
import { useSession } from "@/lib/session";
import { cn } from "@/lib/utils";

const item = "flex w-full items-center gap-3 px-4 py-2.5 text-start text-sm hover:bg-muted";

/**
 * Airbnb-style header: logo, "List your property", language globe and a ☰ + avatar menu with everything else.
 * On phones an app-like bottom bar (Explore · Saved · Log in / Profile) takes over the main actions.
 */
export function Header() {
  const t = useTranslations("nav");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const { user, signOut, can } = useSession();
  const [open, setOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const isBackOffice = can("users.read") || can("tickets.read");
  const otherLocale = locale === "ar" ? "en" : "ar";

  useEffect(() => setOpen(false), [pathname]);
  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent ? e.key === "Escape" : !menuRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", close);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", close);
    };
  }, [open]);

  async function logout() {
    setOpen(false);
    await signOut();
    router.push("/");
    router.refresh();
  }

  const initial = user?.full_name?.trim()?.[0]?.toUpperCase();

  return (
    <>
      <header className="sticky top-0 z-30 border-b border-border bg-white">
        <div className="mx-auto flex h-20 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-1.5 text-primary" aria-label="2ajar home">
            <Building2 className="size-8" strokeWidth={2} aria-hidden />
            <span className="text-2xl font-bold tracking-tight">{locale === "ar" ? "إيجار" : "2ajar"}</span>
          </Link>

          <div className="flex items-center gap-1">
            <Link
              href={user ? "/dashboard/listings/new" : "/register"}
              className="hidden rounded-full px-4 py-3 text-sm font-medium hover:bg-muted md:block"
            >
              {t("register")}
            </Link>
            <Link
              href={pathname}
              locale={otherLocale}
              className="flex items-center gap-1.5 rounded-full p-3 text-sm font-medium hover:bg-muted"
              data-testid="locale-switch"
            >
              <Globe className="size-4" aria-hidden />
              <span>{t("language")}</span>
            </Link>

            <div className="relative" ref={menuRef}>
              <button
                type="button"
                onClick={() => setOpen((v) => !v)}
                aria-expanded={open}
                aria-haspopup="menu"
                aria-label={t("menu")}
                data-testid="user-menu"
                className="flex items-center gap-2.5 rounded-full border border-border py-1.5 pe-1.5 ps-3 transition hover:shadow-md"
              >
                <Menu className="size-4" aria-hidden />
                <span className="flex size-8 items-center justify-center rounded-full bg-neutral-500 text-sm font-semibold text-white">
                  {initial ?? <UserRound className="size-5" aria-hidden />}
                </span>
              </button>
              {open ? (
                <div
                  role="menu"
                  className="absolute end-0 top-full z-40 mt-2 w-64 overflow-hidden rounded-xl border border-border bg-white py-2 shadow-[0_2px_16px_rgba(0,0,0,0.12)]"
                >
                  {user ? (
                    <>
                      <Link href="/saved" role="menuitem" className={cn(item, "font-semibold")} data-testid="nav-saved">
                        <Heart className="size-4" aria-hidden />
                        {t("saved")}
                      </Link>
                      <Link href="/dashboard" role="menuitem" className={cn(item, "font-semibold")} data-testid="nav-dashboard">
                        <LayoutDashboard className="size-4" aria-hidden />
                        {t("dashboard")}
                      </Link>
                      {isBackOffice ? (
                        <Link href="/admin" role="menuitem" className={item} data-testid="nav-admin">
                          <Shield className="size-4" aria-hidden />
                          {t("admin")}
                        </Link>
                      ) : null}
                      <Link href="/tickets" role="menuitem" className={item}>
                        <LifeBuoy className="size-4" aria-hidden />
                        {t("tickets")}
                      </Link>
                      <div className="my-2 h-px bg-border" />
                      <button type="button" role="menuitem" onClick={logout} className={item}>
                        <LogOut className="size-4" aria-hidden />
                        {t("logout")}
                      </button>
                    </>
                  ) : (
                    <>
                      <Link href="/login" role="menuitem" className={cn(item, "font-semibold")}>
                        {t("login")}
                      </Link>
                      <Link href="/register" role="menuitem" className={item}>
                        {t("signup")}
                      </Link>
                      <div className="my-2 h-px bg-border" />
                      <Link href="/register" role="menuitem" className={item}>
                        {t("register")}
                      </Link>
                    </>
                  )}
                </div>
              ) : null}
            </div>
          </div>
        </div>
      </header>

      {/* Phone tab bar, like the Airbnb app. */}
      <nav
        aria-label={t("menu")}
        className="fixed inset-x-0 bottom-0 z-30 flex h-16 items-center justify-around border-t border-border bg-white text-[11px] font-medium text-muted-foreground md:hidden"
      >
        <Link href="/" className={cn("flex flex-col items-center gap-1", pathname === "/" && "text-primary")}>
          <Search className="size-6" aria-hidden />
          {t("explore")}
        </Link>
        <Link href="/saved" className={cn("flex flex-col items-center gap-1", pathname === "/saved" && "text-primary")}>
          <Heart className="size-6" aria-hidden />
          {t("saved")}
        </Link>
        {user ? (
          <Link href="/dashboard" className={cn("flex flex-col items-center gap-1", pathname.startsWith("/dashboard") && "text-primary")}>
            <UserRound className="size-6" aria-hidden />
            {t("profile")}
          </Link>
        ) : (
          <Link href="/login" className="flex flex-col items-center gap-1">
            <LogIn className="size-6" aria-hidden />
            {t("login")}
          </Link>
        )}
      </nav>
    </>
  );
}
