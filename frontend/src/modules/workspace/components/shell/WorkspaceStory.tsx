import type { ErrorViewModel } from "../../presentation/viewmodels/types";
import type { WorkspaceUiState } from "../../presentation/state/workspaceUiState";
import type { WorkspaceViewModel } from "../../presentation/viewmodels/types";
import { AIInsightsCard } from "../ai/AIInsightsCard";

export function WorkspaceStory({
  viewModel,
  onRefreshStory,
  refreshStoryPending,
  uiState,
  error,
}: {
  viewModel: WorkspaceViewModel;
  onRefreshStory: () => void;
  refreshStoryPending?: boolean;
  uiState?: WorkspaceUiState;
  error?: ErrorViewModel | null;
}) {
  return <div data-story><AIInsightsCard viewModel={viewModel} uiState={uiState} error={error} onRefresh={onRefreshStory} refreshPending={refreshStoryPending} /></div>;
}
