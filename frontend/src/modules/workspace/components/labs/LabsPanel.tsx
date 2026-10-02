import type { ReactNode } from "react";
import type { LabsContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { BidiText, NumericValue, UnitValue } from "@/components/ui/bidi";
import { DateValue } from "@/components/ui/bidi";
import { ClinicalValueState } from "@/components/ui/design-system";

export type LabsPanelProps = {
  content: LabsContent | null;
  trust?: ReactNode;
  className?: string;
};

export function LabsPanel({ content, trust, className }: LabsPanelProps) {
  if (content == null || content.rows.length === 0) {
    return (
      <CardChrome className={className} title="Labs" trust={trust} aria-label="Labs">
        <EmptyState state="unavailable" title="نتیجه آزمایش در دسترس نیست" message="نبود نتیجه به معنی طبیعی بودن آزمایش نیست." />
      </CardChrome>
    );
  }

  return (
    <CardChrome className={className} title="Labs" trust={trust} aria-label="Labs">
      <div className="overflow-x-auto rounded-tai-md border border-tai-border" aria-label="Laboratory results"><table className="w-full min-w-[760px] border-collapse text-start text-xs"><thead className="bg-tai-surface text-tai-subdued"><tr><th className="px-3 py-2 text-start">آزمایش</th><th className="px-3 py-2 text-start">نتیجه</th><th className="px-3 py-2 text-start">واحد</th><th className="px-3 py-2 text-start">محدوده مرجع</th><th className="px-3 py-2 text-start">زمان</th><th className="px-3 py-2 text-start">منبع</th><th className="px-3 py-2 text-start">وضعیت</th></tr></thead><tbody className="divide-y divide-tai-border">{content.rows.map((row) => { const highlighted = row.state === "abnormal" || row.state === "critical"; return <tr key={row.id} className={highlighted ? "bg-[hsl(var(--tai-critical-surface))]" : undefined}><th scope="row" className={highlighted ? "px-3 py-2 text-start font-semibold text-danger" : "px-3 py-2 text-start font-semibold text-tai-text"}><BidiText className={highlighted ? "text-danger" : undefined}>{row.name}</BidiText>{row.detail ? <BidiText className="mt-0.5 block text-[11px] font-normal text-tai-subdued">{row.detail}</BidiText> : null}</th><td className="px-3 py-2 font-bold">{row.value ? <NumericValue>{row.value}</NumericValue> : <ClinicalValueState state="unknown" />}</td><td className="px-3 py-2">{row.unit ? <UnitValue>{row.unit}</UnitValue> : <ClinicalValueState state="unknown" />}</td><td className="px-3 py-2">{row.referenceRange ? <NumericValue>{row.referenceRange}</NumericValue> : <ClinicalValueState state="unavailable" />}</td><td className="px-3 py-2">{row.timestamp ? <DateValue>{row.timestamp}</DateValue> : <ClinicalValueState state="unavailable" />}</td><td className="px-3 py-2">{row.source ? <BidiText>{row.source}</BidiText> : <ClinicalValueState state="unavailable" />}</td><td className="px-3 py-2"><ClinicalValueState state={row.state === "critical" || row.state === "abnormal" ? "abnormal" : row.state === "normal" ? "normal" : "unknown"} label={row.state === "critical" ? "بحرانی" : undefined} /></td></tr>; })}</tbody></table></div>
    </CardChrome>
  );
}
