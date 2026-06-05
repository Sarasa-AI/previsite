"use client";

import { useEffect, useState } from "react";
import { LogOut, ArrowLeft } from "lucide-react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import { frontendApi } from "@/lib/client";

export default function DoctorDashboardPage() {
  const [sessions, setSessions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const res = await frontendApi.listSessions();
        setSessions(res.data);
      } catch (err) {
        setError("خطا در بارگذاری جلسات");
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
            <h1 className="text-3xl font-bold text-slate-900">تمام جلسات بیماران</h1>
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
          ) : sessions.length ? (
            sessions.map((session) => (
              <div key={session.id} className="medical-card flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-800">{session.initial_complaint || "جلسه بدون عنوان"}</h3>
                  <p className="text-sm text-slate-500 mt-1">
                    بیمار #{session.patient_id} | تاریخ: {new Date(session.created_at).toLocaleDateString("fa-IR")}
                  </p>
                  <div className="mt-2 flex items-center gap-2">
                    {session.status === "pending_review" ? (
                      <span className="status-chip bg-amber-100 text-amber-700">در انتظار بررسی</span>
                    ) : session.status === "completed" ? (
                      <span className="status-chip bg-mint/50 text-trust">تکمیل شده</span>
                    ) : (
                      <span className="status-chip bg-slate-100 text-slate-500">در حال انجام</span>
                    )}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Link href={`/summary/${session.id}`} className="primary-button sm:w-auto">
                    مشاهده خلاصه و SOAP
                  </Link>
                  <Link href={`/chat/${session.id}`} className="secondary-button sm:w-auto">
                    تاریخچه چت
                  </Link>
                </div>
              </div>
            ))
          ) : (
            <div className="medical-card text-sm text-slate-500">هنوز جلسه‌ای ثبت نشده است.</div>
          )}
        </section>
      </main>
    </ProtectedRoute>
  );
}
