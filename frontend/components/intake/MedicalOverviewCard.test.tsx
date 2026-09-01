import { useState } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { MedicalOverview } from "@/lib/pmh/types";
import type { CurrentMedication } from "@/lib/pmh/types";
import { emptyMedicalOverview } from "@/lib/pmh/types";
import { normalizeMedicalOverview } from "@/lib/intake";
import type { MedicationSearchResult } from "@/lib/client";
import { MedicalOverviewCard, sanitizeMedicalOverview } from "./MedicalOverviewCard";

const resolvedMedication: MedicationSearchResult = {
  id: 101,
  display_name: "Glucophage",
  brand_name_fa: "گلوکوفاژ",
  brand_name_en: "Glucophage",
  generic_name_en: "Metformin",
  form: "TAB",
  strength: "500 mg",
  manufacturer: "Merck",
  dose_unit: "قرص",
};

const ocrMedication = {
  catalog_id: 202,
  name: "Losartan",
  amount: "",
  frequency: "",
  dose_unit: "قرص",
  catalog: {
    catalog_id: 202,
    generic_name: "Losartan",
    strength_raw: "50 mg",
    dosage_form: "TAB",
    manufacturer: "OCR Manufacturer",
  },
  prescription: {
    dose: null,
    dose_unit: "قرص",
    quantity: null,
    frequency: null,
    duration: null,
    route: null,
    instructions: null,
  },
  provenance: {
    source: "ocr",
    confidence: null,
    verification_status: "needs_review",
  },
};

const ambiguousCandidates = [
  {
    catalog_id: 202,
    name: "Losartan 25",
    generic_name: "Losartan",
    strength: "25 mg",
    form: "TAB",
    manufacturer: "Company A",
    company: "Pharma A",
    dose_unit: "قرص",
    catalog: {
      catalog_id: 202,
      generic_name: "Losartan",
      brand_name: "Losartan 25",
      strength_raw: "25 mg",
      dosage_form: "TAB",
      manufacturer: "Company A",
      company_name: "Pharma A",
    },
  },
  {
    catalog_id: 203,
    name: "Losartan 50",
    generic_name: "Losartan",
    strength: "50 mg",
    form: "TAB",
    manufacturer: "Company B",
    company: "Pharma B",
    dose_unit: "قرص",
    catalog: {
      catalog_id: 203,
      generic_name: "Losartan",
      brand_name: "Losartan 50",
      strength_raw: "50 mg",
      dosage_form: "TAB",
      manufacturer: "Company B",
      company_name: "Pharma B",
    },
  },
] as const;

const ambiguousOcrMedication = {
  catalog_id: 202,
  name: "Losartan 25",
  amount: "",
  frequency: "",
  dose_unit: "قرص",
  // The backend echoes the top candidate here; the UI must not apply it
  // silently while the candidate panel is shown.
  catalog: ambiguousCandidates[0].catalog,
  prescription: {
    dose: null,
    dose_unit: "قرص",
    quantity: null,
    frequency: null,
    duration: null,
    route: null,
    instructions: null,
  },
  provenance: {
    source: "ocr",
    confidence: null,
    verification_status: "ambiguous",
  },
  ambiguous: true,
  candidate_count: 2,
  candidates: ambiguousCandidates,
};

const dupOcrMedication = {
  catalog_id: 101,
  name: "Glucophage",
  amount: "",
  frequency: "",
  dose_unit: "قرص",
  catalog: {
    catalog_id: 101,
    generic_name: "Metformin",
    brand_name: "Glucophage",
    strength_raw: "500 mg",
    dosage_form: "TAB",
    manufacturer: "Merck",
  },
  prescription: {
    dose: null,
    dose_unit: "قرص",
    quantity: null,
    frequency: null,
    duration: null,
    route: null,
    instructions: null,
  },
  provenance: {
    source: "ocr",
    confidence: null,
    verification_status: "needs_review",
  },
};

