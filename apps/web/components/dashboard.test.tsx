import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { listing } from "@/test/fixtures";
import { routerMock } from "@/test/setup";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { Dashboard } from "./dashboard";

const broker = {
  id: "u", email: "b@example.com", full_name: "Rami Broker", phone_e164: null, role: "broker", locale: "en",
  memberships: [{ organization_id: "o", organization_name: "Cedar", role: "agency_admin" }],
};
const past = new Date(Date.now() - 86_400_000).toISOString();
const future = new Date(Date.now() + 5 * 86_400_000).toISOString();

beforeEach(() => vi.clearAllMocks());

describe("Dashboard", () => {
  it("lists listings with statuses and leads, and runs actions", async () => {
    const calls = mockFetch({
      "GET /api/v1/me/listings": [
        listing({ id: "d1", status: "draft", lead_count: 0, is_demo: true }),
        listing({ id: "p1", status: "published", expires_at: future, lead_count: 1, title: { en: "Live", ar: null },
                  media: [{ id: "m", url: "/media/x.webp", width: 1, height: 1 }] }),
        listing({ id: "e1", status: "published", expires_at: past, title: { en: "Old", ar: null } }),
        listing({ id: "x1", status: "paused", title: { en: null, ar: null } }),
      ],
      "GET /api/v1/me/leads": [
        { id: "l1", listing_id: "p1", name: "Lea", phone_e164: "+9613123456", email: null, message: "Hi there",
          source: "web", status: "new", duplicate_count: 2, consent_at: future, created_at: future,
          last_contact_at: future, listing_title: "Live" },
      ],
      "GET /api/v1/me": broker,
      "POST /api/v1/listings/": { ok: true },
    });
    renderWithIntl(<Dashboard />);
    const items = await screen.findAllByTestId("dashboard-listing");
    expect(items).toHaveLength(4);
    expect(screen.getByText(/Rami Broker · Cedar/)).toBeInTheDocument();
    expect(within(items[0]).getByText("Draft")).toBeInTheDocument();
    expect(within(items[0]).getByText("DEMO")).toBeInTheDocument();
    expect(within(items[1]).getByText("1 lead")).toBeInTheDocument();
    expect(within(items[1]).getByText(/Expires/)).toBeInTheDocument();
    expect(within(items[2]).getByText(/Expired/)).toBeInTheDocument();
    expect(within(items[3]).getByText("—")).toBeInTheDocument();

    const leads = screen.getByTestId("leads-list");
    expect(within(leads).getByText("Lea")).toBeInTheDocument();
    expect(within(leads).getByText("(contacted 2 more times)")).toBeInTheDocument();
    expect(within(leads).getByRole("link", { name: /WhatsApp/ })).toHaveAttribute("href", "https://wa.me/9613123456");

    const user = userEvent.setup();
    await user.click(within(items[0]).getByRole("button", { name: "Publish" }));
    await user.click(within(items[1]).getByRole("button", { name: "Pause" }));
    await user.click(within(items[1]).getByRole("button", { name: "Still available" }));
    await waitFor(() =>
      expect(calls.filter((c) => c.method === "POST").map((c) => c.url)).toEqual([
        "/api/v1/listings/d1/publish", "/api/v1/listings/p1/pause", "/api/v1/listings/p1/confirm",
      ]),
    );
  });

  it("shows action errors and empty states", async () => {
    mockFetch({
      "GET /api/v1/me/listings": [listing({ id: "d1" })],
      "GET /api/v1/me/leads": [],
      "GET /api/v1/me": { ...broker, memberships: [] },
      "POST /api/v1/listings/d1/publish": () =>
        json({ error: { code: "validation_error", message: "At least one photo is required" } }, 422),
    });
    renderWithIntl(<Dashboard />);
    await userEvent.click(await screen.findByRole("button", { name: "Publish" }));
    expect(await screen.findByText("At least one photo is required")).toBeInTheDocument();
    expect(screen.getByText("No leads yet.")).toBeInTheDocument();
  });

  it("shows a note for seekers and redirects anonymous users", async () => {
    mockFetch({ "GET /api/v1/me": { ...broker, role: "seeker", memberships: [] } });
    renderWithIntl(<Dashboard />);
    expect(await screen.findByText(/Seeker accounts/)).toBeInTheDocument();

    mockFetch({ "GET /api/v1/me": () => json({ error: { code: "unauthorized", message: "x" } }, 401), "POST /api/v1/auth/refresh": 401 });
    renderWithIntl(<Dashboard />);
    await waitFor(() => expect(routerMock.replace).toHaveBeenCalledWith("/login"));

    mockFetch({ "GET /api/v1/me": () => json({ error: { code: "error", message: "Server exploded" } }, 500) });
    renderWithIntl(<Dashboard />);
    expect(await screen.findByText("Server exploded")).toBeInTheDocument();
  });

  it("renders an empty broker dashboard", async () => {
    mockFetch({ "GET /api/v1/me/listings": [], "GET /api/v1/me/leads": [], "GET /api/v1/me": broker });
    renderWithIntl(<Dashboard />);
    expect(await screen.findByText("You have no listings yet.")).toBeInTheDocument();
    expect(screen.getByTestId("import-csv")).toHaveAttribute("href", "/dashboard/import");
  });
});
