import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { GrowthDashboard } from "@2ajar/contracts";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { AdminGrowth } from "./admin-growth";

function growth(over: Partial<GrowthDashboard> = {}): GrowthDashboard {
  return {
    generated_at: "2026-11-09T10:00:00Z",
    demo_mode: true,
    metrics: {
      live_listings: 42, active_publishers: 6, weekly_searches: 120, conversion: 0.04, weekly_inquiries: 9,
      retention_60d: null, weekly_views: 225,
    },
    targets: {
      live_listings: { day30: 150, day90: 600 }, active_publishers: { day30: 15, day90: 80 },
      weekly_searches: { day30: 500, day90: 5000 }, conversion: { day30: 0.05, day90: 0.08 },
      weekly_inquiries: { day30: 50, day90: 400 }, retention_60d: { day30: 0.7, day90: 0.7 },
    },
    renters: {
      index: 12.5,
      factors: [
        { key: "dream", score: 0.4, value: "40%", metric: "bills_reported" },
        { key: "likelihood", score: 0.7, value: "70%", metric: "fresh_photos_areafacts" },
        { key: "time", score: 0.8, value: "20%", metric: "zero_result_searches" },
        { key: "effort", score: null, value: "–", metric: "needed_clarification" },
      ],
    },
    owners: {
      index: null,
      factors: [
        { key: "dream", score: 0.21, value: "0.21", metric: "inquiries_per_listing_week" },
        { key: "likelihood", score: 0.3, value: "30%", metric: "listings_contacted_30d" },
        { key: "time", score: null, value: "–", metric: "hours_to_first_inquiry" },
        { key: "effort", score: 0.9, value: "10%", metric: "drafts_never_published" },
      ],
    },
    funnel: { searches: 120, visitors: 90, views: 225, inquiries: 9 },
    area_gaps: [
      { slug: "verdun", name_en: "Verdun", name_ar: "فردان", searches: 14, zero_results: 6, live_listings: 1, has_area_facts: false },
      { slug: "hamra", name_en: "Hamra", name_ar: "الحمرا", searches: 30, zero_results: 0, live_listings: 12, has_area_facts: true },
    ],
    wishes: [
      { key: "electricity_24_7", searches: 50, data_coverage: 0.4 },
      { key: "pool", searches: 3, data_coverage: null },
    ],
    property_types: [{ key: "apartment", searches: 40 }],
    quiet_listings: [{ id: "l1", title: "Flat in Hamra", visitors: 17 }],
    recommendations: [
      { key: "supply_sprint", priority: 1, lever: "leads", channel: "warm_cold_outreach",
        params: { live: 42, missing: 258, areas_en: "Verdun, Badaro", areas_ar: "فردان، بدارو" } },
      { key: "answer_top_wishes", priority: 2, lever: "dream", channel: null, params: { wishes: ["electricity_24_7", "quiet"] } },
    ],
    playbook: [
      { key: "offer_defined", phase: 1, metric: null, target: null, current: null, progress: null, done: false, auto: false },
      { key: "listings_100", phase: 1, metric: "live_listings", target: 100, current: 42, progress: 0.42, done: false, auto: true },
      { key: "demo_off", phase: 1, metric: "demo_off", target: 1, current: 1, progress: 1, done: true, auto: true },
      { key: "lead_magnet", phase: 2, metric: null, target: null, current: null, progress: null, done: true, auto: false },
      { key: "referrals", phase: 3, metric: null, target: null, current: null, progress: null, done: false, auto: false },
    ],
    ...over,
  };
}