let nextOcrResponse: object[] = [ocrMedication];

vi.mock("./DrugSearch", () => ({
  DrugSearch: ({ onSelect }: { onSelect: (result: MedicationSearchResult) => void }) => (
    <button type="button" onClick={() => onSelect(resolvedMedication)}>
      Select resolved medication
    </button>
  ),
}));

vi.mock("./InlineConditionUpload", () => ({
  InlineConditionUpload: ({
    conditionId,
    conditionType,
    onUploadComplete,
  }: {
    conditionId: string;
    conditionType?: string;
    onUploadComplete?: (conditionId: string, file: object, medications: object[]) => void;
  }) =>
    conditionType === "medication" ? (
      <button
        type="button"
        onClick={() => onUploadComplete?.(conditionId, {}, nextOcrResponse)}
      >
        Complete medication OCR
      </button>
    ) : null,
}));

function Harness() {
  const [value, setValue] = useState<MedicalOverview>(emptyMedicalOverview);
  return (
    <>
      <MedicalOverviewCard
        value={value}
        onChange={setValue}
        sessionId="42"
        conditionFiles={{}}
        onConditionFileChange={vi.fn()}
        labBindIds={[]}
        onAddLabResult={vi.fn()}
        onRemoveLabResult={vi.fn()}
        onLabExtractedData={vi.fn()}
      />
      <output data-testid="overview-state">{JSON.stringify(value)}</output>
    </>
  );
}

function LegacyHarness() {
  const [value, setValue] = useState<MedicalOverview>({
    ...emptyMedicalOverview,
    current_medications: [
      {
        id: "legacy-1",
        catalog_id: 101,
        name: "Glucophage",
        amount: "۱ قرص",
        frequency: "روزی ۱ بار",
        dose_unit: "قرص",
      },
    ],
  });
  return (
    <>
      <MedicalOverviewCard
        value={value}
        onChange={setValue}
        sessionId="42"
        conditionFiles={{}}
        onConditionFileChange={vi.fn()}
        labBindIds={[]}
        onAddLabResult={vi.fn()}
        onRemoveLabResult={vi.fn()}
        onLabExtractedData={vi.fn()}
      />
      <output data-testid="overview-state">{JSON.stringify(value)}</output>
    </>
  );
}

const fullMedication: CurrentMedication = {
  id: "med-full",
  catalog_id: 101,
  name: "Glucophage",
  amount: "۱ قرص",
  frequency: "روزی ۲ بار",
  dose_unit: "قرص",
  catalog: {
    catalog_id: 101,
    generic_name: "Metformin",
    generic_name_en: "Metformin",
    brand_name: "Glucophage",
    brand_name_en: "Glucophage",
    brand_name_fa: "گلوکوفاژ",
    strength_raw: "500 mg",
    dosage_form: "TAB",
    manufacturer: "Merck",
    company_name: "Company X",
    company_slug: "company-x",
    generic_slug: "metformin",
    brand_slug: "glucophage",
  },
  prescription: {
    dose: "۱",
    dose_unit: "قرص",
    quantity: "۳۰",
    frequency: "روزی ۲ بار",
    duration: "۳۰ روز",
    route: "خوراکی",
    instructions: "بعد از غذا",
  },
  provenance: {
    source: "manual",
    confidence: null,
    verification_status: "confirmed",
  },
};

