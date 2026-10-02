import type { ReactNode } from "react";
import { FileText } from "lucide-react";
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
      <section dir="rtl" className={`rounded-tai-lg border border-tai-border bg-white p-4 text-right ${className ?? ""}`} aria-label="شرح حال بیماری فعلی">
        <EmptyState
          title="شرح حال بیماری فعلی ثبت نشده"
          message="شرح حال بیماری فعلی در داده‌های موجود در دسترس نیست."
        />
      </section>
    );
  }

  return (
    <article dir="rtl" className={`rounded-tai-lg border border-tai-border bg-white p-3.5 text-right shadow-tai-sm ${className ?? ""}`} aria-label="شرح حال بیماری فعلی">
      <header className="mb-3 flex items-center justify-between gap-2 border-b border-tai-border pb-2.5"><h2 className="flex items-center gap-2 text-sm font-bold text-tai-navy"><FileText className="size-4 text-tai-teal" aria-hidden="true" />شرح حال بیماری فعلی</h2>{trust}</header>
      <p className="tai-clinical-copy whitespace-pre-line text-sm leading-7 text-tai-text">{content.hpiSummary}</p>
    </article>
  );
}
