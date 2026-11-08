import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { DiscoverOut, ListingPublic } from "@2ajar/contracts";
import { listing } from "@/test/fixtures";
import { routerMock } from "@/test/setup";
import { seekerUser } from "@/test/support-fixtures";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { FavoritesProvider, useFavorites } from "@/lib/favorites";
import { periodSuffixKey, stayOf } from "@/lib/format";
import { FavoriteButton } from "../favorite-button";
import { ListingTile } from "../listing-tile";
import { SavedListings } from "../saved-listings";
import { CategoryBar } from "./category-bar";
import { NearYou } from "./near-you";
import { Row } from "./row";
import { TopAreas } from "./top-areas";

const ID = "11111111-1111-1111-1111-111111111111";
const chalet = (over: Partial<ListingPublic> = {}): ListingPublic =>
  listing({
    status: "published",
    price_period: "nightly",
    price_usd: 180,
    is_demo: true,
    media: [{ id: "m1", url: "/media/c.webp", width: 10, height: 10 }],
    property: { ...listing().property, property_type: "chalet", max_guests: 6, bedrooms: 3 },
    ...over,
  });

afterEach(() => vi.unstubAllGlobals());

describe("format helpers", () => {
  it("maps every price period to a suffix and a stay kind", () => {
    expect(periodSuffixKey("hourly")).toBe("perHour");
    expect(periodSuffixKey("total")).toBeNull();
    expect(["hourly", "daily", "nightly", "weekly", "monthly", "yearly"].map((p) => stayOf(p as never))).toEqual([
      "hours", "hours", "nights", "nights", "months", "months",
    ]);
  });
});

describe("ListingTile", () => {
  it("shows type, area, guests, price per night, demo badge and an optional note", () => {
    renderWithIntl(<ListingTile listing={chalet()} note="2 km away" />);
    const tile = screen.getByTestId("listing-tile");
    expect(tile).toHaveAttribute("href", `/en/listings/${ID}`);
    expect(tile).toHaveTextContent("Chalet · Hamra");
    expect(tile).toHaveTextContent("6 guests · 3 bedrooms");
    expect(tile).toHaveTextContent("$180 /night");
    expect(tile).toHaveTextContent("DEMO");
    expect(tile).toHaveTextContent("2 km away");
  });

  it("handles listings without photos, guests or bedrooms (Arabic)", () => {
    renderWithIntl(
      <ListingTile
        listing={chalet({
          media: [], is_demo: false, price_period: "hourly",
          property: { ...listing().property, max_guests: null, bedrooms: null },
        })}
      />,
      "ar",
    );
    const tile = screen.getByTestId("listing-tile");
    expect(tile).toHaveTextContent("/ساعة");
    expect(tile).not.toHaveTextContent("تجريبي");
  });
});

