import { expect, test } from "@playwright/test";

test("register -> login -> session -> chat -> upload -> summary", async ({ page }) => {
  const nonce = Date.now();
  const email = `patient-${nonce}@example.com`;
  const password = "VeryStrongPassword123!";

  await page.goto("/register");
  await page.getByPlaceholder("نام کامل").fill("بیمار تست");
  await page.getByPlaceholder("ایمیل").fill(email);
  await page.getByPlaceholder("رمز عبور").fill(password);
  await page.getByRole("button", { name: "ثبت‌نام" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByPlaceholder("ایمیل").fill(email);
  await page.getByPlaceholder("رمز عبور").fill(password);
  await page.getByRole("button", { name: "ورود" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByPlaceholder("مشکل اصلی بیمار").fill("سردرد شدید");
  await page.getByRole("button", { name: "ایجاد جلسه" }).click();
  await expect(page.getByText("Session #")).toBeVisible();

  const firstSessionLink = page.getByRole("link", { name: "چت" }).first();
  const href = await firstSessionLink.getAttribute("href");
  expect(href).toBeTruthy();

  await firstSessionLink.click();
  await expect(page).toHaveURL(/\/chat\/\d+$/);
  await page.locator("textarea").fill("از دیروز سردرد دارم");
  await page.getByRole("button", { name: "ارسال پیام" }).click();
  await expect(page.getByText("بیمار")).toBeVisible();

  const sessionId = page.url().split("/").pop();
  expect(sessionId).toBeTruthy();

  await page.goto(`/upload/${sessionId}`);
  const filePath = "tests/e2e/fixtures/report.txt";
  await page.locator('input[type="file"]').setInputFiles(filePath);
  await page.getByRole("button", { name: "آپلود" }).click();
  await expect(page.locator("pre")).toBeVisible();

  await page.goto(`/summary/${sessionId}`);
  await expect(page.getByText(`Session #${sessionId}`)).toBeVisible();
});
