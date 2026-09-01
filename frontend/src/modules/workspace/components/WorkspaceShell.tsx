"use client";

import { Button, StatePanel } from "@/components/ui";
import { DecisionQueue } from "./shell/DecisionQueue";
import { DeferredRegion, WorkspaceRegion } from "./shell/WorkspaceRegions";
import { WorkspaceHeader } from "./shell/WorkspaceHeader";
import { WorkspaceLoading } from "./shell/WorkspaceLoading";
import { WorkspaceNavigation } from "./shell/WorkspaceNavigation";
import { WorkspaceStatusBar } from "./shell/WorkspaceStatusBar";
import type { WorkspaceShellProps } from "./shell/types";

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
}: WorkspaceShellProps) {
  if (uiState === "Forbidden") {
    return (
      <div data-workspace-chrome="forbidden" className="mx-auto max-w-2xl p-4">
        <StatePanel
          kind="error"
          title="دسترسی مجاز نیست"
          message="شما اجازه مشاهده این میزکار را ندارید."
        />
      </div>
    );
  }

  if (uiState === "NotFound") {
    return (
      <div data-workspace-chrome="not-found" className="mx-auto max-w-2xl p-4">
        <StatePanel
          kind="error"
          title="میزکار پیدا نشد"
          message="این میزکار در دسترس نیست."
        />
      </div>
    );
  }

  if (uiState === "Error" && !viewModel) {
    return (
      <div data-workspace-chrome="error" className="mx-auto max-w-2xl p-4">
        <StatePanel
          kind="error"
          title="خطا در میزکار"
          message={error?.code ?? "بارگذاری میزکار ممکن نیست."}
          action={
            <Button
              type="button"
              variant="secondary"
              onClick={onRetry}
              aria-label="Retry"
            >
              تلاش دوباره
            </Button>
          }
        />
      </div>
    );
  }

  if (uiState === "Loading" || (!viewModel && uiState === "Idle")) {
    return (
      <div
        data-workspace-shell
        data-ui-state={uiState}
        dir="rtl"
        className="min-h-screen bg-tai-surface text-tai-text"
      >
        <WorkspaceStatusBar uiState={uiState} error={error} />
        <WorkspaceLoading />
      </div>
    );
  }

  if (!viewModel) {
    return (
      <div
        data-workspace-shell
        data-ui-state={uiState}
        dir="rtl"
        className="mx-auto max-w-2xl p-4"
      >
        <StatePanel
          kind="empty"
          title="برنامه میزکار موجود نیست"
          message="هنوز برنامه‌ای برای نمایش این میزکار وجود ندارد."
        />
      </div>
    );
  }

  const isPartial =
    uiState === "Generating" ||
    viewModel.workspaceState === "generating" ||
    viewModel.workspaceState === "partially_verified";
  const storyRender = {
    onRefreshStory,
    refreshStoryPending,
    uiState,
    error,
  };

  return (
    <div
      data-workspace-shell
      data-ui-state={uiState}
      data-etag={viewModel.planEtag}
      data-partial={isPartial ? "true" : "false"}
      dir="rtl"
      className="min-h-screen overflow-x-clip bg-tai-surface text-tai-text"
    >
      <WorkspaceStatusBar
        uiState={uiState}
        workspaceState={viewModel.workspaceState}
        error={error}
      />

      <main
        aria-label="Doctor workspace"
        className="mx-auto w-full max-w-[1540px] px-3 py-3 sm:px-4 lg:px-5 2xl:px-6 2xl:py-4"
      >
        <WorkspaceHeader viewModel={viewModel} clinicalContent={clinicalContent} />

        <div className="mt-3">
          <WorkspaceNavigation viewModel={viewModel} />
        </div>

        <div className="mt-3 grid min-w-0 gap-3 xl:grid-cols-[minmax(0,1fr)_15rem] xl:items-start 2xl:grid-cols-[minmax(0,1fr)_17rem] 2xl:gap-4">
          <div className="min-w-0 space-y-3 2xl:space-y-4">
            {viewModel.pinCards.length ? (
              <div className="rounded-tai-lg border border-tai-teal/25 bg-white p-2 shadow-tai-sm sm:p-2.5">
                <WorkspaceRegion
                  id="workspace-pinned"
                  name="pin"
                  label="Pinned"
                  cards={viewModel.pinCards}
                  viewModel={viewModel}
                  clinicalContent={clinicalContent}
                  onAcknowledge={onAcknowledge}
                  storyRender={storyRender}
                  className="grid gap-2 lg:grid-cols-12"
                />
              </div>
            ) : null}

            <WorkspaceRegion
              id="workspace-primary"
              name="primary"
              label="Primary"
              cards={viewModel.primaryCards}
              viewModel={viewModel}
              clinicalContent={clinicalContent}
              onAcknowledge={onAcknowledge}
              storyRender={storyRender}
              className="grid gap-3 lg:grid-cols-12 2xl:gap-4"
            />

            <WorkspaceRegion
              id="workspace-secondary"
              name="secondary"
              label="Secondary"
              cards={viewModel.secondaryCards}
              viewModel={viewModel}
              clinicalContent={clinicalContent}
              onAcknowledge={onAcknowledge}
              storyRender={storyRender}
              className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3 2xl:gap-4"
            />

            <DeferredRegion
              viewModel={viewModel}
              clinicalContent={clinicalContent}
              onAcknowledge={onAcknowledge}
              storyRender={storyRender}
            />
          </div>

          <aside
            aria-label="Workspace workflow"
            className="min-w-0 xl:sticky xl:top-3 xl:max-h-[calc(100dvh-1.5rem)] xl:overflow-y-auto xl:overscroll-contain xl:pe-1"
          >
            <DecisionQueue
              viewModel={viewModel}
              onAcknowledge={onAcknowledge}
              onResolve={onResolve}
              onDismiss={onDismiss}
              acknowledgePending={acknowledgePending}
              resolvePending={resolvePending}
              dismissPending={dismissPending}
            />
          </aside>
        </div>
      </main>
    </div>
  );
}
