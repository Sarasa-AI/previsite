/**
 * Ephemeral presentation ViewModels.
 * Module-private — never persist, never share as contracts.
 * Rebuilt from every successful WorkspacePlanResponse for the current ETag only.
 */

export type RenderableSlot = "pin" | "primary" | "secondary" | "deferred";

export type ConfidenceDisplay = number | "unknown";

export interface TrustViewModel {
  readonly primaryProvenance: string;
  readonly allProvenance: readonly string[];
  readonly confidence: ConfidenceDisplay;
  readonly verification: string;
  readonly evidenceRefs: readonly string[];
}

export interface CardViewModel {
  readonly objectId: string;
  readonly priority: string;
  readonly slot: RenderableSlot;
  readonly size: string;
  readonly pinned: boolean;
  readonly trust: TrustViewModel;
  readonly flags: readonly string[];
}

export interface DecisionQueueItemViewModel {
  readonly rank: number;
  readonly objectId: string;
  readonly reasonCode: string;
  readonly explanation: string;
  readonly acknowledgeRequired: boolean;
}

export interface StoryViewModel {
  readonly text: string;
  readonly confidence: ConfidenceDisplay;
  readonly evidenceRefs: readonly string[];
  readonly stale: boolean;
}

export interface CognitiveBudgetViewModel {
  readonly primaryCount: number;
  readonly expandedCount: number;
  readonly deferredCount: number;
}

export interface PlanMetadataViewModel {
  readonly contextHash: string;
  readonly lens: string;
  readonly role: string;
  readonly computedAt: string;
  readonly workspacePlanVersion: string;
  readonly generatedAt: string;
  readonly generatedBy: string;
  readonly computeDurationMs: number;
}

export type ErrorPresentation =
  | "blocking_access_denied"
  | "inline_validation"
  | "soft_conflict_refetch"
  | "queue_item_error_refetch"
  | "switch_read_only"
  | "hide_trace_panel"
  | "retryable_error"
  | "network_retry"
  | "unknown";

export interface ErrorViewModel {
  readonly code: string;
  readonly httpStatus: number;
  readonly presentation: ErrorPresentation;
}

export interface WorkspaceViewModel {
  readonly sessionId: number;
  readonly workspaceState: string;
  readonly planEtag: string;
  readonly contractVersion: string;
  readonly pinCards: readonly CardViewModel[];
  readonly primaryCards: readonly CardViewModel[];
  readonly secondaryCards: readonly CardViewModel[];
  readonly deferredCards: readonly CardViewModel[];
  readonly queue: readonly DecisionQueueItemViewModel[];
  readonly story: StoryViewModel | null;
  readonly cognitiveBudget: CognitiveBudgetViewModel;
  readonly metadata: PlanMetadataViewModel;
  readonly mutationsAllowed: boolean;
}
