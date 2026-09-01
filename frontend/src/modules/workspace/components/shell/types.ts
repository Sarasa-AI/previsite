import type { ClinicalContentViewModel } from "../types";
import type { ErrorViewModel, WorkspaceViewModel } from "../../presentation/viewmodels/types";
import type { WorkspaceUiState } from "../../presentation/state/workspaceUiState";

export type WorkspaceShellProps = {
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
  clinicalContent?: ClinicalContentViewModel | null;
};
