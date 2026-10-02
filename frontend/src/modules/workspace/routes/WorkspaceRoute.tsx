"use client";

import { WorkspaceErrorBoundary } from "@/src/shared/ui/WorkspaceErrorBoundary";
import { WorkspaceLoadingBoundary } from "@/src/shared/ui/WorkspaceLoadingBoundary";
import { WorkspaceShell } from "../components/WorkspaceShell";
import { useWorkspaceScreen } from "../presentation/hooks/useWorkspaceScreen";

type Props = {
  sessionId: string;
  lens?: string;
  role?: string;
};

export function WorkspaceRoute({
  sessionId,
  lens = "general_medicine",
  role = "doctor",
}: Props) {
  const workspace = useWorkspaceScreen({ sessionId, lens, role });

  return (
    <WorkspaceErrorBoundary>
      <WorkspaceLoadingBoundary uiState={workspace.uiState}>
        <WorkspaceShell
          uiState={workspace.uiState}
          viewModel={workspace.viewModel}
          error={workspace.error}
          onAcknowledge={workspace.acknowledge}
          onRefreshStory={workspace.refreshStory}
          onResolve={workspace.resolve}
          onDismiss={workspace.dismiss}
          onRetry={workspace.retry}
          acknowledgePending={workspace.acknowledgePending}
          refreshStoryPending={workspace.refreshStoryPending}
          resolvePending={workspace.resolvePending}
          dismissPending={workspace.dismissPending}
          clinicalContent={workspace.clinicalContent}
        />
      </WorkspaceLoadingBoundary>
    </WorkspaceErrorBoundary>
  );
}
