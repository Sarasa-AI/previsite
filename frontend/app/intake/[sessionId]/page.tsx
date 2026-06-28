"use client";

import { useCallback, useEffect, useState } from "react";
import { AxiosError } from "axios";
import { ArrowLeft, CheckCircle2, Loader2 } from "lucide-react";
import Link from "next/link";
import ProtectedRoute from "@/components/ProtectedRoute";
import Layer1Demographics from "@/components/intake/Layer1Demographics";
import Layer2HPIQuestions from "@/components/intake/Layer2HPIQuestions";
import Layer4MedicalHistory from "@/components/intake/Layer4MedicalHistory";
import { extractApiError } from "@/lib/api";
import { frontendApi } from "@/lib/client";
import type { Demographics, HPIQuestion, IntakeData, MedicalHistory } from "@/lib/intake";
import { usePatientProfile } from "@/src/hooks/usePatientProfile";

const LAYER_LABELS = ["اطلاعات اولیه", "شرح حال", "خلاصه بالینی", "سوابق پزشکی", "ارسال"];

export default function IntakePage({ params }: { params: { sessionId: string } }) {
  const sessionId = params.sessionId;
  const [intake, setIntake] = useState<IntakeData | null>(null);
  const [intakeLoadFailed, setIntakeLoadFailed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const { data: profile, error: profileQueryError } = usePatientProfile();

  const currentLayer = intake?.current_layer ?? 1;

  const loadIntake = useCallback(async () => {
    try {
      const res = await frontendApi.getIntake(sessionId);
      setIntake(res.data);
      setIntakeLoadFailed(false);
      setError("");
    } catch (requestError) {
      if (requestError instanceof AxiosError && requestError.response?.status === 404) {
        setIntake(null);
        setIntakeLoadFailed(false);
        return;
      }
      setIntakeLoadFailed(true);
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(
        extractApiError(
          payload,
          "بارگذاری اطلاعات ناموفق بود — اطلاعات شما در همین صفحه ذخیره است، نگران نباشید.",
        ),
      );
    }
  }, [sessionId]);

  useEffect(() => {
    void loadIntake();
  }, [loadIntake]);

  useEffect(() => {
    if (intake?.current_layer === 3 && !intake.clinical_summary && !loading) {
      const generate = async () => {
        setLoading(true);
        try {
          const res = await frontendApi.generateLayer3(sessionId);
          setIntake(res.data);
        } catch (requestError) {
          const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
          setError(extractApiError(payload, "تولید خلاصه بالینی ناموفق بود."));
        } finally {
          setLoading(false);
        }
      };
      void generate();
    }
  }, [intake?.current_layer, intake?.clinical_summary, loading, sessionId]);

  const handleLayer1 = async (data: Demographics) => {
    setLoading(true);
    setError("");
    try {
      const res = await frontendApi.saveLayer1(sessionId, data);
      setIntake(res.data);
      const genRes = await frontendApi.generateLayer2(sessionId);
      setIntake(genRes.data);
    } catch (requestError) {
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "ذخیره اطلاعات اولیه ناموفق بود."));
    } finally {
      setLoading(false);
    }
  };

  const handleLayer2Answer = async (questionId: string, answer: string) => {
    setLoading(true);
    setError("");
    try {
      const res = await frontendApi.saveLayer2Answer(sessionId, { question_id: questionId, answer });
      setIntake(res.data);

      const questions = res.data.hpi_questions?.questions ?? [];
      const answers = res.data.hpi_answers ?? {};
      const allAnswered = questions.every((q: HPIQuestion) => q.id in answers);

      if (allAnswered) {
        const summaryRes = await frontendApi.generateLayer3(sessionId);
        setIntake(summaryRes.data);
      }
    } catch (requestError) {
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "ذخیره پاسخ ناموفق بود."));
    } finally {
      setLoading(false);
    }
  };

  const handleLayer4 = async (data: MedicalHistory) => {
    setLoading(true);
    setError("");
    try {
      await frontendApi.saveLayer4(sessionId, data);
      await frontendApi.submitIntake(sessionId);
      setSubmitted(true);
      await loadIntake();
    } catch (requestError) {
      const payload = requestError instanceof AxiosError ? requestError.response?.data : undefined;
      setError(extractApiError(payload, "ارسال نهایی ناموفق بود."));
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <ProtectedRoute>
        <main className="page-container flex min-h-[60vh] items-center justify-center">
          <div className="medical-card max-w-lg text-center space-y-4">
            <CheckCircle2 className="mx-auto h-16 w-16 text-trust" />
            <h1 className="text-2xl font-bold text-slate-900">پرونده با موفقیت ارسال شد</h1>
            <p className="text-sm text-slate-600">شرح حال شما برای پزشک ارسال شده و در انتظار بررسی است.</p>
            <Link href="/dashboard" className="primary-button inline-flex">
              بازگشت به داشبورد
            </Link>
          </div>
        </main>
      </ProtectedRoute>
    );
  }

  return (
    <ProtectedRoute>
      <main className="page-container space-y-6">
        <section className="medical-card">
          <Link href="/dashboard" className="inline-flex items-center gap-2 text-sm text-slate-600 hover:text-trust mb-4">
            <ArrowLeft className="h-4 w-4" />
            بازگشت به داشبورد
          </Link>
          <p className="text-sm font-semibold text-trust">مصاحبه پیش از ویزیت — جلسه #{sessionId}</p>
          <h1 className="text-2xl font-bold text-slate-900">فرم چندلایه شرح حال</h1>

          <div className="mt-6 flex flex-wrap gap-2">
            {LAYER_LABELS.map((label, idx) => {
              const layerNum = idx + 1;
              const isActive = currentLayer === layerNum;
              const isDone = currentLayer > layerNum;
              return (
                <span
                  key={label}
                  className={`status-chip ${
                    isDone
                      ? "bg-mint/50 text-trust"
                      : isActive
                        ? "bg-trust text-white"
                        : "bg-slate-100 text-slate-500"
                  }`}
                >
                  {isDone ? "✓" : layerNum}. {label}
                </span>
              );
            })}
          </div>
        </section>

        <section className="medical-card">
          {loading && !intake?.hpi_questions && (
            <div className="flex items-center justify-center gap-3 py-12 text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin" />
              در حال پردازش...
            </div>
          )}

          {currentLayer <= 1 && (
            <Layer1Demographics
              initial={intake?.demographics}
              profile={profile ?? null}
              profileError={
                profileQueryError
                  ? "بارگذاری پروفایل ناموفق بود — می‌توانید اطلاعات را دستی وارد کنید."
                  : undefined
              }
              onSubmit={handleLayer1}
              loading={loading}
            />
          )}

          {currentLayer === 2 && intake?.hpi_questions && (
            <Layer2HPIQuestions
              questions={intake.hpi_questions}
              answers={intake.hpi_answers ?? {}}
              onAnswer={handleLayer2Answer}
              loading={loading}
            />
          )}

          {currentLayer === 3 && (
            <div className="flex items-center justify-center gap-3 py-12 text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin" />
              در حال تولید خلاصه بالینی...
            </div>
          )}

          {currentLayer >= 4 && intake?.clinical_summary && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-mint/30 bg-mint/10 p-4">
                <p className="text-sm font-semibold text-trust mb-1">خلاصه بالینی (لایه ۳)</p>
                <p className="text-sm leading-relaxed text-slate-700">{intake.clinical_summary.hpi_summary}</p>
              </div>
              <Layer4MedicalHistory
                initial={intake.medical_history}
                onSubmit={handleLayer4}
                loading={loading}
              />
            </div>
          )}

          {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
        </section>
      </main>
    </ProtectedRoute>
  );
}
