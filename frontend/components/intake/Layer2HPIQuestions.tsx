"use client";

import { useMemo, useState, type FormEvent } from "react";
import { AlertTriangle, MessageCircle } from "lucide-react";
import type { HPIQuestion, HPIQuestions } from "@/lib/intake";

type Layer2Props = {
  questions: HPIQuestions;
  answers: Record<string, string>;
  onAnswer: (questionId: string, answer: string) => Promise<void>;
  loading?: boolean;
};

export default function Layer2HPIQuestions({ questions, answers, onAnswer, loading }: Layer2Props) {
  const sorted = useMemo(
    () => [...questions.questions].sort((a, b) => a.priority - b.priority),
    [questions.questions],
  );

  const currentIndex = useMemo(() => {
    const idx = sorted.findIndex((q) => !answers[q.id]);
    return idx === -1 ? sorted.length : idx;
  }, [sorted, answers]);

  const currentQuestion: HPIQuestion | null = currentIndex < sorted.length ? sorted[currentIndex] : null;
  const [answer, setAnswer] = useState("");

  const progress = sorted.length ? Math.round((currentIndex / sorted.length) * 100) : 0;
  const isComplete = currentIndex >= sorted.length;

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!currentQuestion || !answer.trim()) return;
    await onAnswer(currentQuestion.id, answer.trim());
    setAnswer("");
  };

  if (isComplete) {
    return (
      <div className="space-y-4 text-center">
        <MessageCircle className="mx-auto h-12 w-12 text-trust" />
        <h2 className="text-xl font-bold text-slate-900">تمام سوالات پاسخ داده شد</h2>
        <p className="text-sm text-slate-600">در حال آماده‌سازی خلاصه بالینی...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3 text-trust">
        <MessageCircle className="h-6 w-6" />
        <div>
          <p className="text-sm font-semibold">لایه ۲ — شرح حال فعلی</p>
          <h2 className="text-xl font-bold text-slate-900">سوالات هدفمند (یکی‌یکی)</h2>
        </div>
      </div>

      <div className="space-y-2">
        <div className="flex justify-between text-sm text-slate-500">
          <span>سوال {currentIndex + 1} از {sorted.length}</span>
          <span>{progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
          <div
            className="h-full rounded-full bg-trust transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {currentQuestion?.red_flag_related && (
        <div className="flex items-center gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <AlertTriangle className="h-4 w-4 shrink-0" />
          این سوال برای ارزیابی علائم هشداردهنده است.
        </div>
      )}

      <div className="rounded-2xl border border-trust/15 bg-trust/5 p-6">
        <p className="text-lg font-semibold leading-relaxed text-slate-900">
          {currentQuestion?.question}
        </p>
      </div>

      <form className="space-y-4" onSubmit={handleSubmit}>
        <textarea
          className="field-input min-h-[120px] resize-none"
          value={answer}
          onChange={(e) => setAnswer(e.target.value)}
          placeholder="پاسخ خود را بنویسید..."
          required
          disabled={loading}
        />
        <button className="primary-button w-full sm:w-auto" type="submit" disabled={loading || !answer.trim()}>
          {loading ? "در حال ذخیره..." : currentIndex === sorted.length - 1 ? "ثبت آخرین پاسخ" : "سوال بعدی"}
        </button>
      </form>
    </div>
  );
}