describe("favorites", () => {
  it("sends signed-out visitors to login", async () => {
    mockFetch({ "GET /api/v1/me": () => json({ error: { code: "unauthorized", message: "x" } }, 401) });
    renderWithIntl(
      <FavoritesProvider>
        <FavoriteButton listingId={ID} />
      </FavoritesProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("favorite-button")).toBeInTheDocument());
    await waitFor(async () => {
      fireEvent.click(screen.getByTestId("favorite-button"));
      expect(routerMock.push).toHaveBeenCalledWith("/login");
    });
  });

  it("loads saved ids, toggles optimistically and rolls back on failure", async () => {
    let fail = false;
    const calls = mockFetch({
      "GET /api/v1/me/favorites/ids": { listing_ids: [ID] },
      "GET /api/v1/me": seekerUser,
      "DELETE /api/v1/me/favorites/": () => (fail ? json({ error: { code: "x", message: "x" } }, 500) : new Response(null, { status: 204 })),
      "PUT /api/v1/me/favorites/": 204,
    });
    renderWithIntl(
      <FavoritesProvider>
        <FavoriteButton listingId={ID} variant="inline" />
      </FavoritesProvider>,
    );
    const button = screen.getByTestId("favorite-button");
    await waitFor(() => expect(button).toHaveAttribute("aria-pressed", "true"));
    expect(button).toHaveTextContent("Saved");
    const user = userEvent.setup();
    await user.click(button);
    await waitFor(() => expect(button).toHaveAttribute("aria-pressed", "false"));
    expect(calls.some((c) => c.method === "DELETE" && c.url.endsWith(ID))).toBe(true);
    await user.click(button);
    await waitFor(() => expect(button).toHaveAttribute("aria-pressed", "true"));
    fail = true;
    await user.click(button);
    await waitFor(() => expect(button).toHaveAttribute("aria-pressed", "true")); // rolled back
  });

  it("works as a no-op outside the provider", async () => {
    function Probe() {
      const { isSaved, toggle } = useFavorites();
      return <button onClick={() => void toggle(ID)}>{String(isSaved(ID))}</button>;
    }
    renderWithIntl(<Probe />);
    fireEvent.click(screen.getByRole("button", { name: "false" }));
    expect(routerMock.push).not.toHaveBeenCalledWith("/login");
  });
});

