import type { ReactNode } from "react";
import type { MissingInfoContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { PriorityBadge } from "../shared/PriorityBadge";
import { StatusBadge } from "@/components/ui/design-system";
import { BidiText } from "@/components/ui/bidi";

export type MissingInformationCardProps = {
  content: MissingInfoContent | null;
  trust?: ReactNode;
  /** Placeholder action — presentation only; parent may wire later. */
  onAction?: () => void;
  className?: string;
};

export function MissingInformationCard({
  content,
  trust,
  onAction,
  className,
}: MissingInformationCardProps) {
  if (content == null || content.items.length === 0) {
    return (
      <CardChrome
        className={className}
        title="Missing information"
        trust={trust}
        aria-label="Missing information"
      >
        <EmptyState title="شکاف اطلاعاتی ثبت نشده" message="این وضعیت به تنهایی کامل بودن پرونده را تایید نمی‌کند." />
      </CardChrome>
    );
  }

  return (
    <CardChrome
      className={className}
      title="Missing information"
      trust={trust}
      actions={
        <button
          type="button"
          className="rounded border border-trust/30 bg-clinical px-2 py-1 text-xs font-medium text-trust focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-trust"
          onClick={onAction}
          aria-label={content.actionLabel}
        >
          {content.actionLabel}
        </button>
      }
      aria-label="Missing information"
    >
      <ul className="divide-y divide-tai-border rounded-tai-md border border-tai-border" aria-label="Missing information checklist">
        {content.items.map((item) => (
          <li
            key={item.id}
            className="grid gap-2 p-3 sm:grid-cols-[minmax(0,1fr)_minmax(9rem,0.65fr)_auto] sm:items-center"
          >
            <div className="min-w-0"><div className="text-[11px] text-tai-subdued">اطلاعات مفقود</div><BidiText className="text-sm font-semibold text-tai-text">{item.label}</BidiText></div>
            <div><div className="text-[11px] text-tai-subdued">دلیل اهمیت</div><span data-semantic-state="unknown" className="text-xs text-tai-subdued">در قرارداد فعلی موجود نیست</span></div>
            <div className="flex flex-wrap items-center gap-2"><StatusBadge state="missing">مفقود</StatusBadge><PriorityBadge priority={item.priority} /></div>
          </li>
        ))}
      </ul>
    </CardChrome>
  );
}
