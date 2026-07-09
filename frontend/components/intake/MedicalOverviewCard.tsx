"use client";

import { useState } from "react";
import { Loader2, Plus, X } from "lucide-react";
import { HybridChipInput } from "@/components/intake/HybridChipInput";
import { InlineConditionUpload, type ExtractedMedication } from "@/components/intake/InlineConditionUpload";
import { SuggestionChips } from "@/components/intake/SuggestionChips";
import {
  MEDICATION_AMOUNT_OPTIONS,
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
  MedicalOverview,
} from "@/lib/pmh/types";

const COMPACT_ROW_CLASS = "flex flex-wrap items-center gap-2 border-b border-slate-100 py-1.5 sm:flex-nowrap";

type MedicalOverviewCardProps = {
  value: MedicalOverview;
  onChange: (value: MedicalOverview) => void;
  sessionId: string;
  conditionFiles: Record<string, ConditionFile>;
  onConditionFileChange: (conditionId: string, file: ConditionFile | null) => void;
  labBindIds: string[];
  onAddLabResult: () => void;
  onRemoveLabResult: (index: number) => void;
  onLabExtractedData: (bindId: string, extracted: string) => void;
  disabled?: boolean;
};

function MedicationRow({
  medication,
  sessionId,
  file,
  isOcrLoading,
  onMedicationChange,
  onConditionFileChange,
  onUploadStart,
  onUploadComplete,
  onRemove,
  disabled,
}: {
  medication: CurrentMedication;
  sessionId: string;
  file: ConditionFile | null;
  isOcrLoading: boolean;
  onMedicationChange: (patch: Partial<CurrentMedication>) => void;
  onConditionFileChange: (conditionId: string, file: ConditionFile | null) => void;
  onUploadStart: (conditionId: string) => void;
  onUploadComplete: (
    conditionId: string,
    file: ConditionFile,
    extractedMedications: ExtractedMedication[] | null | undefined,
  ) => void;
  onRemove: () => void;
  disabled?: boolean;
}) {
  const toggleAmount = (chip: string) => {
    onMedicationChange({ amount: medication.amount === chip ? "" : chip });
  };

  const toggleFrequency = (chip: string) => {
    onMedicationChange({ frequency: medication.frequency === chip ? "" : chip });
  };

  return (
    <div className="space-y-2 border-b border-slate-100 py-2 last:border-b-0">
      <div className={COMPACT_ROW_CLASS} dir="auto">
        <div className="relative min-w-0 flex-1" dir="ltr">
          <input
            type="text"
            className="field-input w-full text-left"
            dir="ltr"
            value={medication.name}
            onChange={(e) => onMedicationChange({ name: e.target.value })}
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
      <div className="grid gap-2 sm:grid-cols-2" dir="rtl">
        <label className="block space-y-1">
          <span className="text-xs font-medium text-slate-600">تعداد در هر وعده</span>
          <input
            type="text"
            className="field-input w-full text-right"
            dir="rtl"
            value={medication.amount}
            onChange={(e) => onMedicationChange({ amount: e.target.value })}
            placeholder="۱ عدد"
            disabled={disabled}
          />
        </label>
        <label className="block space-y-1">
          <span className="text-xs font-medium text-slate-600">تعداد در روز</span>
          <input
            type="text"
            className="field-input w-full text-right"
            dir="rtl"
            value={medication.frequency}
            onChange={(e) => onMedicationChange({ frequency: e.target.value })}
            placeholder="روزی ۱ بار"
            disabled={disabled}
          />
        </label>
      </div>
      <div dir="rtl">
        <SuggestionChips
          suggestions={[...MEDICATION_AMOUNT_OPTIONS]}
          selectedChips={medication.amount ? [medication.amount] : []}
          onChipClick={toggleAmount}
          disabled={disabled}
        />
      </div>
      <div dir="rtl">
        <SuggestionChips
          suggestions={[...MEDICATION_FREQUENCY_OPTIONS]}
          selectedChips={medication.frequency ? [medication.frequency] : []}
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
  disabled,
}: MedicalOverviewCardProps) {
  const [ocrLoadingId, setOcrLoadingId] = useState<string | null>(null);

  const updateField = <K extends keyof MedicalOverview>(field: K, fieldValue: MedicalOverview[K]) => {
    onChange({ ...value, [field]: fieldValue });
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
    updateField("current_medications", [...value.current_medications, medication]);
  };

  const updateMedication = (id: string, patch: Partial<CurrentMedication>) => {
    updateField(
      "current_medications",
      value.current_medications.map((medication) =>
        medication.id === id ? { ...medication, ...patch } : medication,
      ),
    );
  };

  const removeMedication = (id: string) => {
    onConditionFileChange(id, null);
    updateField(
      "current_medications",
      value.current_medications.filter((medication) => medication.id !== id),
    );
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
    let updated = [...value.current_medications];

    const current = updated.find((item) => item.id === conditionId);
    if (current) {
      updated = updated.map((item) =>
        item.id === conditionId
          ? {
              ...item,
              name: item.name.trim() || first.name,
              amount: item.amount.trim() || first.amount,
              frequency: item.frequency.trim() || first.frequency,
            }
          : item,
      );
    }

    const newRows: CurrentMedication[] = rest.map((med) => ({
      id: crypto.randomUUID(),
      name: med.name,
      amount: med.amount,
      frequency: med.frequency,
    }));

    onChange({ ...value, current_medications: [...updated, ...newRows] });
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
                onMedicationChange={(patch) => updateMedication(medication.id, patch)}
                onConditionFileChange={onConditionFileChange}
                onUploadStart={handleMedicationUploadStart}
                onUploadComplete={handleMedicationUploadComplete}
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
  const amount = medication.amount.trim();
  const frequency = medication.frequency.trim();
  const hasFile = Boolean(conditionFiles[medication.id]);
  if (!name && !hasFile) {
    return null;
  }

  return {
    id: medication.id,
    name,
    amount,
    frequency,
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
