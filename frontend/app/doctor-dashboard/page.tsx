"use client";

import { useEffect, useMemo, useState } from "react";
import { LogOut, ArrowLeft } from "lucide-react";
import Link from "next/link";
import PatientFileCard, { type PatientFile } from "@/components/clinician/PatientFileCard";
import ProtectedRoute from "@/components/ProtectedRoute";
import type { SessionResponse } from "@/lib/api";
import { frontendApi } from "@/lib/client";

function groupSessionsByPatient(sessions: SessionResponse[]): PatientFile[] {
  const grouped = sessions.reduce<Record<string, PatientFile>>((acc, session) => {
    const key = String(session.patient_id);
    if (!acc[key]) {
      acc[key] = {
        patient_id: key,
        patient_name: session.patient_name || `بیمار #${session.patient_id}`,
        sessions: [],
      };
    }
    acc[key].sessions.push(session);
    return acc;
  }, {});

  return Object.values(grouped)
    .map((patient) => ({
      ...patient,
      sessions: [...patient.sessions].sort(
        (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      ),
    }))
    .sort((a, b) => {
      const aLatest = a.sessions[0]?.created_at ?? "";
      const bLatest = b.sessions[0]?.created_at ?? "";
      return new Date(bLatest).getTime() - new Date(aLatest).getTime();
    });
}

export default function DoctorDashboardPage() {
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expandedPatientId, setExpandedPatientId] = useState<string | null>(null);

  const patientFiles = useMemo(() => groupSessionsByPatient(sessions), [sessions]);

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const res = await frontendApi.listSessions();
        setSessions(res.data);
      } catch {
        setError("خطا در بارگذاری پرونده‌ها");
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const logout = async () => {
    await frontendApi.logout();
    window.location.href = "/";
  };

  return (
    <ProtectedRoute>
      <main className="page-container space-y-6">
        <section className="medical-card flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <Link href="/" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-trust mb-2">
              <ArrowLeft className="h-4 w-4" />
              بازگشت
            </Link>
            <p className="text-sm font-semibold text-trust">داشبورد پزشک</p>
            <h1 className="text-3xl font-bold text-slate-900">پرونده بیماران</h1>
          </div>
          <button className="secondary-button lg:w-auto" onClick={logout} type="button">
            <LogOut className="h-4 w-4" />
            خروج
          </button>
        </section>

        <section className="space-y-4">
          {loading ? (
            <div className="medical-card text-sm text-slate-500">در حال بارگذاری...</div>
          ) : error ? (
            <div className="medical-card text-sm text-red-600">{error}</div>
          ) : patientFiles.length ? (
            patientFiles.map((patient) => (
              <PatientFileCard
                key={patient.patient_id}
                patient={patient}
                expanded={expandedPatientId === patient.patient_id}
                onToggle={() =>
                  setExpandedPatientId((current) =>
                    current === patient.patient_id ? null : patient.patient_id,
                  )
                }
              />
            ))
          ) : (
            <div className="medical-card text-sm text-slate-500">هنوز پرونده‌ای ثبت نشده است.</div>
          )}
        </section>
      </main>
    </ProtectedRoute>
  );
}
