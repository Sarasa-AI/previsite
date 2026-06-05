"use client";

import { useState, type FormEvent } from "react";
import { FileText } from "lucide-react";
import type { MedicalHistory } from "@/lib/intake";
import {
  ALLERGY_OPTIONS,
  FAMILY_HISTORY_OPTIONS,
  PMH_OPTIONS,
  SURGICAL_OPTIONS,
} from "@/lib/intake";

type Layer4Props = {
  initial?: MedicalHistory | null;
  onSubmit: (data: MedicalHistory) => Promise<void>;
  loading?: boolean;
};

const emptyHistory: MedicalHistory = {
  allergy_history: [],
  past_medical_history: [],
  past_surgical_history: [],
  family_history: [],
};

type MultiSelectFieldProps = {
  label: string;
  options: string[];
  selected: string[];
  onChange: (values: string[]) => void;
};

function MultiSelectField({ label, options, selected, onChange }: MultiSelectFieldProps) {
  const toggle = (value: string) => {
    if (value === "هیچ‌کدام") {
      onChange(["هیچ‌کدام"]);
      return;
    }
    const without = selected.filter((v) => v !== "هیچ‌کدام");
    if (without.includes(value)) {
      onChange(without.filter((v) => v !== value));
    } else {
      onChange([...without, value]);
    }
  };

  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-slate-700">{label}</label>
      <div className="flex flex-wrap gap-2">
        {options.map((opt) => (
          <button
            key={opt}
            type="button"
            onClick={() => toggle(opt)}
            className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition-all ${
              selected.includes(opt)
                ? "border-trust bg-trust text-white"
                : "border-slate-200 bg-white text-slate-600 hover:border-trust/40"
            }`}
          >
            {opt}
          </button>
        ))}
      </div>
    </div>
  );
}

export default function Layer4MedicalHistory({ initial, onSubmit, loading }: Layer4Props) {
  const [form, setForm] = useState<MedicalHistory>(initial ?? emptyHistory);

  const update = (field: keyof MedicalHistory, values: string[]) => {
    setForm((prev) => ({ ...prev, [field]: values }));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await onSubmit(form);
  };

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      <div className="flex items-center gap-3 text-trust">
        <FileText className="h-6 w-6" />
        <div>
          <p className="text-sm font-semibold">لایه ۴ — سوابق پزشکی</p>
          <h2 className="text-xl font-bold text-slate-900">تاریخچه پزشکی گذشته</h2>
        </div>
      </div>

      <MultiSelectField
        label="سابقه حساسیت"
        options={ALLERGY_OPTIONS}
        selected={form.allergy_history}
        onChange={(v) => update("allergy_history", v)}
      />
      <MultiSelectField
        label="سابقه بیماری"
        options={PMH_OPTIONS}
        selected={form.past_medical_history}
        onChange={(v) => update("past_medical_history", v)}
      />
      <MultiSelectField
        label="سابقه جراحی"
        options={SURGICAL_OPTIONS}
        selected={form.past_surgical_history}
        onChange={(v) => update("past_surgical_history", v)}
      />
      <MultiSelectField
        label="سابقه خانوادگی"
        options={FAMILY_HISTORY_OPTIONS}
        selected={form.family_history}
        onChange={(v) => update("family_history", v)}
      />

      <button className="primary-button w-full sm:w-auto" type="submit" disabled={loading}>
        {loading ? "در حال ذخیره..." : "تایید و ارسال به پزشک"}
      </button>
    </form>
  );
}
