import type { ReactNode } from "react";
import type { RedFlagsContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
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
      <CardChrome className={className} title="Red flags" trust={trust} aria-label="Red flags">
        <EmptyState title="No red flags" message="No critical alerts are present." />
      </CardChrome>
    );
  }

  return (
    <CardChrome className={className} title="Red flags" trust={trust} aria-label="Red flags">
      <SeverityList items={content.items} aria-label="Red flag items" />
    </CardChrome>
  );
}