describe("MedicalOverviewCard manual medication selection", () => {
  beforeEach(() => {
    nextOcrResponse = [ocrMedication];
  });

  it("creates one canonical medication record without fabricating a dose", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "Select resolved medication" }));
    await user.click(screen.getByRole("button", { name: "Select resolved medication" }));

    expect(screen.getAllByDisplayValue("Glucophage")).toHaveLength(1);
    expect(screen.getByText("دوز در هر نوبت")).toBeInTheDocument();
    const overview = JSON.parse(screen.getByTestId("overview-state").textContent ?? "{}");
    const medication = overview.current_medications[0];
    expect(medication).toEqual(
      expect.objectContaining({
        catalog_id: 101,
        name: "Glucophage",
        amount: "",
        frequency: "",
        dose_unit: "قرص",
      }),
    );
    expect(medication.prescription).toEqual({
      dose: null,
      dose_unit: "قرص",
      quantity: null,
      frequency: null,
      duration: null,
      route: null,
      instructions: null,
    });
    expect(medication.provenance.verification_status).toBe("confirmed");
    expect(medication.catalog.generic_name).toBe("Metformin");
    expect(medication.catalog.strength_raw).toBe("500 mg");
  });

  it("creates an OCR medication record with catalog but no fabricated instructions", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "Select resolved medication" }));
    await user.click(screen.getByRole("button", { name: "Complete medication OCR" }));

    const overview = JSON.parse(screen.getByTestId("overview-state").textContent ?? "{}");
    const medication = overview.current_medications[0];
    expect(medication).toEqual(expect.objectContaining(ocrMedication));
    expect(medication.prescription.dose).toBeNull();
    expect(medication.prescription.frequency).toBeNull();
    expect(medication.provenance.verification_status).toBe("needs_review");
  });

  it("shows the needs-review state and lets the user confirm", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "افزودن دارو" }));
    await user.click(screen.getByRole("button", { name: "Complete medication OCR" }));

    expect(screen.getByText("نیاز به بررسی")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "تأیید" }));

    const overview = JSON.parse(screen.getByTestId("overview-state").textContent ?? "{}");
    expect(overview.current_medications[0].provenance.verification_status).toBe("confirmed");
    expect(screen.queryByText("نیاز به بررسی")).not.toBeInTheDocument();
  });

  it("renders ambiguous OCR candidates and resolves only on user selection", async () => {
    const user = userEvent.setup();
    nextOcrResponse = [ambiguousOcrMedication];
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "افزودن دارو" }));
    await user.click(screen.getByRole("button", { name: "Complete medication OCR" }));

    expect(screen.getAllByText(/چند داروی مشابه شناسایی شد/).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: /Losartan 25/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Losartan 50/ })).toBeInTheDocument();

    let overview = JSON.parse(screen.getByTestId("overview-state").textContent ?? "{}");
    const pending = overview.current_medications[0];
    // No silent top-candidate selection: catalog stays unknown until picked.
    expect(pending.catalog).toBeNull();
    expect(pending.catalog_id).toBeNull();
    expect(pending.provenance.verification_status).toBe("ambiguous");

    await user.click(screen.getByRole("button", { name: /Losartan 50/ }));

    overview = JSON.parse(screen.getByTestId("overview-state").textContent ?? "{}");
    const resolved = overview.current_medications[0];
    expect(resolved.catalog_id).toBe(203);
    expect(resolved.catalog.catalog_id).toBe(203);
    expect(resolved.catalog.strength_raw).toBe("50 mg");
    expect(resolved.catalog.manufacturer).toBe("Company B");
    expect(resolved.catalog.company_name).toBe("Pharma B");
    expect(resolved.name).toBe("Losartan 50");
    expect(resolved.provenance.verification_status).toBe("confirmed");
    expect(screen.queryAllByText(/چند داروی مشابه شناسایی شد/)).toHaveLength(0);
  });

  it("ambiguous OCR never destabilizes a confirmed row's catalog identity", async () => {
    const user = userEvent.setup();
    nextOcrResponse = [ambiguousOcrMedication];
    render(<Harness />);

    // Add a confirmed manual medication, then upload an ambiguous OCR result
    // onto that same row.
    await user.click(screen.getByRole("button", { name: "Select resolved medication" }));
    await user.click(screen.getByRole("button", { name: "Complete medication OCR" }));

    expect(screen.queryAllByText(/چند داروی مشابه شناسایی شد/)).toHaveLength(0);

    const overview = JSON.parse(screen.getByTestId("overview-state").textContent ?? "{}");
    const medication = overview.current_medications[0];
    expect(medication.name).toBe("Glucophage");
    expect(medication.catalog_id).toBe(101);
    expect(medication.catalog.generic_name).toBe("Metformin");
    expect(medication.catalog.strength_raw).toBe("500 mg");
    expect(medication.provenance.verification_status).toBe("confirmed");
  });

  it("editing prescription fields keeps catalog data intact", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "Select resolved medication" }));
    await user.type(screen.getByPlaceholderText("۱"), "۱");
    await user.type(screen.getByPlaceholderText("روزی ۱ بار"), "روزی ۲ بار");
    await user.type(screen.getByPlaceholderText("مثلاً ۳۰"), "۳۰");
    await user.type(screen.getByPlaceholderText("۳۰ روز"), "۳۰ روز");
    await user.selectOptions(screen.getByRole("combobox", { name: "روش مصرف" }), "خوراکی");
    await user.type(
      screen.getByPlaceholderText("مثلاً بعد از غذا، قبل از خواب"),
      "بعد از غذا",
    );

    const overview = JSON.parse(screen.getByTestId("overview-state").textContent ?? "{}");
    const medication = overview.current_medications[0];
    expect(medication.catalog.generic_name).toBe("Metformin");
    expect(medication.catalog.brand_name).toBe("Glucophage");
    expect(medication.catalog.strength_raw).toBe("500 mg");
    expect(medication.catalog.dosage_form).toBe("TAB");
    expect(medication.catalog.manufacturer).toBe("Merck");
    expect(medication.prescription.dose).toBe("۱");
    expect(medication.prescription.dose_unit).toBe("قرص");
    expect(medication.prescription.quantity).toBe("۳۰");
    expect(medication.prescription.frequency).toBe("روزی ۲ بار");
    expect(medication.prescription.duration).toBe("۳۰ روز");
    expect(medication.prescription.route).toBe("خوراکی");
    expect(medication.prescription.instructions).toBe("بعد از غذا");
    expect(medication.amount).toBe("۱ قرص");
  });

  it("OCR merge does not erase typed prescription data", async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "Select resolved medication" }));
    await user.type(screen.getByPlaceholderText("۱"), "۱");
    await user.type(screen.getByPlaceholderText("روزی ۱ بار"), "روزی ۲ بار");
    await user.click(screen.getByRole("button", { name: "Complete medication OCR" }));

    const overview = JSON.parse(screen.getByTestId("overview-state").textContent ?? "{}");
    const medication = overview.current_medications[0];
    expect(medication.name).toBe("Losartan");
    expect(medication.catalog.generic_name).toBe("Losartan");
    expect(medication.catalog.manufacturer).toBe("OCR Manufacturer");
    expect(medication.prescription.dose).toBe("۱");
    expect(medication.prescription.frequency).toBe("روزی ۲ بار");
    expect(medication.amount).toBe("۱ قرص");
  });

  it("merges OCR into the matching existing row instead of duplicating", async () => {
    const user = userEvent.setup();
    nextOcrResponse = [dupOcrMedication];
    render(<Harness />);

    await user.click(screen.getByRole("button", { name: "Select resolved medication" }));
    await user.click(screen.getByRole("button", { name: "افزودن دارو" }));
    const uploadButtons = screen.getAllByRole("button", { name: "Complete medication OCR" });
    await user.click(uploadButtons[uploadButtons.length - 1]);

    const overview = JSON.parse(screen.getByTestId("overview-state").textContent ?? "{}");
    expect(overview.current_medications).toHaveLength(1);
    expect(overview.current_medications[0].catalog_id).toBe(101);
    expect(overview.current_medications[0].name).toBe("Glucophage");
  });

  it("renders legacy medication payloads without crashing", async () => {
    const user = userEvent.setup();
    render(<LegacyHarness />);

    expect(screen.getByDisplayValue("Glucophage")).toBeInTheDocument();
    expect(screen.getByText(/مقدار قبلی: ۱ قرص/)).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText("روزی ۱ بار"), "هر ۸ ساعت");
    const overview = JSON.parse(screen.getByTestId("overview-state").textContent ?? "{}");
    const medication = overview.current_medications[0];
    expect(medication.prescription.frequency).toBe("هر ۸ ساعت");
    expect(medication.prescription.dose).toBeNull();
    // Legacy amount must survive once the structured dose is still unknown.
    const sanitized = sanitizeMedicalOverview(
      {
        ...overview,
        current_medications: [medication],
      },
      {},
    );
    expect(sanitized.current_medications[0].amount).toBe("۱ قرص");
  });
});

