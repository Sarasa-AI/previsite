import type { ReactNode } from "react";
import type { LabsContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { ResultRows } from "../shared/ResultRows";

export type LabsPanelProps = {
  content: LabsContent | null;
  trust?: ReactNode;
  className?: string;
};

export function LabsPanel({ content, trust, className }: LabsPanelProps) {
  if (content == null || content.rows.length === 0) {
    return (
      <CardChrome className={className} title="Labs" trust={trust} aria-label="Labs">
        <EmptyState title="No labs" message="No laboratory results are available." />
      </CardChrome>
    );
  }

  return (
    <CardChrome className={className} title="Labs" trust={trust} aria-label="Labs">
      <ResultRows
        aria-label="Laboratory results"
        rows={content.rows.map((row) => ({
          id: row.id,
          name: row.name,
          value: row.value,
          unit: row.unit,
          referenceRange: row.referenceRange,
          flagged: row.abnormal,
          trend: row.trend,
          detail: row.detail,
        }))}
      />
    </CardChrome>
  );
}
