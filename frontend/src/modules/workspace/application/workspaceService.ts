/**
 * Thin workspace application service.
 * Calls the typed client only — no clinical logic, no ViewModel construction.
 */

import {
  acknowledgeWorkspaceObject,
  dismissWorkspaceObject,
  getClinicalContent,
  getStoryStatus,
  getWorkspace,
  getWorkspaceTrace,
  refreshWorkspaceStory,
  resolveWorkspaceObject,
  type GetWorkspaceOptions,
} from "../api/client";
import type {
  AcknowledgementRequest,
  WorkspaceQueryParams,
} from "../api/types";

export const workspaceService = {
  fetchPlan(
    sessionId: number | string,
    params?: WorkspaceQueryParams,
    options?: GetWorkspaceOptions,
  ) {
    return getWorkspace(sessionId, params, options);
  },

  fetchTrace(sessionId: number | string, params?: WorkspaceQueryParams) {
    return getWorkspaceTrace(sessionId, params);
  },

  fetchClinicalContent(sessionId: number | string, signal?: AbortSignal) {
    return getClinicalContent(sessionId, { signal });
  },

  acknowledge(
    sessionId: number | string,
    body: AcknowledgementRequest,
    ifMatch: string,
  ) {
    return acknowledgeWorkspaceObject(sessionId, body, ifMatch);
  },

  refreshStory(sessionId: number | string, ifMatch: string) {
    return refreshWorkspaceStory(sessionId, ifMatch);
  },

  resolve(sessionId: number | string, objectId: string, ifMatch: string) {
    return resolveWorkspaceObject(sessionId, objectId, ifMatch);
  },

  dismiss(sessionId: number | string, objectId: string, ifMatch: string) {
    return dismissWorkspaceObject(sessionId, objectId, ifMatch);
  },

  fetchStoryStatus(sessionId: number | string, signal?: AbortSignal) {
    return getStoryStatus(sessionId, { signal });
  },
};
