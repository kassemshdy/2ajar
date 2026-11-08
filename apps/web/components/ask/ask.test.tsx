import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { AskResponse } from "@2ajar/contracts";
import { renderWithIntl } from "@/test/utils";
import { AskBox } from "./ask-box";
import { ReasonList } from "./reason-list";
import { filtersHref, Understood } from "./understood";

const suggestions = [{ id: "s1", text_en: "Quiet flat in Hamra", text_ar: "شقة هادئة في الحمرا" }];

function answer(over: Partial<AskResponse> = {}): AskResponse {
  return {
    query_id: "q1",
    understood: {
      transaction_type: "rent", property_type: null, location_slug: "hamra", location_name_en: "Hamra",
      location_name_ar: "الحمرا", price_min: null, price_max: 900, bedrooms_min: 2, bathrooms_min: null,
      furnished: null, parking_spots: null, sort: "newest",
      preferences: [{ key: "quiet", label_en: "Quiet area", label_ar: "منطقة هادئة" }],
    },
    summary_en: "2+ bedroom homes for rent in Hamra up to $900",
    summary_ar: "عقارات من 2 غرف نوم أو أكثر للإيجار في الحمرا",
    clarification_en: null, clarification_ar: null, relaxed: [], results: [], total: 0,
    ...over,
  };
}

describe("AskBox", () => {
  it("submits to the ask page and links suggestion chips", () => {
    renderWithIntl(<AskBox suggestions={suggestions} defaultQuery="hamra" />);
    const box = screen.getByLabelText(/Ask in plain words/);
    expect(box).toHaveValue("hamra");
    expect(box.closest("form")).toHaveAttribute("action", "/en/ask");
    expect(screen.getByTestId("ask-suggestion")).toHaveAttribute("href", "/en/ask?q=Quiet%20flat%20in%20Hamra");
  });

  it("uses Arabic suggestion text in Arabic and hides chips when there are none", () => {
    renderWithIntl(<AskBox suggestions={suggestions} />, "ar");
    expect(screen.getByTestId("ask-suggestion")).toHaveTextContent("شقة هادئة في الحمرا");
    expect(screen.getByRole("button", { name: "اسأل" })).toBeInTheDocument();
    renderWithIntl(<AskBox />);
    expect(screen.getAllByTestId("ask-box")[1]).not.toHaveTextContent("Try:");
  });
});

describe("ReasonList", () => {
  it("shows status and source of every reason", () => {
    renderWithIntl(
      <ReasonList
        reasons={[
          { key: "location", label_en: "Hamra", label_ar: "الحمرا", status: "match", source: "filter" },
          { key: "electricity_24_7", label_en: "24/7 electricity", label_ar: "كهرباء", status: "miss", source: "listing" },
          { key: "quiet", label_en: "Quiet area", label_ar: "منطقة هادئة", status: "unknown", source: "area" },
        ]}
      />,
    );
    const items = within(screen.getByTestId("reasons")).getAllByRole("listitem");
    expect(items.map((i) => i.dataset.status)).toEqual(["match", "miss", "unknown"]);
    expect(items[0]).toHaveTextContent("matches your search");
    expect(items[1]).toHaveTextContent("reported by the publisher");
    expect(items[2]).toHaveTextContent("Not reported");
    expect(items[2]).toHaveTextContent("area info by the 2ajar team");
  });

  it("renders Arabic labels and nothing for an empty list", () => {
    renderWithIntl(
      <ReasonList reasons={[{ key: "quiet", label_en: "Quiet", label_ar: "منطقة هادئة", status: "match", source: "area" }]} />,
      "ar",
    );
    expect(screen.getByTestId("reasons")).toHaveTextContent("منطقة هادئة");
    const { container } = renderWithIntl(<ReasonList reasons={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("Understood", () => {
  it("summarises, lists preferences and links to equivalent filters", () => {
    renderWithIntl(<Understood answer={answer()} />);
    expect(screen.getByText(/2\+ bedroom homes for rent in Hamra/)).toBeInTheDocument();
    expect(screen.getByText("Quiet area")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Refine with filters" })).toHaveAttribute(
      "href",
      "/en/listings?transaction_type=rent&location=hamra&price_max=900&bedrooms_min=2",
    );
    expect(screen.queryByTestId("ask-clarification")).not.toBeInTheDocument();
  });

  it("shows clarifications and relaxed constraints in Arabic", () => {
    renderWithIntl(
      <Understood
        answer={answer({
          clarification_en: "Which area?", clarification_ar: "أي منطقة؟",
          relaxed: [{ key: "budget", label_en: "Budget raised to $1,080", label_ar: "رفعنا الميزانية" }],
        })}
      />,
      "ar",
    );
    expect(screen.getByTestId("ask-clarification")).toHaveTextContent("أي منطقة؟");
    expect(screen.getByTestId("ask-relaxed")).toHaveTextContent("رفعنا الميزانية");
    expect(screen.getByText("منطقة هادئة")).toBeInTheDocument();
  });

  it("builds filter links without empty values", () => {
    const u = answer().understood;
    expect(filtersHref({ ...u, transaction_type: null, location_slug: null, price_max: null, bedrooms_min: 0 }, "ar")).toBe(
      "/ar/listings",
    );
    expect(
      filtersHref(
        { ...u, price_min: 500, furnished: "furnished", property_type: "studio", sort: "price_asc", bedrooms_min: null },
        "en",
      ),
    ).toBe(
      "/en/listings?transaction_type=rent&location=hamra&price_min=500&price_max=900&furnished=furnished&property_type=studio&sort=price_asc",
    );
  });
});
