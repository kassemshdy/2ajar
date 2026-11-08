import { expect, test } from "@playwright/test";

// The API under test is started with SUPERUSER_EMAIL / SUPERUSER_PASSWORD (see CI and README).
const ADMIN_EMAIL = process.env.E2E_SUPERUSER_EMAIL ?? "superuser@example.com";
const ADMIN_PASSWORD = process.env.E2E_SUPERUSER_PASSWORD ?? "e2e-superuser-password";

test("user reports a bug from the floating button, superuser triages and replies @mutating", async ({ page, browser }, info) => {
  const stamp = `${Date.now()}-${info.project.name}`;
  const title = `Map stays grey ${stamp}`;

  // 1. Visitors do not see the button; a signed-in user does
  await page.goto("/en");
  await expect(page.getByTestId("ask-box")).toBeVisible();
  await expect(page.getByTestId("bug-button")).toHaveCount(0);
  await page.goto("/en/register");
  await page.getByLabel("Looking for a home").check();
  await page.getByLabel("Full name").fill("Bug Reporter");
  await page.getByLabel("Email").fill(`e2e-reporter-${stamp}@example.com`);
  await page.getByLabel("Password").fill("e2e-password-123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/en\/listings/);

  await page.getByTestId("bug-button").click();
  const dialog = page.getByTestId("bug-dialog");
  await dialog.getByLabel("Short summary").fill(title);
  await dialog.getByLabel("What happened? What did you expect?").fill("On the listings page the map never loads.");
  await dialog.getByTestId("bug-submit").click();
  await expect(page.getByTestId("bug-sent")).toContainText("Ticket #");
  await page.getByRole("link", { name: "View ticket" }).click();
  await expect(page.getByTestId("ticket-thread")).toContainText(title);
  const ticketUrl = page.url();

  // 2. Superuser (bootstrapped from env) triages it in the back office
  const adminCtx = await browser.newContext({ ...info.project.use });
  const admin = await adminCtx.newPage();
  await admin.goto("/en/login");
  await admin.getByLabel("Email").fill(ADMIN_EMAIL);
  await admin.getByLabel("Password").fill(ADMIN_PASSWORD);
  await admin.getByRole("button", { name: "Log in" }).click();
  await expect(admin).toHaveURL(/\/en\/dashboard/);
  await admin.goto("/en/admin/tickets");
  await admin.getByLabel("Search").fill(stamp);
  await admin.getByRole("button", { name: "Search" }).click();
  await admin.getByTestId("admin-ticket-row").filter({ hasText: title }).click();
  const panel = admin.getByTestId("triage-panel");
  await panel.getByLabel("Status").selectOption("in_progress");
  await expect(panel.getByLabel("Status")).toHaveValue("in_progress");
  await panel.getByRole("button", { name: "Assign to me" }).click();
  await admin.getByLabel("Internal note (staff only)").uncheck();
  await admin.getByLabel("Reply").fill("Thanks — we are on it.");
  await admin.getByRole("button", { name: "Send" }).click();
  await expect(admin.getByTestId("ticket-comments")).toContainText("Thanks — we are on it.");
  await admin.getByLabel("Internal note (staff only)").check();
  await admin.getByLabel("Reply").fill("Internal: likely tile server CSP");
  await admin.getByRole("button", { name: "Send" }).click();
  await expect(admin.getByTestId("ticket-comments")).toContainText("Internal: likely tile server CSP");

  // User management is reachable for the superuser
  await admin.goto("/en/admin/users");
  await expect(admin.getByTestId("admin-users")).toBeVisible();
  await adminCtx.close();

  // 3. Reporter sees the public reply but not the internal note
  await page.goto(ticketUrl);
  await expect(page.getByTestId("ticket-comments")).toContainText("Thanks — we are on it.");
  await expect(page.getByTestId("ticket-comments")).not.toContainText("Internal:");
  await expect(page.getByText("In progress")).toBeVisible();
  await page.goto("/en/admin/tickets");
  await expect(page.getByText("You do not have access to this area.")).toBeVisible();
});
