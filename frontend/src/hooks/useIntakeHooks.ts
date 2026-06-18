"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { frontendApi } from "../../lib/client";
import type { Demographics, IntakeData } from "../../lib/intake";
import { queryClient as globalQueryClient } from "../../lib/queryClient";

// Query key factory for intake data
export const intakeQueryKeys = {
  all: ["intake"] as const,
  detail: (sessionId: string) => [...intakeQueryKeys.all, sessionId] as const,
};

export function useGetIntake(sessionId: string) {
  return useQuery({
    queryKey: intakeQueryKeys.detail(sessionId),
    queryFn: async () => {
      const { data } = await frontendApi.getIntake(sessionId);
      return data as IntakeData;
    },
    enabled: !!sessionId,
  });
}

export function useSaveLayer1(sessionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (demographics: Demographics) => {
      const { data } = await frontendApi.saveLayer1(sessionId, demographics);
      return data;
    },
    onSuccess: async () => {
      // Invalidate and refetch intake data
      await queryClient.invalidateQueries({
        queryKey: intakeQueryKeys.detail(sessionId),
      });
      // Chain generateLayer2 automatically
      await frontendApi.generateLayer2(sessionId);
      await queryClient.invalidateQueries({
        queryKey: intakeQueryKeys.detail(sessionId),
      });
    },
  });
}

export function useGenerateLayer2(sessionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const { data } = await frontendApi.generateLayer2(sessionId);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: intakeQueryKeys.detail(sessionId),
      });
    },
  });
}

export function useSaveLayer2Answer(sessionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: { question_id: string; answer: string }) => {
      const { data } = await frontendApi.saveLayer2Answer(sessionId, payload);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: intakeQueryKeys.detail(sessionId),
      });
    },
  });
}

export function useGenerateLayer3(sessionId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async () => {
      const { data } = await frontendApi.generateLayer3(sessionId);
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: intakeQueryKeys.detail(sessionId),
      });
    },
  });
}
