import { expect, test } from "@playwright/test";

// Demo data (CI seeds it with DEMO_MODE=true) includes chalets per night and day-use places per hour.

async function expectNoHorizontalScroll(page: import("@playwright/test").Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test("home shows Airbnb-style rows and a chalet opens with its nightly price", async ({ page }) => {
  await page.goto("/ar");
  await expect(page.getByTestId("category").first()).toBeVisible();
  await expect(page.getByTestId("row-recent")).toBeVisible();
  const nights = page.getByTestId("row-nights");
  await expect(nights).toBeVisible();
  await expectNoHorizontalScroll(page);

  await nights.getByTestId("listing-tile").first().click();
  await expect(page.getByTestId("listing-detail")).toBeVisible();
  await expect(page.getByTestId("listing-price")).toContainText(/\/(ليلة|أسبوع)/);
  await expectNoHorizontalScroll(page);
});

test("stay filter and category search are rentals of the right length", async ({ page }) => {
  await page.goto("/en/listings?stay=hours");
  const tiles = page.getByTestId("listing-tile");
  await expect(tiles.first()).toBeVisible();
  for (const text of await tiles.allTextContents()) expect(text).toMatch(/\/(hour|day)/);

  await page.goto("/en");
  await page.getByTestId("category").filter({ hasText: "Chalets" }).click();
  await expect(page).toHaveURL(/\/en\/ask\?q=chalet/);
  await expect(page.getByTestId("ask-result").first()).toContainText("Chalet");
});

test("a visitor saves a home with the heart and finds it under Saved @mutating", async ({ page }, info) => {
  const email = `saver-${Date.now()}-${info.project.name}@example.com`;
  await page.goto("/en/register");
  await page.getByLabel("Full name").fill("Heart Tester");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("correct-horse-battery");
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page).toHaveURL(/\/en\/dashboard$/);

  await page.goto("/en/listings?stay=nights");
  const first = page.getByTestId("listing-tile").first();
  const heart = first.getByTestId("favorite-button");
  await heart.click();
  await expect(heart).toHaveAttribute("aria-pressed", "true");

  await page.getByTestId("nav-saved").click();
  await expect(page).toHaveURL(/\/en\/saved$/);
  await expect(page.getByTestId("saved-grid").getByTestId("listing-tile")).toHaveCount(1);
  await page.getByTestId("saved-grid").getByTestId("favorite-button").click();
  await expect(page.getByTestId("saved-empty")).toBeVisible();
});
