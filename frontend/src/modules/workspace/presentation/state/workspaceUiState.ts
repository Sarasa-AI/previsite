/**
 * Presentation UI state machine.
 * Transitions are observed via transport + plan snapshots — not client-driven orchestration.
 * Do not invent states beyond this set.
 */

export type WorkspaceUiState =
  | "Idle"
  | "Loading"
  | "Generating"
  | "Ready"
  | "Refreshing"
  | "ReadOnly"
  | "Offline"
  | "Forbidden"
  | "NotFound"
  | "Error";

const INTERACTIVE_WIRE_STATES = new Set([
  "verified",
  "partially_verified",
  "conflict_present",
  "review_needed",
  "completed",
]);

export type WorkspaceUiInput = {
  /** True before any fetch has been initiated. */
  isIdle?: boolean;
  /** True when a successful plan body is held. */
  hasPlan: boolean;
  /** Wire workspace_state when a plan is held. */
  workspaceState?: string | null;
  /** Transport or mutation in flight while last good plan held. */
  isRefreshing?: boolean;
  /** Browser/network offline signal. */
  clientOffline?: boolean;
  /** Mapped blocking error UI state, if any. */
  errorUiState?: Extract<WorkspaceUiState, "Forbidden" | "NotFound" | "Error"> | null;
};

/**
 * Derive presentation UI state from transport + wire snapshot.
 * Wire `loading` / `generating` are never errors.
 */
export function deriveWorkspaceUiState(input: WorkspaceUiInput): WorkspaceUiState {
  if (input.errorUiState) {
    return input.errorUiState;
  }

  if (input.isIdle && !input.hasPlan) {
    return "Idle";
  }

  if (input.clientOffline) {
    return "Offline";
  }

  if (!input.hasPlan) {
    return "Loading";
  }

  const wire = input.workspaceState ?? "";

  if (wire === "offline") {
    return "Offline";
  }

  if (wire === "read_only") {
    return "ReadOnly";
  }

  if (input.isRefreshing) {
    return "Refreshing";
  }

  if (wire === "loading") {
    return "Loading";
  }

  if (wire === "generating") {
    return "Generating";
  }

  if (INTERACTIVE_WIRE_STATES.has(wire)) {
    return "Ready";
  }

  // Unknown wire state: render as Ready-like interactive chrome without inventing modes.
  // Caller may show a non-blocking banner via telemetry elsewhere.
  return "Ready";
}

export function isMutationsAllowedUiState(state: WorkspaceUiState): boolean {
  return state === "Ready" || state === "Generating" || state === "Refreshing";
}
