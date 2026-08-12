import type { ReactNode } from "react";
import type { SnapshotStripContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { MetricStrip } from "../shared/MetricStrip";
import { EmptyState } from "../shared/EmptyState";

export type ClinicalSnapshotStripProps = {
  content: SnapshotStripContent | null;
  trust?: ReactNode;
  className?: string;
};

export function ClinicalSnapshotStrip({ content, trust, className }: ClinicalSnapshotStripProps) {
  if (content == null) {
    return (
      <CardChrome
        className={className}
        title="Clinical snapshot"
        trust={trust}
        aria-label="Clinical snapshot"
      >
        <EmptyState title="No snapshot" message="Clinical snapshot metrics are not available." />
      </CardChrome>
    );
  }

  return (
    <CardChrome
      className={className}
      title="Clinical snapshot"
      trust={trust}
      aria-label="Clinical snapshot"
    >
      <MetricStrip
        aria-label="Clinical snapshot metrics"
        items={[
          { id: "vitals", label: "Vitals", value: content.vitals },
          { id: "problems", label: "Problems", value: content.problems },
          { id: "risk", label: "Risk", value: content.risk },
          { id: "allergies", label: "Allergies", value: content.allergies },
          { id: "meds", label: "Medications", value: String(content.medicationCount) },
          { id: "timeline", label: "Timeline", value: String(content.timelineCount) },
        ]}
      />
    </CardChrome>
  );
}
