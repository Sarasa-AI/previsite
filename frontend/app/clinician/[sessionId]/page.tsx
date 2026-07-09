"use client";

import { useEffect, useState } from "react";
import { AxiosError } from "axios";
import { ArrowLeft, Download, Loader2 } from "lucide-react";
import Link from "next/link";
import ClinicianDashboard from "@/components/clinician/ClinicianDashboard";
import ProtectedRoute from "@/components/ProtectedRoute";
import { extractApiError } from "@/lib/api";
import { frontendApi } from "@/lib/client";
import type { IntakeData } from "@/lib/intake";

export default function ClinicianPage({ params }: { params: { sessionId: string } }) {
  const sessionId = params.sessionId;
  const [intake, setIntake] = useState<IntakeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfError, setPdfError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const res = await frontendApi.getIntake(sessionId);
        setIntake(res.data);
        setError("");
      } catch (requestError) {
        const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
        setError(extractApiError(payload, "بارگذاری اطلاعات پرونده ناموفق بود."));
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [sessionId]);

  const handleDownloadPdf = async () => {
    setPdfLoading(true);
    setPdfError("");
    try {
      const response = await fetch(`/api/proxy/api/sessions/${sessionId}/pdf`, {
        credentials: "include",
      });
      if (!response.ok) {
        let message = "دانلود PDF ناموفق بود.";
        try {
          const payload = await response.json();
          message = extractApiError(payload, message);
        } catch {
          // Binary or non-JSON error body — keep default message.
        }
        throw new Error(message);
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `patient_report_${sessionId}.pdf`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (downloadError) {
      const message =
        downloadError instanceof Error ? downloadError.message : "دانلود PDF ناموفق بود.";
      setPdfError(message);
    } finally {
      setPdfLoading(false);
    }
  };

  return (
    <ProtectedRoute>
      <main className="page-container space-y-6">
        <section className="medical-card">
          <Link
            href="/doctor-dashboard"
            className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-trust mb-4"
          >
            <ArrowLeft className="h-4 w-4" />
            بازگشت به داشبورد پزشک
          </Link>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="text-sm font-semibold text-trust">داشبورد پزشک</p>
              <h1 className="text-2xl font-bold text-slate-900">پرونده جلسه #{sessionId}</h1>
            </div>
            <button
              type="button"
              onClick={() => void handleDownloadPdf()}
              disabled={pdfLoading || loading || !intake}
              className="secondary-button inline-flex items-center justify-center gap-2 self-start"
            >
              {pdfLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              چاپ پرونده / دانلود PDF
            </button>
          </div>
          {pdfError ? <p className="mt-3 text-sm text-red-600">{pdfError}</p> : null}
        </section>

        {loading ? (
          <div className="medical-card text-sm text-slate-500">در حال بارگذاری...</div>
        ) : error ? (
          <div className="medical-card text-sm text-red-600">{error}</div>
        ) : intake ? (
          <ClinicianDashboard intake={intake} sessionId={sessionId} />
        ) : (
          <div className="medical-card text-sm text-slate-500">اطلاعات پرونده یافت نشد.</div>
        )}
      </main>
    </ProtectedRoute>
  );
}
