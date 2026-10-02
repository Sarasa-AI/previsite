import type { CardPresenterProps } from "../../presentation/registry/types";
import type {
  ChiefComplaintContent,
  DocumentsContent,
  LabsContent,
  MedicationsContent,
  RedFlagsContent,
  SnapshotStripContent,
  SoapContent,
  TimelineContent,
} from "../types";
import type { HPIContent } from "../types/content";
import { ChiefComplaintCard } from "../cards/ChiefComplaintCard";
import { HPICard } from "../cards/HPICard";
import { RedFlagsCard } from "../cards/RedFlagsCard";
import { SoapPreviewCard } from "../cards/SoapPreviewCard";
import { ClinicalSnapshotStrip } from "../layout/ClinicalSnapshotStrip";
import { Timeline } from "../timeline/Timeline";
import { MedicationList } from "../medications/MedicationList";
import { LabsPanel } from "../labs/LabsPanel";
import { SourceDocumentsCard } from "../documents/SourceDocumentsCard";
import { PresenterChrome, trustSlot } from "./presenterChrome";
import { AllergiesCard, ProblemsCard } from "../clinical/ClinicalDataCards";

/** Production presenters — layout/trust from CardViewModel; body from feature content slices. */

export function ChiefComplaintPresenter({ card, content }: CardPresenterProps) {
  return (
    <ChiefComplaintCard
      content={(content as ChiefComplaintContent | null | undefined) ?? null}
      trust={trustSlot(card)}
    />
  );
}

export function HPIPresenter({ card, content }: CardPresenterProps) {
  return (
    <HPICard
      content={(content as HPIContent | null | undefined) ?? null}
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
      emptyTitle="داده هشدارهای بحرانی در دسترس نیست"
      emptyMessage="قرارداد محتوای فعلی داده‌ای برای تایید یا رد هشدار بحرانی ارائه نمی‌کند."
      emptyState="unavailable"
    />
  );
}

export function ConflictsPresenter({ card }: CardPresenterProps) {
  return (
    <PresenterChrome
      card={card}
      title="Conflicts"
      emptyTitle="داده تعارض‌ها در دسترس نیست"
      emptyMessage="نبود داده ساختاریافته به معنی نبود یا حل‌شدن تعارض بالینی نیست."
      emptyState="unavailable"
    />
  );
}

export function AllergiesPresenter({ card, content }: CardPresenterProps) {
  const snapshot = (content as SnapshotStripContent | null | undefined) ?? null;
  return <AllergiesCard content={snapshot} state={snapshot?.allergyState === "not_documented" ? "missing" : snapshot?.allergyState} trust={trustSlot(card)} />;
}

export function TimelinePresenter({ card, content }: CardPresenterProps) {
  return (
    <Timeline
      content={(content as TimelineContent | null | undefined) ?? null}
      trust={trustSlot(card)}
      provenance={card.trust}
    />
  );
}

export function StoryPresenter({ card }: CardPresenterProps) {
  return null;
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
      emptyTitle="داده آزمایش بحرانی در دسترس نیست"
      emptyMessage="این وضعیت به معنی طبیعی بودن یا نبود نتیجه بحرانی نیست."
      emptyState="unavailable"
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

export function PmhPresenter({ card, content }: CardPresenterProps) {
  return <ProblemsCard content={(content as SnapshotStripContent | null | undefined) ?? null} trust={trustSlot(card)} />;
}

export function DocumentsPresenter({ card, content }: CardPresenterProps) {
  return (
    <SourceDocumentsCard
      content={(content as DocumentsContent | null | undefined) ?? null}
      trust={trustSlot(card)}
      provenance={card.trust}
    />
  );
}

export function SoapPresenter({ card, content }: CardPresenterProps) {
  return (
    <SoapPreviewCard
      content={(content as SoapContent | null | undefined) ?? null}
      trust={trustSlot(card)}
      provenance={card.trust}
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

/** @deprecated Removed from the workspace presentation. */
export function MissingDataPresenter(_props: CardPresenterProps) { return null; }

/** @deprecated Removed from the workspace presentation. */
export function PatientQuestionsPresenter(_props: CardPresenterProps) { return null; }
