"use client";

import { useState, type FormEvent } from "react";
import { User } from "lucide-react";
import type { Demographics } from "@/lib/intake";
import { INSURANCE_PROVIDERS, SEX_OPTIONS } from "@/lib/intake";

type Layer1Props = {
  initial?: Demographics | null;
  onSubmit: (data: Demographics) => Promise<void>;
  loading?: boolean;
};

const emptyForm: Demographics = {
  first_name: "",
  last_name: "",
  national_id: "",
  insurance_provider: INSURANCE_PROVIDERS[0],
  age: 0,
  sex: "female",
  weight: 0,
  height: 0,
  chief_complaint: "",
};

export default function Layer1Demographics({ initial, onSubmit, loading }: Layer1Props) {
  const [form, setForm] = useState<Demographics>(initial ?? emptyForm);

  const update = (field: keyof Demographics, value: string | number) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await onSubmit(form);
  };

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      <div className="flex items-center gap-3 text-trust">
        <User className="h-6 w-6" />
        <div>
          <p className="text-sm font-semibold">لایه ۱ — اطلاعات اولیه</p>
          <h2 className="text-xl font-bold text-slate-900">مشخصات بیمار و شکایت اصلی</h2>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">نام</label>
          <input
            className="field-input"
            value={form.first_name}
            onChange={(e) => update("first_name", e.target.value)}
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">نام خانوادگی</label>
          <input
            className="field-input"
            value={form.last_name}
            onChange={(e) => update("last_name", e.target.value)}
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">کد ملی</label>
          <input
            className="field-input"
            value={form.national_id}
            onChange={(e) => update("national_id", e.target.value)}
            pattern="\d{10}"
            maxLength={10}
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">بیمه</label>
          <select
            className="field-input"
            value={form.insurance_provider}
            onChange={(e) => update("insurance_provider", e.target.value)}
            required
          >
            {INSURANCE_PROVIDERS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">سن</label>
          <input
            className="field-input"
            type="number"
            min={0}
            max={150}
            value={form.age || ""}
            onChange={(e) => update("age", Number(e.target.value))}
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">جنسیت</label>
          <select
            className="field-input"
            value={form.sex}
            onChange={(e) => update("sex", e.target.value)}
            required
          >
            {SEX_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">وزن (کیلوگرم)</label>
          <input
            className="field-input"
            type="number"
            min={1}
            step="0.1"
            value={form.weight || ""}
            onChange={(e) => update("weight", Number(e.target.value))}
            required
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">قد (سانتی‌متر)</label>
          <input
            className="field-input"
            type="number"
            min={1}
            value={form.height || ""}
            onChange={(e) => update("height", Number(e.target.value))}
            required
          />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-sm font-medium text-slate-700">شکایت اصلی</label>
        <textarea
          className="field-input min-h-[100px] resize-none"
          value={form.chief_complaint}
          onChange={(e) => update("chief_complaint", e.target.value)}
          placeholder="مثلاً: دل درد، سردرد، یا مراجعه دوره‌ای دیابت"
          required
        />
      </div>

      <button className="primary-button w-full sm:w-auto" type="submit" disabled={loading}>
        {loading ? "در حال ذخیره..." : "ادامه به سوالات شرح حال"}
      </button>
    </form>
  );
}
