import type { ReactNode } from "react";
import type { MedicationsContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { GroupedList } from "../shared/GroupedList";
import { SourceIndicator } from "../shared/SourceIndicator";
import { StatusChip } from "../shared/StatusChip";

export type MedicationListProps = {
  content: MedicationsContent | null;
  trust?: ReactNode;
  className?: string;
};

export function MedicationList({ content, trust, className }: MedicationListProps) {
  if (content == null || content.groups.length === 0) {
    return (
      <CardChrome className={className} title="Medications" trust={trust} aria-label="Medications">
        <EmptyState title="No medications" message="No medication list is available." />
      </CardChrome>
    );
  }

  return (
    <CardChrome className={className} title="Medications" trust={trust} aria-label="Medications">
      <GroupedList
        aria-label="Medication groups"
        groups={content.groups.map((group) => ({
          id: group.label,
          label: group.label,
          items: group.items.map((item) => ({
            id: item.id,
            primary: item.name,
            secondary: (
              <span>
                {item.dose} · {item.frequency}
              </span>
            ),
            meta: (
              <span className="flex flex-col items-end gap-0.5">
                <StatusChip status={item.status} />
                <SourceIndicator source={item.source} />
              </span>
            ),
          })),
        }))}
      />
    </CardChrome>
  );
}
