import { expect, test } from "@playwright/test";

/** Build a valid Iranian national ID from a numeric seed. */
function nationalIdFromSeed(seed: number): string {
  let candidate = 1_000_000_000 + (Math.abs(seed) % 900_000_000);
  while (candidate < 9_999_999_999) {
    const nationalId = String(candidate).padStart(10, "0");
    if (isValidIranianNationalId(nationalId)) return nationalId;
    candidate += 1;
  }
  return "0499370899";
}

function isValidIranianNationalId(nationalId: string): boolean {
  if (!/^\d{10}$/.test(nationalId)) return false;
  if (new Set(nationalId).size === 1) return false;
  const checkDigit = Number(nationalId[9]);
  const weightedSum =
    nationalId
      .slice(0, 9)
      .split("")
      .reduce((sum, digit, index) => sum + Number(digit) * (10 - index), 0) % 11;
  if (weightedSum < 2) return checkDigit === weightedSum;
  return checkDigit === 11 - weightedSum;
}

test("register -> complete layer 1 demographics -> logout", async ({ page }) => {
  const nationalId = nationalIdFromSeed(Date.now());
  const password = "VeryStrongPassword123!";

  await page.goto("/register");
  await page.getByPlaceholder("کد ملی (۱۰ رقم)").fill(nationalId);
  await page.getByPlaceholder("رمز عبور").fill(password);
  await page.getByPlaceholder("تکرار رمز عبور").fill(password);
  await page.getByRole("button", { name: "ثبت‌نام" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByPlaceholder("کد ملی (۱۰ رقم)").fill(nationalId);
  await page.getByPlaceholder("رمز عبور").fill(password);
  await page.getByRole("button", { name: "ورود" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByPlaceholder("مشکل اصلی بیمار را وارد کنید").fill("سردرد شدید");
  await page.getByRole("button", { name: "ایجاد جلسه" }).click();
  await expect(page.getByText(/جلسه #/)).toBeVisible({ timeout: 15_000 });

  await page.getByRole("link", { name: /ادامه مصاحبه/ }).first().click();
  await expect(page).toHaveURL(/\/intake\/\d+$/);

  await expect(page.getByText("لایه ۱ — اطلاعات اولیه")).toBeVisible({ timeout: 10_000 });
  await page.getByLabel("نام", { exact: true }).fill("علی");
  await page.getByLabel("نام خانوادگی").fill("تستی");
  await page.getByLabel("کد ملی").fill(nationalId);
  await page.getByLabel("سن").fill("34");
  await page.getByLabel("وزن (کیلوگرم)").fill("70");
  await page.getByLabel("قد (سانتی‌متر)").fill("175");
  await page.getByLabel("شکایت اصلی").fill("سردرد شدید از دیروز");
  await page.getByRole("button", { name: /ذخیره و ادامه|ادامه/ }).click();

  await expect(page.getByTestId("progress-chip-1")).toHaveAttribute("data-done", "true", {
    timeout: 30_000,
  });

  await page.goto("/dashboard");
  await page.getByRole("button", { name: "خروج" }).click();
  await expect(page).toHaveURL(/\/login$/);
});
