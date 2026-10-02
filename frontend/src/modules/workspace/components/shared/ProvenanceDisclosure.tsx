import { ChevronDown, Fingerprint } from "lucide-react";
import { BidiText, DateValue } from "@/components/ui/bidi";
import { StatusBadge } from "@/components/ui/design-system";
import type { TrustViewModel } from "../../presentation/viewmodels/types";

export type ProvenanceDisclosureProps = {
  trust?: TrustViewModel;
  source?: string | null;
  timestamp?: string | null;
  confidence?: number | "unknown" | null;
  evidenceRefs?: readonly string[];
  scopeLabel?: string;
};

export function ProvenanceDisclosure({ trust, source, timestamp, confidence, evidenceRefs, scopeLabel = "این مورد" }: ProvenanceDisclosureProps) {
  const resolvedSource = source?.trim() || trust?.primaryProvenance || null;
  const resolvedConfidence = confidence ?? trust?.confidence ?? "unknown";
  const refs = evidenceRefs ?? trust?.evidenceRefs ?? [];
  const verification = trust?.verification?.trim() || null;
  const verified = verification?.toLowerCase() === "verified";

  return (
    <details className="group mt-2 border-t border-tai-border pt-2">
      <summary className="flex cursor-pointer list-none items-center gap-2 text-xs font-semibold text-tai-navy marker:content-none focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tai-navy [&::-webkit-details-marker]:hidden">
        <Fingerprint className="size-3.5" aria-hidden="true" />
        منشأ و شواهد
        <ChevronDown className="ms-auto size-3.5 transition-transform group-open:rotate-180 motion-reduce:transition-none" aria-hidden="true" />
      </summary>
      <dl className="mt-2 grid gap-2 rounded-tai-md bg-tai-surface p-3 text-xs sm:grid-cols-2" aria-label={`Provenance for ${scopeLabel}`}>
        <div><dt className="text-tai-subdued">منبع</dt><dd className="mt-0.5 font-medium">{resolvedSource ? <BidiText>{resolvedSource}</BidiText> : <span data-semantic-state="missing">موجود نیست</span>}</dd></div>
        <div><dt className="text-tai-subdued">زمان</dt><dd className="mt-0.5 font-medium">{timestamp ? <DateValue>{timestamp}</DateValue> : <span data-semantic-state="unknown">نامشخص</span>}</dd></div>
        <div><dt className="text-tai-subdued">وضعیت تایید</dt><dd className="mt-0.5"><StatusBadge state={verified ? "verified" : "unverified"}>{verification || "تایید نشده"}</StatusBadge></dd></div>
        <div><dt className="text-tai-subdued">اطمینان</dt><dd className="mt-0.5 font-medium">{typeof resolvedConfidence === "number" ? `${Math.round(resolvedConfidence * 100)}٪` : <span data-semantic-state="unknown">نامشخص</span>}</dd></div>
        <div className="sm:col-span-2"><dt className="text-tai-subdued">ارجاع شواهد</dt><dd className="mt-1 flex flex-wrap gap-1">{refs.length ? refs.map((ref) => <code key={ref} dir="ltr" className="rounded-tai-sm border border-tai-border bg-white px-1.5 py-0.5 text-[11px]">{ref}</code>) : <span data-semantic-state="missing">ارجاعی موجود نیست</span>}</dd></div>
      </dl>
    </details>
  );
}
