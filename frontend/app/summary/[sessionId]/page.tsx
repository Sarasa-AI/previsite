"use client";

import { useCallback, useEffect, useState } from "react";
import { AxiosError } from "axios";
import ProtectedRoute from "@/components/ProtectedRoute";
import MedicalSummaryView from "@/components/summary/MedicalSummaryView";
import { extractApiError } from "@/lib/api";
import { frontendApi } from "@/lib/client";

type SummaryData = {
  id: number;
  session_id: number;
  soap_note: string | null;
  soap_status: "pending" | "generating" | "failed" | "ready";
  soap_error_detail?: string | null;
  soap_citations?: Array<{
    index?: number;
    marker?: string;
    source?: string | null;
    source_title?: string | null;
    content?: string | null;
    source_excerpt?: string | null;
    verified?: boolean;
    verification_status?: string;
    similarity_score?: number | null;
  }> | null;
  soap_verification_status?: string | null;
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
  const [files, setFiles] = useState<Array<{ id: number; filename: string; size: number; mime_type: string; url: string }>>([]);
  const [error, setError] = useState("");
  const [retryLoading, setRetryLoading] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [summaryRes, filesRes] = await Promise.all([
        frontendApi.summary(sessionId),
        frontendApi.listFiles(sessionId),
      ]);
      setData(summaryRes.data);
      setFiles(filesRes.data);
      setError("");
    } catch (requestError) {
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "دریافت اطلاعات ناموفق بود."));
    }
  }, [sessionId]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  useEffect(() => {
    if (!data || data.soap_status !== "generating") return;

    const interval = setInterval(() => {
      void loadData();
    }, 4000);

    return () => clearInterval(interval);
  }, [data?.soap_status, loadData]);

  const handleRetrySoap = async () => {
    setRetryLoading(true);
    try {
      await frontendApi.retrySoap(sessionId);
      await loadData();
    } catch (requestError) {
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "تلاش مجدد ناموفق بود."));
    } finally {
      setRetryLoading(false);
    }
  };

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
        {data ? (
          <MedicalSummaryView
            data={data}
            files={files}
            onRetrySoap={handleRetrySoap}
            retryLoading={retryLoading}
          />
        ) : null}
      </main>
    </ProtectedRoute>
  );
}
