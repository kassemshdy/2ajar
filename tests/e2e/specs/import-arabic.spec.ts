import { expect, test } from "@playwright/test";

const CSV = [
  "transaction_type,property_type,location,price_usd,price_period,bedrooms,title_en,title_ar,contact_whatsapp",
  "rent,apartment,hamra,800,monthly,1,Imported Hamra studio,,+961 70 111 222",
  "rent,apartment,الأشرفية,1400,monthly,3,,شقة مستوردة في الأشرفية,+961 70 111 222",
  "rent,apartment,atlantis,900,monthly,2,Broken row,,+961 70 111 222",
].join("\n");

test("Arabic broker registers and imports listings from CSV @mutating", async ({ page }, info) => {
  const stamp = `${Date.now()}-${info.project.name}`;
  await page.goto("/ar/register");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await page.getByLabel("وسيط عقاري").check();
  await page.getByLabel("الاسم الكامل").fill("وسيط تجريبي");
  await page.getByLabel("البريد الإلكتروني").fill(`e2e-ar-${stamp}@example.com`);
  await page.getByLabel("اسم الوكالة (اختياري)").fill(`وكالة ${stamp}`);
  await page.getByLabel("كلمة المرور").fill("e2e-password-123");
  await page.getByRole("button", { name: "إنشاء الحساب" }).click();
  await expect(page).toHaveURL(/\/ar\/dashboard$/);

  await page.getByTestId("import-csv").click();
  await expect(page.getByTestId("csv-import")).toBeVisible();
  const template = await page.request.get("/api/v1/listings/import/template");
  expect(template.ok()).toBeTruthy();
  expect(await template.text()).toContain("transaction_type,property_type,location");

  await page.getByTestId("csv-input").setInputFiles({ name: "listings.csv", mimeType: "text/csv", buffer: Buffer.from(CSV) });
  await page.getByTestId("csv-preview").click();
  await expect(page.getByTestId("csv-summary")).toContainText("2");
  await expect(page.getByTestId("csv-row")).toHaveCount(3);
  await expect(page.getByText("Unknown location 'atlantis'")).toBeVisible();
  await page.getByTestId("csv-confirm").click();
  await expect(page.getByTestId("csv-created")).toBeVisible();

  await page.goto("/ar/dashboard");
  await expect(page.getByTestId("dashboard-listing").filter({ hasText: "شقة مستوردة في الأشرفية" })).toContainText("مسودة");
  await expect(page.getByTestId("dashboard-listing").filter({ hasText: "Imported Hamra studio" })).toBeVisible();
});
