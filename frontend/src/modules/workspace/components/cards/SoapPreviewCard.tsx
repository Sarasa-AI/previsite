import type { ReactNode } from "react";
import type { SoapContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { ExpandableBlock } from "../shared/ExpandableBlock";

export type SoapPreviewCardProps = {
  content: SoapContent | null;
  trust?: ReactNode;
  /** When true, sections start expanded (native details open). */
  defaultExpanded?: boolean;
  className?: string;
};

export function SoapPreviewCard({
  content,
  trust,
  defaultExpanded = false,
  className,
}: SoapPreviewCardProps) {
  if (content == null) {
    return (
      <CardChrome className={className} title="SOAP preview" trust={trust} aria-label="SOAP preview">
        <EmptyState title="No SOAP preview" message="Assessment and plan are not available." />
      </CardChrome>
    );
  }

  return (
    <CardChrome className={className} title="SOAP preview" trust={trust} aria-label="SOAP preview">
      <div className="rounded-md border border-trust/10">
        <ExpandableBlock
          open={defaultExpanded || undefined}
          summary={<span className="font-medium text-trust">Assessment</span>}
          className="px-2"
        >
          <p className="whitespace-pre-wrap">{content.assessment}</p>
        </ExpandableBlock>
        <ExpandableBlock
          open={defaultExpanded || undefined}
          summary={<span className="font-medium text-trust">Plan</span>}
          className="px-2"
        >
          <p className="whitespace-pre-wrap">{content.plan}</p>
        </ExpandableBlock>
      </div>
    </CardChrome>
  );
}
