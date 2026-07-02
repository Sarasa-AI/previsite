"use client";

import { Plus, X } from "lucide-react";
import { InlineConditionUpload } from "@/components/intake/InlineConditionUpload";
import type { ChronicCondition, ConditionFile, MedicalOverview } from "@/lib/pmh/types";

type MedicalOverviewCardProps = {
  value: MedicalOverview;
  onChange: (value: MedicalOverview) => void;
  sessionId: string;
  conditionFiles: Record<string, ConditionFile>;
  onConditionFileChange: (conditionId: string, file: ConditionFile | null) => void;
  disabled?: boolean;
};

type TextAreaFieldProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
  disabled?: boolean;
};

function TextAreaField({ label, value, onChange, placeholder, disabled }: TextAreaFieldProps) {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-slate-700">{label}</label>
      <textarea
        className="field-input min-h-[100px] resize-none"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
      />
    </div>
  );
}

export function MedicalOverviewCard({
  value,
  onChange,
  sessionId,
  conditionFiles,
  onConditionFileChange,
  disabled,
}: MedicalOverviewCardProps) {
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
    updateField("current_medications", [...value.current_medications, ""]);
  };

  const updateMedication = (index: number, medication: string) => {
    updateField(
      "current_medications",
      value.current_medications.map((m, i) => (i === index ? medication : m)),
    );
  };

  const removeMedication = (index: number) => {
    updateField(
      "current_medications",
      value.current_medications.filter((_, i) => i !== index),
    );
  };

  return (
    <div className="medical-card max-h-[70vh] space-y-8 overflow-y-auto">
      <TextAreaField
        label="سابقه حساسیت"
        value={value.allergies}
        onChange={(v) => updateField("allergies", v)}
        placeholder="حساسیت‌های دارویی یا غذایی را بنویسید..."
        disabled={disabled}
      />
      <TextAreaField
        label="سابقه جراحی"
        value={value.surgical_history}
        onChange={(v) => updateField("surgical_history", v)}
        placeholder="سوابق جراحی قبلی را بنویسید..."
        disabled={disabled}
      />
      <TextAreaField
        label="سابقه خانوادگی"
        value={value.family_history}
        onChange={(v) => updateField("family_history", v)}
        placeholder="بیماری‌های خانوادگی را بنویسید..."
        disabled={disabled}
      />

      <div className="space-y-4">
        <h3 className="text-base font-bold text-slate-900">بیماری‌های مزمن</h3>
        {value.chronic_conditions.length === 0 ? (
          <p className="text-sm text-slate-500">هنوز بیماری مزمنی ثبت نشده است.</p>
        ) : (
          <div className="space-y-3">
            {value.chronic_conditions.map((condition) => (
              <div
                key={condition.id}
                className="grid gap-3 rounded-2xl border border-slate-200 bg-slate-50/50 p-4 sm:grid-cols-[1fr_140px_120px_auto]"
              >
                <input
                  type="text"
                  className="field-input"
                  value={condition.name}
                  onChange={(e) => updateCondition(condition.id, { name: e.target.value })}
                  placeholder="مثلاً دیابت نوع ۲"
                  disabled={disabled}
                />
                <input
                  type="text"
                  className="field-input"
                  value={condition.duration}
                  onChange={(e) => updateCondition(condition.id, { duration: e.target.value })}
                  placeholder="مثلاً ۵ سال"
                  disabled={disabled}
                />
                <InlineConditionUpload
                  sessionId={sessionId}
                  conditionId={condition.id}
                  file={conditionFiles[condition.id] ?? null}
                  onFileChange={onConditionFileChange}
                  disabled={disabled}
                />
                <button
                  type="button"
                  onClick={() => removeCondition(condition.id)}
                  className="flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition-colors hover:border-red-200 hover:text-red-600"
                  aria-label="حذف بیماری"
                  disabled={disabled}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
        <button
          type="button"
          onClick={addCondition}
          className="inline-flex items-center gap-2 rounded-full border border-trust/30 px-4 py-2 text-sm font-semibold text-trust transition-colors hover:bg-trust/5"
          disabled={disabled}
        >
          <Plus className="h-4 w-4" />
          افزودن بیماری
        </button>
      </div>

      <div className="space-y-4">
        <h3 className="text-base font-bold text-slate-900">داروهای فعلی</h3>
        {value.current_medications.length === 0 ? (
          <p className="text-sm text-slate-500">هنوز دارویی ثبت نشده است.</p>
        ) : (
          <div className="space-y-3">
            {value.current_medications.map((medication, index) => (
              <div key={index} className="flex gap-3">
                <input
                  type="text"
                  className="field-input flex-1"
                  value={medication}
                  onChange={(e) => updateMedication(index, e.target.value)}
                  placeholder="نام دارو"
                  disabled={disabled}
                />
                <button
                  type="button"
                  onClick={() => removeMedication(index)}
                  className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition-colors hover:border-red-200 hover:text-red-600"
                  aria-label="حذف دارو"
                  disabled={disabled}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        )}
        <button
          type="button"
          onClick={addMedication}
          className="inline-flex items-center gap-2 rounded-full border border-trust/30 px-4 py-2 text-sm font-semibold text-trust transition-colors hover:bg-trust/5"
          disabled={disabled}
        >
          <Plus className="h-4 w-4" />
          افزودن دارو
        </button>
      </div>
    </div>
  );
}

export function sanitizeMedicalOverview(value: MedicalOverview): MedicalOverview {
  return {
    allergies: value.allergies.trim(),
    surgical_history: value.surgical_history.trim(),
    family_history: value.family_history.trim(),
    chronic_conditions: value.chronic_conditions
      .filter((c) => c.name.trim())
      .map((c) => ({
        id: c.id,
        name: c.name.trim(),
        duration: c.duration.trim(),
      })),
    current_medications: value.current_medications
      .map((m) => m.trim())
      .filter(Boolean),
  };
}
