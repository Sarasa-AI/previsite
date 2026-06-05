"use client";

import { useEffect, useState, type FormEvent } from "react";
import { AxiosError } from "axios";
import { LogOut, PlusCircle } from "lucide-react";
import SessionCard from "@/components/dashboard/SessionCard";
import ProtectedRoute from "@/components/ProtectedRoute";
import { extractApiError, type SessionResponse } from "@/lib/api";
import { frontendApi } from "@/lib/client";

export default function DashboardPage() {
  const [sessions, setSessions] = useState<SessionResponse[]>([]);
  const [complaint, setComplaint] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const loadSessions = async () => {
    try {
      const response = await frontendApi.listSessions();
      setSessions(response.data);
      setError("");
    } catch (requestError) {
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "دریافت لیست جلسات ناموفق بود."));
    }
  };

  useEffect(() => {
    void loadSessions();
  }, []);

  const createSession = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);

    try {
      await frontendApi.createSession({ initial_complaint: complaint });
      setComplaint("");
      setError("");
      await loadSessions();
    } catch (requestError) {
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "ایجاد جلسه ناموفق بود."));
    } finally {
      setLoading(false);
    }
  };

  const logout = async () => {
    await frontendApi.logout();
    window.location.href = "/login";
  };

  return (
    <ProtectedRoute>
      <main className="page-container space-y-6">
        <section className="medical-card flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <p className="text-sm font-semibold text-trust">داشبورد بیمار</p>
            <h1 className="text-3xl font-bold text-slate-900">جلسات PreVisit</h1>
            <p className="mt-2 max-w-2xl text-sm leading-7 text-slate-600">
              هر کارت وضعیت فعلی مصاحبه را با پیشرفت دایره‌ای نمایش می‌دهد تا بیمار سریع بداند کدام جلسه هنوز نیاز به تکمیل دارد.
            </p>
          </div>
          <button className="secondary-button lg:w-auto" onClick={logout} type="button">
            <LogOut className="h-4 w-4" />
            خروج
          </button>
        </section>

        <form className="medical-card space-y-4" onSubmit={createSession}>
          <div className="flex items-center gap-2 text-trust">
            <PlusCircle className="h-5 w-5" />
            <h2 className="text-xl font-bold">ساخت جلسه جدید</h2>
          </div>
          <input
            className="field-input"
            value={complaint}
            onChange={(event) => setComplaint(event.target.value)}
            placeholder="مشکل اصلی بیمار را وارد کنید"
            required
          />
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            {error ? <p className="text-sm text-red-600">{error}</p> : <span className="text-sm text-slate-500">جلسه جدید با وضعیت اولیه در حال انجام ایجاد می‌شود.</span>}
            <button className="primary-button sm:w-auto" disabled={loading} type="submit">
              {loading ? "در حال ساخت..." : "ایجاد جلسه"}
            </button>
          </div>
        </form>

        <section className="grid gap-4 lg:grid-cols-2">
          {sessions.length ? (
            sessions.map((session) => <SessionCard key={session.id} session={session} />)
          ) : (
            <div className="medical-card text-sm text-slate-500">هنوز جلسه‌ای ساخته نشده است.</div>
          )}
        </section>
      </main>
    </ProtectedRoute>
  );
}
