import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { AdminAgency } from "@2ajar/contracts";
import { listing } from "@/test/fixtures";
import { staffUser } from "@/test/support-fixtures";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { AdminAgencies } from "./admin/admin-agencies";
import { AdminShell } from "./admin/admin-shell";
import { CopyLinkButton } from "./copy-link-button";
import { Dashboard } from "./dashboard";
import { InfoTip } from "./info-tip";
import { ListingTile } from "./listing-tile";

const broker = {
  id: "u", email: "b@example.com", full_name: "Rami Broker", phone_e164: null, role: "broker", locale: "en",
  memberships: [{ organization_id: "o", organization_name: "Cedar", role: "agency_admin" }],
};

describe("InfoTip", () => {
  it("opens an explanation and closes on Escape, the close button or an outside click", async () => {
    const user = userEvent.setup();
    renderWithIntl(
      <div>
        <InfoTip term="valueEquation" />
        <p>outside</p>
      </div>,
    );
    const button = screen.getByTestId("info-valueEquation");
    await user.click(button);
    expect(screen.getByRole("dialog")).toHaveTextContent(/Dream outcome/);
    expect(button).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(button);
    await user.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    await user.click(button);
    fireEvent.mouseDown(screen.getByText("outside"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("speaks Arabic", async () => {
    renderWithIntl(<InfoTip term="rule100" />, "ar");
    await userEvent.setup().click(screen.getByTestId("info-rule100"));
    expect(screen.getByRole("dialog").textContent).toMatch(/[؀-ۿ]/);
  });
});

describe("verified badge", () => {
  it("shows on tiles of verified publishers only", () => {
    const verified = listing({ id: "v" });
    verified.publisher = { ...verified.publisher, verified: true };
    renderWithIntl(
      <>
        <ListingTile listing={verified} />
        <ListingTile listing={listing({ id: "n" })} />
      </>,
    );
    expect(screen.getAllByTestId("verified-badge")).toHaveLength(1);
  });
});

describe("CopyLinkButton", () => {
  it("copies the page URL and confirms", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderWithIntl(<CopyLinkButton label="Copy link" copiedLabel="Link copied" />);
    fireEvent.click(screen.getByTestId("copy-link"));
    expect(await screen.findByText("Link copied")).toBeInTheDocument();
    expect(writeText).toHaveBeenCalledWith(window.location.href);
    await act(async () => {
      vi.advanceTimersByTime(2500);
    });
    expect(screen.getByText("Copy link")).toBeInTheDocument();
    vi.useRealTimers();
  });

  it("stays quiet when the clipboard is blocked", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    renderWithIntl(<CopyLinkButton label="Copy link" copiedLabel="Link copied" />);
    fireEvent.click(screen.getByTestId("copy-link"));
    await waitFor(() => expect(writeText).toHaveBeenCalled());
    expect(screen.getByText("Copy link")).toBeInTheDocument();
  });
});

describe("Dashboard monthly report", () => {
  it("shows per-listing stats and 30-day totals", async () => {
    mockFetch({
      "GET /api/v1/me/listings": [
        listing({ id: "a", stats: { visitors_30d: 10, whatsapp_30d: 2, leads_30d: 1, saves: 3 } }),
        listing({ id: "b", stats: { visitors_30d: 5, whatsapp_30d: 1, leads_30d: 0, saves: 1 } }),
      ],
      "GET /api/v1/me/leads": [],
      "GET /api/v1/me": broker,
    });
    renderWithIntl(<Dashboard />);
    const report = await screen.findByTestId("monthly-report");
    expect(within(report).getByText("Last 30 days")).toBeInTheDocument();
    expect(within(report).getByText("15")).toBeInTheDocument();
    expect(within(report).getByText("3")).toBeInTheDocument();
    expect(within(report).getByText("4")).toBeInTheDocument();
    const stats = screen.getAllByTestId("listing-stats");
    expect(stats[0]).toHaveTextContent("10 visitors · 2 WhatsApp taps · 1 contact request · 3 saves");
  });
});

describe("AdminAgencies", () => {
  const cedar: AdminAgency = {
    id: "o1", name: "Cedar Homes", slug: "cedar-homes-abc", is_verified: false, is_demo: true, members: 2,
    live_listings: 7, created_at: "2026-11-01T00:00:00Z",
  };

  it("shows an Agencies tab to staff", async () => {
    mockFetch({ "GET /api/v1/me": staffUser });
    renderWithIntl(<AdminShell need="listings.moderate">x</AdminShell>);
    expect(await screen.findByRole("link", { name: "Agencies" })).toHaveAttribute("href", "/admin/agencies");
  });

  it("lists agencies and toggles the badge", async () => {
    const calls = mockFetch({
      "GET /api/v1/admin/agencies": [cedar],
      "PATCH /api/v1/admin/agencies/o1": (_url, init) =>
        json({ ...cedar, is_verified: JSON.parse(init.body as string).is_verified }),
    });
    renderWithIntl(<AdminAgencies />);
    const row = await screen.findByTestId("agency-row");
    expect(within(row).getByRole("link", { name: "Cedar Homes" })).toHaveAttribute("href", "/en/agencies/cedar-homes-abc");
    expect(within(row).getByText("Demo")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.click(within(row).getByRole("button", { name: "Verify" }));
    expect(await within(row).findByRole("button", { name: "Remove badge" })).toBeInTheDocument();
    expect(JSON.parse(calls.find((c) => c.method === "PATCH")!.init.body as string)).toEqual({ is_verified: true });
  });

  it("shows API errors", async () => {
    mockFetch({
      "GET /api/v1/admin/agencies": [cedar],
      "PATCH /api/v1/admin/agencies/o1": () => json({ error: { code: "forbidden", message: "Nope" } }, 403),
    });
    renderWithIntl(<AdminAgencies />);
    const row = await screen.findByTestId("agency-row");
    await userEvent.setup().click(within(row).getByRole("button", { name: "Verify" }));
    expect(await screen.findByText("Nope")).toBeInTheDocument();
  });
});
