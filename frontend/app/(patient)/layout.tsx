import type { ReactNode } from "react";

/**
 * Patient route group. Mounts `.patient-theme`, which is the only scope where
 * the patient semantic roles resolve; no clinician acuity role is reachable
 * from anywhere inside this subtree.
 *
 * Mobile-first: one column, sized for a 360px floor and capped so the measure
 * stays readable on a tablet. Inline padding uses `px-*` (padding-inline),
 * which is direction-agnostic — no physical left/right utilities anywhere.
 */
export default function PatientLayout({ children }: { children: ReactNode }) {
  return (
    <div dir="rtl" className="patient-theme min-h-screen w-full">
      <div className="mx-auto w-full max-w-screen-sm px-4 pb-16 pt-6 sm:px-6">
        {children}
      </div>
    </div>
  );
}
