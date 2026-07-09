"use client";

import { FileText, MessageCircleQuestion } from "lucide-react";
import { fileDownloadUrl } from "@/lib/files";
import type { ConditionFile, CurrentMedication, MedicalOverview } from "@/lib/pmh/types";

function ReadOnlyFileChip({ file }: { file: ConditionFile }) {
  const href = fileDownloadUrl(file.id);
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex max-w-[160px] items-center gap-1.5 rounded-full border border-mint/70 bg-mint/25 px-2 py-1 text-trust"
      title={file.filename}
    >
      <FileText className="h-3.5 w-3.5 shrink-0" />
      <span className="truncate text-xs font-medium">{file.filename}</span>
    </a>
  );
}

function TextSection({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-3">
      <p className="mb-1 text-sm font-semibold text-trust">{label}</p>
      <p className="text-sm leading-relaxed text-slate-700">{value.trim() || "ثبت نشده"}</p>
    </div>
  );
}

function formatMedicationDetail(medication: CurrentMedication, hasFile: boolean): string {
  const name = medication.name.trim();
  const label = name || (hasFile ? "نامشخص - تصویر پیوست شد" : "—");
  const dosage = [medication.amount.trim(), medication.frequency.trim()].filter(Boolean).join(" ");
  return dosage ? `${label} - ${dosage}` : label;
}

function ConditionDisplayRow({
  label,
  detail,
  duration,
  file,
}: {
  label?: string;
  detail: string;
  duration?: string;
  file?: ConditionFile | null;
}) {
  return (
    <li className="flex flex-wrap items-center gap-2 border-b border-slate-100 py-1.5 text-sm text-slate-700 last:border-b-0">
      {label ? <span className="font-bold text-slate-900">{label}</span> : null}
      <span>{detail}</span>
      {duration ? <span className="text-slate-500">— {duration}</span> : null}
      {file ? <ReadOnlyFileChip file={file} /> : null}
    </li>
  );
}

type MedicalOverviewReadOnlyProps = {
  overview: MedicalOverview;
  conditionFiles?: Record<string, ConditionFile>;
};

export default function MedicalOverviewReadOnly({
  overview,
  conditionFiles = {},
}: MedicalOverviewReadOnlyProps) {
  const chronicRows = overview.chronic_conditions
    .map((condition) => {
      const file = conditionFiles[condition.id] ?? null;
      const detail = condition.name.trim();
      if (!detail && !condition.duration && !file) {
        return null;
      }
      return (
        <ConditionDisplayRow
          key={condition.id}
          detail={detail || "—"}
          duration={condition.duration}
          file={file}
        />
      );
    })
    .filter(Boolean);

  const medicationRows = overview.current_medications
    .map((medication) => {
      const file = conditionFiles[medication.id] ?? null;
      const hasFile = Boolean(file);
      const detail = formatMedicationDetail(medication, hasFile);
      if (!medication.name.trim() && !medication.amount && !medication.frequency && !hasFile) {
        return null;
      }
      return (
        <ConditionDisplayRow key={medication.id} detail={detail} file={file} />
      );
    })
    .filter(Boolean);

  const hasChronicData = chronicRows.length > 0;
  const hasMedicationData = medicationRows.length > 0;
  const hasLabData = overview.lab_results.some(
    (lab) => lab.name.trim() || lab.extracted_data || (lab.id && conditionFiles[lab.id]),
  );
  const patientQuestions = overview.patient_questions?.trim() ?? "";

  return (
    <div className="medical-card space-y-3">
      <div className="flex items-center gap-2 text-trust">
        <FileText className="h-5 w-5" />
        <h3 className="text-lg font-bold">سوابق پزشکی (لایه ۴)</h3>
      </div>
      {patientQuestions ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50/90 p-3">
          <div className="mb-2 flex items-center gap-2 text-amber-900">
            <MessageCircleQuestion className="h-5 w-5 shrink-0" />
            <p className="text-sm font-semibold">سوالات و ملاحظات بیمار</p>
          </div>
          <p className="text-sm leading-relaxed text-slate-800">{patientQuestions}</p>
        </div>
      ) : null}
      <div className="grid gap-3 sm:grid-cols-2">
        <TextSection label="حساسیت‌ها" value={overview.allergies} />
        <TextSection label="سوابق جراحی" value={overview.surgical_history} />
        <TextSection label="سابقه خانوادگی" value={overview.family_history} />
        <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-3 sm:col-span-2">
          <p className="mb-1 text-sm font-semibold text-trust">بیماری‌های مزمن</p>
          {!hasChronicData ? (
            <span className="text-sm text-slate-500">ثبت نشده</span>
          ) : (
            <ul className="space-y-0">
              {chronicRows}
            </ul>
          )}
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-3 sm:col-span-2">
          <p className="mb-1 text-sm font-semibold text-trust">داروهای فعلی</p>
          {!hasMedicationData ? (
            <span className="text-sm text-slate-500">ثبت نشده</span>
          ) : (
            <ul className="space-y-0">
              {medicationRows}
            </ul>
          )}
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50/80 p-3 sm:col-span-2">
          <p className="mb-1 text-sm font-semibold text-trust">آزمایشات</p>
          {!hasLabData ? (
            <span className="text-sm text-slate-500">ثبت نشده</span>
          ) : (
            <ul className="space-y-3">
              {overview.lab_results.map((lab) => {
                const file = conditionFiles[lab.id] ?? null;
                const name = lab.name.trim();
                if (!name && !lab.extracted_data && !file) {
                  return null;
                }
                return (
                  <li key={lab.id} className="border-b border-slate-100 pb-3 last:border-b-0 last:pb-0">
                    <div className="flex flex-wrap items-center gap-2 text-sm text-slate-700">
                      <span className="font-bold text-slate-900">{name || "—"}</span>
                      {file ? <ReadOnlyFileChip file={file} /> : null}
                    </div>
                    {lab.extracted_data ? (
                      <div className="mt-2 rounded-lg border border-slate-200 bg-slate-100/80 px-3 py-2 font-mono text-sm text-slate-800">
                        {lab.extracted_data}
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
