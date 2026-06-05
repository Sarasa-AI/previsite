"use client";

import { useEffect, useState } from "react";
import { AxiosError } from "axios";
import { ArrowLeft } from "lucide-react";
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
          <p className="text-sm font-semibold text-trust">داشبورد پزشک</p>
          <h1 className="text-2xl font-bold text-slate-900">پرونده جلسه #{sessionId}</h1>
        </section>

        {loading ? (
          <div className="medical-card text-sm text-slate-500">در حال بارگذاری...</div>
        ) : error ? (
          <div className="medical-card text-sm text-red-600">{error}</div>
        ) : intake ? (
          <ClinicianDashboard intake={intake} />
        ) : (
          <div className="medical-card text-sm text-slate-500">اطلاعات پرونده یافت نشد.</div>
        )}
      </main>
    </ProtectedRoute>
  );
}
