"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { AxiosError } from "axios";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import MedicalOverviewReadOnly from "@/components/clinician/MedicalOverviewReadOnly";
import ProtectedRoute from "@/components/ProtectedRoute";
import { extractApiError } from "@/lib/api";
import { frontendApi } from "@/lib/client";
import type { MedicalOverview } from "@/lib/pmh/types";

type PatientOverviewResponse = {
  patient_id: number;
  overview: MedicalOverview | null;
  last_updated: string | null;
};

export default function PatientPmhPage({ params }: { params: { patientId: string } }) {
  const patientId = params.patientId;
  const searchParams = useSearchParams();
  const patientName = searchParams.get("name");
  const [overview, setOverview] = useState<MedicalOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true);
        const res = await frontendApi.getPatientOverview(patientId);
        const data = res.data as PatientOverviewResponse;
        setOverview(data.overview);
        setError("");
      } catch (requestError) {
        const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
        setError(extractApiError(payload, "بارگذاری سوابق پزشکی ناموفق بود."));
      } finally {
        setLoading(false);
      }
    };
    void load();
  }, [patientId]);

  const displayName = patientName || `بیمار #${patientId}`;

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
          <p className="text-sm font-semibold text-trust">سوابق پزشکی</p>
          <h1 className="text-2xl font-bold text-slate-900">{displayName}</h1>
          <p className="mt-1 text-sm text-slate-500">شناسه بیمار: {patientId}</p>
        </section>

        {loading ? (
          <div className="medical-card text-sm text-slate-500">در حال بارگذاری...</div>
        ) : error ? (
          <div className="medical-card text-sm text-red-600">{error}</div>
        ) : overview ? (
          <MedicalOverviewReadOnly overview={overview} />
        ) : (
          <div className="medical-card text-sm text-slate-500">سوابق پزشکی ثبت نشده است.</div>
        )}
      </main>
    </ProtectedRoute>
  );
}
