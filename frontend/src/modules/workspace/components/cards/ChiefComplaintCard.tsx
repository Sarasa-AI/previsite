import type { ReactNode } from "react";
import type { ChiefComplaintContent } from "../types";
import { MessageSquareText } from "lucide-react";
import { BidiText } from "@/components/ui";
import { PriorityBadge } from "../shared/PriorityBadge";
import { EmptyState } from "../shared/EmptyState";

export type ChiefComplaintCardProps = {
  content: ChiefComplaintContent | null;
  trust?: ReactNode;
  className?: string;
};

export function ChiefComplaintCard({ content, trust, className }: ChiefComplaintCardProps) {
  if (content == null) {
    return (
      <section className={`rounded-tai-lg border border-semantic-missing/30 bg-white p-4 ${className ?? ""}`} aria-label="Chief complaint">
        <><span className="sr-only">No chief complaint</span><EmptyState title="شکایت اصلی ثبت نشده" message="شکایت اصلی بیمار در داده‌های موجود ثبت نشده است." /></>
      </section>
    );
  }

  return (
    <article className={`rounded-tai-lg border border-tai-teal/30 bg-white shadow-tai-sm ${className ?? ""}`} aria-label="Chief complaint">
      <div className="flex items-center justify-between gap-3 border-b border-tai-border bg-tai-teal-soft/50 px-4 py-2.5">
        <h2 className="flex items-center gap-2 text-sm font-bold text-tai-navy"><MessageSquareText className="size-4 text-tai-teal" aria-hidden="true" />شکایت اصلی</h2>
        <div className="flex items-center gap-2"><PriorityBadge priority={content.priority} />{trust}</div>
      </div>
      <div className="p-4">
        <p className="text-lg font-bold leading-8 text-tai-text"><BidiText>{content.title}</BidiText></p>
        <div className="mt-3 flex items-center gap-2 text-sm"><span className="text-tai-subdued">مدت / شروع:</span>{content.duration.trim() ? <BidiText className="font-semibold text-tai-text">{content.duration}</BidiText> : <span className="font-semibold text-semantic-unknown">نامشخص</span>}</div>
      </div>
    </article>
  );
}
