"use client";

import { AlertTriangle, CheckCircle, FileText, Stethoscope, User, XCircle } from "lucide-react";
import type { ClinicalSummary, Demographics, IntakeData } from "@/lib/intake";
import type { MedicalOverview } from "@/lib/pmh/types";
import { SEX_OPTIONS } from "@/lib/intake";

type ClinicianDashboardProps = {
  intake: IntakeData;
};

function sexLabel(value?: string) {
  return SEX_OPTIONS.find((o) => o.value === value)?.label ?? value ?? "—";
}

function TagList({ items, variant }: { items: string[]; variant: "positive" | "negative" | "red" | "neutral" }) {
  const styles = {
    positive: "bg-mint/30 text-trust border-mint/50",
    negative: "bg-slate-100 text-slate-600 border-slate-200",
    red: "bg-red-50 text-red-700 border-red-200",
    neutral: "bg-slate-100 text-slate-700 border-slate-200",
  };

  if (!items.length) {
    return <span className="text-sm text-slate-500">ثبت نشده</span>;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item) => (
        <span key={item} className={`rounded-full border px-3 py-1 text-xs font-semibold ${styles[variant]}`}>
          {item}
        </span>
      ))}
    </div>
  );
}

function DemographicsCard({ data }: { data: Demographics }) {
  return (
    <div className="medical-card space-y-3">
      <div className="flex items-center gap-2 text-trust">
        <User className="h-5 w-5" />
        <h3 className="text-lg font-bold">مشخصات بیمار</h3>
      </div>
      <div className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div><span className="text-slate-500">نام:</span> {data.first_name} {data.last_name}</div>
        <div><span className="text-slate-500">کد ملی:</span> {data.national_id}</div>
        <div><span className="text-slate-500">سن:</span> {data.age} سال</div>
        <div><span className="text-slate-500">جنسیت:</span> {sexLabel(data.sex)}</div>
        <div><span className="text-slate-500">وزن:</span> {data.weight} kg</div>
        <div><span className="text-slate-500">قد:</span> {data.height} cm</div>
        <div><span className="text-slate-500">بیمه:</span> {data.insurance_provider}</div>
        <div><span className="text-slate-500">شکایت:</span> {data.chief_complaint}</div>
      </div>
    </div>
  );
}

function ClinicalSummaryCard({ summary }: { summary: ClinicalSummary }) {
  return (
    <div className="space-y-4">
      <div className="rounded-[28px] border border-trust/10 bg-trust/5 p-5">
        <div className="flex items-center gap-3">
          <Stethoscope className="h-6 w-6 text-trust" />
          <div>
            <p className="text-sm font-semibold text-trust">CC | دلیل مراجعه</p>
            <h2 className="text-2xl font-bold text-slate-900">{summary.chief_complaint}</h2>
          </div>
        </div>
      </div>

      <div className="medical-card space-y-3">
        <h3 className="text-lg font-bold text-trust">HPI | خلاصه شرح حال</h3>
        <p className="leading-relaxed text-slate-700">{summary.hpi_summary}</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="medical-card space-y-3">
          <div className="flex items-center gap-2 text-trust">
            <CheckCircle className="h-5 w-5" />
            <h3 className="font-bold">Positives</h3>
          </div>
          <TagList items={summary.pertinent_positives} variant="positive" />
        </div>
        <div className="medical-card space-y-3">
          <div className="flex items-center gap-2 text-slate-600">
            <XCircle className="h-5 w-5" />
            <h3 className="font-bold">Negatives</h3>
          </div>
          <TagList items={summary.pertinent_negatives} variant="negative" />
        </div>
        <div className="medical-card space-y-3">
          <div className="flex items-center gap-2 text-red-600">
            <AlertTriangle className="h-5 w-5" />
            <h3 className="font-bold">Red Flags</h3>
          </div>
          <TagList items={summary.red_flags} variant="red" />
        </div>
      </div>
    </div>
  );
}

function TextSection({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4">
      <p className="mb-2 text-sm font-semibold text-trust">{label}</p>
      <p className="text-sm leading-relaxed text-slate-700">{value.trim() || "ثبت نشده"}</p>
    </div>
  );
}

function MedicalOverviewCard({ overview }: { overview: MedicalOverview }) {
  return (
    <div className="medical-card space-y-4">
      <div className="flex items-center gap-2 text-trust">
        <FileText className="h-5 w-5" />
        <h3 className="text-lg font-bold">سوابق پزشکی (لایه ۴)</h3>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <TextSection label="حساسیت‌ها" value={overview.allergies} />
        <TextSection label="سوابق جراحی" value={overview.surgical_history} />
        <TextSection label="سابقه خانوادگی" value={overview.family_history} />
        <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 sm:col-span-2">
          <p className="mb-2 text-sm font-semibold text-trust">بیماری‌های مزمن</p>
          {overview.chronic_conditions.length === 0 ? (
            <span className="text-sm text-slate-500">ثبت نشده</span>
          ) : (
            <ul className="space-y-2 text-sm text-slate-700">
              {overview.chronic_conditions.map((condition) => (
                <li key={condition.id}>
                  {condition.name}
                  {condition.duration ? ` — ${condition.duration}` : ""}
                </li>
              ))}
            </ul>
          )}
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-4 sm:col-span-2">
          <p className="mb-2 text-sm font-semibold text-trust">داروهای فعلی</p>
          <TagList items={overview.current_medications} variant="neutral" />
        </div>
      </div>
    </div>
  );
}

export default function ClinicianDashboard({ intake }: ClinicianDashboardProps) {
  return (
    <section className="space-y-6">
      {intake.demographics && <DemographicsCard data={intake.demographics} />}
      {intake.clinical_summary && <ClinicalSummaryCard summary={intake.clinical_summary} />}
      {intake.medical_overview && <MedicalOverviewCard overview={intake.medical_overview} />}
    </section>
  );
}
