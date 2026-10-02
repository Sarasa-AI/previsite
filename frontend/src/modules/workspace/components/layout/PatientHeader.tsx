import type { ReactNode } from "react";
import { CalendarDays, Clock3, IdCard, Stethoscope, UserRound } from "lucide-react";
import { BidiText, DateValue, MrnValue, NumericValue } from "@/components/ui";
import type { PatientHeaderContent } from "../types";
import { StatusChip } from "../shared/StatusChip";

export type PatientHeaderProps = {
  content: PatientHeaderContent | null;
  /** Trust chrome — never embedded in content ViewModel. */
  trust?: ReactNode;
  encounter?: {
    readonly visitDate?: string | null;
    readonly lastUpdated?: string | null;
  };
  className?: string;
};

function ContextItem({ icon, label, children }: { icon: ReactNode; label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 items-start gap-2">
      <span className="mt-0.5 text-tai-teal" aria-hidden="true">{icon}</span>
      <span className="min-w-0">
        <span className="block text-[11px] font-medium text-tai-subdued">{label}</span>
        <span className="block truncate text-sm font-semibold text-tai-text">{children}</span>
      </span>
    </div>
  );
}

export function PatientHeader({ content, trust, encounter, className }: PatientHeaderProps) {
  if (content == null) {
    return (
      <section className={`rounded-tai-lg border border-semantic-missing/30 bg-[hsl(var(--tai-missing-surface))] p-4 ${className ?? ""}`} aria-label="Patient header" role="status">
        <p className="font-semibold text-tai-navy">اطلاعات بیمار</p>
        <p className="mt-1 text-sm text-semantic-missing">مشخصات جمعیت‌شناختی بیمار در دسترس نیست.</p>
      </section>
    );
  }

  return (
    <section className={`overflow-hidden rounded-tai-lg border border-tai-border bg-white shadow-tai-sm ${className ?? ""}`} aria-label="Patient header">
      <div className="h-0.5 bg-tai-teal-bright" />
      <div className="grid gap-3 p-3 lg:grid-cols-[minmax(15rem,1.05fr)_minmax(0,2fr)] lg:items-center 2xl:p-3.5">
        <div className="flex min-w-0 items-center gap-3">
          <span className="grid size-10 shrink-0 place-items-center rounded-tai-md bg-tai-navy text-white shadow-sm" aria-hidden="true"><UserRound className="size-5" /></span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="truncate text-lg font-bold text-tai-navy"><BidiText>{content.name}</BidiText></h2>
              <StatusChip status={content.status} />
            </div>
            <p className="mt-1 inline-flex items-center gap-1 text-sm text-tai-subdued"><NumericValue>{content.age}</NumericValue><span>سال ·</span><BidiText>{content.sex}</BidiText></p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-x-3 gap-y-2 border-t border-tai-border pt-3 sm:grid-cols-4 lg:border-s lg:border-t-0 lg:ps-3 lg:pt-0 2xl:gap-x-4 2xl:ps-4">
          <ContextItem icon={<IdCard className="size-4" />} label="شناسه بیمار"><span className="sr-only">{`MRN ${content.mrn}`}</span><MrnValue>{content.mrn}</MrnValue></ContextItem>
          <ContextItem icon={<Stethoscope className="size-4" />} label="نوع مراجعه"><BidiText>{content.visitType}</BidiText></ContextItem>
          <ContextItem icon={<CalendarDays className="size-4" />} label="تاریخ مراجعه">{encounter?.visitDate ? <DateValue>{encounter.visitDate}</DateValue> : <span className="text-semantic-unknown">نامشخص</span>}</ContextItem>
          <ContextItem icon={<Clock3 className="size-4" />} label="آخرین به‌روزرسانی">{encounter?.lastUpdated ? <DateValue>{encounter.lastUpdated}</DateValue> : <span className="text-semantic-unknown">نامشخص</span>}</ContextItem>
        </div>
      </div>
      {trust ? <div className="border-t border-tai-border px-4 py-2">{trust}</div> : null}
    </section>
  );
}
