"use client";

import { useState, type Dispatch, type SetStateAction } from "react";
import { Loader2, MessageCircleQuestion, Plus, X } from "lucide-react";
import { HybridChipInput } from "@/components/intake/HybridChipInput";
import { DrugSearch } from "@/components/intake/DrugSearch";
import {
  InlineConditionUpload,
  type ExtractedMedication,
  type ExtractedMedicationCandidate,
} from "@/components/intake/InlineConditionUpload";
import { SuggestionChips } from "@/components/intake/SuggestionChips";
import {
  MEDICATION_FREQUENCY_OPTIONS,
} from "@/lib/pmh/medication-options";
import {
  ALLERGY_SUGGESTIONS,
  CHRONIC_DISEASE_SUGGESTIONS,
  FAMILY_SUGGESTIONS,
  SURGERY_SUGGESTIONS,
} from "@/lib/pmh/suggestions";
import type {
  ChronicCondition,
  ConditionFile,
  CurrentMedication,
  LabResult,
  MedicationCatalogSnapshot,
  MedicationPrescription,
  MedicalOverview,
} from "@/lib/pmh/types";
import type { MedicationSearchResult } from "@/lib/client";

const COMPACT_ROW_CLASS = "flex flex-wrap items-center gap-2 border-b border-slate-100 py-1.5 sm:flex-nowrap";
const MEDICATION_COMPACT_ROW_CLASS = "flex flex-wrap items-center gap-2 py-1.5 sm:flex-nowrap";

function medicationFingerprint(med: Pick<CurrentMedication, "name" | "amount" | "frequency">): string {
  return `${med.name.trim()}|${med.amount.trim()}|${med.frequency.trim()}`;
}

const DOSE_UNIT_OPTIONS = [
  "قرص",
  "کپسول",
  "عدد",
  "میلی‌لیتر",
  "قطره",
  "پاف",
  "آمپول",
  "ساشه",
  "ویال",
  "گرم",
  "واحد",
] as const;

const ROUTE_OPTIONS = [
  "خوراکی",
  "موضعی",
  "استنشاقی",
  "تزریقی",
  "زیرجلدی",
  "عضلانی",
  "وریدی",
] as const;

const PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹";

function isNegativeNumber(value: string | null | undefined): boolean {
  if (!value) {
    return false;
  }
  const normalized = value
    .replace(/[۰-۹]/g, (digit) => String(PERSIAN_DIGITS.indexOf(digit)))
    .replace("٫", ".")
    .replace("،", ".");
  const match = normalized.match(/[-+]?\d+(?:\.\d+)?/);
  if (!match) {
    return false;
  }
  return Number(match[0]) < 0;
}

function prescriptionAmount(prescription: MedicationPrescription | null | undefined): string {
  if (!prescription?.dose) {
    return "";
  }
  return [prescription.dose, prescription.dose_unit].filter(Boolean).join(" ");
}

function selectOptions(current: string | null | undefined, options: readonly string[]): string[] {
  const values = [...options];
  if (current && !values.includes(current)) {
    values.push(current);
  }
  return values;
}

function catalogDetailLines(catalog: MedicationCatalogSnapshot): string[] {
  return [
    catalog.generic_name ? `ژنریک: ${catalog.generic_name}` : "",
    catalog.brand_name ? `برند: ${catalog.brand_name}` : "",
    catalog.strength_raw ? `مقدار: ${catalog.strength_raw}` : "",
    catalog.dosage_form ? `شکل: ${catalog.dosage_form}` : "",
    catalog.manufacturer ? `سازنده: ${catalog.manufacturer}` : "",
    catalog.company_name ? `شرکت: ${catalog.company_name}` : "",
  ].filter(Boolean);
}

function definedOnly<T extends Record<string, unknown>>(value: T | null | undefined): Partial<T> {
  if (!value) {
    return {};
  }
  return Object.fromEntries(
    Object.entries(value).filter(([, item]) => item !== null && item !== undefined),
  ) as Partial<T>;
}

function mergeObjects<T extends Record<string, unknown>>(
  base: T | null | undefined,
  incoming: T | null | undefined,
): T | null {
  if (!base && !incoming) {
    return null;
  }
  return { ...(base ?? {}), ...definedOnly(incoming) } as T;
}

function catalogSnapshotFromResult(result: MedicationSearchResult): MedicationCatalogSnapshot {
  return {
    catalog_id: result.id,
    brand_name: result.brand_name ?? result.brand_name_en ?? result.brand_name_fa,
    brand_name_fa: result.brand_name_fa,
    brand_name_en: result.brand_name_en,
    generic_name: result.generic_name ?? result.generic_name_en,
    generic_name_en: result.generic_name_en,
    generic_slug: result.generic_slug,
    brand_slug: result.brand_slug,
    strength_raw: result.strength,
    dosage_form: result.form,
    manufacturer: result.manufacturer,
    company_name: result.company_name,
    company_slug: result.company_slug,
  };
}

