import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { ContactPanel } from "./contact-panel";

const ID = "abc";

async function fillLead() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Your name"), "Lea");
  await user.type(screen.getByLabelText("Phone (WhatsApp)"), "03 123 456");
  await user.type(screen.getByLabelText("Email (optional)"), "lea@example.com");
  await user.type(screen.getByLabelText("Message (optional)"), "Hello");
  return user;
}

describe("ContactPanel", () => {
  it("records a view and submits a consented lead", async () => {
    const calls = mockFetch({
      [`POST /api/v1/listings/${ID}/view`]: 204,
      [`POST /api/v1/listings/${ID}/leads`]: { id: "l1", deduplicated: false },
    });
    renderWithIntl(<ContactPanel listingId={ID} consentVersion="v1" />);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/view"))).toBe(true));
    const user = await fillLead();
    await user.click(screen.getByTestId("lead-consent"));
    await user.click(screen.getByRole("button", { name: "Send my details" }));
    expect(await screen.findByTestId("lead-success")).toHaveTextContent("Thank you");
    const lead = calls.find((c) => c.url.endsWith("/leads"))!;
    expect(JSON.parse(lead.init.body as string)).toEqual({
      name: "Lea",
      phone: "03 123 456",
      email: "lea@example.com",
      message: "Hello",
      consent: true,
      consent_text_version: "v1",
    });
  });

  it("requires the consent checkbox before submitting", async () => {
    const calls = mockFetch({ [`POST /api/v1/listings/${ID}/view`]: 204 });
    renderWithIntl(<ContactPanel listingId={ID} consentVersion="v1" />);
    expect(screen.getByTestId("lead-consent")).toBeRequired();
    // Bypass native validation to prove the payload would carry consent=false (server rejects it).
    mockFetch({
      [`POST /api/v1/listings/${ID}/leads`]: () =>
        json({ error: { code: "validation_error", message: "Explicit consent is required" } }, 422),
    });
    fireEvent.submit(screen.getByTestId("lead-form"));
    expect(await screen.findByText("Explicit consent is required")).toBeInTheDocument();
    expect(calls.every((c) => !c.url.endsWith("/leads"))).toBe(true);
  });

  it("shows the duplicate message", async () => {
    mockFetch({
      [`POST /api/v1/listings/${ID}/view`]: 204,
      [`POST /api/v1/listings/${ID}/leads`]: { id: "l1", deduplicated: true },
    });
    renderWithIntl(<ContactPanel listingId={ID} consentVersion="v1" />);
    const user = await fillLead();
    await user.click(screen.getByTestId("lead-consent"));
    await user.click(screen.getByRole("button", { name: "Send my details" }));
    expect(await screen.findByTestId("lead-success")).toHaveTextContent("already contacted");
  });

  it("opens WhatsApp through the tracked endpoint and reports errors", async () => {
    const assigned: string[] = [];
    Object.defineProperty(window, "location", {
      configurable: true,
      value: { set href(v: string) { assigned.push(v); }, get href() { return "http://x/"; } },
    });
    const calls = mockFetch({
      [`POST /api/v1/listings/${ID}/view`]: 204,
      [`POST /api/v1/listings/${ID}/contact/whatsapp`]: { url: "https://wa.me/961?text=hi" },
    });
    renderWithIntl(<ContactPanel listingId={ID} consentVersion="v1" />, "ar");
    await userEvent.click(screen.getByTestId("whatsapp-button"));
    await waitFor(() => expect(assigned).toEqual(["https://wa.me/961?text=hi"]));
    expect(calls.find((c) => c.url.includes("whatsapp"))!.url).toContain("locale=ar");

    mockFetch({
      [`POST /api/v1/listings/${ID}/contact/whatsapp`]: () =>
        json({ error: { code: "rate_limited", message: "Too many requests" } }, 429),
    });
    await userEvent.click(screen.getByTestId("whatsapp-button"));
    expect(await screen.findByText("Too many requests")).toBeInTheDocument();
  });

  it("shows a network error message", async () => {
    mockFetch({ [`POST /api/v1/listings/${ID}/view`]: 204 });
    renderWithIntl(<ContactPanel listingId={ID} consentVersion="v1" />);
    const user = await fillLead();
    await user.click(screen.getByTestId("lead-consent"));
    const { vi } = await import("vitest");
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await user.click(screen.getByRole("button", { name: "Send my details" }));
    expect(await screen.findByText("Network error. Check your connection.")).toBeInTheDocument();
  });
});
