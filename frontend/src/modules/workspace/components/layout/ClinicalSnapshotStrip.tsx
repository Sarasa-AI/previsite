import type { ReactNode } from "react";
import { Activity, HeartPulse } from "lucide-react";
import type { SnapshotStripContent } from "../types";
import { EmptyState } from "../shared/EmptyState";

export type ClinicalSnapshotStripProps = {
  content: SnapshotStripContent | null;
  trust?: ReactNode;
  className?: string;
};

export function ClinicalSnapshotStrip({ content, trust, className }: ClinicalSnapshotStripProps) {
  if (content == null) {
    return (
      <section className={`rounded-tai-lg border border-tai-border bg-white p-4 ${className ?? ""}`} aria-label="Clinical snapshot"><span className="sr-only">No snapshot</span><EmptyState title="نمای بالینی موجود نیست" message="علائم حیاتی و خلاصه وضعیت در داده‌های موجود در دسترس نیستند." /></section>
    );
  }

  return (
    <article className={`rounded-tai-lg border border-tai-border bg-white p-4 shadow-tai-sm ${className ?? ""}`} aria-label="Clinical snapshot">
      <header className="mb-3 flex items-center justify-between gap-2"><h2 className="flex items-center gap-2 text-sm font-bold text-tai-navy"><HeartPulse className="size-4 text-tai-teal" aria-hidden="true" />علائم حیاتی <span className="sr-only">Vitals</span></h2>{trust}</header>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6" aria-label="Clinical snapshot metrics">
        {["فشار خون", "ضربان قلب", "تعداد تنفس", "دما", "SpO₂", "وزن"].map((label) => <div key={label} className="rounded-tai-md border border-tai-border bg-tai-surface p-2.5"><span className="block text-[11px] font-medium text-tai-subdued">{label}</span><span className="mt-1 flex items-center gap-1 text-xs font-semibold text-semantic-unknown"><Activity className="size-3" aria-hidden="true" />در دسترس نیست</span></div>)}
      </div>
      <div className="mt-3 rounded-tai-md border border-tai-border p-3"><p className="text-xs font-semibold text-tai-subdued">خلاصه قدیمی علائم حیاتی</p><p className="mt-1 text-sm text-tai-text" dir="auto">{content.vitals || "در دسترس نیست"}</p><p className="mt-1 text-[11px] text-semantic-unverified">این متن تفکیک یا تفسیر نشده است؛ مقادیر ساختاریافته در قرارداد فعلی وجود ندارند.</p></div>
    </article>
  );
}
