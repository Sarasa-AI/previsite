const { test, expect } = require("@playwright/test");
const { execSync } = require("child_process");
const fs = require("fs");

const BASE = "http://127.0.0.1:3001";
const DB = "/Users/sarasa/Documents/MVP_previsit/backend/previsit_local.db";
const PY = "/Users/sarasa/Documents/MVP_previsit/.venv/bin/python";

function nationalIdFromSeed(seed) {
  let candidate = 1_000_000_000 + (Math.abs(seed) % 900_000_000);
  while (candidate < 9_999_999_999) {
    const nationalId = String(candidate).padStart(10, "0");
    if (isValidIranianNationalId(nationalId)) return nationalId;
    candidate += 1;
  }
  return "0499370899";
}
function isValidIranianNationalId(nationalId) {
  if (!/^\d{10}$/.test(nationalId)) return false;
  if (new Set(nationalId).size === 1) return false;
  const checkDigit = Number(nationalId[9]);
  const weightedSum =
    nationalId.slice(0, 9).split("").reduce((sum, digit, index) => sum + Number(digit) * (10 - index), 0) % 11;
  return weightedSum < 2 ? checkDigit === weightedSum : checkDigit === 11 - weightedSum;
}

test("real medication flow: search, select, prescribe, save, reload, OCR", async ({ page }) => {
  const nationalId = nationalIdFromSeed(Date.now());
  const password = "VeryStrongPassword123!";

  // ---- Register + login + create session ----
  await page.goto(`${BASE}/register`);
  await page.getByPlaceholder("کد ملی (۱۰ رقم)").fill(nationalId);
  await page.getByPlaceholder("رمز عبور", { exact: true }).fill(password);
  await page.getByPlaceholder("تکرار رمز عبور").fill(password);
  await page.getByRole("button", { name: "ثبت‌نام" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByPlaceholder("کد ملی (۱۰ رقم)").fill(nationalId);
  await page.getByPlaceholder("رمز عبور", { exact: true }).fill(password);
  await page.getByRole("button", { name: "ورود" }).click();
  await expect(page).toHaveURL(/\/dashboard$/);

  await page.getByPlaceholder("مشکل اصلی بیمار را وارد کنید").fill("دیابت نوع ۲");
  await page.getByRole("button", { name: "ایجاد جلسه" }).click();
  await expect(page.getByText(/جلسه #/)).toBeVisible({ timeout: 15_000 });
  const href = await page.getByRole("link", { name: /ادامه مصاحبه/ }).first().getAttribute("href");
  const sessionId = href.match(/\d+/)[0];
  console.log("sessionId:", sessionId);

  // ---- Jump to layer 4 directly (LLM layers 2-3 are not runnable locally) ----
  const layerPy = `/tmp/task5a/layer_jump_${sessionId}.py`;
  fs.writeFileSync(layerPy, `
import sqlite3, json
conn = sqlite3.connect("${DB}")
cur = conn.cursor()
summary = {
  "chief_complaint": "دیابت نوع ۲", "hpi_summary": "بیمار دیابت نوع ۲ دارد.",
  "pertinent_positives": [], "pertinent_negatives": [], "red_flags": [],
  "patient_questions": [], "is_hpi_complete": True,
  "current_medications": [], "extracted_at": "2026-08-31T00:00:00+00:00",
}
demographics = {
  "first_name": "علی", "last_name": "تستی", "national_id": "${nationalId}",
  "insurance_provider": "تأمین اجتماعی", "age": 34, "sex": "male",
  "weight": 70.0, "height": 175.0, "chief_complaint": "دیابت نوع ۲",
}
cur.execute(
  "UPDATE intakes SET current_layer=4, demographics_json=?, hpi_questions_json='[]', hpi_answers_json='{}', clinical_summary_json=? WHERE session_id=?",
  (json.dumps(demographics, ensure_ascii=False), json.dumps(summary, ensure_ascii=False), ${sessionId}),
)
conn.commit(); conn.close()
print("layer set to 4")
`);
  // Open intake once so the backend creates the intake row, then jump to
  // layer 4 and reload (LLM layers 2-3 are not runnable locally).
  await page.goto(`${BASE}/intake/${sessionId}`);
  await expect(page.getByText(/لایه ۱ — اطلاعات اولیه/)).toBeVisible({ timeout: 15_000 });
  console.log("DB:", execSync(`${PY} ${layerPy}`).toString().trim());
  await page.reload();
  await expect(page.getByText("لایه ۴ — سوابق پزشکی")).toBeVisible({ timeout: 15_000 });

  // ---- Search real DrugYab ----
  await page.getByLabel("جستجوی دارو").fill("متفورمین ۵۰۰");
  await page.getByRole("button", { name: "جستجو" }).click();
  const resultButton = page.getByRole("button", { name: /متفورمین|METFORMIN/i }).first();
  await expect(resultButton).toBeVisible({ timeout: 15_000 });
  console.log("RESULT CARD:\n" + (await resultButton.innerText()));
  await resultButton.click();

  await expect(page.getByText(/ژنریک: Metformin/).first()).toBeVisible({ timeout: 10_000 });
  console.log("CATALOG BLOCK:\n" + (await page.getByText(/ژنریک: Metformin/).first().innerText()));

  // ---- Fill all seven prescription fields ----
  await page.getByRole("textbox", { name: /دوز در هر نوبت/ }).fill("1");
  await page.getByLabel("واحد دوز").selectOption({ label: "قرص" });
  await page.getByRole("textbox", { name: /تعداد کل/ }).fill("60");
  await page.getByRole("textbox", { name: /تعداد در روز/ }).fill("روزی ۲ بار");
  await page.getByRole("textbox", { name: /مدت مصرف/ }).fill("۳۰ روز");
  await page.getByLabel("روش مصرف").selectOption({ label: "خوراکی" });
  await page.getByRole("textbox", { name: /دستور مصرف/ }).fill("بعد از غذا");

  // ---- Save (real persistence) ----
  await page.getByRole("button", { name: "تایید و ارسال به پزشک" }).click();
  await expect(page.getByText("پرونده با موفقیت ارسال شد")).toBeVisible({ timeout: 20_000 });
  console.log("SUBMITTED OK");

  // ---- Verify stored payload in the real app DB ----
  const storedPy = `/tmp/task5a/read_stored_${sessionId}.py`;
  fs.writeFileSync(storedPy, `
import sqlite3
conn = sqlite3.connect("${DB}")
row = conn.execute("SELECT medical_history_json FROM intakes WHERE session_id=${sessionId}").fetchone()
conn.close()
print(row[0])
`);
  const storedRaw = execSync(`${PY} ${storedPy}`).toString().trim();
  const stored = JSON.parse(storedRaw);
  const med = stored.current_medications[0];
  console.log("STORED medication:", JSON.stringify(med, null, 1).slice(0, 1400));
  expect(med.catalog_id).toBeTruthy();
  expect(med.catalog.generic_name).toBe("Metformin");
  expect(med.catalog.strength_raw).toBeTruthy();
  expect(med.prescription.dose).toBe("1");
  expect(med.prescription.quantity).toBe("60");
  expect(med.prescription.frequency).toBe("روزی ۲ بار");
  expect(med.prescription.duration).toBe("۳۰ روز");
  expect(med.prescription.route).toBe("خوراکی");
  expect(med.prescription.instructions).toBe("بعد از غذا");
  expect(med.provenance.verification_status).toBe("confirmed");
  expect(med.amount).toBe("1 قرص");
  console.log("STORED PAYLOAD VERIFIED");

  // ---- Reload: reopen intake and verify hydration ----
  await page.goto(`${BASE}/intake/${sessionId}`);
  await expect(page.getByText("لایه ۴ — سوابق پزشکی")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText(/ژنریک: Metformin/).first()).toBeVisible({ timeout: 10_000 });
  await expect(page.getByRole("textbox", { name: /تعداد کل/ })).toHaveValue("60", { timeout: 10_000 });
  await expect(page.getByRole("textbox", { name: /دستور مصرف/ })).toHaveValue("بعد از غذا", { timeout: 10_000 });
  await expect(page.getByRole("textbox", { name: /مدت مصرف/ })).toHaveValue("۳۰ روز", { timeout: 10_000 });
  await expect(page.getByRole("textbox", { name: /تعداد در روز/ })).toHaveValue("روزی ۲ بار", { timeout: 10_000 });
  console.log("RELOAD HYDRATION OK");

  // ---- OCR ambiguity resolution on a NEW blank medication row ----
  // The already-confirmed row must stay stable; candidate selection is
  // exercised on a fresh row so no silent first-result selection happens.
  await page.getByRole("button", { name: "افزودن دارو" }).click();
  const fileInputs = page.locator('input[type="file"]');
  await expect(fileInputs).toHaveCount(2);
  await fileInputs.nth(1).setInputFiles("/tmp/task5a/label_b_with_instructions.png");
  await expect(page.getByText(/چند داروی مشابه شناسایی شد/).first()).toBeVisible({ timeout: 30_000 });
  const candidates = page.getByRole("group", { name: "داروهای مشابه" }).getByRole("button");
  const candidateCount = await candidates.count();
  console.log("candidate buttons:", candidateCount);
  expect(candidateCount).toBeGreaterThan(1);
  const texts = [];
  for (let i = 0; i < candidateCount; i++) texts.push(await candidates.nth(i).innerText());
  console.log("CANDIDATES:\n" + texts.join("\n---\n"));
  await candidates.first().click();
  await expect(page.getByText(/METFORMIN AMIN 1000MG/).first()).toBeVisible({ timeout: 10_000 });
  expect(await page.getByText(/چند داروی مشابه شناسایی شد/).count()).toBe(0);
  console.log("CANDIDATE SELECTED AND CATALOG STORED");

  // ---- OCR merge onto the confirmed row preserves catalog identity ----
  await page.locator('input[type="file"]').nth(0).setInputFiles("/tmp/task5a/label_b_with_instructions.png");
  await expect(page.getByText(/APO-METFORMIN/).first()).toBeVisible({ timeout: 30_000 });
  expect(await page.getByText("نیاز به بررسی").count()).toBe(0);
  expect(await page.getByText(/چند داروی مشابه شناسایی شد/).count()).toBe(0);
  await expect(page.getByRole("textbox", { name: /دوز در هر نوبت/ }).first()).toHaveValue("۱");
  await expect(page.getByRole("textbox", { name: /تعداد کل/ }).first()).toHaveValue("60");
  await expect(page.getByRole("textbox", { name: /مدت مصرف/ }).first()).toHaveValue("۳۰ روز");
  await expect(page.getByRole("combobox", { name: "روش مصرف" }).first()).toHaveValue("خوراکی");
  console.log("CONFIRMED ROW OCR MERGE OK");
  console.log("BROWSER E2E DONE");
});
