import type { ReactNode } from "react";
import { FileText, Minus, Plus } from "lucide-react";
import { BidiText } from "@/components/ui";
import { EmptyState } from "../shared/EmptyState";
import type { HPIContent } from "../types/content";

export type HPICardProps = {
  content: HPIContent | null;
  trust?: ReactNode;
  className?: string;
};

export function HPICard({ content, trust, className }: HPICardProps) {
  if (content == null) {
    return (
      <section className={`rounded-tai-lg border border-tai-border bg-white p-4 ${className ?? ""}`} aria-label="History of present illness">
        <EmptyState
          title="شرح حال بیماری فعلی ثبت نشده"
          message="HPI در داده‌های موجود در دسترس نیست."
        />
      </section>
    );
  }

  return (
    <article className={`rounded-tai-lg border border-tai-border bg-white p-3.5 shadow-tai-sm transition-shadow hover:shadow-tai-md ${className ?? ""}`} aria-label="History of present illness">
      <header className="mb-3 flex items-center justify-between gap-2 border-b border-tai-border pb-2.5"><h2 className="flex items-center gap-2 text-sm font-bold text-tai-navy"><FileText className="size-4 text-tai-teal" aria-hidden="true" />شرح حال بیماری فعلی</h2>{trust}</header>
      <section aria-label="HPI summary"><p className="mb-1 text-xs font-semibold text-tai-subdued">خلاصه HPI</p><p className="tai-clinical-copy text-sm leading-7 text-tai-text"><BidiText>{content.hpiSummary}</BidiText></p></section>
      <div className="mt-3 grid gap-2 sm:grid-cols-2">
        <section className="rounded-tai-md border border-tai-border bg-tai-surface p-3" aria-label="Pertinent positives"><h3 className="flex items-center gap-1.5 text-xs font-bold text-tai-navy"><Plus className="size-3.5 text-tai-teal" aria-hidden="true" />یافته‌های مثبت مرتبط</h3><p className="mt-2 text-xs text-semantic-unknown">به‌صورت ساختاریافته در قرارداد فعلی موجود نیست.</p></section>
        <section className="rounded-tai-md border border-tai-border bg-tai-surface p-3" aria-label="Pertinent negatives"><h3 className="flex items-center gap-1.5 text-xs font-bold text-tai-navy"><Minus className="size-3.5 text-tai-teal" aria-hidden="true" />یافته‌های منفی مرتبط</h3><p className="mt-2 text-xs text-semantic-unknown">به‌صورت ساختاریافته در قرارداد فعلی موجود نیست.</p></section>
      </div>
    </article>
  );
}
