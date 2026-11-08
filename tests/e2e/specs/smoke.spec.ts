import { expect, test } from "@playwright/test";

async function expectNoHorizontalScroll(page: import("@playwright/test").Page) {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
}

test("root opens the Arabic home (primary language)", async ({ page }) => {
  await page.goto("/");
  await expect(page).toHaveURL(/\/ar$/);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
});

test("English home with search", async ({ page }) => {
  await page.goto("/en");
  await expect(page.locator("html")).toHaveAttribute("dir", "ltr");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Find your next home");
  await expect(page.getByTestId("ask-box")).toBeVisible();
  await expect(page.getByTestId("category").first()).toBeVisible();
  await expectNoHorizontalScroll(page);
});

test("Arabic home renders right-to-left", async ({ page }) => {
  await page.goto("/ar");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.locator("html")).toHaveAttribute("lang", "ar");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("اعثر على منزلك");
  // In RTL the logo (first header item) sits on the right side.
  const logo = await page.getByLabel("2ajar home").boundingBox();
  const viewport = page.viewportSize()!;
  expect(logo!.x).toBeGreaterThan(viewport.width / 2);
  await expectNoHorizontalScroll(page);
});

test("search filters narrow results and Arabic search page works", async ({ page }) => {
  await page.goto("/en/listings?stay=months&location=beirut");
  await expect(page.getByTestId("results-count")).toBeVisible();
  const cards = page.getByTestId("listing-tile");
  const count = await cards.count();
  if (count > 0) {
    await cards.first().click();
    await expect(page.getByTestId("listing-detail")).toBeVisible();
    await expect(page.getByTestId("contact-panel")).toBeVisible();
  }
  await page.goto("/ar/listings");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(page.getByTestId("search-form")).toBeVisible();
  await expectNoHorizontalScroll(page);
});

test("language switch keeps the current page", async ({ page }) => {
  await page.goto("/en/listings");
  await page.getByTestId("locale-switch").click();
  await expect(page).toHaveURL(/\/ar\/listings/);
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
});