describe("Row", () => {
  it("renders a titled scroller with arrows and a link, and nothing when empty", () => {
    const scrollBy = vi.fn();
    Element.prototype.scrollBy = scrollBy;
    renderWithIntl(
      <Row title="Chalets" subtitle="By the night" href="/en/listings?stay=nights" testId="row">
        {[<span key="a">A</span>, <span key="b">B</span>]}
      </Row>,
    );
    const row = screen.getByTestId("row");
    expect(row).toHaveTextContent("Chalets");
    expect(within(row).getByRole("link", { name: "Show all" })).toHaveAttribute("href", "/en/listings?stay=nights");
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Previous" }));
    expect(scrollBy).toHaveBeenCalledTimes(2);
    const { container } = renderWithIntl(<Row title="Empty">{[]}</Row>);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("NearYou", () => {
  const geo = (impl: (ok: PositionCallback, err: PositionErrorCallback) => void) =>
    vi.stubGlobal("navigator", { ...navigator, geolocation: { getCurrentPosition: impl } });

  it("asks for location only on click and shows nearby homes with distance", async () => {
    const calls = mockFetch({ "GET /api/v1/listings/nearby": [{ listing: chalet(), distance_km: 1.4 }] });
    geo((ok) => ok({ coords: { latitude: 33.896012, longitude: 35.482034 } } as GeolocationPosition));
    renderWithIntl(<NearYou />);
    const nearbyCalls = () => calls.filter((c) => c.url.includes("/nearby"));
    expect(nearbyCalls()).toHaveLength(0); // nothing is asked or sent before the click
    fireEvent.click(screen.getByRole("button", { name: "Use my location" }));
    expect(await screen.findByTestId("row-near-you")).toHaveTextContent("1.4 km away");
    expect(nearbyCalls()[0].url).toBe("/api/v1/listings/nearby?lat=33.8960&lng=35.4820&limit=12");
  });

  it("explains when location is denied, unavailable or nothing is near", async () => {
    geo((_ok, err) => err({ code: 1 } as GeolocationPositionError));
    renderWithIntl(<NearYou />);
    fireEvent.click(screen.getByRole("button", { name: "Use my location" }));
    expect(await screen.findByText(/couldn't get your location/)).toBeInTheDocument();

    mockFetch({ "GET /api/v1/listings/nearby": [] });
    geo((ok) => ok({ coords: { latitude: 1, longitude: 1 } } as GeolocationPosition));
    renderWithIntl(<NearYou />);
    fireEvent.click(screen.getAllByRole("button", { name: "Use my location" })[1]);
    expect(await screen.findByText(/No homes within 40 km/)).toBeInTheDocument();

    mockFetch({ "GET /api/v1/listings/nearby": () => json({ error: { code: "x", message: "x" } }, 500) });
    geo((ok) => ok({ coords: { latitude: 1, longitude: 1 } } as GeolocationPosition));
    renderWithIntl(<NearYou />);
    fireEvent.click(screen.getAllByRole("button", { name: "Use my location" })[2]);
    await waitFor(() => expect(screen.getAllByText(/couldn't get your location/).length).toBe(2));

    vi.stubGlobal("navigator", {});
    renderWithIntl(<NearYou />);
    fireEvent.click(screen.getAllByRole("button", { name: "Use my location" })[3]);
    await waitFor(() => expect(screen.getAllByText(/couldn't get your location/).length).toBe(3));
  });
});

describe("SavedListings", () => {
  it("shows saved homes and drops one when un-hearted", async () => {
    mockFetch({
      "GET /api/v1/me/favorites/ids": { listing_ids: [ID] },
      "GET /api/v1/me/favorites": [chalet()],
      "GET /api/v1/me": seekerUser,
      "DELETE /api/v1/me/favorites/": 204,
    });
    renderWithIntl(
      <FavoritesProvider>
        <SavedListings />
      </FavoritesProvider>,
    );
    const grid = await screen.findByTestId("saved-grid");
    fireEvent.click(within(grid).getByTestId("favorite-button"));
    expect(await screen.findByTestId("saved-empty")).toHaveTextContent("Tap the heart");
  });

  it("asks signed-out visitors to log in and copes with errors", async () => {
    mockFetch({ "GET /api/v1/me": () => json({ error: { code: "unauthorized", message: "x" } }, 401) });
    renderWithIntl(<SavedListings />);
    expect(await screen.findByRole("link", { name: "Log in to save homes" })).toHaveAttribute("href", "/login");

    mockFetch({ "GET /api/v1/me": seekerUser, "GET /api/v1/me/favorites": 500 });
    renderWithIntl(<SavedListings />, "ar");
    expect(await screen.findByTestId("saved-empty")).toHaveTextContent("اضغط على القلب");
  });
});

describe("CategoryBar and TopAreas", () => {
  it("links each category to a plain-language search", () => {
    renderWithIntl(<CategoryBar />, "ar");
    const links = screen.getAllByTestId("category");
    expect(links.length).toBeGreaterThanOrEqual(10);
    expect(links[0]).toHaveTextContent("شاليهات");
    expect(links[0]).toHaveAttribute("href", `/ar/ask?q=${encodeURIComponent("شاليه")}`);
  });

  it("shows curated scores with listing counts and demo labels", () => {
    const area = {
      location_slug: "jounieh", location_name_en: "Jounieh", location_name_ar: "جونية", safety_score: 5,
      theft_reports_12m: null, quiet_score: 4, noise_notes_en: null, noise_notes_ar: null,
      garbage_collection: null, flood_risk: null, summary_en: null, summary_ar: null, source_note: null,
      is_demo: true, updated_at: "2026-11-01T00:00:00Z",
    };
    const areas: DiscoverOut["top_areas"] = [
      { area, listing_count: 3 },
      { area: { ...area, location_slug: "hamra", location_name_en: "Hamra", is_demo: false, safety_score: null, quiet_score: null }, listing_count: 1 },
    ];
    renderWithIntl(<TopAreas areas={areas} />);
    const section = screen.getByTestId("row-top-areas");
    expect(section).toHaveTextContent("Jounieh");
    expect(section).toHaveTextContent("Safety 5/5");
    expect(section).toHaveTextContent("Quiet 4/5");
    expect(section).toHaveTextContent("3 homes");
    expect(section).toHaveTextContent("DEMO");
    expect(within(section).getAllByRole("link")[1]).toHaveAttribute("href", "/en/listings?location=hamra");
    const { container } = renderWithIntl(<TopAreas areas={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
