import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { CsvImport } from "./csv-import";

const rows = [
  { row: 2, ok: true, listing_id: null, title: "Flat", errors: [] },
  { row: 3, ok: false, listing_id: null, title: null, errors: ["Unknown location 'x'"] },
];

describe("CsvImport", () => {
  it("previews then imports", async () => {
    const calls = mockFetch({
      "POST /api/v1/listings/import?dry_run=true": { dry_run: true, total: 2, valid: 1, created: 0, rows },
      "POST /api/v1/listings/import?dry_run=false": {
        dry_run: false, total: 2, valid: 1, created: 1,
        rows: [{ ...rows[0], listing_id: "new" }, rows[1]],
      },
    });
    renderWithIntl(<CsvImport />);
    expect(screen.getByRole("link", { name: /Download template/ })).toHaveAttribute(
      "href", "/api/v1/listings/import/template",
    );
    const user = userEvent.setup();
    expect(screen.getByTestId("csv-preview")).toBeDisabled();
    await user.upload(screen.getByTestId("csv-input"), new File(["a,b"], "l.csv", { type: "text/csv" }));
    await user.click(screen.getByTestId("csv-preview"));
    expect(await screen.findByTestId("csv-summary")).toHaveTextContent("1 of 2 rows are valid");
    expect(screen.getByText("Unknown location 'x'")).toBeInTheDocument();
    await user.click(screen.getByTestId("csv-confirm"));
    expect(await screen.findByTestId("csv-created")).toHaveTextContent("1 draft created");
    expect(screen.getByRole("link", { name: "Add photos" })).toHaveAttribute("href", "/dashboard/listings/new/edit");
    expect(calls.find((c) => c.method !== "GET")!.init.body).toBeInstanceOf(FormData);
  });

  it("explains when nothing is importable and shows errors", async () => {
    mockFetch({
      "POST /api/v1/listings/import?dry_run=true": { dry_run: true, total: 1, valid: 0, created: 0, rows: [rows[1]] },
    });
    renderWithIntl(<CsvImport />, "ar");
    const user = userEvent.setup();
    await user.upload(screen.getByTestId("csv-input"), new File(["a"], "l.csv", { type: "text/csv" }));
    await user.click(screen.getByTestId("csv-preview"));
    expect(await screen.findByText("لا توجد صفوف صالحة للاستيراد.")).toBeInTheDocument();

    mockFetch({
      "POST /api/v1/listings/import": () => json({ error: { code: "validation_error", message: "Missing columns: location" } }, 422),
    });
    await user.click(screen.getByTestId("csv-preview"));
    expect(await screen.findByText("Missing columns: location")).toBeInTheDocument();

    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await user.click(screen.getByTestId("csv-preview"));
    await waitFor(() => expect(screen.getByRole("status")).toBeInTheDocument());
  });
});
