"use client";

import { useMemo, useState } from "react";
import { AlertCircle, ChevronDown, FileText, Loader2, Pill, RefreshCw, ShieldAlert, Stethoscope } from "lucide-react";
import AttachedDocumentsGrid from "@/components/shared/AttachedDocumentsGrid";
import SoapCitationText, { type SoapCitation } from "@/components/summary/SoapCitationText";

type SoapStatus = "pending" | "generating" | "failed" | "ready";

type SummaryPayload = {
  soap_note?: string | null;
  soap_status?: SoapStatus;
  soap_error_detail?: string | null;
  soap_citations?: SoapCitation[] | null;
  soap_verification_status?: string | null;
  medical_data?: {
    chief_complaint?: string | null;
    history_present_illness?: string | null;
    past_medical_history?: string | null;
    medications?: string | null;
    allergies?: string | null;
  };
};

type FileItem = {
  id: number;
  filename: string;
  size: number;
  mime_type: string;
  url: string;
};

type MedicalSummaryViewProps = {
  data: SummaryPayload;
  files?: FileItem[];
  onRetrySoap?: () => void;
  retryLoading?: boolean;
};

function parseList(value?: string | null) {
  if (!value) return [];
  return value
    .split(/[\n،,]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function soapSections(note?: string | null) {
  const source = note ?? "";
  const sections = [
    { key: "Subjective", patterns: [/Subjective/i, /\*\*S\s*-\s*Subjective/i, /ذهنی/i] },
    { key: "Objective", patterns: [/Objective/i, /\*\*O\s*-\s*Objective/i, /عینی/i] },
    { key: "Assessment", patterns: [/Assessment/i, /\*\*A\s*-\s*Assessment/i, /ارزیابی/i] },
    { key: "Plan", patterns: [/Plan/i, /\*\*P\s*-\s*Plan/i, /برنامه/i] },
  ];

  return sections.map((section, index) => {
    let start = -1;
    for (const pattern of section.patterns) {
      const match = source.match(pattern);
      if (match && match.index !== undefined) {
        start = match.index + match[0].length;
        break;
      }
    }

    let end = source.length;
    if (index < sections.length - 1) {
      for (let i = index + 1; i < sections.length; i++) {
        for (const pattern of sections[i].patterns) {
          const nextMatch = source.match(pattern);
          if (nextMatch && nextMatch.index !== undefined) {
            end = nextMatch.index;
            break;
          }
        }
        if (end !== source.length) break;
      }
    }

    const raw = start >= 0 ? source.slice(start, end) : "";
    return {
      title: section.key,
      content: raw.replace(/^[:\-\s#\*]+/, "").trim(),
    };
  });
}

function SoapSectionContent({
  title,
  content,
  status,
  errorDetail,
  onRetry,
  retryLoading,
  citations,
}: {
  title: string;
  content: string;
  status: SoapStatus;
  errorDetail?: string | null;
  onRetry?: () => void;
  retryLoading?: boolean;
  citations?: SoapCitation[];
}) {
  if (status === "generating") {
    return (
      <article className="glass-card min-h-[180px]">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-trust/75">{title}</p>
        <div className="mt-6 flex items-center gap-3 text-slate-500">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">در حال تولید خلاصه...</span>
        </div>
      </article>
    );
  }

  if (status === "failed") {
    return (
      <article className="glass-card min-h-[180px] border border-red-100">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-trust/75">{title}</p>
        <p className="mt-3 text-sm text-red-600">
          {errorDetail || "تولید SOAP ناموفق بود."}
        </p>
        {onRetry ? (
          <button
            type="button"
            className="mt-4 inline-flex items-center gap-2 rounded-xl border border-red-200 px-3 py-2 text-sm font-medium text-red-700 hover:bg-red-50"
            onClick={onRetry}
            disabled={retryLoading}
          >
            <RefreshCw className={`h-4 w-4 ${retryLoading ? "animate-spin" : ""}`} />
            تلاش دوباره
          </button>
        ) : null}
      </article>
    );
  }

  if (status === "ready" && content) {
    return (
      <article className="glass-card min-h-[180px]">
        <p className="text-sm font-semibold uppercase tracking-[0.2em] text-trust/75">{title}</p>
        <div className="mt-3">
          <SoapCitationText text={content} citations={citations} />
        </div>
      </article>
    );
  }

  return (
    <article className="glass-card min-h-[180px]">
      <p className="text-sm font-semibold uppercase tracking-[0.2em] text-trust/75">{title}</p>
      <p className="mt-3 text-sm leading-7 text-slate-500">
        هنوز محتوایی برای این بخش تولید نشده است
      </p>
    </article>
  );
}

export default function MedicalSummaryView({
  data,
  files = [],
  onRetrySoap,
  retryLoading,
}: MedicalSummaryViewProps) {
  const [pmhOpen, setPmhOpen] = useState(true);
  const meds = useMemo(() => parseList(data.medical_data?.medications), [data.medical_data?.medications]);
  const allergies = useMemo(() => parseList(data.medical_data?.allergies), [data.medical_data?.allergies]);
  const sections = useMemo(() => soapSections(data.soap_note), [data.soap_note]);
  const soapStatus: SoapStatus = data.soap_status ?? (data.soap_note ? "ready" : "pending");

  return (
    <section className="space-y-6">
      <div className="rounded-[28px] border border-trust/10 bg-trust/5 p-5 shadow-soft">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-trust text-white">
            <AlertCircle className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold text-trust">CC | دلیل اصلی مراجعه</p>
            <h2 className="text-2xl font-bold text-slate-900">
              {data.medical_data?.chief_complaint || "دلیل مراجعه هنوز استخراج نشده است."}
            </h2>
          </div>
        </div>
      </div>

      <div className="medical-card space-y-3">
        <div className="flex items-center gap-2 text-trust">
          <Stethoscope className="h-5 w-5" />
          <h3 className="text-lg font-bold">HPI | تاریخچه بیماری فعلی</h3>
        </div>
        <p className="leading-relaxed text-slate-700">
          {data.medical_data?.history_present_illness || "هنوز شرح حال فعلی برای این بیمار ثبت نشده است."}
        </p>
      </div>

      <div className="medical-card">
        <button
          className="flex w-full items-center justify-between gap-3 text-right"
          onClick={() => setPmhOpen((current) => !current)}
          type="button"
        >
          <span className="flex items-center gap-2 text-lg font-bold text-trust">
            <FileText className="h-5 w-5" />
            PMH | سوابق پزشکی
          </span>
          <ChevronDown className={`h-5 w-5 text-slate-500 transition-transform duration-300 ${pmhOpen ? "rotate-180" : ""}`} />
        </button>
        {pmhOpen ? (
          <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 px-4 py-3 text-sm leading-7 text-slate-700">
            {data.medical_data?.past_medical_history || "سابقه پزشکی قابل‌نمایشی ثبت نشده است."}
          </div>
        ) : null}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="medical-card space-y-3">
          <div className="flex items-center gap-2 text-trust">
            <Pill className="h-5 w-5" />
            <h3 className="text-lg font-bold">داروها</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {meds.length ? meds.map((item) => <span key={item} className="status-chip bg-slate-100 text-slate-700">{item}</span>) : <span className="text-sm text-slate-500">دارویی ثبت نشده است.</span>}
          </div>
        </div>

        <div className="medical-card space-y-3">
          <div className="flex items-center gap-2 text-trust">
            <ShieldAlert className="h-5 w-5" />
            <h3 className="text-lg font-bold">حساسیت‌ها</h3>
          </div>
          <div className="flex flex-wrap gap-2">
            {allergies.length ? allergies.map((item) => <span key={item} className="rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs font-semibold text-red-700">{item}</span>) : <span className="text-sm text-slate-500">حساسیتی ثبت نشده است.</span>}
          </div>
        </div>
      </div>

      <div className="space-y-4">
        <div>
          <p className="text-sm font-semibold text-trust">SOAP Note</p>
          <h3 className="text-xl font-bold text-slate-900">نمای ۲×۲ برای اسکن سه‌ثانیه‌ای پزشک</h3>
        </div>
        <div className="grid gap-4 md:grid-cols-2">
          {sections.map((section) => (
            <SoapSectionContent
              key={section.title}
              title={section.title}
              content={section.content}
              status={soapStatus}
              errorDetail={data.soap_error_detail}
              onRetry={onRetrySoap}
              retryLoading={retryLoading}
              citations={data.soap_citations ?? []}
            />
          ))}
        </div>
      </div>

      <AttachedDocumentsGrid files={files} />
    </section>
  );
}
