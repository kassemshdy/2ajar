import { expect, test } from "@playwright/test";

// Runs against demo data (CI seeds it with DEMO_MODE=true): listings and area profiles are synthetic.

async function expectNoHorizontalScroll(page: import("@playwright/test").Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test("plain-text search from the home page explains every result", async ({ page }) => {
  await page.goto("/en");
  await page.getByLabel(/Ask in plain words/).fill("Something in Jounieh with 24/7 electricity, quiet and safe");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page).toHaveURL(/\/en\/ask\?q=/);
  const understood = page.getByTestId("ask-understood");
  await expect(understood).toContainText("Jounieh");
  await expect(understood).toContainText("24/7 electricity");
  const results = page.getByTestId("ask-result");
  await expect(results.first()).toBeVisible();
  const reasons = results.first().getByTestId("reasons");
  await expect(reasons).toContainText("Jounieh");
  await expect(reasons.locator("[data-status]").first()).toBeVisible();
  await expectNoHorizontalScroll(page);

  // Detail page shows publisher-reported living factors and the (demo-labelled) area profile.
  // Only seeded demo listings (with living factors) exist in Jounieh; other specs create theirs in Beirut.
  await results.filter({ hasText: "DEMO" }).first().getByTestId("listing-card").click();
  await expect(page.getByTestId("living-here")).toBeVisible();
  await expect(page.getByTestId("area-info")).toContainText("Demo values");
});

test("suggestion chips and Arabic questions work right-to-left", async ({ page }) => {
  await page.goto("/ar");
  const chip = page.getByTestId("ask-suggestion").first();
  await expect(chip).toBeVisible();
  await chip.click();
  await expect(page).toHaveURL(/\/ar\/ask\?q=/);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByTestId("ask-understood")).toContainText("ما فهمناه");

  await page.goto(`/ar/ask?q=${encodeURIComponent("بدي شقة بالأشرفية حتى 1500 دولار مع موقف")}`);
  await expect(page.getByTestId("ask-understood")).toContainText("الأشرفية");
  await expect(page.getByTestId("ask-count")).toBeVisible();
  await expectNoHorizontalScroll(page);
});

test("vague questions get a clarifying hint", async ({ page }) => {
  await page.goto("/en/ask?q=hello");
  await expect(page.getByTestId("ask-clarification")).toContainText("Which area");
});
