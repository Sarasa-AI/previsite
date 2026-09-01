import { Badge, StatusBadge } from "@/components/ui";
import type { ErrorViewModel } from "../../presentation/viewmodels/types";
import type { WorkspaceUiState } from "../../presentation/state/workspaceUiState";

export function WorkspaceStatusBar({ uiState, workspaceState, error }: { uiState: WorkspaceUiState; workspaceState?: string; error: ErrorViewModel | null }) {
  return (
    <header data-workspace-chrome="banner" aria-label="Workspace status" className="border-b border-tai-border bg-white">
      <div className="mx-auto flex min-h-10 w-full max-w-screen-2xl flex-wrap items-center gap-2 px-3 py-2 sm:px-4 lg:px-6">
        <Badge data-workspace-state={workspaceState} className="font-semibold">{uiState}</Badge>
        {uiState === "ReadOnly" || workspaceState === "read_only" ? <StatusBadge state="unverified" data-banner="read-only">فقط خواندنی</StatusBadge> : null}
        {uiState === "Offline" || workspaceState === "offline" ? <StatusBadge state="warning" data-workspace-banner="offline">آفلاین؛ نمایش آخرین برنامه موجود</StatusBadge> : null}
        {uiState === "Generating" || workspaceState === "generating" ? <StatusBadge state="ai-generated" data-workspace-banner="generating">در حال تولید میزکار</StatusBadge> : null}
        {uiState === "Refreshing" ? <StatusBadge state="info" data-workspace-banner="refreshing">در حال به‌روزرسانی</StatusBadge> : null}
        {error ? <StatusBadge state="critical" data-error-code={error.code}>{error.code}</StatusBadge> : null}
      </div>
    </header>
  );
}
