import { expect, test } from "@playwright/test";

const SESSION_ID = process.env.E2E_SESSION_ID || "1";
const CLINICIAN_USERNAME = process.env.E2E_CLINICIAN_USERNAME || "mvp_clinician";
const CLINICIAN_PASSWORD =
  process.env.E2E_CLINICIAN_PASSWORD || "MvpClinicianPassword123!";
const PATIENT_NAME = process.env.E2E_PATIENT_NAME || "MVP Verification Patient";

function buildLabPdf(): Buffer {
  const lines = [
    "CBC Laboratory Report",
    "Patient ID: PV-MVP-001",
    "Date: 2026-08-30",
    "Hemoglobin: 13.7 g/dL",
    "WBC: 8,421 /uL",
    "Platelets: 245,000 /uL",
  ];
  const commands = ["BT", "/F1 12 Tf"];
  let y = 720;
  for (const line of lines) {
    commands.push(`1 0 0 1 72 ${y} Tm (${line}) Tj`);
    y -= 20;
  }
  commands.push("ET");
  const content = Buffer.from(commands.join("\n"), "latin1");
  const objects = [
    Buffer.from("<< /Type /Catalog /Pages 2 0 R >>"),
    Buffer.from("<< /Type /Pages /Kids [3 0 R] /Count 1 >>"),
    Buffer.from(
      "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] " +
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
    ),
    Buffer.concat([
      Buffer.from(`<< /Length ${content.length} >>\nstream\n`),
      content,
      Buffer.from("\nendstream"),
    ]),
    Buffer.from("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
  ];

  const chunks = [Buffer.from("%PDF-1.4\n")];
  const offsets: number[] = [];
  let length = chunks[0].length;
  objects.forEach((object, index) => {
    offsets.push(length);
    const chunk = Buffer.concat([
      Buffer.from(`${index + 1} 0 obj\n`),
      object,
      Buffer.from("\nendobj\n"),
    ]);
    chunks.push(chunk);
    length += chunk.length;
  });
  const xrefAt = length;
  chunks.push(Buffer.from(`xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`));
  offsets.forEach((offset) => chunks.push(Buffer.from(`${String(offset).padStart(10, "0")} 00000 n \n`)));
  chunks.push(
    Buffer.from(
      `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xrefAt}\n%%EOF\n`,
    ),
  );
  return Buffer.concat(chunks);
}

test("clinician login -> patient -> workspace -> upload -> extracted lab", async ({ page }) => {
  await page.goto("/doctor-login");
  await page.getByPlaceholder("نام کاربری").fill(CLINICIAN_USERNAME);
  await page.getByPlaceholder("رمز عبور").fill(CLINICIAN_PASSWORD);
  await page.getByRole("button", { name: "ورود" }).click();
  await expect(page).toHaveURL(/\/doctor-dashboard$/);

  await expect(page.getByText(PATIENT_NAME)).toBeVisible();
  await page.getByText(PATIENT_NAME).click();
  await page.locator(`a[href="/clinician/${SESSION_ID}/workspace"]`).click();
  await expect(page).toHaveURL(new RegExp(`/clinician/${SESSION_ID}/workspace$`));

  await page.goto(`/upload/${SESSION_ID}`);
  await page.locator('input[type="file"]').setInputFiles({
    name: "pv-mvp-lab.pdf",
    mimeType: "application/pdf",
    buffer: buildLabPdf(),
  });
  await page.getByRole("button", { name: "شروع آپلود" }).click();
  await expect(page.getByText("آپلود با موفقیت انجام شد")).toBeVisible({ timeout: 30_000 });

  let apiValue = "";
  await expect
    .poll(
      async () => {
        const response = await page.request.get(
          `/api/proxy/api/sessions/${SESSION_ID}/clinical-content`,
        );
        if (!response.ok()) return "";
        const body = await response.json();
        const row = body.content?.labs?.rows?.find(
          (candidate: { name?: string }) => candidate.name === "Hemoglobin",
        );
        apiValue = row?.value || "";
        return apiValue;
      },
      { timeout: 30_000 },
    )
    .toContain("13.7");

  await page.goto(`/clinician/${SESSION_ID}/workspace`);
  await expect(page.getByRole("main", { name: "Doctor workspace" })).toBeVisible({
    timeout: 30_000,
  });
  const labs = page.getByRole("article", { name: "Labs" });
  await expect(labs).toBeVisible({ timeout: 30_000 });
  await expect(labs.getByText("Hemoglobin")).toBeVisible();
  const renderedValue =
    (await labs.getByText(/^13\.7 g\/dL$/).first().textContent())?.trim() || "";
  const browserValue = renderedValue;

  expect(browserValue).toBe(apiValue);
  console.log(`API_VALUE=${apiValue}`);
  console.log(`BROWSER_VALUE=${browserValue}`);
});
