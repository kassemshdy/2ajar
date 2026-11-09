import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { adminRow, adminUser, seekerUser, staffUser, ticket } from "@/test/support-fixtures";
import { json, mockFetch, renderWithIntl } from "@/test/utils";
import { AdminShell } from "./admin-shell";
import { AdminTicketDetail, AdminTickets } from "./admin-tickets";
import { AdminUsers } from "./admin-users";

const catalog = [
  { key: "tickets.read", grantable: true, roles: ["staff", "platform_admin"] },
  { key: "mcp.access", grantable: true, roles: ["staff", "platform_admin"] },
  { key: "users.manage", grantable: false, roles: ["platform_admin"] },
];

describe("AdminShell", () => {
  it("blocks users without the permission and shows tabs for staff", async () => {
    mockFetch({ "GET /api/v1/me": seekerUser });
    renderWithIntl(<AdminShell need="tickets.read">secret</AdminShell>);
    expect(await screen.findByText("You do not have access to this area.")).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();

    mockFetch({ "GET /api/v1/me": staffUser });
    renderWithIntl(<AdminShell need="tickets.read">secret</AdminShell>);
    expect(await screen.findByText("secret")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Tickets" })).toHaveAttribute("href", "/admin/tickets");
    expect(screen.getByRole("link", { name: "API tokens" })).toBeInTheDocument();
  });
});

describe("AdminUsers", () => {
  it("searches, filters and edits a user's role, status and permissions", async () => {
    let row = adminRow();
    const calls = mockFetch({
      "GET /api/v1/me": adminUser,
      "GET /api/v1/admin/permissions": catalog,
      "GET /api/v1/admin/users": () => json({ items: [row], total: 1, page: 1, page_size: 50 }),
      "PATCH /api/v1/admin/users/u-2": (_url, init) => {
        const body = JSON.parse(init.body as string);
        row = { ...row, ...body, permissions: body.extra_permissions };
        return json(row);
      },
    });
    renderWithIntl(<AdminUsers />);
    expect(await screen.findByText("Bob Broker")).toBeInTheDocument();
    expect(screen.getByText("Cedar")).toBeInTheDocument();
    expect(screen.getByText(/never/)).toBeInTheDocument();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Search by e-mail or name"), "bob");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await user.selectOptions(screen.getByLabelText("Role"), "broker");
    await waitFor(() => expect(calls.some((c) => c.url.includes("q=bob") && c.url.includes("role=broker"))).toBe(true));

    await user.click(screen.getByRole("button", { name: "Edit" }));
    const editor = screen.getByTestId("user-editor");
    expect(within(editor).queryByText("users.manage")).not.toBeInTheDocument(); // not grantable
    await user.click(within(editor).getByRole("checkbox", { name: /tickets\.read/ }));
    await user.click(within(editor).getByRole("checkbox", { name: "Active" }));
    await user.click(within(editor).getByTestId("verified-owner"));
    await user.click(screen.getByTestId("user-save"));
    expect(await within(editor).findByText("Saved")).toBeInTheDocument();
    const patch = calls.find((c) => c.method === "PATCH")!;
    expect(JSON.parse(patch.init.body as string)).toEqual({
      role: "broker",
      is_active: false,
      is_verified: true,
      extra_permissions: ["tickets.read"],
    });
    // Choosing the staff role implies its permissions (checked and locked)
    await user.selectOptions(within(editor).getByLabelText("Role"), "staff");
    expect(within(editor).getByRole("checkbox", { name: /mcp\.access/ })).toBeDisabled();
  });

  it("shows server errors from the guards", async () => {
    mockFetch({
      "GET /api/v1/me": adminUser,
      "GET /api/v1/admin/permissions": catalog,
      "GET /api/v1/admin/users": { items: [adminRow({ id: "u-9", role: "platform_admin" })], total: 1, page: 1, page_size: 50 },
      "PATCH /api/v1/admin/users/u-9": () =>
        json({ error: { code: "conflict", message: "At least one active platform admin must remain" } }, 409),
    });
    renderWithIntl(<AdminUsers />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    await user.click(screen.getByTestId("user-save"));
    expect(await screen.findByText("At least one active platform admin must remain")).toBeInTheDocument();
  });

  it("locks your own role and status", async () => {
    mockFetch({
      "GET /api/v1/me": adminUser,
      "GET /api/v1/admin/permissions": catalog,
      "GET /api/v1/admin/users": { items: [adminRow({ id: "admin-1", role: "platform_admin" })], total: 1, page: 1, page_size: 50 },
    });
    renderWithIntl(<AdminUsers />);
    await userEvent.setup().click(await screen.findByRole("button", { name: "Edit" }));
    const editor = screen.getByTestId("user-editor");
    expect(within(editor).getByLabelText("Role")).toBeDisabled();
    expect(within(editor).getByRole("checkbox", { name: "Active" })).toBeDisabled();
  });

  it("is read-only for staff (users.read without users.manage)", async () => {
    mockFetch({
      "GET /api/v1/me": staffUser,
      "GET /api/v1/admin/permissions": catalog,
      "GET /api/v1/admin/users": { items: [adminRow()], total: 1, page: 1, page_size: 50 },
    });
    renderWithIntl(<AdminUsers />);
    await userEvent.setup().click(await screen.findByRole("button", { name: "Edit" }));
    expect(screen.queryByTestId("user-save")).not.toBeInTheDocument();
    expect(within(screen.getByTestId("user-editor")).getByLabelText("Role")).toBeDisabled();
  });
});

describe("AdminTickets", () => {
  it("filters the queue", async () => {
    const calls = mockFetch({
      "GET /api/v1/me": staffUser,
      "GET /api/v1/admin/tickets": {
        items: [{ ...ticket(), assignee: { id: "staff-1", name: "Sara Staff" }, comment_count: 3 }],
        total: 1,
        page: 1,
        page_size: 50,
      },
    });
    renderWithIntl(<AdminTickets />);
    expect(await screen.findByText("Map is grey")).toBeInTheDocument();
    expect(screen.getByText(/Sara Staff/)).toBeInTheDocument();
    expect(screen.getByText("Map is grey").closest("a")).toHaveAttribute("href", "/admin/tickets/t-1");
    const user = userEvent.setup();
    await user.selectOptions(screen.getByLabelText("Status"), "");
    await user.selectOptions(screen.getByLabelText("Priority"), "urgent");
    await user.type(screen.getByLabelText("Search"), "map");
    await user.click(screen.getByRole("button", { name: "Search" }));
    await waitFor(() =>
      expect(calls.some((c) => c.url.includes("priority=urgent") && c.url.includes("q=map") && !c.url.includes("status="))).toBe(true),
    );
  });

  it("triages a ticket", async () => {
    let current = ticket();
    const calls = mockFetch({
      "GET /api/v1/me": staffUser,
      "GET /api/v1/tickets/t-1": () => json(current),
      "PATCH /api/v1/admin/tickets/t-1": (_u, init) => {
        const body = JSON.parse(init.body as string);
        current = {
          ...current,
          ...body,
          assignee: body.assignee_user_id ? { id: "staff-1", name: "Sara Staff" } : current.assignee,
        };
        return json(current);
      },
    });
    renderWithIntl(<AdminTicketDetail id="t-1" />);
    const panel = await screen.findByTestId("triage-panel");
    expect(screen.getByText("lea@example.com")).toBeInTheDocument();
    expect(screen.getByText("390x844")).toBeInTheDocument();
    const user = userEvent.setup();
    await user.selectOptions(within(panel).getByLabelText("Status"), "in_progress");
    await user.selectOptions(within(panel).getByLabelText("Priority"), "high");
    await user.click(within(panel).getByRole("button", { name: "Assign to me" }));
    expect(await within(panel).findByText("Sara Staff")).toBeInTheDocument();
    const bodies = calls.filter((c) => c.method === "PATCH").map((c) => JSON.parse(c.init.body as string));
    expect(bodies).toEqual([{ status: "in_progress" }, { priority: "high" }, { assignee_user_id: "staff-1" }]);
  });

  it("reports errors", async () => {
    mockFetch({
      "GET /api/v1/me": staffUser,
      "GET /api/v1/tickets/t-1": ticket(),
      "PATCH /api/v1/admin/tickets/t-1": () => json({ error: { code: "x", message: "Nope" } }, 422),
    });
    renderWithIntl(<AdminTicketDetail id="t-1" />);
    const panel = await screen.findByTestId("triage-panel");
    await userEvent.setup().selectOptions(within(panel).getByLabelText("Status"), "closed");
    expect(await within(panel).findByText("Nope")).toBeInTheDocument();
    mockFetch({ "GET /api/v1/me": staffUser });
    renderWithIntl(<AdminTicketDetail id="missing" />);
    expect(await screen.findByText("no mock")).toBeInTheDocument();
  });
});
