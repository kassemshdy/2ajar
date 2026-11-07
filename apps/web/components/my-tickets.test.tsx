import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { routerMock } from "@/test/setup";
import { seekerUser, staffUser, ticket } from "@/test/support-fixtures";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { MyTickets, TicketDetail } from "./my-tickets";

beforeEach(() => vi.clearAllMocks());

describe("MyTickets", () => {
  it("lists my tickets with status", async () => {
    mockFetch({
      "GET /api/v1/me/tickets": [ticket(), ticket({ id: "t-2", number: 8, title: "Typo", status: "resolved", comment_count: 2 })],
      "GET /api/v1/me": seekerUser,
    });
    renderWithIntl(<MyTickets />);
    expect(await screen.findByText("Map is grey")).toBeInTheDocument();
    expect(screen.getByText("Resolved")).toBeInTheDocument();
    expect(screen.getByText(/2 replies/)).toBeInTheDocument();
    expect(screen.getByText("Typo").closest("a")).toHaveAttribute("href", "/tickets/t-2");
  });

  it("shows the empty state and redirects visitors", async () => {
    mockFetch({ "GET /api/v1/me/tickets": [], "GET /api/v1/me": seekerUser });
    renderWithIntl(<MyTickets />);
    expect(await screen.findByText("You have not reported anything yet.")).toBeInTheDocument();
    mockFetch({ "GET /api/v1/me": () => json({}, 401), "POST /api/v1/auth/refresh": 401 });
    renderWithIntl(<MyTickets />);
    await waitFor(() => expect(routerMock.replace).toHaveBeenCalledWith("/login"));
  });
});

describe("TicketDetail", () => {
  it("shows the conversation and lets the reporter reply", async () => {
    const withReply = ticket({
      comments: [
        { id: "c1", body: "Thanks, looking", is_internal: false, via: "web", author: { id: "staff-1", name: "Sara Staff" }, author_is_staff: true, created_at: "2026-11-01T11:00:00Z" },
        { id: "c2", body: "My answer", is_internal: false, via: "web", author: { id: "seek-1", name: "Lea Seeker" }, author_is_staff: false, created_at: "2026-11-01T12:00:00Z" },
      ],
      has_attachment: true,
    });
    const calls = mockFetch({
      "GET /api/v1/me": seekerUser,
      "GET /api/v1/tickets/t-1": ticket({ has_attachment: true }),
      "POST /api/v1/tickets/t-1/comments": withReply,
    });
    renderWithIntl(<TicketDetail id="t-1" />);
    expect(await screen.findByText("The map never loads on my phone.")).toBeInTheDocument();
    expect(screen.getByAltText("Screenshot")).toHaveAttribute("src", "/api/v1/tickets/t-1/attachment");
    expect(screen.queryByText("Internal note (staff only)")).not.toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Reply"), "My answer");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("2ajar team")).toBeInTheDocument();
    expect(screen.getByText("You")).toBeInTheDocument();
    expect(JSON.parse(calls.find((c) => c.method === "POST")!.init.body as string)).toEqual({ body: "My answer", is_internal: false });
  });

  it("staff see internal notes, MCP badges and can write internal notes", async () => {
    const internal = ticket({
      comments: [{ id: "c1", body: "Root cause: CSP", is_internal: true, via: "mcp", author: { id: "staff-1", name: "Sara Staff" }, author_is_staff: true, created_at: "2026-11-01T11:00:00Z" }],
    });
    const calls = mockFetch({
      "GET /api/v1/me": staffUser,
      "GET /api/v1/tickets/t-1": internal,
      "POST /api/v1/tickets/t-1/comments": () => json({ error: { code: "x", message: "Boom" } }, 500),
    });
    renderWithIntl(<TicketDetail id="t-1" />);
    expect(await screen.findByText("Root cause: CSP")).toBeInTheDocument();
    expect(screen.getByText("MCP")).toBeInTheDocument();
    const checkbox = await screen.findByRole("checkbox", { name: "Internal note (staff only)" });
    expect(checkbox).toBeChecked();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Reply"), "note");
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Boom")).toBeInTheDocument();
    expect(JSON.parse(calls.find((c) => c.method === "POST")!.init.body as string).is_internal).toBe(true);
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await user.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Network error. Check your connection.")).toBeInTheDocument();
  });

  it("shows not found", async () => {
    mockFetch({ "GET /api/v1/me": seekerUser });
    renderWithIntl(<TicketDetail id="nope" />);
    expect(await screen.findByText("Ticket not found.")).toBeInTheDocument();
  });
});
