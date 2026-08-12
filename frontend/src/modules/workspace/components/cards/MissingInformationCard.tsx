import type { ReactNode } from "react";
import type { MissingInfoContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { PriorityBadge } from "../shared/PriorityBadge";

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
        <EmptyState title="Nothing missing" message="No outstanding information requests." />
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
      <ul className="space-y-1" aria-label="Missing information checklist">
        {content.items.map((item) => (
          <li
            key={item.id}
            className="flex items-center justify-between gap-2 rounded border border-trust/10 px-2 py-1.5"
          >
            <label className="flex min-w-0 items-center gap-2 text-sm text-ink">
              <input
                type="checkbox"
                className="size-3.5 shrink-0 rounded border-trust/40 text-trust focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-trust"
                disabled
                aria-label={item.label}
              />
              <span className="truncate">{item.label}</span>
            </label>
            <PriorityBadge priority={item.priority} />
          </li>
        ))}
      </ul>
    </CardChrome>
  );
}
