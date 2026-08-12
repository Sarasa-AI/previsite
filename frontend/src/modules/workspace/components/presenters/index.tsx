import type { CardPresenterProps } from "../../presentation/registry/types";
import type {
  ChiefComplaintContent,
  DocumentsContent,
  LabsContent,
  MedicationsContent,
  MissingInfoContent,
  RedFlagsContent,
  SnapshotStripContent,
  SoapContent,
  TimelineContent,
} from "../types";
import { ChiefComplaintCard } from "../cards/ChiefComplaintCard";
import { RedFlagsCard } from "../cards/RedFlagsCard";
import { MissingInformationCard } from "../cards/MissingInformationCard";
import { SoapPreviewCard } from "../cards/SoapPreviewCard";
import { ClinicalSnapshotStrip } from "../layout/ClinicalSnapshotStrip";
import { Timeline } from "../timeline/Timeline";
import { MedicationList } from "../medications/MedicationList";
import { LabsPanel } from "../labs/LabsPanel";
import { SourceDocumentsCard } from "../documents/SourceDocumentsCard";
import { PresenterChrome, trustSlot } from "./presenterChrome";

/** Production presenters — layout/trust from CardViewModel; body from feature content slices. */

export function ChiefComplaintPresenter({ card, content }: CardPresenterProps) {
  return (
    <ChiefComplaintCard
      content={(content as ChiefComplaintContent | null | undefined) ?? null}
      trust={trustSlot(card)}
    />
  );
}

export function RedFlagsPresenter({ card, content }: CardPresenterProps) {
  return (
    <RedFlagsCard
      content={(content as RedFlagsContent | null | undefined) ?? null}
      trust={trustSlot(card)}
    />
  );
}

export function CriticalAlertsPresenter({ card }: CardPresenterProps) {
  return (
    <PresenterChrome
      card={card}
      title="Critical alerts"
      emptyTitle="No critical alerts"
      emptyMessage="No critical alerts are present."
    />
  );
}

export function ConflictsPresenter({ card }: CardPresenterProps) {
  return (
    <PresenterChrome
      card={card}
      title="Conflicts"
      emptyTitle="No conflicts"
      emptyMessage="No clinical conflicts are present."
    />
  );
}

export function AllergiesPresenter({ card }: CardPresenterProps) {
  return (
    <PresenterChrome
      card={card}
      title="Allergies"
      emptyTitle="No allergies"
      emptyMessage="No allergy records are available."
    />
  );
}

export function TimelinePresenter({ card, content }: CardPresenterProps) {
  return (
    <Timeline
      content={(content as TimelineContent | null | undefined) ?? null}
      trust={trustSlot(card)}
    />
  );
}

export function StoryPresenter({ card }: CardPresenterProps) {
  return (
    <PresenterChrome
      card={card}
      title="Story"
      emptyTitle="Story"
      emptyMessage="Prefer the top-level clinical story when present."
    />
  );
}

export function LabsPresenter({ card, content }: CardPresenterProps) {
  return (
    <LabsPanel
      content={(content as LabsContent | null | undefined) ?? null}
      trust={trustSlot(card)}
    />
  );
}

export function CriticalLabsPresenter({ card }: CardPresenterProps) {
  return (
    <PresenterChrome
      card={card}
      title="Critical labs"
      emptyTitle="No critical labs"
      emptyMessage="No critical laboratory results are available."
    />
  );
}

export function MedicationsPresenter({ card, content }: CardPresenterProps) {
  return (
    <MedicationList
      content={(content as MedicationsContent | null | undefined) ?? null}
      trust={trustSlot(card)}
    />
  );
}

export function PmhPresenter({ card }: CardPresenterProps) {
  return (
    <PresenterChrome
      card={card}
      title="Past medical history"
      emptyTitle="No PMH"
      emptyMessage="Past medical history is not available."
    />
  );
}

export function DocumentsPresenter({ card, content }: CardPresenterProps) {
  return (
    <SourceDocumentsCard
      content={(content as DocumentsContent | null | undefined) ?? null}
      trust={trustSlot(card)}
    />
  );
}

export function PatientQuestionsPresenter({ card }: CardPresenterProps) {
  return (
    <PresenterChrome
      card={card}
      title="Patient questions"
      emptyTitle="No questions"
      emptyMessage="No patient questions are available."
    />
  );
}

export function MissingDataPresenter({ card, content }: CardPresenterProps) {
  return (
    <MissingInformationCard
      content={(content as MissingInfoContent | null | undefined) ?? null}
      trust={trustSlot(card)}
    />
  );
}

export function SoapPresenter({ card, content }: CardPresenterProps) {
  return (
    <SoapPreviewCard
      content={(content as SoapContent | null | undefined) ?? null}
      trust={trustSlot(card)}
      defaultExpanded={card.size === "expanded"}
    />
  );
}

export function SnapshotPresenter({ card, content }: CardPresenterProps) {
  return (
    <ClinicalSnapshotStrip
      content={(content as SnapshotStripContent | null | undefined) ?? null}
      trust={trustSlot(card)}
      className={card.size === "badge" ? "max-w-xs" : undefined}
    />
  );
}
