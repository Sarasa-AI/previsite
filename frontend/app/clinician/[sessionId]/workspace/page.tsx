"use client";

import ProtectedRoute from "@/components/ProtectedRoute";
import { WorkspaceRoute } from "@/src/modules/workspace/routes/WorkspaceRoute";

export default function ClinicianWorkspacePage({
  params,
}: {
  params: { sessionId: string };
}) {
  return (
    <ProtectedRoute>
      <WorkspaceRoute sessionId={params.sessionId} />
    </ProtectedRoute>
  );
}
