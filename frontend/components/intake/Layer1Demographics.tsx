"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { CheckCircle2, Pencil, User } from "lucide-react";
import type { Demographics } from "@/lib/intake";
import { INSURANCE_PROVIDERS, SEX_OPTIONS } from "@/lib/intake";
import type { PatientProfile } from "@/src/hooks/usePatientProfile";

type Layer1Props = {
  initial?: Demographics | null;
  sessionInitialComplaint?: string | null;
  profile?: PatientProfile | null;
  profileError?: string;
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

function profileToDemographics(profile: PatientProfile): Partial<Demographics> {
  return {
    first_name: profile.first_name ?? "",
    last_name: profile.last_name ?? "",
    national_id: profile.national_id ?? "",
    age: profile.age ?? 0,
    sex: profile.sex === "مرد" ? "male" : profile.sex === "زن" ? "female" : (profile.sex as "male" | "female") ?? "female",
    weight: profile.weight ?? 0,
    height: profile.height ?? 0,
  };
}

function sexLabel(value: string) {
  return SEX_OPTIONS.find((o) => o.value === value)?.label ?? value;
}

export default function Layer1Demographics({
  initial,
  sessionInitialComplaint,
  profile,
  profileError,
  onSubmit,
  loading,
}: Layer1Props) {
  const formInitialized = useRef(false);
  const [form, setForm] = useState<Demographics>(emptyForm);
  const [mode, setMode] = useState<"confirm" | "edit">("edit");

  useEffect(() => {
    if (formInitialized.current) return;

    const hasSessionData = Boolean(initial?.first_name || initial?.national_id);
    const profilePartial = profile ? profileToDemographics(profile) : {};
    const merged: Demographics = {
      ...emptyForm,
      ...profilePartial,
      ...(initial ?? {}),
    };
    if (!merged.chief_complaint?.trim() && sessionInitialComplaint?.trim()) {
      merged.chief_complaint = sessionInitialComplaint.trim();
    }

    const hasPrefillData =
      Object.values(profilePartial).some(Boolean) ||
      hasSessionData ||
      Boolean(sessionInitialComplaint?.trim());

    if (hasPrefillData) {
      setForm(merged);
      formInitialized.current = true;
      if (profile?.is_complete && !hasSessionData) {
        setMode("confirm");
      }
    }
  }, [initial, profile, sessionInitialComplaint]);

  const update = (field: keyof Demographics, value: string | number) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await onSubmit(form);
  };

  const profileComplete = profile?.is_complete ?? false;
  const showConfirm = mode === "confirm" && profileComplete;

  if (showConfirm) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3 text-trust">
          <CheckCircle2 className="h-6 w-6" />
          <div>
            <p className="text-sm font-semibold">لایه ۱ — تأیید اطلاعات</p>
            <h2 className="text-xl font-bold text-slate-900">اطلاعات شما از قبل ثبت شده است</h2>
          </div>
        </div>

        {profileError ? (
          <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            {profileError}
          </p>
        ) : null}

        <div className="rounded-2xl border border-mint/30 bg-mint/10 p-4 text-sm leading-7 text-slate-700">
          <p><span className="font-semibold">نام:</span> {form.first_name} {form.last_name}</p>
          <p><span className="font-semibold">کد ملی:</span> {form.national_id}</p>
          <p><span className="font-semibold">سن:</span> {form.age} سال</p>
          <p><span className="font-semibold">جنسیت:</span> {sexLabel(form.sex)}</p>
          <p><span className="font-semibold">وزن:</span> {form.weight} کیلوگرم</p>
          <p><span className="font-semibold">قد:</span> {form.height} سانتی‌متر</p>
        </div>

        <form className="space-y-4" onSubmit={handleSubmit}>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">بیمه (این ویزیت)</label>
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
            <label className="mb-1 block text-sm font-medium text-slate-700">شکایت اصلی (این ویزیت)</label>
            <textarea
              className="field-input min-h-[100px] resize-none"
              value={form.chief_complaint}
              onChange={(e) => update("chief_complaint", e.target.value)}
              placeholder="مثلاً: دل درد، سردرد، یا مراجعه دوره‌ای دیابت"
              required
            />
          </div>
          <div className="flex flex-wrap gap-3">
            <button className="primary-button" type="submit" disabled={loading}>
              {loading ? "در حال ذخیره..." : "تأیید و ادامه"}
            </button>
            <button
              className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
              type="button"
              onClick={() => setMode("edit")}
            >
              <Pencil className="h-4 w-4" />
              ویرایش اطلاعات
            </button>
          </div>
        </form>
      </div>
    );
  }

  return (
    <form className="space-y-6" onSubmit={handleSubmit}>
      <div className="flex items-center gap-3 text-trust">
        <User className="h-6 w-6" />
        <div>
          <p className="text-sm font-semibold">لایه ۱ — اطلاعات اولیه</p>
          <h2 className="text-xl font-bold text-slate-900">مشخصات بیمار و شکایت اصلی</h2>
        </div>
      </div>

      {profileError ? (
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {profileError}
        </p>
      ) : null}

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

      {profileComplete ? (
        <button
          className="text-sm text-trust hover:underline"
          type="button"
          onClick={() => setMode("confirm")}
        >
          بازگشت به حالت تأیید سریع
        </button>
      ) : null}

      <button className="primary-button w-full sm:w-auto" type="submit" disabled={loading}>
        {loading ? "در حال ذخیره..." : "ادامه به سوالات شرح حال"}
      </button>
    </form>
  );
}
