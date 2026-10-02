/**
 * Frontend telemetry channel for workspace presentation events.
 * Stub implementation — no PHI; structural only.
 */

export type WorkspaceTelemetryEvent =
  | "workspace.unknown_object_id"
  | "workspace.unknown_enum"
  | "workspace.etag_mismatch"
  | "workspace.unsupported_contract";

export type WorkspaceTelemetryPayload = {
  object_id?: string;
  session_id?: number | string;
  plan_etag?: string;
  contract_version?: string;
  field?: string;
  value?: string;
  [key: string]: unknown;
};

const listeners: Array<(event: WorkspaceTelemetryEvent, payload: WorkspaceTelemetryPayload) => void> =
  [];

export function onWorkspaceTelemetry(
  listener: (event: WorkspaceTelemetryEvent, payload: WorkspaceTelemetryPayload) => void,
): () => void {
  listeners.push(listener);
  return () => {
    const index = listeners.indexOf(listener);
    if (index >= 0) listeners.splice(index, 1);
  };
}

export function emitWorkspaceTelemetry(
  event: WorkspaceTelemetryEvent,
  payload: WorkspaceTelemetryPayload = {},
): void {
  for (const listener of listeners) {
    try {
      listener(event, payload);
    } catch {
      // Telemetry must never break rendering.
    }
  }
  if (typeof process !== "undefined" && process.env.NODE_ENV === "development") {
    // eslint-disable-next-line no-console
    console.debug(`[workspace.telemetry] ${event}`, payload);
  }
}
