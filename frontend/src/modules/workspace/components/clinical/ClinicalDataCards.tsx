import type { ReactNode } from "react";
import { AlertTriangle, ClipboardList, ShieldAlert } from "lucide-react";
import { BidiText } from "@/components/ui/bidi";
import { ClinicalValueState } from "@/components/ui/design-system";
import type { SnapshotStripContent } from "../types";
import { CardChrome } from "../shared/CardChrome";

type SnapshotCardProps = {
  content: SnapshotStripContent | null;
  trust?: ReactNode;
};

function Unavailable({ children = "در قرارداد فعلی موجود نیست" }: { children?: ReactNode }) {
  return <ClinicalValueState state="unavailable" label={children} />;
}

export function ProblemsCard({ content, trust }: SnapshotCardProps) {
  const value = content?.problems.trim();
  return (
    <CardChrome title="مشکلات بالینی" subtitle="Problems" trust={trust} aria-label="Problems">
      {value ? (
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_9rem]">
          <div className="min-w-0 border-s-4 border-tai-navy ps-3">
            <div className="mb-1 flex items-center gap-2 text-xs font-semibold text-tai-subdued">
              <ClipboardList className="size-4" aria-hidden="true" /> نام مشکل / خلاصه ثبت‌شده
            </div>
            <BidiText className="block text-sm font-semibold text-tai-text">{value}</BidiText>
            <div className="mt-2 text-xs text-tai-subdued">
              داده پشتیبان: <Unavailable />
            </div>
          </div>
          <div className="border-t border-tai-border pt-2 sm:border-s sm:border-t-0 sm:ps-3 sm:pt-0">
            <div className="text-xs text-tai-subdued">وضعیت</div>
            <div className="mt-1"><ClinicalValueState state="unknown" /></div>
          </div>
        </div>
      ) : (
        <div role="status" aria-live="polite" data-semantic-state="missing" className="flex items-start gap-2 rounded-tai-md border border-tai-border bg-tai-surface p-3">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-semantic-missing" aria-hidden="true" />
          <div><p className="text-sm font-semibold text-tai-text">اطلاعات مشکلات در دسترس نیست</p><p className="mt-1 text-xs text-tai-subdued">نبود داده به معنی نبود مشکل یا وضعیت طبیعی نیست.</p></div>
        </div>
      )}
    </CardChrome>
  );
}

export type AllergySemanticState = "confirmed" | "nkda" | "unknown" | "missing" | "conflict";

export function AllergiesCard({ content, trust, state }: SnapshotCardProps & { state?: AllergySemanticState }) {
  const value = content?.allergies.trim();
  const effectiveState: AllergySemanticState = state ?? (value ? "unknown" : "missing");
  const labels: Record<AllergySemanticState, string> = {
    confirmed: "حساسیت تاییدشده",
    nkda: "NKDA ثبت‌شده",
    unknown: value ? "معنا/وضعیت نامشخص" : "نامشخص",
    missing: "مستندسازی موجود نیست",
    conflict: "تعارض حل‌نشده",
  };
  const badgeState = effectiveState === "confirmed" ? "confirmed" : effectiveState === "nkda" ? "confirmed" : effectiveState;

  return (
    <CardChrome title="حساسیت‌ها" subtitle="Allergies" trust={trust} aria-label="Allergies">
      <div className="flex flex-col items-start gap-2.5">
        <div className="min-w-0 w-full [overflow-wrap:anywhere]">
          <div className="mb-1 flex items-center gap-2 text-xs font-semibold text-tai-subdued"><ShieldAlert className="size-4" aria-hidden="true" /> مستند بالینی</div>
          {value ? <BidiText className="block text-sm font-semibold text-tai-text">{value}</BidiText> : <Unavailable>مقداری ثبت نشده است</Unavailable>}
        </div>
        <ClinicalValueState state={badgeState} label={labels[effectiveState]} announce={effectiveState === "conflict"} className="self-start" />
      </div>
      {effectiveState === "unknown" && value ? <p className="mt-3 border-t border-tai-border pt-2 text-xs text-tai-subdued">متن بدون تفسیر نمایش داده شده است؛ قرارداد فعلی نوع «حساسیت تاییدشده» یا «NKDA» را مشخص نمی‌کند.</p> : null}
      {effectiveState === "missing" ? <p className="mt-3 text-xs text-tai-subdued">نبود مستندات حساسیت، NKDA یا نتیجه منفی محسوب نمی‌شود.</p> : null}
      {effectiveState === "conflict" ? <p className="mt-3 text-xs font-medium text-semantic-critical">تعارض به صورت خودکار حل نشده است.</p> : null}
    </CardChrome>
  );
}