describe("AdminGrowth", () => {
  it("shows the north star, scoreboard, value equations, funnel and gaps", async () => {
    mockFetch({ "GET /api/v1/admin/growth": growth() });
    renderWithIntl(<AdminGrowth />);
    expect(await screen.findByTestId("north-star")).toHaveTextContent("9");
    expect(screen.getByText(/Demo mode is on/)).toBeInTheDocument();
    expect(screen.getByTestId("scoreboard")).toHaveTextContent("Live listings");
    expect(screen.getByTestId("scoreboard")).toHaveTextContent("4%");
    expect(screen.getByTestId("scoreboard")).toHaveTextContent("not enough data yet");
    expect(screen.getByTestId("value-renters")).toHaveTextContent("12.5");
    expect(screen.getByTestId("value-renters")).toHaveTextContent("listings that report electricity + water costs");
    expect(screen.getByTestId("value-owners")).toHaveTextContent("–");
    expect(within(screen.getByTestId("funnel")).getByText("75%")).toBeInTheDocument(); // visitors / searches
    expect(within(screen.getByTestId("funnel")).getByText("4%")).toBeInTheDocument(); // inquiries / views
    expect(screen.getByTestId("area-gaps")).toHaveTextContent("Verdun");
    expect(screen.getByTestId("wishes")).toHaveTextContent("24/7 electricity");
    expect(screen.getByTestId("wishes")).toHaveTextContent("40% of listings can answer");
    expect(screen.getByTestId("wishes")).toHaveTextContent("answered by amenities");
    expect(screen.getByRole("link", { name: "Flat in Hamra" })).toHaveAttribute("href", "/en/listings/l1");
  });

  it("explains next steps with their lever, channel and numbers (Arabic)", async () => {
    mockFetch({ "GET /api/v1/admin/growth": growth({ demo_mode: false }) });
    renderWithIntl(<AdminGrowth />, "ar");
    await screen.findByTestId("north-star");
    fireEvent.click(screen.getByRole("tab", { name: /الخطوات التالية/ }));
    const recs = screen.getByTestId("recommendations");
    expect(recs).toHaveTextContent("258 إعلاناً إضافياً");
    expect(recs).toHaveTextContent("فردان، بدارو");
    expect(recs).toHaveTextContent("تواصل دافئ + بارد");
    expect(recs).toHaveTextContent("كهرباء 24/24، منطقة هادئة");
    expect(screen.queryByText(/الوضع التجريبي مفعّل/)).not.toBeInTheDocument();
  });

  it("says when nothing is urgent", async () => {
    mockFetch({ "GET /api/v1/admin/growth": growth({ recommendations: [], area_gaps: [], wishes: [], quiet_listings: [], property_types: [] }) });
    renderWithIntl(<AdminGrowth />);
    await screen.findByTestId("north-star");
    expect(screen.getAllByText("not enough data yet").length).toBeGreaterThan(1);
    fireEvent.click(screen.getByRole("tab", { name: /Next steps/ }));
    expect(screen.getByText(/Nothing urgent/)).toBeInTheDocument();
  });

  it("ticks playbook steps and shows measured ones", async () => {
    let data = growth();
    const calls = mockFetch({
      "GET /api/v1/admin/growth": () => json(data),
      "PUT /api/v1/admin/growth/tasks/": (url, init) => {
        const key = url.split("/").pop()!;
        const done = JSON.parse(init.body as string).done;
        data = { ...data, playbook: data.playbook.map((x) => (x.key === key ? { ...x, done } : x)) };
        return new Response(null, { status: 204 });
      },
    });
    renderWithIntl(<AdminGrowth />);
    await screen.findByTestId("north-star");
    await userEvent.click(screen.getByRole("tab", { name: /90-day playbook/ }));
    const playbook = screen.getByTestId("playbook");
    expect(playbook).toHaveTextContent("measured · 42 / 100");
    await userEvent.click(screen.getByTestId("step-offer_defined"));
    await waitFor(() => expect(screen.getByTestId("step-offer_defined")).toBeChecked());
    expect(calls.some((c) => c.method === "PUT" && c.url.endsWith("/offer_defined"))).toBe(true);
  });

  it("shows the business model canvas, revenue streams and a live revenue calculator", async () => {
    mockFetch({ "GET /api/v1/admin/growth": growth() });
    renderWithIntl(<AdminGrowth />);
    await screen.findByTestId("north-star");
    await userEvent.click(screen.getByRole("tab", { name: /Business model/ }));
    expect(within(screen.getByTestId("canvas")).getAllByRole("heading")).toHaveLength(9);
    expect(screen.getByTestId("revenue-streams")).toHaveTextContent("Featured listings");
    // 6 publishers x 30% x $15 = $27
    expect(screen.getByTestId("sim-today-pro")).toHaveTextContent("$27");
    const price = screen.getByTestId("sim-proPrice");
    fireEvent.change(price, { target: { value: "20" } });
    expect(screen.getByTestId("sim-today-pro")).toHaveTextContent("$36");
    fireEvent.change(price, { target: { value: "" } });
    expect(screen.getByTestId("sim-today-pro")).toHaveTextContent("$0");
  });

  it("shows API errors", async () => {
    mockFetch({ "GET /api/v1/admin/growth": () => json({ error: { code: "forbidden", message: "No permission" } }, 403) });
    renderWithIntl(<AdminGrowth />);
    expect(await screen.findByText("No permission")).toBeInTheDocument();
  });
});
