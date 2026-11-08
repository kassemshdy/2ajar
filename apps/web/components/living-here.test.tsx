import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AreaProfile } from "@2ajar/contracts";
import { emptyLiving } from "@/test/fixtures";
import { renderWithIntl } from "@/test/utils";
import { AreaInfo, LivingHere } from "./living-here";

const area: AreaProfile = {
  location_slug: "hamra", location_name_en: "Hamra", location_name_ar: "الحمرا",
  safety_score: 4, theft_reports_12m: 3, quiet_score: 2, noise_notes_en: "Bars on weekends",
  noise_notes_ar: "حانات في عطلة نهاية الأسبوع", garbage_collection: "daily", flood_risk: "low",
  summary_en: "Lively student area", summary_ar: null, source_note: "Field visit", is_demo: false,
  updated_at: "2026-11-01T10:00:00Z",
};

describe("LivingHere", () => {
  it("renders nothing when the publisher reported nothing", () => {
    const { container } = renderWithIntl(<LivingHere living={emptyLiving} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows running costs, comfort, flags and publisher notes", () => {
    renderWithIntl(
      <LivingHere
        living={{
          electricity_supply: "edl_plus_generator", generator_amps: 10, electricity_usd_month: 90,
          water_source: "municipal", water_usd_month: 12, sewage: "public_network", parking_spots: 1,
          solar_ready: true, elevator_backup: false, winter_comfort: "cold", summer_comfort: "cool",
          highlights: ["Sunny"], things_to_know: ["Tank on roof"],
        }}
      />,
    );
    const section = screen.getByTestId("living-here");
    expect(section).toHaveTextContent("EDL + generator · 10 A subscription · ~$90/month electricity");
    expect(section).toHaveTextContent("Municipal (state) water · ~$12/month water");
    expect(section).toHaveTextContent("Public sewage network");
    expect(section).toHaveTextContent("Cold");
    expect(section).toHaveTextContent("Cool");
    expect(section).toHaveTextContent("1 parking spot");
    expect(section).toHaveTextContent("Roof/balcony can take solar panels");
    expect(section).toHaveTextContent("Elevator stops during power cuts");
    expect(screen.getByText("Sunny")).toBeInTheDocument();
    expect(screen.getByText("Tank on roof")).toBeInTheDocument();
  });

  it("handles partial data in Arabic", () => {
    renderWithIntl(
      <LivingHere
        living={{ ...emptyLiving, electricity_usd_month: 40, water_source: "tanker", solar_ready: false,
          elevator_backup: true, parking_spots: 0 }}
      />,
      "ar",
    );
    const section = screen.getByTestId("living-here");
    expect(section).toHaveTextContent("العيش هنا");
    expect(section).toHaveTextContent("صهاريج مياه");
    expect(section).toHaveTextContent("لا يمكن تركيب ألواح شمسية");
    expect(section).toHaveTextContent("المصعد يعمل عند انقطاع الكهرباء");
    expect(section).toHaveTextContent("لا يوجد موقف");
  });
});

describe("AreaInfo", () => {
  it("shows curated facts with date and source", () => {
    renderWithIntl(<AreaInfo area={area} />);
    const s = screen.getByTestId("area-info");
    expect(s).toHaveTextContent("About the neighbourhood · Hamra");
    expect(s).toHaveTextContent("4/5");
    expect(s).toHaveTextContent("3 theft reports (12 months)");
    expect(s).toHaveTextContent("Daily");
    expect(s).toHaveTextContent("Low");
    expect(s).toHaveTextContent("Bars on weekends");
    expect(s).toHaveTextContent("Source: Field visit");
    expect(s).toHaveTextContent("Lively student area");
    expect(s).not.toHaveTextContent("Demo values");
  });

  it("marks demo profiles and falls back between languages", () => {
    renderWithIntl(
      <AreaInfo
        area={{ ...area, is_demo: true, summary_ar: null, noise_notes_ar: null, source_note: null,
          safety_score: null, quiet_score: null, garbage_collection: null, flood_risk: null, theft_reports_12m: null }}
      />,
      "ar",
    );
    const s = screen.getByTestId("area-info");
    expect(s).toHaveTextContent("قيم تجريبية");
    expect(s).toHaveTextContent("الحمرا");
    expect(s).toHaveTextContent("Lively student area"); // English summary when no Arabic one exists
    expect(s).toHaveTextContent("Bars on weekends");
  });
});
