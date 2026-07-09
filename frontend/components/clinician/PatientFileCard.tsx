"use client";

import Link from "next/link";
import { ChevronDown, FileText } from "lucide-react";
import type { SessionResponse } from "@/lib/api";

export type PatientFile = {
  patient_id: string;
  patient_name: string;
  sessions: SessionResponse[];
};

type PatientFileCardProps = {
  patient: PatientFile;
  expanded: boolean;
  onToggle: () => void;
};

function statusChip(status: string) {
  if (status === "pending_review") {
    return <span className="status-chip bg-amber-100 text-amber-700">در انتظار بررسی</span>;
  }
  if (status === "completed") {
    return <span className="status-chip bg-mint/50 text-trust">تکمیل شده</span>;
  }
  return <span className="status-chip bg-slate-100 text-slate-500">در حال انجام</span>;
}

function formatVisitCount(count: number) {
  return `${count.toLocaleString("fa-IR")} ویزیت`;
}

export default function PatientFileCard({ patient, expanded, onToggle }: PatientFileCardProps) {
  const visitCount = patient.sessions.length;
  const pmhHref = `/clinician/patient/${patient.patient_id}?name=${encodeURIComponent(patient.patient_name)}`;

  return (
    <article className="medical-card overflow-hidden">
      <button
        className="flex w-full items-center justify-between gap-4 text-right"
        onClick={onToggle}
        type="button"
      >
        <div className="min-w-0 flex-1 space-y-1">
          <h3 className="text-lg font-bold text-slate-900">{patient.patient_name}</h3>
          {expanded ? (
            <p className="text-sm text-slate-500">شناسه بیمار: {patient.patient_id}</p>
          ) : null}
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="status-chip bg-trust/10 text-trust">{formatVisitCount(visitCount)}</span>
          <ChevronDown
            className={`h-5 w-5 text-slate-500 transition-transform duration-300 ${expanded ? "rotate-180" : ""}`}
          />
        </div>
      </button>

      {expanded ? (
        <div className="mt-4 space-y-4 border-t border-slate-100 pt-4">
          <Link className="secondary-button w-full sm:w-auto" href={pmhHref}>
            <FileText className="h-4 w-4" />
            سوابق پزشکی (PMH)
          </Link>

          <div className="divide-y divide-slate-100">
            {patient.sessions.map((session) => (
              <div
                key={session.id}
                className="flex flex-col gap-3 py-3 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 space-y-1.5">
                  <p className="font-semibold text-slate-800">
                    {session.initial_complaint || "جلسه بدون عنوان"} —{" "}
                    {new Date(session.created_at).toLocaleDateString("fa-IR")}
                  </p>
                  {statusChip(session.status)}
                </div>
                <Link className="primary-button shrink-0 sm:w-auto" href={`/clinician/${session.id}`}>
                  داشبورد پزشک
                </Link>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </article>
  );
}
