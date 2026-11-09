import { expect, test } from "@playwright/test";

const ADMIN_EMAIL = process.env.E2E_SUPERUSER_EMAIL ?? "superuser@example.com";
const ADMIN_PASSWORD = process.env.E2E_SUPERUSER_PASSWORD ?? "e2e-superuser-password";

test("admin sees growth: value equation, next steps, playbook and business model", async ({ page }) => {
  await page.goto("/en/login");
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Log in" }).click();
  await expect(page).toHaveURL(/\/en\/dashboard/);

  await page.goto("/en/admin/growth");
  await expect(page.getByTestId("north-star")).toBeVisible();
  await expect(page.getByTestId("value-renters")).toContainText("Dream outcome");
  await expect(page.getByTestId("value-owners")).toContainText("Effort");

  await page.getByRole("tab", { name: /Next steps/ }).click();
  await expect(page.getByTestId("recommendations")).toBeVisible();

  await page.getByRole("tab", { name: /90-day playbook/ }).click();
  await expect(page.getByTestId("playbook")).toContainText("Days 1–30");

  await page.getByRole("tab", { name: /Business model/ }).click();
  await expect(page.getByTestId("canvas")).toContainText("Value propositions");
  await expect(page.getByTestId("revenue-sim")).toContainText("Total / month");

  await page.goto("/ar/admin/growth");
  await expect(page.getByTestId("north-star")).toContainText("النجم الشمالي");
});
