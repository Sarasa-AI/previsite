"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { AxiosError } from "axios";
import { FileText } from "lucide-react";
import { MedicalOverviewCard, sanitizeMedicalOverview } from "@/components/intake/MedicalOverviewCard";
import { extractApiError } from "@/lib/api";
import { frontendApi } from "@/lib/client";
import { normalizeMedicalOverview } from "@/lib/intake";
import type { ConditionFile, CurrentMedication, MedicalOverview } from "@/lib/pmh/types";

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

function createLabBindIds(labResults: { id: string }[]): string[] {
  return labResults.map((lab) => lab.id);
}

function recoverMedicationIds(
  medications: CurrentMedication[],
  files: ConditionFile[],
  chronicConditionIds: string[],
  labBindIds: string[],
): CurrentMedication[] {
  const meds = medications.map((medication) => ({
    ...medication,
    id: medication.id || crypto.randomUUID(),
  }));
  const knownIds = new Set([
    ...chronicConditionIds,
    ...labBindIds,
    ...meds.map((medication) => medication.id),
  ]);
  const orphanFiles = files.filter(
    (file) => file.condition_id && !knownIds.has(file.condition_id),
  );

  orphanFiles.forEach((file, index) => {
    if (index < meds.length && file.condition_id) {
      meds[index] = { ...meds[index], id: file.condition_id };
    }
  });

  return meds;
}

function recoverLabBindIds(
  files: ConditionFile[],
  labCount: number,
  initialBindIds: string[],
  chronicConditionIds: string[],
  medicationIds: string[],
): string[] {
  const knownIds = new Set([...chronicConditionIds, ...initialBindIds, ...medicationIds]);
  const orphanFiles = files.filter(
    (file) => file.condition_id && !knownIds.has(file.condition_id),
  );

  const bindIds = [...initialBindIds];
  while (bindIds.length < labCount) {
    bindIds.push(crypto.randomUUID());
  }

  orphanFiles.forEach((file, index) => {
    if (index < bindIds.length && file.condition_id) {
      bindIds[index] = file.condition_id;
    }
  });

  return bindIds.slice(0, labCount);
}

export default function Layer4MedicalHistory({ sessionId, initial, onSubmit, loading }: Layer4Props) {
  const normalizedInitial = useMemo(() => normalizeMedicalOverview(initial), [initial]);
  const [form, setForm] = useState<MedicalOverview>(() => normalizedInitial);
  const [labBindIds, setLabBindIds] = useState<string[]>(() =>
    createLabBindIds(normalizedInitial.lab_results),
  );
  const [conditionFiles, setConditionFiles] = useState<Record<string, ConditionFile>>({});
  const [filesError, setFilesError] = useState("");

  useEffect(() => {
    const loadFiles = async () => {
      try {
        const response = await frontendApi.listFiles(sessionId);
        const files = response.data as ConditionFile[];
        setConditionFiles(buildConditionFileMap(files));
        const chronicIds = normalizedInitial.chronic_conditions.map((c) => c.id);
        const recoveredLabBindIds = recoverLabBindIds(
          files,
          normalizedInitial.lab_results.length,
          createLabBindIds(normalizedInitial.lab_results),
          chronicIds,
          normalizedInitial.current_medications.map((medication) => medication.id),
        );
        setLabBindIds(recoveredLabBindIds);
        setForm((prev) => ({
          ...prev,
          current_medications: recoverMedicationIds(
            prev.current_medications,
            files,
            chronicIds,
            recoveredLabBindIds,
          ),
        }));
        setFilesError("");
      } catch (requestError) {
        const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
        setFilesError(extractApiError(payload, "بارگذاری فایل‌ها ناموفق بود."));
      }
    };

    void loadFiles();
  }, [sessionId, normalizedInitial.current_medications.length, normalizedInitial.lab_results.length]);

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

  const handleAddLabResult = useCallback(() => {
    const id = crypto.randomUUID();
    setForm((prev) => ({
      ...prev,
      lab_results: [...prev.lab_results, { id, name: "" }],
    }));
    setLabBindIds((prev) => [...prev, id]);
  }, []);

  const handleRemoveLabResult = useCallback((index: number) => {
    setForm((prev) => ({
      ...prev,
      lab_results: prev.lab_results.filter((_, i) => i !== index),
    }));
    setLabBindIds((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleLabExtractedData = useCallback((bindId: string, extracted: string) => {
    setForm((prev) => ({
      ...prev,
      lab_results: prev.lab_results.map((lab) =>
        lab.id === bindId ? { ...lab, extracted_data: extracted } : lab,
      ),
    }));
  }, []);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    await onSubmit(sanitizeMedicalOverview(form, conditionFiles));
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
        labBindIds={labBindIds}
        onAddLabResult={handleAddLabResult}
        onRemoveLabResult={handleRemoveLabResult}
        onLabExtractedData={handleLabExtractedData}
        disabled={loading}
      />

      <button className="primary-button w-full sm:w-auto" type="submit" disabled={loading}>
        {loading ? "در حال ذخیره..." : "تایید و ارسال به پزشک"}
      </button>
    </form>
  );
}
