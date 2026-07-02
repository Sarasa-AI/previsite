"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { AxiosError } from "axios";
import { FileText } from "lucide-react";
import { MedicalOverviewCard, sanitizeMedicalOverview } from "@/components/intake/MedicalOverviewCard";
import { extractApiError } from "@/lib/api";
import { frontendApi } from "@/lib/client";
import { normalizeMedicalOverview } from "@/lib/intake";
import type { ConditionFile, MedicalOverview } from "@/lib/pmh/types";

type Layer4Props = {
  sessionId: string;
  initial?: MedicalOverview | null;
  onSubmit: (data: MedicalOverview) => Promise<void>;
  loading?: boolean;
};

function buildConditionFileMap(files: ConditionFile[]): Record<string, ConditionFile> {
  const map: Record<string, ConditionFile> = {};
  for (const file of files) {
    if (file.condition_id) {
      map[file.condition_id] = file;
    }
  }
  return map;
}

export default function Layer4MedicalHistory({ sessionId, initial, onSubmit, loading }: Layer4Props) {
  const [form, setForm] = useState<MedicalOverview>(() => normalizeMedicalOverview(initial));
  const [conditionFiles, setConditionFiles] = useState<Record<string, ConditionFile>>({});
  const [filesError, setFilesError] = useState("");

  useEffect(() => {
    const loadFiles = async () => {
      try {
        const response = await frontendApi.listFiles(sessionId);
        setConditionFiles(buildConditionFileMap(response.data as ConditionFile[]));
        setFilesError("");
      } catch (requestError) {
        const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
        setFilesError(extractApiError(payload, "بارگذاری فایل‌ها ناموفق بود."));
      }
    };

    void loadFiles();
  }, [sessionId]);

  const handleConditionFileChange = useCallback((conditionId: string, file: ConditionFile | null) => {
    setConditionFiles((prev) => {
      const next = { ...prev };
      if (file) {
        next[conditionId] = file;
      } else {
        delete next[conditionId];
      }
      return next;
    });
  }, []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await onSubmit(sanitizeMedicalOverview(form));
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

      {filesError ? <p className="text-sm text-red-600">{filesError}</p> : null}

      <MedicalOverviewCard
        value={form}
        onChange={setForm}
        sessionId={sessionId}
        conditionFiles={conditionFiles}
        onConditionFileChange={handleConditionFileChange}
        disabled={loading}
      />

      <button className="primary-button w-full sm:w-auto" type="submit" disabled={loading}>
        {loading ? "در حال ذخیره..." : "تایید و ارسال به پزشک"}
      </button>
    </form>
  );
}
