import { SkeletonBone, SkeletonFrame } from "./SkeletonBone";

export function PatientHeaderSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonFrame className={className} aria-label="Loading patient header">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0 flex-1 space-y-2">
          <SkeletonBone className="h-4 w-40" />
          <SkeletonBone className="h-3 w-64" />
        </div>
        <SkeletonBone className="h-5 w-16" />
      </div>
    </SkeletonFrame>
  );
}

export function SnapshotStripSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonFrame className={className} aria-label="Loading clinical snapshot">
      <SkeletonBone className="mb-2 h-4 w-36" />
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="space-y-1 rounded-md border border-trust/10 p-2">
            <SkeletonBone className="h-3 w-12" />
            <SkeletonBone className="h-4 w-20" />
          </div>
        ))}
      </div>
    </SkeletonFrame>
  );
}

export function ChiefComplaintSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonFrame className={className} aria-label="Loading chief complaint">
      <div className="mb-2 flex items-center justify-between gap-2">
        <SkeletonBone className="h-4 w-32" />
        <SkeletonBone className="h-5 w-10" />
      </div>
      <SkeletonBone className="h-4 w-3/4 max-w-xs" />
    </SkeletonFrame>
  );
}

export function RedFlagsSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonFrame className={className} aria-label="Loading red flags">
      <SkeletonBone className="mb-2 h-4 w-24" />
      <div className="space-y-2">
        <SkeletonBone className="h-8 w-full" />
        <SkeletonBone className="h-8 w-full" />
      </div>
    </SkeletonFrame>
  );
}

export function TimelineSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonFrame className={className} aria-label="Loading timeline">
      <SkeletonBone className="mb-2 h-4 w-20" />
      <SkeletonBone className="mb-1 h-3 w-24" />
      <div className="space-y-2">
        <SkeletonBone className="h-8 w-full" />
        <SkeletonBone className="h-8 w-5/6" />
      </div>
    </SkeletonFrame>
  );
}

export function MedicationListSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonFrame className={className} aria-label="Loading medications">
      <SkeletonBone className="mb-2 h-4 w-28" />
      <SkeletonBone className="mb-1 h-3 w-20" />
      <div className="space-y-2">
        <SkeletonBone className="h-10 w-full" />
        <SkeletonBone className="h-10 w-full" />
      </div>
    </SkeletonFrame>
  );
}

export function LabsPanelSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonFrame className={className} aria-label="Loading labs">
      <SkeletonBone className="mb-2 h-4 w-16" />
      <div className="space-y-2">
        <SkeletonBone className="h-8 w-full" />
        <SkeletonBone className="h-8 w-full" />
        <SkeletonBone className="h-8 w-full" />
      </div>
    </SkeletonFrame>
  );
}

export function MissingInfoSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonFrame className={className} aria-label="Loading missing information">
      <div className="mb-2 flex items-center justify-between gap-2">
        <SkeletonBone className="h-4 w-36" />
        <SkeletonBone className="h-6 w-24" />
      </div>
      <div className="space-y-2">
        <SkeletonBone className="h-8 w-full" />
        <SkeletonBone className="h-8 w-full" />
      </div>
    </SkeletonFrame>
  );
}

export function SoapSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonFrame className={className} aria-label="Loading SOAP preview">
      <SkeletonBone className="mb-2 h-4 w-28" />
      <div className="space-y-2">
        <SkeletonBone className="h-8 w-full" />
        <SkeletonBone className="h-8 w-full" />
      </div>
    </SkeletonFrame>
  );
}

export function DocumentsSkeleton({ className }: { className?: string }) {
  return (
    <SkeletonFrame className={className} aria-label="Loading source documents">
      <SkeletonBone className="mb-2 h-4 w-36" />
      <div className="space-y-2">
        <SkeletonBone className="h-10 w-full" />
        <SkeletonBone className="h-10 w-full" />
      </div>
    </SkeletonFrame>
  );
}
