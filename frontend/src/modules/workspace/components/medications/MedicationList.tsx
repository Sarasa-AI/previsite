import type { ReactNode } from "react";
import type { MedicationsContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { SourceIndicator } from "../shared/SourceIndicator";
import { StatusChip } from "../shared/StatusChip";
import { BidiText, DoseValue } from "@/components/ui/bidi";
import { ClinicalValueState } from "@/components/ui/design-system";

function Field({ label, value, numeric = false }: { label: string; value?: string | null; numeric?: boolean }) {
  const Value = numeric ? DoseValue : BidiText;
  return <div className="min-w-0"><dt className="text-[11px] text-tai-subdued">{label}</dt><dd className="mt-0.5 text-xs font-medium text-tai-text">{value?.trim() ? <Value>{value}</Value> : <ClinicalValueState state="unknown" />}</dd></div>;
}

export type MedicationListProps = {
  content: MedicationsContent | null;
  trust?: ReactNode;
  className?: string;
};

export function MedicationList({ content, trust, className }: MedicationListProps) {
  if (content == null || content.groups.length === 0) {
    return (
      <CardChrome className={className} title="Medications" trust={trust} aria-label="Medications">
        <EmptyState state="unavailable" title="دارویی در دسترس نیست" message="نبود فهرست دارو به معنی مصرف نکردن دارو نیست." />
      </CardChrome>
    );
  }

  return (
    <CardChrome className={className} title="Medications" trust={trust} aria-label="Medications">
      <div className="space-y-4" aria-label="Medication groups">
        {content.groups.map((group) => <section key={group.label} aria-label={group.label}><h3 className="mb-2 text-xs font-semibold text-tai-navy"><BidiText>{group.label}</BidiText></h3><ul className="divide-y divide-tai-border rounded-tai-md border border-tai-border">{group.items.map((item) => <li key={item.id} className="p-3"><div className="flex flex-wrap items-start justify-between gap-2"><BidiText className="text-sm font-bold text-tai-text">{item.name}</BidiText><StatusChip status={item.status} /></div><dl className="mt-2 grid grid-cols-2 gap-x-3 gap-y-2 sm:grid-cols-4"><Field label="دوز" value={item.dose} numeric /><Field label="راه مصرف" value={item.route} /><Field label="دفعات" value={item.frequency} /><Field label="شکل دارویی" value={item.dosageForm} /></dl><div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-tai-border pt-2 text-xs"><SourceIndicator source={item.source} />{item.verificationStatus ? <span aria-label={`Verification ${item.verificationStatus}`}>تایید: <BidiText>{item.verificationStatus}</BidiText></span> : <ClinicalValueState state="unknown" label="تایید: نامشخص" />}{item.confidence != null ? <span aria-label={`Confidence ${Math.round(item.confidence * 100)}%`}>اطمینان: {Math.round(item.confidence * 100)}٪</span> : <ClinicalValueState state="unknown" label="اطمینان: نامشخص" />}</div></li>)}</ul></section>)}
      </div>
    </CardChrome>
  );
}
