/**
 * Server-state hook for clinical content projection.
 * Fetch → map only. No clinical reasoning or multi-API composition.
 */

"use client";

import { useQuery } from "@tanstack/react-query";
import { workspaceService } from "../../application/workspaceService";
import { projectClinicalContent } from "../mappers/projectClinicalContent";
import type { ClinicalContentViewModel } from "../../components/types";
import { clinicalContentQueryKey } from "@/src/shared/query/workspaceCache";

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
    queryFn: async ({ signal }): Promise<ClinicalContentViewModel> => {
      const response = await workspaceService.fetchClinicalContent(sessionId, signal);
      return projectClinicalContent(response);
    },
    enabled,
    staleTime: 0,
  });

  return {
    clinicalContent: query.data ?? null,
    isLoading: query.isLoading,
    isFetching: query.isFetching,
    error: query.error,
    refetch: query.refetch,
  };
}
