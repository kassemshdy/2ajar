import path from "node:path";
import { expect, test } from "@playwright/test";

const PHOTO = path.join(__dirname, "..", "fixtures", "photo.jpg");

test("broker lists a property, visitor contacts them, broker sees the lead @mutating", async ({ page, browser }, info) => {
  const stamp = `${Date.now()}-${info.project.name}`;
  const email = `e2e-broker-${stamp}@example.com`;
  const title = `E2E apartment ${stamp}`;

  // 1. Register as broker
  await page.goto("/en/register");
  await page.getByLabel("Real estate broker").check();
  await page.getByLabel("Full name").fill("E2E Broker");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Phone number").fill("+961 71 555 666");
  await page.getByLabel("Agency name (optional)").fill(`E2E Agency ${stamp}`);
  await page.getByLabel("Password").fill("e2e-password-123");
  await page.getByRole("button", { name: "Create account" }).click();
  await expect(page).toHaveURL(/\/en\/dashboard$/);
  await expect(page.getByTestId("dashboard")).toBeVisible();

  // 2. Create listing
  await page.getByTestId("new-listing").click();
  await page.getByLabel("Location").selectOption({ label: "  Hamra" });
  await page.getByLabel("Price (USD)").fill("950");
  await page.getByLabel("Bedrooms").fill("2");
  await page.getByLabel("Bathrooms").fill("1");
  await page.getByLabel("Area (m²)").fill("110");
  await page.getByLabel("24/7 generator").check();
  await page.getByLabel("Title (English)").fill(title);
  await page.getByLabel("Title (Arabic)").fill("شقة للاختبار في الحمرا");
  await page.getByLabel("Description (English)").fill("Bright apartment near AUB. Created by an automated test.");
  await page.getByLabel("WhatsApp number for inquiries").fill("+961 71 555 666");
  await page.getByTestId("save-listing").click();
  await expect(page).toHaveURL(/\/dashboard\/listings\/[0-9a-f-]+\/edit$/);

  // 3. Publishing without a photo is rejected, then upload and publish
  await page.getByTestId("publish-button").click();
  await expect(page.getByTestId("form-error")).toContainText("photo");
  await page.getByTestId("photo-input").setInputFiles(PHOTO);
  await expect(page.locator("img[src*='/media/listings/']")).toHaveCount(1);
  await page.getByTestId("publish-button").click();
  await expect(page.getByTestId("form-notice")).toContainText("live");
  const listingUrl = page.url().replace("/dashboard/listings/", "/listings/").replace(/\/edit$/, "");

  // 4. Anonymous visitor finds it, opens WhatsApp handoff and submits a lead
  const visitor = await browser.newContext({ ...info.project.use });
  const v = await visitor.newPage();
  await v.goto(listingUrl);
  await expect(v.getByRole("heading", { level: 1 })).toHaveText(title);
  await expect(v.getByTestId("listing-price")).toContainText("$950");
  await expect(v.getByText("71 555 666")).toHaveCount(0); // phone not exposed in page

  let waUrl = "";
  await v.route("https://wa.me/**", (route) => {
    waUrl = route.request().url();
    return route.fulfill({ status: 200, body: "whatsapp" });
  });
  await v.getByTestId("whatsapp-button").click();
  await expect.poll(() => waUrl).toContain("https://wa.me/96171555666?text=");
  await v.goBack();

  await v.getByLabel("Your name").fill("Visitor Test");
  await v.getByLabel("Phone (WhatsApp)").fill("03 123 456");
  await v.getByLabel("Message (optional)").fill("Is it available next month?");
  await v.getByRole("button", { name: "Send my details" }).click();
  // Native validation blocks submit until consent is given
  await expect(v.getByTestId("lead-success")).toHaveCount(0);
  await v.getByTestId("lead-consent").check();
  await v.getByRole("button", { name: "Send my details" }).click();
  await expect(v.getByTestId("lead-success")).toBeVisible();
  await visitor.close();

  // 5. Broker sees the lead
  await page.goto("/en/dashboard");
  await expect(page.getByTestId("leads-list")).toContainText("Visitor Test");
  await expect(page.getByTestId("leads-list")).toContainText("+9613123456");
  await expect(page.getByTestId("dashboard-listing").filter({ hasText: title })).toContainText("1 lead");
});