type MedicalOverviewCardProps = {
  value: MedicalOverview;
  onChange: Dispatch<SetStateAction<MedicalOverview>>;
  sessionId: string;
  conditionFiles: Record<string, ConditionFile>;
  onConditionFileChange: (conditionId: string, file: ConditionFile | null) => void;
  labBindIds: string[];
  onAddLabResult: () => void;
  onRemoveLabResult: (index: number) => void;
  onLabExtractedData: (bindId: string, extracted: string) => void;
  llmPatientQuestions?: string[];
  disabled?: boolean;
};

function MedicationRow({
  medication,
  sessionId,
  file,
  isOcrLoading,
  ocrCandidates,
  onMedicationChange,
  onConditionFileChange,
  onUploadStart,
  onUploadComplete,
  onResolveOcrCandidate,
  onRemove,
  disabled,
}: {
  medication: CurrentMedication;
  sessionId: string;
  file: ConditionFile | null;
  isOcrLoading: boolean;
  ocrCandidates: ExtractedMedicationCandidate[] | null;
  onMedicationChange: (patch: Partial<CurrentMedication>) => void;
  onConditionFileChange: (conditionId: string, file: ConditionFile | null) => void;
  onUploadStart: (conditionId: string) => void;
  onUploadComplete: (
    conditionId: string,
    file: ConditionFile,
    extractedMedications: ExtractedMedication[] | null | undefined,
  ) => void;
  onResolveOcrCandidate: (rowId: string, candidate: ExtractedMedicationCandidate) => void;
  onRemove: () => void;
  disabled?: boolean;
}) {
  const prescription = medication.prescription ?? null;
  const reviewState = medication.provenance?.verification_status ?? null;
  const quantityInvalid = isNegativeNumber(prescription?.quantity);
  const durationInvalid = isNegativeNumber(prescription?.duration);

  const fieldHint = (value: string | null | undefined) =>
    value ? null : (
      <span className="text-[10px] font-normal text-slate-400">مشخص نشده</span>
    );

  const updatePrescription = (patch: Partial<MedicationPrescription>) => {
    const next: MedicationPrescription = {
      dose: prescription?.dose ?? null,
      dose_unit: prescription?.dose_unit ?? null,
      quantity: prescription?.quantity ?? null,
      frequency: prescription?.frequency ?? null,
      duration: prescription?.duration ?? null,
      route: prescription?.route ?? null,
      instructions: prescription?.instructions ?? null,
      ...patch,
    };
    // Only the dose/dose_unit fields drive the legacy amount mirror. Editing
    // another prescription field must never erase previously recorded legacy
    // data (e.g. an old "۱ قرص" amount on a record without a structured dose).
    const doseTouched = Object.prototype.hasOwnProperty.call(patch, "dose");
    const nextAmount = doseTouched
      ? prescriptionAmount(next)
      : prescriptionAmount(next) || medication.amount || "";
    onMedicationChange({
      prescription: next,
      amount: nextAmount,
      frequency: next.frequency ?? "",
      dose_unit: next.dose_unit ?? medication.dose_unit ?? null,
    });
  };

  const toggleFrequency = (chip: string) => {
    updatePrescription({ frequency: prescription?.frequency === chip ? null : chip });
  };

  return (
    <div className="space-y-2 border-b border-gray-100 pb-3">
      <div className={MEDICATION_COMPACT_ROW_CLASS} dir="auto">
        <div className="relative min-w-0 flex-1" dir="ltr">
          <input
            type="text"
            className="field-input w-full text-left"
            dir="ltr"
            value={medication.name}
            onChange={(e) =>
              onMedicationChange({
                name: e.target.value,
                catalog_id: null,
                dose_unit: null,
                catalog: null,
                prescription: null,
                provenance: null,
              })
            }
            placeholder="نام دارو"
            disabled={disabled || isOcrLoading}
          />
          {isOcrLoading ? (
            <div className="pointer-events-none absolute inset-y-0 left-2 flex items-center text-slate-400">
              <Loader2 className="h-4 w-4 animate-spin" />
            </div>
          ) : null}
        </div>
        <InlineConditionUpload
          sessionId={sessionId}
          conditionId={medication.id}
          conditionType="medication"
          file={file}
          onFileChange={onConditionFileChange}
          onUploadStart={onUploadStart}
          onUploadComplete={onUploadComplete}
          disabled={disabled}
        />
        <button
          type="button"
          onClick={onRemove}
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:border-red-200 hover:text-red-600"
          aria-label="حذف دارو"
          disabled={disabled}
        >
          <X className="h-4 w-4" />
        </button>
      </div>
      {reviewState === "needs_review" ? (
        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2">
          <span className="text-xs font-semibold text-amber-900">نیاز به بررسی</span>
          <button
            type="button"
            onClick={() =>
              onMedicationChange({
                provenance: {
                  source: medication.provenance?.source ?? "ocr",
                  confidence: medication.provenance?.confidence ?? null,
                  verification_status: "confirmed",
                },
              })
            }
            className="rounded-full border border-amber-400 px-2.5 py-0.5 text-xs font-semibold text-amber-900 transition-colors hover:bg-amber-100"
            disabled={disabled}
          >
            تأیید
          </button>
        </div>
      ) : null}
      {reviewState === "ambiguous" ? (
        <div
          className="rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900"
          role="status"
        >
          چند داروی مشابه شناسایی شد — یکی از گزینه‌ها را انتخاب کنید
        </div>
      ) : null}
      {medication.catalog ? (
        <div
          className="rounded-xl border border-mint/50 bg-mint/10 px-3 py-2 text-xs leading-relaxed text-slate-700"
          dir="auto"
        >
          {catalogDetailLines(medication.catalog).join(" · ")}
        </div>
      ) : null}
      {!medication.prescription &&
      (medication.amount.trim() || medication.frequency.trim()) ? (
        <div
          className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-600"
          dir="rtl"
        >
          مقدار قبلی: {medication.amount.trim() || "—"} · دفعات: {medication.frequency.trim() || "—"}
        </div>
      ) : null}
      {ocrCandidates && ocrCandidates.length > 0 ? (
        <div
          className="rounded-xl border border-amber-300 bg-amber-50 p-3"
          role="group"
          aria-label="داروهای مشابه"
        >
          <p className="mb-2 text-xs font-bold text-amber-900">
            چند داروی مشابه شناسایی شد — گزینه صحیح را انتخاب کنید
          </p>
          <ul className="space-y-2">
            {ocrCandidates.map((candidate, index) => (
              <li key={candidate.catalog_id}>
                <button
                  type="button"
                  onClick={() => onResolveOcrCandidate(medication.id, candidate)}
                  className="w-full rounded-lg border border-amber-300 bg-white px-3 py-2 text-start transition-colors hover:border-amber-500 hover:bg-amber-50 disabled:cursor-not-allowed disabled:opacity-60"
                  disabled={disabled}
                >
                  <span className="block text-sm font-semibold text-slate-900">
                    {index + 1}. {candidate.name}
                  </span>
                  {candidate.generic_name ? (
                    <span className="block text-xs text-slate-600" dir="auto">
                      {candidate.generic_name}
                    </span>
                  ) : null}
                  {candidate.strength || candidate.form ? (
                    <span className="block text-xs text-slate-500" dir="auto">
                      {[candidate.strength, candidate.form].filter(Boolean).join(" · ")}
                    </span>
                  ) : null}
                  {candidate.manufacturer || candidate.company ? (
                    <span className="block text-xs text-slate-400" dir="auto">
                      {[candidate.manufacturer && `سازنده: ${candidate.manufacturer}`, candidate.company && `شرکت: ${candidate.company}`]
                        .filter(Boolean)
                        .join(" · ")}
                    </span>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
      <div className="grid gap-2 sm:grid-cols-2" dir="rtl">
        <label className="block space-y-1">
          <span className="text-xs font-medium text-slate-600">
            دوز در هر نوبت {fieldHint(prescription?.dose)}
          </span>
          <input
            type="text"
            className="field-input w-full text-right"
            dir="rtl"
            value={prescription?.dose ?? ""}
            onChange={(e) => updatePrescription({ dose: e.target.value || null })}
            placeholder="۱"
            disabled={disabled}
          />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-slate-600">
            تعداد در روز {fieldHint(prescription?.frequency)}
          </span>
          <input
            type="text"
            className="field-input w-full text-right"
            dir="rtl"
            value={prescription?.frequency ?? ""}
            onChange={(e) => updatePrescription({ frequency: e.target.value || null })}
            placeholder="روزی ۱ بار"
            disabled={disabled}
          />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-slate-600">
            واحد دوز {fieldHint(prescription?.dose_unit)}
          </span>
          <select
            className="field-input w-full text-right"
            dir="rtl"
            aria-label="واحد دوز"
            value={prescription?.dose_unit ?? ""}
            onChange={(e) => updatePrescription({ dose_unit: e.target.value || null })}
            disabled={disabled}
          >
            <option value="">—</option>
            {selectOptions(prescription?.dose_unit, DOSE_UNIT_OPTIONS).map((unit) => (
              <option key={unit} value={unit}>
                {unit}
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-slate-600">
            تعداد کل (مقدار) {fieldHint(prescription?.quantity)}
          </span>
          <input
            type="text"
            aria-invalid={quantityInvalid || undefined}
            className={`field-input w-full text-right${quantityInvalid ? " border-red-400" : ""}`}
            dir="rtl"
            value={prescription?.quantity ?? ""}
            onChange={(e) => updatePrescription({ quantity: e.target.value || null })}
            placeholder="مثلاً ۳۰"
            disabled={disabled}
          />
          {quantityInvalid ? (
            <span className="text-[11px] text-red-600">تعداد نمی‌تواند منفی باشد</span>
          ) : null}
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-slate-600">
            مدت مصرف {fieldHint(prescription?.duration)}
          </span>
          <input
            type="text"
            aria-invalid={durationInvalid || undefined}
            className={`field-input w-full text-right${durationInvalid ? " border-red-400" : ""}`}
            dir="rtl"
            value={prescription?.duration ?? ""}
            onChange={(e) => updatePrescription({ duration: e.target.value || null })}
            placeholder="۳۰ روز"
            disabled={disabled}
          />
          {durationInvalid ? (
            <span className="text-[11px] text-red-600">مدت مصرف نمی‌تواند منفی باشد</span>
          ) : null}
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-slate-600">
            روش مصرف {fieldHint(prescription?.route)}
          </span>
          <select
            className="field-input w-full text-right"
            dir="rtl"
            aria-label="روش مصرف"
            value={prescription?.route ?? ""}
            onChange={(e) => updatePrescription({ route: e.target.value || null })}
            disabled={disabled}
          >
            <option value="">—</option>
            {selectOptions(prescription?.route, ROUTE_OPTIONS).map((route) => (
              <option key={route} value={route}>
                {route}
              </option>
            ))}
          </select>
        </label>
        <label className="block space-y-1 sm:col-span-2">
          <span className="text-xs font-medium text-slate-600">
            دستور مصرف {fieldHint(prescription?.instructions)}
          </span>
          <textarea
            className="field-input min-h-[56px] w-full resize-none text-right"
            dir="rtl"
            value={prescription?.instructions ?? ""}
            onChange={(e) => updatePrescription({ instructions: e.target.value || null })}
            placeholder="مثلاً بعد از غذا، قبل از خواب"
            disabled={disabled}
          />
        </label>
      </div>
      <div dir="rtl">
        <SuggestionChips
          suggestions={[...MEDICATION_FREQUENCY_OPTIONS]}
          selectedChips={prescription?.frequency ? [prescription.frequency] : []}
          onChipClick={toggleFrequency}
          disabled={disabled}
        />
      </div>
    </div>
  );
}

function ExtraConditionRow({
  condition,
  sessionId,
  file,
  onConditionChange,
  onConditionFileChange,
  onRemove,
  disabled,
}: {
  condition: ChronicCondition;
  sessionId: string;
  file: ConditionFile | null;
  onConditionChange: (patch: Partial<ChronicCondition>) => void;
  onConditionFileChange: (conditionId: string, file: ConditionFile | null) => void;
  onRemove: () => void;
  disabled?: boolean;
}) {
  return (
    <div className={COMPACT_ROW_CLASS}>
      <input
        type="text"
        className="field-input min-w-0 flex-1"
        value={condition.name}
        onChange={(e) => onConditionChange({ name: e.target.value })}
        placeholder="مثلاً دیابت نوع ۲"
        disabled={disabled}
      />
      <input
        type="text"
        className="field-input w-full shrink-0 sm:w-24"
        value={condition.duration}
        onChange={(e) => onConditionChange({ duration: e.target.value })}
        placeholder="۵ سال"
        disabled={disabled}
      />
      <InlineConditionUpload
        sessionId={sessionId}
        conditionId={condition.id}
        conditionType="chronic"
        file={file}
        onFileChange={onConditionFileChange}
        disabled={disabled}
      />
      <button
        type="button"
        onClick={onRemove}
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:border-red-200 hover:text-red-600"
        aria-label="حذف بیماری"
        disabled={disabled}
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}

export function MedicalOverviewCard({
  value,
  onChange,
  sessionId,
  conditionFiles,
  onConditionFileChange,
  labBindIds,
  onAddLabResult,
  onRemoveLabResult,
  onLabExtractedData,
  llmPatientQuestions,
  disabled,
}: MedicalOverviewCardProps) {
  const [ocrLoadingId, setOcrLoadingId] = useState<string | null>(null);
  const [pendingOcrCandidates, setPendingOcrCandidates] = useState<
    Record<string, ExtractedMedicationCandidate[]>
  >({});

  const updateField = <K extends keyof MedicalOverview>(field: K, fieldValue: MedicalOverview[K]) => {
    onChange((prev) => ({ ...prev, [field]: fieldValue }));
  };

  const addCondition = () => {
    const condition: ChronicCondition = {
      id: crypto.randomUUID(),
      name: "",
      duration: "",
    };
    updateField("chronic_conditions", [...value.chronic_conditions, condition]);
  };

  const addConditionFromChip = (name: string) => {
    const trimmed = name.trim();
    if (!trimmed) {
      return;
    }
    const exists = value.chronic_conditions.some((c) => c.name.trim() === trimmed);
    if (exists) {
      return;
    }
    const condition: ChronicCondition = {
      id: crypto.randomUUID(),
      name: trimmed,
      duration: "",
    };
    updateField("chronic_conditions", [...value.chronic_conditions, condition]);
  };

  const updateCondition = (id: string, patch: Partial<ChronicCondition>) => {
    updateField(
      "chronic_conditions",
      value.chronic_conditions.map((c) => (c.id === id ? { ...c, ...patch } : c)),
    );
  };

  const removeCondition = (id: string) => {
    onConditionFileChange(id, null);
    updateField(
      "chronic_conditions",
      value.chronic_conditions.filter((c) => c.id !== id),
    );
  };

  const addMedication = () => {
    const medication: CurrentMedication = {
      id: crypto.randomUUID(),
      name: "",
      amount: "",
      frequency: "",
    };
    onChange((prev) => ({
      ...prev,
      current_medications: [...prev.current_medications, medication],
    }));
  };

  const addResolvedMedication = (result: MedicationSearchResult) => {
    onChange((prev) => {
      const normalizedName = result.display_name.trim().toLocaleLowerCase();
      if (
        prev.current_medications.some(
          (medication) =>
            medication.catalog_id === result.id ||
            medication.name.trim().toLocaleLowerCase() === normalizedName,
        )
      ) {
        return prev;
      }
      return {
        ...prev,
        current_medications: [
          ...prev.current_medications,
          {
            id: crypto.randomUUID(),
            catalog_id: result.id,
            name: result.display_name,
            amount: "",
            frequency: "",
            dose_unit: result.dose_unit,
            catalog: catalogSnapshotFromResult(result),
            prescription: {
              dose: null,
              dose_unit: result.dose_unit,
              quantity: null,
              frequency: null,
              duration: null,
              route: null,
              instructions: null,
            },
            provenance: {
              source: "manual",
              confidence: null,
              verification_status: "confirmed",
            },
          },
        ],
      };
    });
  };

  const updateMedication = (id: string, patch: Partial<CurrentMedication>) => {
    onChange((prev) => ({
      ...prev,
      current_medications: prev.current_medications.map((medication) =>
        medication.id === id ? { ...medication, ...patch } : medication,
      ),
    }));
  };

  const removeMedication = (id: string) => {
    onConditionFileChange(id, null);
    setPendingOcrCandidates((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
    onChange((prev) => ({
      ...prev,
      current_medications: prev.current_medications.filter((medication) => medication.id !== id),
    }));
  };

  const resolveOcrCandidate = (rowId: string, candidate: ExtractedMedicationCandidate) => {
    setPendingOcrCandidates((prev) => {
      const next = { ...prev };
      delete next[rowId];
      return next;
    });
    onChange((prev) => ({
      ...prev,
      current_medications: prev.current_medications.map((item) =>
        item.id === rowId
          ? {
              ...item,
              catalog_id: candidate.catalog_id,
              name: candidate.name,
              dose_unit: candidate.dose_unit ?? item.dose_unit ?? null,
              catalog: candidate.catalog ?? item.catalog ?? null,
              provenance: {
                source: item.provenance?.source ?? "ocr",
                confidence: item.provenance?.confidence ?? null,
                verification_status: "confirmed",
              },
            }
          : item,
      ),
    }));
  };

  const handleMedicationUploadStart = (conditionId: string) => {
    setOcrLoadingId(conditionId);
  };

  const handleMedicationUploadComplete = (
    conditionId: string,
    _file: ConditionFile,
    extractedMedications: ExtractedMedication[] | null | undefined,
  ) => {
    setOcrLoadingId(null);
    if (!extractedMedications?.length) {
      return;
    }

    const [first, ...rest] = extractedMedications;
    const ambiguous = Boolean(first.ambiguous && first.candidates && first.candidates.length > 0);

    // Resolve which row owns the OCR merge before mutating state so the
    // candidate panel can be keyed by a stable row id.
    const targetIndex = value.current_medications.findIndex((item) => item.id === conditionId);
    const targetRow = targetIndex >= 0 ? value.current_medications[targetIndex] : null;
    const targetBlank = !targetRow || !targetRow.name.trim();
    const targetConfirmed =
      Boolean(targetRow?.catalog) &&
      targetRow?.provenance?.verification_status === "confirmed";

    let ownerRowId = conditionId;
    let mergeBase: CurrentMedication | null = targetRow;
    let dropBlankTarget = false;

    if (targetBlank) {
      const dedupMatch = value.current_medications.find(
        (item) =>
          item.id !== conditionId &&
          (first.catalog_id != null && item.catalog_id === first.catalog_id
            ? true
            : item.name.trim().toLocaleLowerCase() === first.name.trim().toLocaleLowerCase()),
      );
      if (dedupMatch) {
        ownerRowId = dedupMatch.id;
        mergeBase = dedupMatch;
        dropBlankTarget = targetIndex >= 0;
      }
    }

    // An ambiguous OCR match must not silently finalize the top candidate.
    const showAmbiguity = ambiguous && !targetConfirmed;

    // A confirmed row keeps its product identity when OCR is ambiguous:
    // never silently swap in the OCR top candidate, never downgrade the
    // confirmed provenance, and never attach an unresolvable candidate
    // panel. Only explicit OCR-extracted prescription fields are merged.
    const keepConfirmedIdentity = targetConfirmed && ambiguous;

    const existingFingerprints = new Set(
      value.current_medications.map((med) => medicationFingerprint(med)),
    );

    let medications = value.current_medications.filter(
      (item) => !(dropBlankTarget && item.id === conditionId),
    );

    const mergedPrescription = mergeObjects(mergeBase?.prescription, first.prescription);
    const mergePatch: Partial<CurrentMedication> = {
      name: keepConfirmedIdentity ? (mergeBase?.name ?? first.name) : first.name,
      amount: prescriptionAmount(mergedPrescription) || first.amount || mergeBase?.amount || "",
      frequency:
        mergedPrescription?.frequency || first.frequency || mergeBase?.frequency || "",
      catalog_id: showAmbiguity || keepConfirmedIdentity
        ? (mergeBase?.catalog_id ?? null)
        : (first.catalog_id ?? mergeBase?.catalog_id ?? null),
      dose_unit: showAmbiguity
        ? (mergedPrescription?.dose_unit ?? mergeBase?.dose_unit ?? null)
        : (mergedPrescription?.dose_unit ?? first.dose_unit ?? mergeBase?.dose_unit ?? null),
      // OCR supplies a complete catalog snapshot for the product it
      // identified; it replaces the previous product identity wholesale
      // instead of mixing catalog facts across products. Ambiguous matches
      // wait for the user to pick a candidate instead.
      catalog: showAmbiguity || keepConfirmedIdentity
        ? (mergeBase?.catalog ?? null)
        : (first.catalog ?? mergeBase?.catalog ?? null),
      prescription: mergedPrescription,
      provenance: showAmbiguity
        ? {
            source: "ocr",
            confidence: first.provenance?.confidence ?? null,
            verification_status: "ambiguous",
          }
        : keepConfirmedIdentity
          ? (mergeBase?.provenance ?? null)
        : mergeObjects(mergeBase?.provenance, first.provenance),
    };

    medications = medications.map((item) =>
      item.id === ownerRowId ? { ...item, ...mergePatch } : item,
    );
    if (!mergeBase) {
      medications = [
        {
          id: ownerRowId,
          name: mergePatch.name ?? "",
          amount: mergePatch.amount ?? "",
          frequency: mergePatch.frequency ?? "",
          catalog_id: mergePatch.catalog_id ?? null,
          dose_unit: mergePatch.dose_unit ?? null,
          catalog: mergePatch.catalog ?? null,
          prescription: mergePatch.prescription ?? null,
          provenance: mergePatch.provenance ?? null,
        },
        ...medications,
      ];
    }

    existingFingerprints.add(medicationFingerprint(first));

    const newRows: CurrentMedication[] = [];
    const pendingAmbiguous: Array<[string, ExtractedMedicationCandidate[]]> = [];
    for (const med of rest) {
      const fingerprint = medicationFingerprint({
        name: med.name,
        amount: prescriptionAmount(med.prescription) || med.amount || "",
        frequency: med.prescription?.frequency || med.frequency || "",
      });
      if (existingFingerprints.has(fingerprint)) {
        continue;
      }
      existingFingerprints.add(fingerprint);
      const medAmbiguous = Boolean(med.ambiguous && med.candidates && med.candidates.length > 0);
      const rowId = crypto.randomUUID();
      newRows.push({
        id: rowId,
        name: med.name,
        amount: prescriptionAmount(med.prescription) || med.amount || "",
        frequency: med.prescription?.frequency || med.frequency || "",
        catalog_id: medAmbiguous ? null : (med.catalog_id ?? null),
        dose_unit: med.prescription?.dose_unit ?? med.dose_unit ?? null,
        catalog: medAmbiguous ? null : (med.catalog ?? null),
        prescription: med.prescription ?? null,
        provenance: medAmbiguous
          ? {
              source: "ocr",
              confidence: med.provenance?.confidence ?? null,
              verification_status: "ambiguous",
            }
          : (med.provenance ?? null),
      });
      if (medAmbiguous) {
        pendingAmbiguous.push([rowId, med.candidates ?? []]);
      }
    }

    onChange({
      ...value,
      current_medications: [...medications, ...newRows],
    });

    if (showAmbiguity || pendingAmbiguous.length > 0) {
      setPendingOcrCandidates((prev) => {
        const next = { ...prev };
        if (showAmbiguity) {
          next[ownerRowId] = first.candidates ?? [];
        }
        for (const [rowId, candidates] of pendingAmbiguous) {
          next[rowId] = candidates;
        }
        return next;
      });
    }
  };

  const addLabResult = () => {
    onAddLabResult();
  };

  const updateLabResult = (index: number, name: string) => {
    updateField(
      "lab_results",
      value.lab_results.map((lab, i) => (i === index ? { ...lab, name } : lab)),
    );
  };

  const removeLabResult = (index: number) => {
    const bindId = labBindIds[index];
    if (bindId) {
      onConditionFileChange(bindId, null);
    }
    onRemoveLabResult(index);
  };

  return (
    <div className="medical-card space-y-4">
      <HybridChipInput
        label="سابقه حساسیت"
        value={value.allergies}
        suggestions={ALLERGY_SUGGESTIONS}
        onChange={(v) => updateField("allergies", v)}
        otherPlaceholder="حساسیت‌های دیگر را بنویسید..."
        disabled={disabled}
      />
      <HybridChipInput
        label="سابقه جراحی"
        value={value.surgical_history}
        suggestions={SURGERY_SUGGESTIONS}
        onChange={(v) => updateField("surgical_history", v)}
        otherPlaceholder="جراحی‌های دیگر را بنویسید..."
        disabled={disabled}
      />
      <HybridChipInput
        label="سابقه خانوادگی"
        value={value.family_history}
        suggestions={FAMILY_SUGGESTIONS}
        onChange={(v) => updateField("family_history", v)}
        otherPlaceholder="بیماری‌های خانوادگی دیگر را بنویسید..."
        disabled={disabled}
      />

      <div className="space-y-2">
        <h3 className="text-sm font-bold text-slate-900">بیماری‌های مزمن</h3>
        <SuggestionChips
          suggestions={CHRONIC_DISEASE_SUGGESTIONS}
          disabledChips={value.chronic_conditions.map((c) => c.name.trim()).filter(Boolean)}
          onChipClick={addConditionFromChip}
          disabled={disabled}
        />
        {value.chronic_conditions.length > 0 ? (
          <div className="space-y-0 pt-1">
            {value.chronic_conditions.map((condition) => (
              <ExtraConditionRow
                key={condition.id}
                condition={condition}
                sessionId={sessionId}
                file={conditionFiles[condition.id] ?? null}
                onConditionChange={(patch) => updateCondition(condition.id, patch)}
                onConditionFileChange={onConditionFileChange}
                onRemove={() => removeCondition(condition.id)}
                disabled={disabled}
              />
            ))}
          </div>
        ) : null}
        <button
          type="button"
          onClick={addCondition}
          className="inline-flex items-center gap-2 rounded-full border border-trust/30 px-3 py-1.5 text-sm font-semibold text-trust transition-colors hover:bg-trust/5"
          disabled={disabled}
        >
          <Plus className="h-4 w-4" />
          افزودن بیماری
        </button>
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-bold text-slate-900">داروهای فعلی</h3>
        <DrugSearch
          selectedCatalogIds={new Set(
            value.current_medications
              .map((medication) => medication.catalog_id)
              .filter((catalogId): catalogId is number => catalogId != null),
          )}
          selectedNames={new Set(
            value.current_medications
              .map((medication) => medication.name.trim().toLocaleLowerCase())
              .filter(Boolean),
          )}
          onSelect={addResolvedMedication}
          disabled={disabled}
        />
        {value.current_medications.length === 0 ? (
          <p className="text-sm text-slate-500">هنوز دارویی ثبت نشده است.</p>
        ) : (
          <div className="space-y-0">
            {value.current_medications.map((medication) => (
              <MedicationRow
                key={medication.id}
                medication={medication}
                sessionId={sessionId}
                file={conditionFiles[medication.id] ?? null}
                isOcrLoading={ocrLoadingId === medication.id}
                ocrCandidates={pendingOcrCandidates[medication.id] ?? null}
                onMedicationChange={(patch) => updateMedication(medication.id, patch)}
                onConditionFileChange={onConditionFileChange}
                onUploadStart={handleMedicationUploadStart}
                onUploadComplete={handleMedicationUploadComplete}
                onResolveOcrCandidate={resolveOcrCandidate}
                onRemove={() => removeMedication(medication.id)}
                disabled={disabled}
              />
            ))}
          </div>
        )}
        <button
          type="button"
          onClick={addMedication}
          className="inline-flex items-center gap-2 rounded-full border border-trust/30 px-3 py-1.5 text-sm font-semibold text-trust transition-colors hover:bg-trust/5"
          disabled={disabled}
        >
          <Plus className="h-4 w-4" />
          افزودن دارو
        </button>
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-bold text-slate-900">آزمایشات اخیر</h3>
        {value.lab_results.length === 0 ? (
          <p className="text-sm text-slate-500">هنوز آزمایشی ثبت نشده است.</p>
        ) : (
          <div className="space-y-0">
            {value.lab_results.map((lab, index) => {
              const bindId = labBindIds[index];
              return (
                <div key={bindId ?? index} className={COMPACT_ROW_CLASS}>
                  <input
                    type="text"
                    className="field-input min-w-0 flex-1"
                    value={lab.name}
                    onChange={(e) => updateLabResult(index, e.target.value)}
                    placeholder="مثلاً آزمایش خون CBC"
                    disabled={disabled}
                  />
                  {bindId ? (
                    <InlineConditionUpload
                      sessionId={sessionId}
                      conditionId={bindId}
                      conditionType="lab"
                      file={conditionFiles[bindId] ?? null}
                      onFileChange={onConditionFileChange}
                      onExtractedData={(extracted) => onLabExtractedData(bindId, extracted)}
                      disabled={disabled}
                    />
                  ) : null}
                  <button
                    type="button"
                    onClick={() => removeLabResult(index)}
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 text-slate-500 transition-colors hover:border-red-200 hover:text-red-600"
                    aria-label="حذف آزمایش"
                    disabled={disabled}
                  >
                    <X className="h-4 w-4" />
                  </button>
                </div>
              );
            })}
          </div>
        )}
        <button
          type="button"
          onClick={addLabResult}
          className="inline-flex items-center gap-2 rounded-full border border-trust/30 px-3 py-1.5 text-sm font-semibold text-trust transition-colors hover:bg-trust/5"
          disabled={disabled}
        >
          <Plus className="h-4 w-4" />
          افزودن آزمایش
        </button>
      </div>

      <div className="space-y-2 border-t border-slate-100 pt-4">
        <h3 className="text-sm font-bold text-slate-900">سوالات و ملاحظات</h3>
        {llmPatientQuestions?.length ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50/90 p-3">
            <div className="mb-2 flex items-center gap-2 text-amber-900">
              <MessageCircleQuestion className="h-5 w-5 shrink-0" />
              <p className="text-sm font-semibold">سوالات و ملاحظات بیمار</p>
            </div>
            <ul className="list-disc space-y-1 pr-5 text-sm leading-relaxed text-slate-800">
              {llmPatientQuestions.map((question) => (
                <li key={question}>{question}</li>
              ))}
            </ul>
          </div>
        ) : null}
        <label className="mb-1 block text-sm font-medium text-slate-700">
          آیا سوال دیگری از پزشک دارید؟
        </label>
        <textarea
          className="field-input min-h-[100px] resize-none"
          value={value.patient_questions ?? ""}
          onChange={(e) => updateField("patient_questions", e.target.value)}
          placeholder="اگر سوال خاصی دارید یا موردی هست که می‌خواهید پزشک حتماً بداند، اینجا بنویسید..."
          disabled={disabled}
        />
      </div>
    </div>
  );
}

function sanitizeCondition(condition: ChronicCondition): ChronicCondition | null {
  const name = condition.name.trim();
  const duration = condition.duration.trim();
  if (!name) {
    return null;
  }

  return {
    id: condition.id,
    name,
    duration,
  };
}

function sanitizeLabResult(lab: LabResult): LabResult | null {
  const name = lab.name.trim();
  if (!name) {
    return null;
  }

  return {
    id: lab.id,
    name,
    ...(lab.extracted_data ? { extracted_data: lab.extracted_data } : {}),
  };
}

function sanitizeMedication(
  medication: CurrentMedication,
  conditionFiles: Record<string, ConditionFile>,
): CurrentMedication | null {
  const name = medication.name.trim();
  const hasFile = Boolean(conditionFiles[medication.id]);
  if (!name && !hasFile) {
    return null;
  }
  const prescription = medication.prescription ?? null;
  // When the structured dose is still unknown, keep the legacy amount so an
  // edit on any other prescription field never erases previously recorded data.
  const amount = prescription
    ? prescriptionAmount(prescription) || medication.amount.trim()
    : medication.amount.trim();
  const frequency = prescription?.frequency || medication.frequency.trim();
  const dose_unit = prescription?.dose_unit ?? medication.dose_unit ?? null;

  return {
    id: medication.id,
    ...(medication.catalog_id != null ? { catalog_id: medication.catalog_id } : {}),
    name,
    amount,
    frequency,
    ...(dose_unit ? { dose_unit } : {}),
    ...(medication.catalog ? { catalog: medication.catalog } : {}),
    ...(prescription ? { prescription } : {}),
    ...(medication.provenance ? { provenance: medication.provenance } : {}),
  };
}

export function sanitizeMedicalOverview(
  value: MedicalOverview,
  conditionFiles: Record<string, ConditionFile> = {},
): MedicalOverview {
  const patientQuestions = value.patient_questions?.trim() || null;
  return {
    allergies: value.allergies.trim(),
    surgical_history: value.surgical_history.trim(),
    family_history: value.family_history.trim(),
    chronic_conditions: value.chronic_conditions
      .map(sanitizeCondition)
      .filter((condition): condition is ChronicCondition => condition !== null),
    current_medications: value.current_medications
      .map((medication) => sanitizeMedication(medication, conditionFiles))
      .filter((medication): medication is CurrentMedication => medication !== null),
    lab_results: value.lab_results
      .map(sanitizeLabResult)
      .filter((lab): lab is LabResult => lab !== null),
    patient_questions: patientQuestions,
  };
}
