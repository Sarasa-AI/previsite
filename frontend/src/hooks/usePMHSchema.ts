"use client";

import { useQuery } from "@tanstack/react-query";
import { frontendApi } from "@/lib/client";
import type { PMHSchema } from "@/lib/pmh/types";

export const pmhSchemaQueryKey = ["pmh", "schema"] as const;

export function usePMHSchema() {
  return useQuery({
    queryKey: pmhSchemaQueryKey,
    queryFn: async () => {
      const { data } = await frontendApi.getPMHSchema();
      return data as PMHSchema;
    },
    staleTime: 60 * 60 * 1000,
    retry: 1,
  });
}
