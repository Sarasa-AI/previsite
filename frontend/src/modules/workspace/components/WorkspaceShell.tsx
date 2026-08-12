"use client";

/**
 * Canonical Doctor Workspace screen composition.
 * Layout + region rendering only — no fetch, hooks, or clinical logic.
 */

import type { ReactNode } from "react";
import type { CardViewModel, WorkspaceViewModel, ErrorViewModel } from "../presentation/viewmodels/types";
import { resolveCardPresenter } from "../presentation/registry/cardRegistry";
import type { WorkspaceUiState } from "../presentation/state/workspaceUiState";
import type { ClinicalContentViewModel } from "./types";
import { selectClinicalSlice } from "./selectClinicalSlice";
import { PatientHeader } from "./layout/PatientHeader";
import { ErrorState } from "./shared/ErrorState";
import { EmptyState } from "./shared/EmptyState";
import { cx } from "./shared/cx";
import {
  ChiefComplaintSkeleton,
  DocumentsSkeleton,
  LabsPanelSkeleton,
  MedicationListSkeleton,
  MissingInfoSkeleton,
  PatientHeaderSkeleton,
  RedFlagsSkeleton,
  SnapshotStripSkeleton,
  SoapSkeleton,
  TimelineSkeleton,
} from "./skeletons";

type Props = {
  uiState: WorkspaceUiState;
  viewModel: WorkspaceViewModel | null;
  error: ErrorViewModel | null;
  onAcknowledge: (objectId: string) => void;
  onRefreshStory: () => void;
  onRetry: () => void;
  onResolve?: (objectId: string) => void;
  onDismiss?: (objectId: string) => void;
  acknowledgePending?: boolean;
  refreshStoryPending?: boolean;
  resolvePending?: boolean;
  dismissPending?: boolean;
  /** Presentation Integration Aggregate — Shell selects feature slices for presenters. */
  clinicalContent?: ClinicalContentViewModel | null;
};

function CardSlot({
  card,
  viewModel,
  clinicalContent,
  onAcknowledge,
}: {
  card: CardViewModel;
  viewModel: WorkspaceViewModel;
  clinicalContent?: ClinicalContentViewModel | null;
  onAcknowledge: (objectId: string) => void;
}) {
  const Presenter = resolveCardPresenter(card.objectId, {
    sessionId: viewModel.sessionId,
    planEtag: viewModel.planEtag,
    contractVersion: viewModel.contractVersion,
  });
  if (!Presenter) return null;
  const content = selectClinicalSlice(card.objectId, clinicalContent);
  return (
    <div
      data-workspace-card={card.objectId}
      data-slot={card.slot}
      data-size={card.size}
      data-priority={card.priority}
      className="min-w-0"
    >
      <Presenter card={card} content={content} onAcknowledge={onAcknowledge} />
    </div>
  );
}

function Region({
  name,
  label,
  cards,
  viewModel,
  clinicalContent,
  onAcknowledge,
  className,
  children,
}: {
  name: string;
  label: string;
  cards: readonly CardViewModel[];
  viewModel: WorkspaceViewModel;
  clinicalContent?: ClinicalContentViewModel | null;
  onAcknowledge: (objectId: string) => void;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <section
      data-workspace-band={name}
      aria-label={label}
      className={cx("flex min-w-0 flex-col gap-3", className)}
    >
      {children}
      {cards.map((card) => (
        <CardSlot
          key={`${card.slot}-${card.objectId}`}
          card={card}
          viewModel={viewModel}
          clinicalContent={clinicalContent}
          onAcknowledge={onAcknowledge}
        />
      ))}
    </section>
  );
}

function WorkspaceChrome({
  uiState,
  workspaceState,
  error,
}: {
  uiState: WorkspaceUiState;
  workspaceState?: string;
  error: ErrorViewModel | null;
}) {
  const banners: ReactNode[] = [];

  if (uiState === "ReadOnly" || workspaceState === "read_only") {
    banners.push(
      <div key="read-only" data-banner="read-only" className="text-xs font-medium text-trust">
        Read only
      </div>,
    );
  }
  if (uiState === "Offline" || workspaceState === "offline") {
    banners.push(
      <div key="offline" data-workspace-banner="offline" className="text-xs font-medium text-danger">
        Offline — showing last available plan
      </div>,
    );
  }
  if (uiState === "Generating" || workspaceState === "generating") {
    banners.push(
      <div
        key="generating"
        data-workspace-banner="generating"
        className="text-xs font-medium text-trust"
      >
        Generating workspace…
      </div>,
    );
  }
  if (uiState === "Refreshing") {
    banners.push(
      <div
        key="refreshing"
        data-workspace-banner="refreshing"
        className="text-xs font-medium text-trust"
      >
        Refreshing…
      </div>,
    );
  }
  if (error) {
    banners.push(
      <div key="error" data-error-code={error.code} className="text-xs text-danger">
        {error.code}
      </div>,
    );
  }

  if (banners.length === 0 && !workspaceState) return null;

  return (
    <header
      data-workspace-chrome="banner"
      className="flex flex-wrap items-center gap-2 border-b border-trust/10 bg-clinical px-3 py-2"
      aria-label="Workspace status"
    >
      {workspaceState ? (
        <span
          data-workspace-state={workspaceState}
          className="text-xs font-semibold uppercase tracking-wide text-trust"
        >
          {uiState}
        </span>
      ) : null}
      {banners}
    </header>
  );
}

