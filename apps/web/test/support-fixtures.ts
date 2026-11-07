import type { AdminUser, Ticket, User } from "@2ajar/contracts";

export const staffUser: User = {
  id: "staff-1",
  email: "staff@example.com",
  full_name: "Sara Staff",
  phone_e164: null,
  role: "staff",
  locale: "en",
  memberships: [],
  permissions: ["analytics.read", "listings.moderate", "mcp.access", "tickets.manage", "tickets.read", "users.read"],
};

export const adminUser: User = { ...staffUser, id: "admin-1", role: "platform_admin", full_name: "Ada Admin",
  permissions: [...staffUser.permissions, "users.manage"] };

export const seekerUser: User = { ...staffUser, id: "seek-1", role: "seeker", full_name: "Lea Seeker", permissions: [] };

export function ticket(over: Partial<Ticket> = {}): Ticket {
  return {
    id: "t-1",
    number: 7,
    title: "Map is grey",
    category: "bug",
    status: "open",
    priority: "normal",
    reporter: { id: "seek-1", name: "Lea Seeker", email: "lea@example.com" },
    assignee: null,
    comment_count: 0,
    created_at: "2026-11-01T10:00:00Z",
    updated_at: "2026-11-01T10:00:00Z",
    description: "The map never loads on my phone.",
    page_url: "https://2ajar.test/en/listings/1",
    context: { viewport: "390x844", locale: "en" },
    has_attachment: false,
    resolved_at: null,
    comments: [],
    ...over,
  };
}

export function adminRow(over: Partial<AdminUser> = {}): AdminUser {
  return {
    id: "u-2",
    email: "broker@example.com",
    full_name: "Bob Broker",
    phone_e164: null,
    role: "broker",
    is_active: true,
    is_demo: false,
    extra_permissions: [],
    permissions: [],
    memberships: [{ organization_id: "o-1", organization_name: "Cedar", role: "agency_admin" }],
    created_at: "2026-11-01T10:00:00Z",
    last_login_at: null,
    ...over,
  };
}
