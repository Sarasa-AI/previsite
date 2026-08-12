import type { ReactNode } from "react";
import type { ChiefComplaintContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
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
      <CardChrome
        className={className}
        title="Chief complaint"
        trust={trust}
        aria-label="Chief complaint"
      >
        <EmptyState title="No chief complaint" message="Chief complaint has not been recorded." />
      </CardChrome>
    );
  }

  return (
    <CardChrome
      className={className}
      title="Chief complaint"
      subtitle={content.duration}
      badges={<PriorityBadge priority={content.priority} />}
      trust={trust}
      aria-label="Chief complaint"
    >
      <p className="text-sm text-ink">{content.title}</p>
    </CardChrome>
  );
}
