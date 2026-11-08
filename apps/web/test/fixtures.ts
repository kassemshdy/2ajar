import type { LivingFactors, ListingPrivate, Location } from "@2ajar/contracts";

export const locations: Location[] = [
  { id: "g1", parent_id: null, level: "governorate", slug: "beirut", name_en: "Beirut", name_ar: "بيروت", path: "beirut" },
  { id: "a1", parent_id: "g1", level: "area", slug: "hamra", name_en: "Hamra", name_ar: "الحمرا", path: "beirut/hamra" },
];

export const emptyLiving: LivingFactors = {
  electricity_supply: null,
  generator_amps: null,
  electricity_usd_month: null,
  water_source: null,
  water_usd_month: null,
  sewage: null,
  parking_spots: null,
  solar_ready: null,
  elevator_backup: null,
  winter_comfort: null,
  summer_comfort: null,
  highlights: [],
  things_to_know: [],
};

export function listing(over: Partial<ListingPrivate> = {}): ListingPrivate {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    status: "draft",
    transaction_type: "rent",
    price_usd: 1200,
    price_period: "monthly",
    title: { en: "Bright flat", ar: "شقة مشرقة" },
    description: { en: "Nice", ar: null },
    property: {
      property_type: "apartment",
      bedrooms: 2,
      bathrooms: 1,
      area_sqm: 100,
      floor: 3,
      furnished: "furnished",
      amenities: ["parking"],
      living: { ...emptyLiving },
    },
    location: { slug: "hamra", name_en: "Hamra", name_ar: "الحمرا", path: "beirut/hamra" },
    media: [],
    publisher: { type: "broker", display_name: "Org", organization_name: "Org" },
    published_at: null,
    last_confirmed_at: null,
    is_demo: false,
    contact_whatsapp: "+96170123456",
    expires_at: null,
    created_at: "2026-11-01T00:00:00Z",
    updated_at: "2026-11-01T00:00:00Z",
    location_id: "a1",
    lead_count: 0,
    ...over,
  };
}
