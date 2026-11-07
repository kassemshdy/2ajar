import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { seekerUser, ticket } from "@/test/support-fixtures";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { BugReportButton, captureContext } from "./bug-report-button";

describe("BugReportButton", () => {
  it("is hidden for visitors", async () => {
    const calls = mockFetch({ "GET /api/v1/me": () => json({}, 401), "POST /api/v1/auth/refresh": 401 });
    renderWithIntl(<BugReportButton />);
    await waitFor(() => expect(calls.some((c) => c.url.endsWith("/auth/refresh"))).toBe(true));
    expect(screen.queryByTestId("bug-button")).not.toBeInTheDocument();
  });

  it("files a ticket with page context and an optional screenshot", async () => {
    const calls = mockFetch({
      "GET /api/v1/me": seekerUser,
      "POST /api/v1/tickets/t-1/attachment": ticket({ has_attachment: true }),
      "POST /api/v1/tickets": () => json(ticket(), 201),
    });
    renderWithIntl(<BugReportButton />);
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("bug-button"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("Type"), "feedback");
    await user.type(screen.getByLabelText("Short summary"), "Map is grey");
    await user.type(screen.getByLabelText("What happened? What did you expect?"), "The map never loads on my phone.");
    await user.upload(screen.getByLabelText("Screenshot (optional)"), new File(["x"], "s.png", { type: "image/png" }));
    await user.click(screen.getByTestId("bug-submit"));
    expect(await screen.findByTestId("bug-sent")).toHaveTextContent("Ticket #7");
    const body = JSON.parse(calls.find((c) => c.url === "/api/v1/tickets")!.init.body as string);
    expect(body).toMatchObject({ category: "feedback", title: "Map is grey", page_url: window.location.href });
    expect(body.context).toMatchObject({ locale: "en", online: true });
    expect(calls.some((c) => c.url.endsWith("/attachment"))).toBe(true);
    expect(screen.getByRole("link", { name: "View ticket" })).toHaveAttribute("href", "/tickets/t-1");
    await user.click(screen.getByRole("link", { name: "View ticket" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows API errors and can be cancelled", async () => {
    mockFetch({
      "GET /api/v1/me": seekerUser,
      "POST /api/v1/tickets": () => json({ error: { code: "rate_limited", message: "Too many requests" } }, 429),
    });
    renderWithIntl(<BugReportButton />, "ar");
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("bug-button"));
    await user.type(screen.getByLabelText("ملخص قصير"), "خريطة لا تعمل");
    await user.type(screen.getByLabelText("ماذا حدث؟ وماذا كنت تتوقع؟"), "الخريطة لا تظهر أبداً");
    await user.click(screen.getByTestId("bug-submit"));
    expect(await screen.findByText("Too many requests")).toBeInTheDocument();
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await user.click(screen.getByTestId("bug-submit"));
    expect(await screen.findByText("خطأ في الشبكة. تحقّق من اتصالك.")).toBeInTheDocument();
    const [, cancelButton] = screen.getAllByRole("button", { name: "إلغاء" }); // [X icon, Cancel]
    await user.click(cancelButton);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("closes with Escape and captures context", async () => {
    mockFetch({ "GET /api/v1/me": seekerUser });
    renderWithIntl(<BugReportButton />);
    const user = userEvent.setup();
    await user.click(await screen.findByTestId("bug-button"));
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(captureContext("ar")).toMatchObject({ locale: "ar", viewport: expect.stringMatching(/^\d+x\d+$/) });
  });
});
