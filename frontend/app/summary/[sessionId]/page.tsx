"use client";

import { useEffect, useState } from "react";
import { AxiosError } from "axios";
import ProtectedRoute from "@/components/ProtectedRoute";
import MedicalSummaryView from "@/components/summary/MedicalSummaryView";
import { extractApiError } from "@/lib/api";
import { frontendApi } from "@/lib/client";

type SummaryData = {
  id: number;
  session_id: number;
  soap_note: string | null;
  medical_data: {
    chief_complaint: string | null;
    history_present_illness: string | null;
    past_medical_history: string | null;
    medications: string | null;
    allergies: string | null;
  };
  created_at: string | null;
};

export default function SummaryPage({ params }: { params: { sessionId: string } }) {
  const sessionId = params.sessionId;
  const [data, setData] = useState<SummaryData | null>(null);
  const [files, setFiles] = useState<any[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadData = async () => {
      try {
        const [summaryRes, filesRes] = await Promise.all([
          frontendApi.summary(sessionId),
          frontendApi.listFiles(sessionId)
        ]);
        setData(summaryRes.data);
        setFiles(filesRes.data);
        setError("");
      } catch (requestError) {
        const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
        setError(extractApiError(payload, "دریافت اطلاعات ناموفق بود."));
        setData(null);
      }
    };

    void loadData();
  }, [sessionId]);

  return (
    <ProtectedRoute>
      <main className="page-container space-y-6">
        <section className="medical-card">
          <p className="text-sm font-semibold text-trust">خلاصه پزشکی</p>
          <h1 className="text-3xl font-bold text-slate-900">Summary جلسه #{sessionId}</h1>
          <p className="mt-2 text-sm leading-7 text-slate-600">
            این صفحه طوری ساختاربندی شده که پزشک بتواند در چند ثانیه دلیل مراجعه، سیر بیماری، حساسیت‌ها و SOAP Note را اسکن کند.
          </p>
        </section>

        {error ? <div className="medical-card text-sm text-red-600">{error}</div> : null}
        {data ? <MedicalSummaryView data={data} files={files} /> : null}
      </main>
    </ProtectedRoute>
  );
}
