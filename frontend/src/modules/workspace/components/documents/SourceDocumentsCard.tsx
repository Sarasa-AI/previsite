import type { ReactNode } from "react";
import { FileText } from "lucide-react";
import type { DocumentsContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { ExpandableBlock } from "../shared/ExpandableBlock";

export type SourceDocumentsCardProps = {
  content: DocumentsContent | null;
  trust?: ReactNode;
  className?: string;
};

function confidenceLabel(confidence: number | "unknown"): string {
  if (confidence === "unknown") return "unknown";
  return `${Math.round(confidence * 100)}%`;
}

export function SourceDocumentsCard({ content, trust, className }: SourceDocumentsCardProps) {
  if (content == null || content.items.length === 0) {
    return (
      <CardChrome
        className={className}
        title="Source documents"
        trust={trust}
        aria-label="Source documents"
      >
        <EmptyState title="No documents" message="No source documents are available." />
      </CardChrome>
    );
  }

  return (
    <CardChrome
      className={className}
      title="Source documents"
      trust={trust}
      aria-label="Source documents"
    >
      <div className="rounded-md border border-trust/10">
        {content.items.map((item) => (
          <ExpandableBlock
            key={item.id}
            className="px-2"
            summary={
              <span className="flex w-full flex-wrap items-center justify-between gap-2">
                <span className="flex min-w-0 items-center gap-2">
                  <FileText className="size-4 shrink-0 text-trust" aria-hidden="true" />
                  <span className="truncate font-medium text-ink">{item.name}</span>
                </span>
                <span className="flex shrink-0 flex-col items-end gap-0.5 text-xs text-ink/60">
                  <span aria-label={`Confidence ${confidenceLabel(item.confidence)}`}>
                    {confidenceLabel(item.confidence)}
                  </span>
                  <time dateTime={item.uploadedAt}>{item.uploadedAt}</time>
                </span>
              </span>
            }
          >
            {item.detail}
          </ExpandableBlock>
        ))}
      </div>
    </CardChrome>
  );
}
