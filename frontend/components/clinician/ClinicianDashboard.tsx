"use client";

import { useEffect, useState } from "react";
import { AxiosError } from "axios";
import { AlertTriangle, CheckCircle, Stethoscope, User, XCircle } from "lucide-react";
import { extractApiError } from "@/lib/api";
import { frontendApi } from "@/lib/client";
import type { ClinicalSummary, Demographics, IntakeData } from "@/lib/intake";
import { SEX_OPTIONS } from "@/lib/intake";
import MedicalOverviewReadOnly from "@/components/clinician/MedicalOverviewReadOnly";
import AttachedDocumentsGrid from "@/components/shared/AttachedDocumentsGrid";
import type { ConditionFile } from "@/lib/pmh/types";

type ClinicianDashboardProps = {
  intake: IntakeData;
  sessionId: string;
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
      {items.map((item, index) => (
        <span
          key={`${item}-${index}`}
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${styles[variant]}`}
        >
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

export default function ClinicianDashboard({ intake, sessionId }: ClinicianDashboardProps) {
  const [files, setFiles] = useState<ConditionFile[]>([]);
  const [conditionFiles, setConditionFiles] = useState<Record<string, ConditionFile>>({});
  const [filesError, setFilesError] = useState("");

  useEffect(() => {
    const loadFiles = async () => {
      try {
        const response = await frontendApi.listFiles(sessionId);
        const listed = response.data as ConditionFile[];
        const map: Record<string, ConditionFile> = {};
        for (const file of listed) {
          if (file.condition_id) {
            map[file.condition_id] = file;
          }
        }
        setFiles(listed);
        setConditionFiles(map);
        setFilesError("");
      } catch (requestError) {
        const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
        setFilesError(extractApiError(payload, "بارگذاری فایل‌ها ناموفق بود."));
      }
    };

    void loadFiles();
  }, [sessionId]);

  return (
    <section className="space-y-6">
      {intake.demographics && <DemographicsCard data={intake.demographics} />}
      {intake.clinical_summary && <ClinicalSummaryCard summary={intake.clinical_summary} />}
      {filesError ? <p className="text-sm text-red-600">{filesError}</p> : null}
      {intake.medical_overview && (
        <MedicalOverviewReadOnly overview={intake.medical_overview} conditionFiles={conditionFiles} />
      )}
      <AttachedDocumentsGrid files={files} />
    </section>
  );
}
