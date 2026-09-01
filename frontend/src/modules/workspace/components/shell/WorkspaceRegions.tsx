import type { ReactNode } from "react";
import type { CardViewModel, WorkspaceViewModel } from "../../presentation/viewmodels/types";
import type { ClinicalContentViewModel } from "../types";
import { resolveCardPresenter } from "../../presentation/registry/cardRegistry";
import { selectClinicalSlice } from "../selectClinicalSlice";
import { cx } from "../shared/cx";
import { WorkspaceStory } from "./WorkspaceStory";
import type { ErrorViewModel } from "../../presentation/viewmodels/types";
import type { WorkspaceUiState } from "../../presentation/state/workspaceUiState";

type StoryRenderProps = {
  onRefreshStory: () => void;
  refreshStoryPending?: boolean;
  uiState?: WorkspaceUiState;
  error?: ErrorViewModel | null;
};

export function WorkspaceCardSlot({ card, viewModel, clinicalContent, onAcknowledge, storyRender }: { card: CardViewModel; viewModel: WorkspaceViewModel; clinicalContent: ClinicalContentViewModel | null; onAcknowledge: (objectId: string) => void; storyRender?: StoryRenderProps }) {
  const layoutClass = card.slot === "pin"
    ? card.objectId === "red_flags" ? "lg:col-span-5" : card.objectId === "allergies" ? "lg:col-span-4" : "lg:col-span-3"
    : card.slot === "primary"
      ? card.objectId === "chief_complaint" ? "lg:col-span-5" : card.objectId === "hpi" ? "lg:col-span-7" : card.objectId === "medications" || card.objectId === "story" ? "lg:col-span-6" : "lg:col-span-12"
      : "";
  if (card.objectId === "story" && storyRender) {
    return <div data-workspace-card={card.objectId} data-slot={card.slot} data-size={card.size} data-priority={card.priority} className={cx("min-w-0 [&>div]:h-full [&_article]:h-full", layoutClass)}><WorkspaceStory viewModel={viewModel} {...storyRender} /></div>;
  }
  const Presenter = resolveCardPresenter(card.objectId, { sessionId: viewModel.sessionId, planEtag: viewModel.planEtag, contractVersion: viewModel.contractVersion });
  if (!Presenter) return null;
  return <div data-workspace-card={card.objectId} data-slot={card.slot} data-size={card.size} data-priority={card.priority} className={cx("min-w-0 [&>article]:h-full [&>section]:h-full", layoutClass)}><Presenter card={card} content={selectClinicalSlice(card.objectId, clinicalContent)} onAcknowledge={onAcknowledge} /></div>;
}

export function WorkspaceRegion({ id, name, label, cards, viewModel, clinicalContent, onAcknowledge, storyRender, className, children }: { id: string; name: string; label: string; cards: readonly CardViewModel[]; viewModel: WorkspaceViewModel; clinicalContent: ClinicalContentViewModel | null; onAcknowledge: (objectId: string) => void; storyRender?: StoryRenderProps; className?: string; children?: ReactNode }) {
  return <section id={id} data-workspace-band={name} aria-label={label} className={cx("min-w-0 scroll-mt-4", className)}>{children}{cards.map((card) => <WorkspaceCardSlot key={`${card.slot}-${card.objectId}`} card={card} viewModel={viewModel} clinicalContent={clinicalContent} onAcknowledge={onAcknowledge} storyRender={storyRender} />)}</section>;
}

export function DeferredRegion({ viewModel, clinicalContent, onAcknowledge, storyRender }: { viewModel: WorkspaceViewModel; clinicalContent: ClinicalContentViewModel | null; onAcknowledge: (objectId: string) => void; storyRender?: StoryRenderProps }) {
  if (!viewModel.deferredCards.length) return null;
  return <details id="workspace-deferred" data-workspace-band="deferred" className="group scroll-mt-4 rounded-tai-lg border border-tai-border bg-white shadow-tai-sm"><summary className="cursor-pointer list-none px-4 py-3 text-sm font-semibold text-tai-navy marker:content-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-tai-navy [&::-webkit-details-marker]:hidden" aria-label="Deferred cards">موارد تعویق‌شده ({viewModel.deferredCards.length})</summary><div className="flex flex-col gap-3 border-t border-tai-border p-3 [content-visibility:auto] [contain-intrinsic-size:1px_480px] sm:p-4">{viewModel.deferredCards.map((card) => <WorkspaceCardSlot key={`deferred-${card.objectId}`} card={card} viewModel={viewModel} clinicalContent={clinicalContent} onAcknowledge={onAcknowledge} storyRender={storyRender} />)}</div></details>;
}
