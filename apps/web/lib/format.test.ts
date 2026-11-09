import { describe, expect, it } from "vitest";
import { listing } from "@/test/fixtures";
import { formatDate, formatUsd, listingTitle, localized, locationName } from "./format";

describe("format", () => {
  it("formats USD with western digits in both locales", () => {
    expect(formatUsd(1200, "en")).toBe("$1,200");
    expect(formatUsd(1200, "ar")).toBe("\u2066$1,200\u2069"); // isolated so RTL text cannot reorder it
  });

  it("formats dates and handles empty values", () => {
    expect(formatDate(null, "en")).toBe("");
    expect(formatDate(undefined, "ar")).toBe("");
    expect(formatDate("2026-11-05T10:00:00Z", "en")).toMatch(/2026/);
  });

  it("falls back to the other language", () => {
    expect(localized({ en: "Hi", ar: null }, "ar")).toBe("Hi");
    expect(localized({ en: null, ar: "مرحبا" }, "en")).toBe("مرحبا");
    expect(localized({ en: null, ar: null }, "en")).toBe("");
    expect(listingTitle(listing(), "ar")).toBe("شقة مشرقة");
    expect(locationName({ name_en: "Hamra", name_ar: "الحمرا" }, "ar")).toBe("الحمرا");
    expect(locationName({ name_en: "Hamra", name_ar: "الحمرا" }, "en")).toBe("Hamra");
  });
});
