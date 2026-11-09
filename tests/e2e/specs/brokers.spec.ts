import { expect, test } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_SUPERUSER_EMAIL ?? "superuser@example.com";
const ADMIN_PASSWORD = process.env.E2E_SUPERUSER_PASSWORD ?? "e2e-superuser-password";

// Demo agencies are seeded as verified, so their listings carry the badge and link to an agency page.

test("agency page lists its homes, and each home links back with the verified badge", async ({ page }) => {
  await page.goto("/en/agencies/cedar-homes-demo");
  const agency = page.getByTestId("agency-page");
  await expect(agency).toContainText("Cedar Homes");
  await expect(agency.getByTestId("agency-verified")).toBeVisible();
  const tile = agency.getByTestId("listing-tile").first();
  await expect(tile.getByTestId("verified-badge")).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);

  await tile.click();
  const publisher = page.getByTestId("publisher");
  await expect(publisher).toContainText("Broker");
  await expect(publisher.getByTestId("publisher-verified")).toBeVisible();
  await publisher.getByRole("link").click();
  await expect(page).toHaveURL(/\/en\/agencies\/cedar-homes-demo$/);
});

test("unknown agency is a 404", async ({ page }) => {
  const res = await page.goto("/en/agencies/no-such-agency");
  expect(res?.status()).toBe(404);
});

test("admin verifies agencies and reads Hormozi terms explained", async ({ page }) => {
  await page.goto("/en/login");
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/en\/dashboard/);

  await page.goto("/en/admin/agencies");
  const row = page.getByTestId("agency-row").first();
  await expect(row).toBeVisible();
  const toggle = row.getByTestId("agency-toggle");
  const before = await toggle.textContent();
  await toggle.click();
  await expect(toggle).not.toHaveText(before ?? "");
  await toggle.click(); // put it back for the other tests
  await expect(toggle).toHaveText(before ?? "");

  await page.goto("/en/admin/growth");
  await page.getByTestId("info-valueEquation").click();
  await expect(page.getByRole("dialog")).toContainText("Dream outcome");
});
