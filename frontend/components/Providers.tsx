"use client";

import { useEffect, type ReactNode } from "react";
import { QueryClientProvider } from "@tanstack/react-query";
import { queryClient } from "@/lib/queryClient";
import { initClientSentry } from "@/lib/sentry";

export default function Providers({ children }: { children: ReactNode }) {
  useEffect(() => {
    initClientSentry();
  }, []);

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
