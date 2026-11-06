import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/";
});

// next-intl navigation helpers need the Next router; tests use simple stand-ins.
export const routerMock = { push: vi.fn(), replace: vi.fn(), refresh: vi.fn() };
function omitLocale(props: Record<string, unknown>) {
  const copy = { ...props };
  delete copy.locale;
  return copy;
}

vi.mock("@/i18n/navigation", async () => {
  const React = await import("react");
  return {
    Link: ({ href, children, ...rest }: { href: string; children: React.ReactNode; locale?: string }) =>
      React.createElement("a", { href, ...omitLocale(rest) }, children),
    useRouter: () => routerMock,
    usePathname: () => "/listings",
  };
});
