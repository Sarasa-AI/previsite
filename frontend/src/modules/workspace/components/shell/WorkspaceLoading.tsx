import { StatePanel } from "@/components/ui";
import { ChiefComplaintSkeleton, DocumentsSkeleton, LabsPanelSkeleton, MedicationListSkeleton, PatientHeaderSkeleton, RedFlagsSkeleton, SnapshotStripSkeleton, SoapSkeleton, TimelineSkeleton } from "../skeletons";

export function WorkspaceLoading() {
  return <main aria-label="Doctor workspace" className="mx-auto w-full max-w-screen-2xl px-3 py-4 sm:px-4 lg:px-6"><div data-workspace-chrome="loading" className="space-y-3" role="status" aria-busy="true" aria-label="Loading doctor workspace"><StatePanel kind="loading" title="در حال آماده‌سازی میزکار پزشک" message="اطلاعات پرونده و برنامه نمایش در حال بارگذاری است." /><PatientHeaderSkeleton /><div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4"><ChiefComplaintSkeleton /><RedFlagsSkeleton /><ChiefComplaintSkeleton /><RedFlagsSkeleton /></div><SnapshotStripSkeleton /><SoapSkeleton /><div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3"><TimelineSkeleton /><LabsPanelSkeleton /><MedicationListSkeleton /><DocumentsSkeleton /></div></div></main>;
}
