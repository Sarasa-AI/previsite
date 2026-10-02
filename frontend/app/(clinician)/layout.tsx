import type { ReactNode } from "react";

/**
 * Clinician route group. Mounts `.clinician-theme`, the only scope where the
 * acuity roles resolve — and the patient semantic roles are not reachable from
 * anywhere inside this subtree.
 *
 * Desktop-first and data-dense, degrading to tablet rather than phone (§5,
 * Phase 5). Inline padding uses `px-*` (padding-inline), never physical
 * left/right utilities.
 */
export default function ClinicianLayout({ children }: { children: ReactNode }) {
  return (
    <div dir="rtl" className="clinician-theme min-h-screen w-full">
      <div className="mx-auto w-full max-w-screen-2xl px-6 py-6 xl:px-10">
        {children}
      </div>
    </div>
  );
}
