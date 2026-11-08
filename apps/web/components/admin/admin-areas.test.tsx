import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { AreaProfile, Location } from "@2ajar/contracts";
import { staffUser } from "@/test/support-fixtures";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { AdminAreas } from "./admin-areas";
import { AdminShell } from "./admin-shell";

const locations: Location[] = [
  { id: "g1", parent_id: null, level: "governorate", slug: "beirut", name_en: "Beirut", name_ar: "بيروت", path: "beirut" },
  { id: "a1", parent_id: "g1", level: "area", slug: "hamra", name_en: "Hamra", name_ar: "الحمرا", path: "beirut/hamra" },
];
const hamra: AreaProfile = {
  location_slug: "hamra", location_name_en: "Hamra", location_name_ar: "الحمرا", safety_score: 3,
  theft_reports_12m: 12, quiet_score: 2, noise_notes_en: null, noise_notes_ar: null, garbage_collection: "weekly",
  flood_risk: null, summary_en: "[DEMO] x", summary_ar: null, source_note: null, is_demo: true,
  updated_at: "2026-11-01T00:00:00Z",
};

describe("AdminAreas", () => {
  it("shows an Areas tab to staff", async () => {
    mockFetch({ "GET /api/v1/me": staffUser });
    renderWithIntl(<AdminShell need="areas.manage">x</AdminShell>);
    expect(await screen.findByRole("link", { name: "Areas" })).toHaveAttribute("href", "/admin/areas");
  });

  it("edits an existing profile and creates a new one", async () => {
    let profiles = [hamra];
    const calls = mockFetch({
      "GET /api/v1/locations": locations,
      "GET /api/v1/admin/areas": () => json(profiles),
      "PUT /api/v1/admin/areas/": (url, init) => {
        const body = JSON.parse(init.body as string);
        const loc = locations.find((l) => url.endsWith(l.id))!;
        const saved = { ...hamra, ...body, location_slug: loc.slug, is_demo: false };
        profiles = [...profiles.filter((p) => p.location_slug !== loc.slug), saved];
        return json(saved);
      },
    });
    renderWithIntl(<AdminAreas />);
    const user = userEvent.setup();
    expect(await screen.findByRole("option", { name: /Hamra ✓/ })).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Area"), "a1");
    expect(screen.getByText("Demo values — not real statistics")).toBeInTheDocument();
    expect(screen.getByLabelText("Theft reports in the last 12 months")).toHaveValue(12);
    await user.selectOptions(screen.getByLabelText("Safety (1–5)"), "5");
    await user.clear(screen.getByLabelText("Summary (English)"));
    await user.type(screen.getByLabelText("Summary (English)"), "  Reviewed  ");
    await user.type(screen.getByLabelText("Source"), "ISF 2026");
    await user.click(screen.getByTestId("save-area"));
    expect(await screen.findByText("Area profile saved")).toBeInTheDocument();
    const put = calls.find((c) => c.method === "PUT")!;
    expect(put.url).toBe("/api/v1/admin/areas/a1");
    expect(JSON.parse(put.init.body as string)).toEqual({
      safety_score: 5, quiet_score: 2, theft_reports_12m: 12, garbage_collection: "weekly", flood_risk: null,
      noise_notes_en: null, noise_notes_ar: null, summary_en: "Reviewed", summary_ar: null, source_note: "ISF 2026",
    });
    await waitFor(() => expect(screen.queryByText("Demo values — not real statistics")).not.toBeInTheDocument());

    await user.selectOptions(screen.getByLabelText("Area"), "g1");
    await user.selectOptions(screen.getByLabelText("Flood risk"), "high");
    await user.click(screen.getByTestId("save-area"));
    await waitFor(() => expect(calls.filter((c) => c.method === "PUT").length).toBe(2));
    expect(JSON.parse(calls.filter((c) => c.method === "PUT")[1].init.body as string)).toMatchObject({
      flood_risk: "high", safety_score: null,
    });
  });

  it("reports API errors", async () => {
    mockFetch({
      "GET /api/v1/locations": locations,
      "GET /api/v1/admin/areas": [],
      "PUT /api/v1/admin/areas/": () => json({ error: { code: "forbidden", message: "No permission" } }, 403),
    });
    renderWithIntl(<AdminAreas />, "ar");
    const user = userEvent.setup();
    await screen.findByRole("option", { name: /الحمرا/ });
    await user.selectOptions(screen.getByLabelText("المنطقة"), "a1");
    await user.click(screen.getByTestId("save-area"));
    expect(await screen.findByText("No permission")).toBeInTheDocument();

    mockFetch({ "GET /api/v1/locations": 500 });
    renderWithIntl(<AdminAreas />);
    expect(await screen.findByRole("status")).toBeInTheDocument();
  });
});
