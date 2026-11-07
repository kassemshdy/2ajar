import { render } from "@testing-library/react";
import { NextIntlClientProvider } from "next-intl";
import type { ReactElement } from "react";
import { vi } from "vitest";
import ar from "../messages/ar.json";
import en from "../messages/en.json";
import { SessionProvider } from "@/lib/session";

export function renderWithIntl(ui: ReactElement, locale: "en" | "ar" = "en") {
  return render(
    <NextIntlClientProvider locale={locale} messages={locale === "ar" ? ar : en} timeZone="Asia/Beirut">
      <SessionProvider>{ui}</SessionProvider>
    </NextIntlClientProvider>,
  );
}

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

/** Install a fetch mock routing by "METHOD path" prefix. Returns the call log. */
export function mockFetch(routes: Record<string, Handler | object | number>) {
  const calls: { method: string; url: string; init: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init: RequestInit = {}) => {
      const method = (init.method ?? "GET").toUpperCase();
      calls.push({ method, url, init });
      const key = Object.keys(routes)
        .filter((k) => {
          const [m, p] = k.split(" ");
          return m === method && url.startsWith(p);
        })
        .sort((a, b) => b.length - a.length)[0];
      if (!key) return json({ error: { code: "not_found", message: "no mock" } }, 404);
      const route = routes[key];
      if (typeof route === "function") return (route as Handler)(url, init);
      if (typeof route === "number") return new Response(null, { status: route });
      return json(route);
    }),
  );
  return calls;
}

export function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
