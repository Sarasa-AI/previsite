"use client";

import { useQuery } from "@tanstack/react-query";
import { frontendApi } from "@/lib/client";

export type PatientProfile = {
  first_name?: string | null;
  last_name?: string | null;
  national_id?: string | null;
  age?: number | null;
  sex?: string | null;
  weight?: number | null;
  height?: number | null;
  is_complete: boolean;
};

export const patientProfileQueryKey = ["patient", "profile"] as const;

export function usePatientProfile() {
  return useQuery({
    queryKey: patientProfileQueryKey,
    queryFn: async () => {
      const { data } = await frontendApi.getPatientProfile();
      return data as PatientProfile;
    },
    staleTime: 60_000,
    retry: 1,
  });
}
