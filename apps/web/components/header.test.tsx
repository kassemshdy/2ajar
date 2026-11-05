import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { routerMock } from "@/test/setup";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { Header } from "./header";

beforeEach(() => vi.clearAllMocks());

describe("Header", () => {
  it("shows login links for visitors", async () => {
    mockFetch({ "GET /api/v1/me": () => json({}, 401), "POST /api/v1/auth/refresh": 401 });
    renderWithIntl(<Header />);
    expect(await screen.findByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(screen.getByTestId("locale-switch")).toHaveTextContent("العربية");
  });

  it("shows dashboard and logs out", async () => {
    const calls = mockFetch({ "GET /api/v1/me": { id: "u" }, "POST /api/v1/auth/logout": 204 });
    renderWithIntl(<Header />, "ar");
    expect(await screen.findByTestId("nav-dashboard")).toBeInTheDocument();
    expect(screen.getByText("إيجار")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "تسجيل الخروج" }));
    await waitFor(() => expect(routerMock.push).toHaveBeenCalledWith("/"));
    expect(calls.some((c) => c.url.endsWith("/auth/logout"))).toBe(true);
  });
});
