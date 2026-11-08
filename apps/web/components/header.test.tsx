import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { routerMock } from "@/test/setup";
import { staffUser } from "@/test/support-fixtures";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { Header } from "./header";
import { SiteFooter } from "./site-footer";

beforeEach(() => vi.clearAllMocks());

describe("Header", () => {
  it("offers log in, sign up and listing to visitors from the menu and the phone tab bar", async () => {
    mockFetch({ "GET /api/v1/me": () => json({}, 401), "POST /api/v1/auth/refresh": 401 });
    renderWithIntl(<Header />);
    expect(screen.getByTestId("locale-switch")).toHaveTextContent("العربية");
    expect(screen.getByRole("link", { name: "List your property" })).toHaveAttribute("href", "/register");
    await userEvent.click(screen.getByTestId("user-menu"));
    const menu = screen.getByRole("menu");
    expect(within(menu).getByRole("menuitem", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(within(menu).getByRole("menuitem", { name: "Sign up" })).toHaveAttribute("href", "/register");
    const tabs = screen.getByRole("navigation", { name: "Menu" });
    expect(within(tabs).getByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(within(tabs).getByRole("link", { name: "Saved" })).toHaveAttribute("href", "/saved");
    // Escape and outside clicks close the menu.
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    await userEvent.click(screen.getByTestId("user-menu"));
    fireEvent.keyDown(document, { key: "a" });
    expect(screen.getByRole("menu")).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
  });

  it("shows saved, dashboard and admin to staff, and logs out (Arabic)", async () => {
    const calls = mockFetch({ "GET /api/v1/me": staffUser, "POST /api/v1/auth/logout": 204 });
    renderWithIntl(<Header />, "ar");
    expect(screen.getByText("إيجار")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("user-menu")).toHaveTextContent("S"));
    expect(screen.getByRole("link", { name: "أضف عقارك" })).toHaveAttribute("href", "/dashboard/listings/new");
    await userEvent.click(screen.getByTestId("user-menu"));
    expect(screen.getByTestId("nav-saved")).toHaveAttribute("href", "/saved");
    expect(screen.getByTestId("nav-dashboard")).toHaveAttribute("href", "/dashboard");
    expect(screen.getByTestId("nav-admin")).toHaveAttribute("href", "/admin");
    expect(within(screen.getByRole("navigation", { name: "القائمة" })).getByRole("link", { name: "الحساب" })).toHaveAttribute(
      "href",
      "/dashboard",
    );
    await userEvent.click(screen.getByRole("menuitem", { name: "تسجيل الخروج" }));
    await waitFor(() => expect(routerMock.push).toHaveBeenCalledWith("/"));
    expect(calls.some((c) => c.url.endsWith("/auth/logout"))).toBe(true);
  });
});

describe("SiteFooter", () => {
  it("renders link columns in the page language", () => {
    renderWithIntl(<SiteFooter locale="ar" />, "ar");
    expect(screen.getByRole("link", { name: "اعرض عقارك" })).toHaveAttribute("href", "/ar/register");
    expect(screen.getByText(/إيجار · لبنان/)).toBeInTheDocument();
  });
});
