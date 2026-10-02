import { Badge, DateValue, NumericValue } from "@/components/ui";
import type { ClinicalContentViewModel } from "../types";
import type { WorkspaceViewModel } from "../../presentation/viewmodels/types";
import { PatientHeader } from "../layout/PatientHeader";

export function WorkspaceHeader({ viewModel, clinicalContent }: { viewModel: WorkspaceViewModel; clinicalContent: ClinicalContentViewModel | null }) {
  return (
    <section id="workspace-patient" aria-labelledby="workspace-title" className="space-y-2 scroll-mt-3">
      <div className="flex flex-col gap-1.5 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-[11px] font-bold uppercase text-tai-teal">TreatAI Clinical Workspace</p>
          <h1 id="workspace-title" className="text-lg font-bold text-tai-navy sm:text-xl">میزکار پزشک</h1>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-1.5 text-xs text-tai-subdued md:justify-end" aria-label="Encounter context">
          <Badge>جلسه <NumericValue>{viewModel.sessionId}</NumericValue></Badge>
          <Badge>{viewModel.metadata.lens}</Badge>
          <Badge>{viewModel.metadata.role}</Badge>
          <span className="hidden lg:inline">به‌روزرسانی <DateValue>{viewModel.metadata.computedAt}</DateValue></span>
        </div>
      </div>
      <PatientHeader
        content={clinicalContent?.patientHeader ?? null}
        encounter={{
          visitDate: viewModel.metadata.computedAt,
          lastUpdated: viewModel.metadata.generatedAt,
        }}
      />
    </section>
  );
}