describe("MedicalOverviewCard save/reload round-trip", () => {
  it("preserves catalog, prescription and provenance through sanitize + normalize", () => {
    const overview: MedicalOverview = {
      ...emptyMedicalOverview,
      current_medications: [fullMedication],
    };

    const saved = sanitizeMedicalOverview(overview, {});
    const reloaded = normalizeMedicalOverview(saved);
    const medication = reloaded.current_medications[0];

    expect(medication.catalog).toEqual(fullMedication.catalog);
    expect(medication.prescription).toEqual(fullMedication.prescription);
    expect(medication.provenance).toEqual(fullMedication.provenance);
    expect(medication.catalog_id).toBe(101);
    expect(medication.amount).toBe("۱ قرص");
    expect(medication.frequency).toBe("روزی ۲ بار");
  });

  it("editing frequency only leaves catalog and the rest of the prescription intact", () => {
    const overview: MedicalOverview = {
      ...emptyMedicalOverview,
      current_medications: [fullMedication],
    };
    const reloaded = normalizeMedicalOverview(sanitizeMedicalOverview(overview, {}));
    const edited: CurrentMedication = {
      ...reloaded.current_medications[0],
      prescription: {
        ...(reloaded.current_medications[0].prescription as NonNullable<typeof fullMedication.prescription>),
        frequency: "هر ۸ ساعت",
      },
    };
    const sanitized = sanitizeMedicalOverview(
      { ...reloaded, current_medications: [edited] },
      {},
    );
    const medication = sanitized.current_medications[0];

    expect(medication.catalog).toEqual(fullMedication.catalog);
    expect(medication.catalog_id).toBe(101);
    expect(medication.prescription?.dose).toBe("۱");
    expect(medication.prescription?.dose_unit).toBe("قرص");
    expect(medication.prescription?.quantity).toBe("۳۰");
    expect(medication.prescription?.duration).toBe("۳۰ روز");
    expect(medication.prescription?.route).toBe("خوراکی");
    expect(medication.prescription?.instructions).toBe("بعد از غذا");
    expect(medication.prescription?.frequency).toBe("هر ۸ ساعت");
    expect(medication.catalog?.strength_raw).toBe("500 mg");
  });

  it("editing dose never overwrites catalog strength", () => {
    const overview: MedicalOverview = {
      ...emptyMedicalOverview,
      current_medications: [fullMedication],
    };
    const reloaded = normalizeMedicalOverview(sanitizeMedicalOverview(overview, {}));
    const edited: CurrentMedication = {
      ...reloaded.current_medications[0],
      prescription: {
        ...(reloaded.current_medications[0].prescription as NonNullable<typeof fullMedication.prescription>),
        dose: "۲",
      },
    };
    const medication = sanitizeMedicalOverview(
      { ...reloaded, current_medications: [edited] },
      {},
    ).current_medications[0];

    expect(medication.prescription?.dose).toBe("۲");
    expect(medication.catalog?.strength_raw).toBe("500 mg");
    expect(medication.amount).toBe("۲ قرص");
  });
});
