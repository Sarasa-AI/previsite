"use client";

import type { ReactNode } from "react";
import type { WorkspaceUiState } from "@/src/modules/workspace/presentation/state/workspaceUiState";

type Props = {
  uiState: WorkspaceUiState;
  children: ReactNode;
};

/**
 * Pass-through banners for generating/refreshing/offline.
 * Loading UI is owned by WorkspaceShell (skeleton composition).
 */
export function WorkspaceLoadingBoundary({ uiState, children }: Props) {
  if (uiState === "Generating") {
    return (
      <div data-workspace-boundary="generating">
        {children}
      </div>
    );
  }
  if (uiState === "Refreshing") {
    return (
      <div data-workspace-boundary="refreshing">
        {children}
      </div>
    );
  }
  if (uiState === "Offline") {
    return (
      <div data-workspace-boundary="offline">
        {children}
      </div>
    );
  }
  return <>{children}</>;
}