function LoadingLayout() {
  return (
    <div
      data-workspace-chrome="loading"
      className="flex flex-col gap-3 p-3"
      role="status"
      aria-busy="true"
      aria-label="Loading doctor workspace"
    >
      <PatientHeaderSkeleton />
      <ChiefComplaintSkeleton />
      <RedFlagsSkeleton />
      <SnapshotStripSkeleton />
      <div className="grid gap-3 lg:grid-cols-2">
        <TimelineSkeleton />
        <LabsPanelSkeleton />
        <MedicationListSkeleton />
      </div>
      <div className="grid gap-3 lg:grid-cols-3">
        <MissingInfoSkeleton />
        <SoapSkeleton />
        <DocumentsSkeleton />
      </div>
    </div>
  );
}

function DecisionQueuePanel({
  viewModel,
  onAcknowledge,
  onResolve,
  onDismiss,
  acknowledgePending,
  resolvePending,
  dismissPending,
}: {
  viewModel: WorkspaceViewModel;
  onAcknowledge: (objectId: string) => void;
  onResolve?: (objectId: string) => void;
  onDismiss?: (objectId: string) => void;
  acknowledgePending?: boolean;
  resolvePending?: boolean;
  dismissPending?: boolean;
}) {
  if (viewModel.queue.length === 0) return null;

  return (
    <section
      data-workspace-band="queue"
      aria-label="Decision queue"
      className="flex flex-col gap-2 rounded-lg border border-trust/15 bg-white p-3 shadow-sm"
    >
      <h2 className="text-sm font-semibold text-trust">Decision queue</h2>
      <ol className="flex flex-col gap-2">
        {viewModel.queue.map((item) => (
          <li
            key={`queue-${item.rank}-${item.objectId}`}
            data-queue-rank={item.rank}
            className="flex flex-wrap items-start justify-between gap-2 border-b border-trust/10 pb-2 last:border-b-0 last:pb-0"
          >
            <div className="min-w-0">
              <div className="text-sm font-medium text-ink">
                {item.rank}. {item.objectId}
              </div>
              <p className="text-xs text-ink/70">{item.explanation}</p>
            </div>
            {viewModel.mutationsAllowed ? (
              <div className="flex flex-wrap gap-1">
                {item.acknowledgeRequired ? (
                  <button
                    type="button"
                    disabled={acknowledgePending}
                    onClick={() => onAcknowledge(item.objectId)}
                    className="rounded border border-trust/30 bg-clinical px-2 py-1 text-xs font-medium text-trust focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-trust disabled:opacity-50"
                  >
                    Acknowledge
                  </button>
                ) : null}
                {onResolve ? (
                  <button
                    type="button"
                    disabled={resolvePending}
                    onClick={() => onResolve(item.objectId)}
                    className="rounded border border-trust/30 bg-white px-2 py-1 text-xs font-medium text-trust focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-trust disabled:opacity-50"
                  >
                    Resolve
                  </button>
                ) : null}
                {onDismiss ? (
                  <button
                    type="button"
                    disabled={dismissPending}
                    onClick={() => onDismiss(item.objectId)}
                    className="rounded border border-ink/20 bg-white px-2 py-1 text-xs font-medium text-ink/80 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-trust disabled:opacity-50"
                  >
                    Dismiss
                  </button>
                ) : null}
              </div>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}

export function WorkspaceShell({
  uiState,
  viewModel,
  error,
  onAcknowledge,
  onRefreshStory,
  onRetry,
  onResolve,
  onDismiss,
  acknowledgePending,
  refreshStoryPending,
  resolvePending,
  dismissPending,
  clinicalContent = null,
}: Props) {
  if (uiState === "Forbidden") {
    return (
      <div data-workspace-chrome="forbidden" className="p-4">
        <ErrorState title="Access denied" message="You do not have access to this workspace." />
      </div>
    );
  }

  if (uiState === "NotFound") {
    return (
      <div data-workspace-chrome="not-found" className="p-4">
        <ErrorState title="Workspace not found" message="This workspace could not be located." />
      </div>
    );
  }

  if (uiState === "Error" && !viewModel) {
    return (
      <div data-workspace-chrome="error" className="flex flex-col gap-3 p-4">
        <ErrorState title="Workspace error" message={error?.code ?? "Unable to load workspace."} />
        <button
          type="button"
          onClick={onRetry}
          className="self-start rounded border border-trust/30 bg-clinical px-3 py-1.5 text-sm font-medium text-trust focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-trust"
        >
          Retry
        </button>
      </div>
    );
  }

  if (uiState === "Loading" || (!viewModel && uiState === "Idle")) {
    return (
      <div data-workspace-shell data-ui-state={uiState} className="min-h-screen bg-clinical text-ink">
        <WorkspaceChrome uiState={uiState} error={error} />
        <LoadingLayout />
      </div>
    );
  }

  if (!viewModel) {
    return (
      <div data-workspace-shell data-ui-state={uiState} className="p-4">
        <EmptyState title="No workspace plan" message="A workspace plan is not available yet." />
      </div>
    );
  }

  const isPartial =
    uiState === "Generating" ||
    viewModel.workspaceState === "generating" ||
    viewModel.workspaceState === "partially_verified";

  return (
    <div
      data-workspace-shell
      data-ui-state={uiState}
      data-etag={viewModel.planEtag}
      data-partial={isPartial ? "true" : "false"}
      className="min-h-screen bg-clinical text-ink"
    >
      <WorkspaceChrome
        uiState={uiState}
        workspaceState={viewModel.workspaceState}
        error={error}
      />

      <main
        aria-label="Doctor workspace"
        className="mx-auto flex w-full max-w-screen-2xl flex-col gap-3 overflow-x-hidden px-3 py-3 lg:px-4"
      >
        <PatientHeader content={clinicalContent?.patientHeader ?? null} />

        {/* Pin zone — sticky, first-screen critical */}
        {viewModel.pinCards.length > 0 ? (
          <div className="sticky top-0 z-10 -mx-3 border-b border-trust/10 bg-clinical px-3 py-2 lg:-mx-4 lg:px-4">
            <Region
              name="pin"
              label="Pinned"
              cards={viewModel.pinCards}
              viewModel={viewModel}
              clinicalContent={clinicalContent}
              onAcknowledge={onAcknowledge}
            />
          </div>
        ) : null}

        {/* Primary content — above the fold emphasis */}
        <Region
          name="primary"
          label="Primary"
          cards={viewModel.primaryCards}
          viewModel={viewModel}
          clinicalContent={clinicalContent}
          onAcknowledge={onAcknowledge}
          className="lg:gap-4"
        >
          {viewModel.story ? (
            <article
              data-story
              data-stale={viewModel.story.stale ? "true" : "false"}
              className="rounded-lg border border-trust/15 bg-white p-3 shadow-sm"
              aria-label="Clinical story"
            >
              <h2 className="mb-1 text-sm font-semibold text-trust">Clinical story</h2>
              <p className="text-sm text-ink">{viewModel.story.text}</p>
              {viewModel.story.stale && viewModel.mutationsAllowed ? (
                <button
                  type="button"
                  onClick={onRefreshStory}
                  disabled={refreshStoryPending}
                  className="mt-2 rounded border border-trust/30 bg-clinical px-2 py-1 text-xs font-medium text-trust focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-trust disabled:opacity-50"
                >
                  Refresh story
                </button>
              ) : null}
            </article>
          ) : null}
        </Region>

        {/* Secondary content */}
        <Region
          name="secondary"
          label="Secondary"
          cards={viewModel.secondaryCards}
          viewModel={viewModel}
          clinicalContent={clinicalContent}
          onAcknowledge={onAcknowledge}
          className="grid gap-3 md:grid-cols-2 xl:grid-cols-3"
        />

        {/* Deferred — collapsed by default (native details, no React state) */}
        {viewModel.deferredCards.length > 0 ? (
          <details
            data-workspace-band="deferred"
            className="group rounded-lg border border-trust/15 bg-white shadow-sm"
          >
            <summary
              className="cursor-pointer list-none px-3 py-2 text-sm font-semibold text-trust marker:content-none focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-trust [&::-webkit-details-marker]:hidden"
              aria-label="Deferred cards"
            >
              Deferred ({viewModel.deferredCards.length})
            </summary>
            <div className="flex flex-col gap-3 border-t border-trust/10 p-3">
              {viewModel.deferredCards.map((card) => (
                <CardSlot
                  key={`deferred-${card.objectId}`}
                  card={card}
                  viewModel={viewModel}
                  clinicalContent={clinicalContent}
                  onAcknowledge={onAcknowledge}
                />
              ))}
            </div>
          </details>
        ) : null}

        <DecisionQueuePanel
          viewModel={viewModel}
          onAcknowledge={onAcknowledge}
          onResolve={onResolve}
          onDismiss={onDismiss}
          acknowledgePending={acknowledgePending}
          resolvePending={resolvePending}
          dismissPending={dismissPending}
        />
      </main>
    </div>
  );
}
