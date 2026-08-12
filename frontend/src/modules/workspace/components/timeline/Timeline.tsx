import type { ReactNode } from "react";
import type { TimelineContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { ExpandableBlock } from "../shared/ExpandableBlock";
import { SourceIndicator } from "../shared/SourceIndicator";

export type TimelineProps = {
  content: TimelineContent | null;
  trust?: ReactNode;
  className?: string;
};

export function Timeline({ content, trust, className }: TimelineProps) {
  if (content == null || content.groups.length === 0) {
    return (
      <CardChrome className={className} title="Timeline" trust={trust} aria-label="Timeline">
        <EmptyState title="No timeline events" message="No clinical timeline events are available." />
      </CardChrome>
    );
  }

  return (
    <CardChrome className={className} title="Timeline" trust={trust} aria-label="Timeline">
      <div className="space-y-3">
        {content.groups.map((group) => (
          <section key={group.date} aria-label={`Events on ${group.date}`}>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-trust">
              {group.date}
            </h3>
            <div className="rounded-md border border-trust/10">
              {group.events.map((event) => (
                <ExpandableBlock
                  key={event.id}
                  className="px-2"
                  summary={
                    <span className="flex w-full flex-wrap items-baseline justify-between gap-2">
                      <span className="font-medium text-ink">{event.title}</span>
                      <SourceIndicator source={event.source} />
                    </span>
                  }
                >
                  {event.detail}
                </ExpandableBlock>
              ))}
            </div>
          </section>
        ))}
      </div>
    </CardChrome>
  );
}
