/**
 * Server-state hook for clinical content projection.
 * Fetch → map only. No clinical reasoning or multi-API composition.
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { workspaceService } from "../../application/workspaceService";
import { projectClinicalContentEnvelope, type ClinicalContentProjection } from "../mappers/projectClinicalContent";
import { clinicalContentQueryKey } from "@/src/shared/query/workspaceCache";
import { CLINICAL_CONTENT_VERSION } from "../../api/types";
import { WorkspaceApiError } from "../../api/client";

export type UseClinicalContentParams = {
  sessionId: number | string;
  /** Align cache with plan context_hash when available. */
  contextHash?: string | null;
  enabled?: boolean;
};

export function useClinicalContent({
  sessionId,
  contextHash = null,
  enabled = true,
}: UseClinicalContentParams) {
  const query = useQuery({
    queryKey: clinicalContentQueryKey({ sessionId, contextHash }),
    queryFn: async ({ signal }): Promise<ClinicalContentProjection> => {
      const response = await workspaceService.fetchClinicalContent(sessionId, signal);
      if (String(response.session_id) !== String(sessionId)) {
        throw new WorkspaceApiError("Clinical content session mismatch", 409, "CLINICAL_CONTENT_SESSION_MISMATCH");
      }
      if (response.content_version.split(".")[0] !== CLINICAL_CONTENT_VERSION.split(".")[0]) {
        throw new WorkspaceApiError("Unsupported clinical content version", 200, "UNSUPPORTED_CLINICAL_CONTENT_VERSION");
      }
      return projectClinicalContentEnvelope(response);
    },
    enabled,
    staleTime: 0,
  });

  return {
    projection: query.data ?? null,
    clinicalContent: query.data?.clinicalContent ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  };
}
