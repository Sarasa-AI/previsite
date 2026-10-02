import type { ReactNode } from "react";
import { ShieldAlert } from "lucide-react";
import type { RedFlagsContent } from "../types";
import { EmptyState } from "../shared/EmptyState";
import { SeverityList } from "../shared/SeverityList";

export type RedFlagsCardProps = {
  content: RedFlagsContent | null;
  trust?: ReactNode;
  className?: string;
};

export function RedFlagsCard({ content, trust, className }: RedFlagsCardProps) {
  if (content == null || content.items.length === 0) {
    return (
      <section className={`rounded-tai-lg border border-tai-border bg-white p-4 ${className ?? ""}`} aria-label="Red flags">
        <div className="mb-3 flex items-center justify-between gap-2"><h2 className="flex items-center gap-2 text-sm font-bold text-tai-navy"><ShieldAlert className="size-4 text-tai-teal" aria-hidden="true" />هشدارهای بالینی</h2>{trust}</div>
        <><span className="sr-only">No red flags</span><EmptyState title="هشداری گزارش نشده" message="داده موجود شامل هشدار بالینی نیست؛ این وضعیت به معنی طبیعی بودن یا رد خطر نیست." /></>
      </section>
    );
  }

  return (
    <article className={`rounded-tai-lg border border-semantic-critical/35 bg-white p-3 shadow-tai-sm ring-1 ring-inset ring-semantic-critical/5 transition-shadow hover:shadow-tai-md ${className ?? ""}`} aria-label="Red flags">
      <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2 border-b border-semantic-critical/15 pb-2"><h2 className="flex items-center gap-2 text-sm font-bold text-semantic-critical"><span className="grid size-7 place-items-center rounded-tai-md bg-[hsl(var(--tai-critical-surface))]"><ShieldAlert className="size-4" aria-hidden="true" /></span>هشدارهای بالینی مهم <span className="rounded-tai-sm bg-semantic-critical px-1.5 py-0.5 text-[11px] text-white">{content.items.length}</span></h2>{trust}</div>
      <SeverityList items={content.items} aria-label="Red flag items" />
    </article>
  );
}
