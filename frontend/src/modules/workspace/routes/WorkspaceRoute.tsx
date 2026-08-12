"use client";

import { WorkspaceErrorBoundary } from "@/src/shared/ui/WorkspaceErrorBoundary";
import { WorkspaceLoadingBoundary } from "@/src/shared/ui/WorkspaceLoadingBoundary";
import { WorkspaceShell } from "../components/WorkspaceShell";
import { useClinicalContent } from "../presentation/hooks/useClinicalContent";
import { useWorkspacePlan } from "../presentation/hooks/useWorkspacePlan";

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
  const workspace = useWorkspacePlan({ sessionId, lens, role });
  const contextHash = workspace.viewModel?.metadata.contextHash ?? null;
  const content = useClinicalContent({
    sessionId,
    contextHash,
    enabled: !!workspace.viewModel,
  });

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
          clinicalContent={content.clinicalContent}
        />
      </WorkspaceLoadingBoundary>
    </WorkspaceErrorBoundary>
  );
}
