import type { ReactNode } from "react";
import type { PatientHeaderContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { StatusChip } from "../shared/StatusChip";

export type PatientHeaderProps = {
  content: PatientHeaderContent | null;
  /** Trust chrome — never embedded in content ViewModel. */
  trust?: ReactNode;
  className?: string;
};

export function PatientHeader({ content, trust, className }: PatientHeaderProps) {
  if (content == null) {
    return (
      <CardChrome
        className={className}
        aria-label="Patient header"
        title="Patient"
        trust={trust}
      >
        <p className="text-xs text-ink/70">Patient demographics are not available.</p>
      </CardChrome>
    );
  }

  const subtitle = (
    <span className="flex flex-wrap gap-x-3 gap-y-1">
      <span>
        {content.age}y · {content.sex}
      </span>
      <span>MRN {content.mrn}</span>
      <span>{content.visitType}</span>
    </span>
  );

  return (
    <CardChrome
      className={className}
      aria-label="Patient header"
      title={content.name}
      subtitle={subtitle}
      badges={<StatusChip status={content.status} />}
      trust={trust}
    />
  );
}
