import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { emptyLiving, listing, locations } from "@/test/fixtures";
import { routerMock } from "@/test/setup";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { ListingForm } from "./listing-form";

const ID = "11111111-1111-1111-1111-111111111111";
beforeEach(() => vi.clearAllMocks());

describe("ListingForm (create)", () => {
  it("maps form fields to the API payload and opens the editor", async () => {
    const calls = mockFetch({ "POST /api/v1/listings": { ...listing(), id: "new-id" } });
    renderWithIntl(<ListingForm locations={locations} />);
    const user = userEvent.setup();
    expect(screen.getByRole("option", { name: /Beirut/ })).toBeDisabled(); // only areas are selectable
    await user.selectOptions(screen.getByLabelText("Location"), "a1");
    await user.type(screen.getByLabelText("Price (USD)"), "900");
    await user.selectOptions(screen.getByLabelText("Price period"), "yearly");
    await user.type(screen.getByLabelText("Bedrooms"), "2");
    await user.click(screen.getByLabelText("Sea view"));
    await user.type(screen.getByLabelText("Title (English)"), "Flat");
    await user.type(screen.getByLabelText("WhatsApp number for inquiries"), "70123456");
    await user.selectOptions(screen.getByLabelText("Electricity"), "edl_plus_generator");
    await user.type(screen.getByLabelText("Generator subscription (amps)"), "10");
    await user.type(screen.getByLabelText("Typical electricity bill ($/month)"), "90");
    await user.selectOptions(screen.getByLabelText("Can solar panels be installed?"), "yes");
    await user.selectOptions(screen.getByLabelText("Elevator works during power cuts?"), "no");
    await user.selectOptions(screen.getByLabelText("Winter"), "warm");
    await user.type(screen.getByLabelText("Highlights"), "Sunny{enter}{enter}  Quiet street ");
    await user.click(screen.getByTestId("save-listing"));
    await waitFor(() => expect(routerMock.push).toHaveBeenCalledWith("/dashboard/listings/new-id/edit"));
    expect(JSON.parse(calls.find((c) => c.method !== "GET")!.init.body as string)).toEqual({
      transaction_type: "rent", property_type: "apartment", location_id: "a1", price_usd: 900,
      price_period: "yearly", bedrooms: 2, bathrooms: null, area_sqm: null, floor: null, furnished: null,
      amenities: ["sea_view"], title_en: "Flat", title_ar: null, description_en: null, description_ar: null,
      contact_whatsapp: "70123456",
      electricity_supply: "edl_plus_generator", generator_amps: 10, electricity_usd_month: 90,
      water_source: null, water_usd_month: null, sewage: null, parking_spots: null, solar_ready: true,
      elevator_backup: false, winter_comfort: "warm", summer_comfort: null,
      highlights: ["Sunny", "Quiet street"], things_to_know: [],
    });
  });

  it("forces a total price for sales and shows validation errors", async () => {
    const calls = mockFetch({
      "POST /api/v1/listings": () => json({ error: { code: "validation_error", message: "Invalid", details: ["Bad price"] } }, 422),
    });
    renderWithIntl(<ListingForm locations={locations} />);
    const user = userEvent.setup();
    await user.click(screen.getByLabelText("Sale"));
    expect(screen.queryByLabelText("Price period")).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Location"), "a1");
    await user.type(screen.getByLabelText("Price (USD)"), "250000");
    await user.click(screen.getByTestId("save-listing"));
    expect(await screen.findByTestId("form-error")).toHaveTextContent("Bad price");
    expect(JSON.parse(calls.find((c) => c.method !== "GET")!.init.body as string)).toMatchObject({ transaction_type: "sale", price_period: "total" });
  });
});

describe("ListingForm (edit)", () => {
  it("loads, saves, uploads, removes photos and publishes", async () => {
    let current = listing({ media: [{ id: "m1", url: "/media/a.webp", width: 10, height: 10 }] });
    current.property.living = {
      ...emptyLiving, solar_ready: false, elevator_backup: true, parking_spots: 2, highlights: ["A", "B"],
    };
    const calls = mockFetch({
      [`GET /api/v1/listings/${ID}`]: () => json(current),
      [`PATCH /api/v1/listings/${ID}`]: () => json(current),
      [`POST /api/v1/listings/${ID}/media`]: () => json({ id: "m2" }, 201),
      [`DELETE /api/v1/listings/${ID}/media/m1`]: 204,
      [`POST /api/v1/listings/${ID}/publish`]: () => {
        current = { ...current, status: "published" };
        return json(current);
      },
    });
    renderWithIntl(<ListingForm locations={locations} listingId={ID} />);
    expect(await screen.findByDisplayValue("Bright flat")).toBeInTheDocument();
    const user = userEvent.setup();

    await user.click(screen.getByTestId("save-listing"));
    expect(await screen.findByTestId("form-notice")).toHaveTextContent("Saved");
    const patch = calls.find((c) => c.method === "PATCH")!;
    expect(JSON.parse(patch.init.body as string)).toMatchObject({
      amenities: ["parking"], furnished: "furnished", solar_ready: false, elevator_backup: true, parking_spots: 2,
      highlights: ["A", "B"],
    });

    const file = new File(["x"], "p.jpg", { type: "image/jpeg" });
    await user.upload(screen.getByTestId("photo-input"), [file, file]);
    await waitFor(() => expect(calls.filter((c) => c.url.endsWith("/media")).length).toBe(2));

    await user.click(screen.getByLabelText("Remove"));
    await waitFor(() => expect(calls.some((c) => c.method === "DELETE")).toBe(true));

    await user.click(screen.getByTestId("publish-button"));
    expect(await screen.findByTestId("form-notice")).toHaveTextContent("live");
    expect(screen.getByTestId("view-live")).toHaveAttribute("href", `/listings/${ID}`);
  });

  it("redirects to login when the session is gone and shows load errors", async () => {
    mockFetch({ [`GET /api/v1/listings/${ID}`]: () => json({ error: { code: "unauthorized", message: "x" } }, 401) });
    renderWithIntl(<ListingForm locations={locations} listingId={ID} />);
    await waitFor(() => expect(routerMock.replace).toHaveBeenCalledWith("/login"));

    mockFetch({ [`GET /api/v1/listings/${ID}`]: () => json({ error: { code: "not_found", message: "Listing not found" } }, 404) });
    renderWithIntl(<ListingForm locations={locations} listingId={ID} />);
    expect(await screen.findByText("Listing not found")).toBeInTheDocument();
  });

  it("reports publish and upload failures", async () => {
    mockFetch({
      [`GET /api/v1/listings/${ID}`]: () => json(listing({ title: { en: null, ar: "عنوان" } })),
      [`POST /api/v1/listings/${ID}/publish`]: () =>
        json({ error: { code: "validation_error", message: "x", details: ["At least one photo is required"] } }, 422),
      [`POST /api/v1/listings/${ID}/media`]: () => json({ error: { code: "payload_too_large", message: "Too big" } }, 413),
    });
    renderWithIntl(<ListingForm locations={locations} listingId={ID} />, "ar");
    await screen.findByDisplayValue("عنوان");
    const user = userEvent.setup();
    await user.click(screen.getByTestId("publish-button"));
    expect(await screen.findByTestId("form-error")).toHaveTextContent("At least one photo is required");
    await user.upload(screen.getByTestId("photo-input"), new File(["x"], "p.jpg", { type: "image/jpeg" }));
    expect(await screen.findByText("Too big")).toBeInTheDocument();
  });
});
