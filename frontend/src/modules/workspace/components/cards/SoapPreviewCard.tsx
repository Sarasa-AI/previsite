"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import { CheckCircle2, Edit3, Eye, RotateCcw, ShieldCheck } from "lucide-react";
import { BidiText } from "@/components/ui/bidi";
import { Button, ClinicalValueState, StatusBadge } from "@/components/ui";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { TrustViewModel } from "../../presentation/viewmodels/types";
import type { SoapContent } from "../types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { ErrorState } from "../shared/ErrorState";
import { ProvenanceDisclosure } from "../shared/ProvenanceDisclosure";

export type SoapPreviewCardProps = {
  content: SoapContent | null;
  trust?: ReactNode;
  provenance?: TrustViewModel;
  state?: "ready" | "loading" | "error" | "unavailable" | "stale";
  confirmed?: boolean;
  onConfirm?: (content: SoapContent) => void;
  defaultExpanded?: boolean;
  className?: string;
};

function SoapSection({ title, value, editing, onChange, unavailable = false }: { title: string; value: string; editing: boolean; onChange?: (value: string) => void; unavailable?: boolean }) {
  return <section className="grid gap-1 sm:grid-cols-[5.5rem_minmax(0,1fr)] sm:gap-3" aria-label={title}><h3 className="text-sm font-bold leading-7 text-tai-navy">{title}:</h3>{unavailable ? <p data-semantic-state="missing" className="text-sm leading-7 text-tai-subdued">در قرارداد فعلی موجود نیست.</p> : editing ? <textarea value={value} onChange={(event) => onChange?.(event.target.value)} className="min-h-28 w-full resize-y rounded-tai-md border border-tai-border bg-white p-3 text-sm leading-7 text-tai-text outline-none focus-visible:ring-2 focus-visible:ring-tai-navy" dir="auto" aria-label={`Edit ${title}`} /> : value.trim() ? <BidiText className="tai-clinical-copy block text-sm leading-7 text-tai-text">{value}</BidiText> : <p data-semantic-state="missing" className="text-sm leading-7 text-tai-subdued">محتوایی ثبت نشده است.</p>}</section>;
}

export function SoapPreviewCard({
  content,
  trust,
  provenance,
  state = "ready",
  confirmed = false,
  onConfirm,
  className,
}: SoapPreviewCardProps) {
  const [mode, setMode] = useState<"view" | "review" | "edit">("view");
  const [assessment, setAssessment] = useState(content?.assessment ?? "");
  const [plan, setPlan] = useState(content?.plan ?? "");
  const [confirmOpen, setConfirmOpen] = useState(false);
  useEffect(() => { setAssessment(content?.assessment ?? ""); setPlan(content?.plan ?? ""); setMode("view"); }, [content]);
  const edited = useMemo(() => content != null && (assessment !== content.assessment || plan !== content.plan), [assessment, content, plan]);
  const currentContent = useMemo(() => ({ assessment, plan }), [assessment, plan]);

  if (state === "loading") return <CardChrome className={className} title="یادداشت SOAP" trust={trust} aria-label="SOAP draft"><div role="status" aria-busy="true" className="rounded-tai-md border border-tai-border bg-tai-surface p-4 text-sm">در حال بارگذاری یادداشت SOAP...</div></CardChrome>;
  if (state === "error") return <CardChrome className={className} title="یادداشت SOAP" trust={trust} aria-label="SOAP draft"><ErrorState title="بارگذاری یادداشت SOAP ناموفق بود" message="پیش‌نویس در حال حاضر قابل نمایش نیست." /></CardChrome>;
  if (state === "unavailable") return <CardChrome className={className} title="یادداشت SOAP" trust={trust} aria-label="SOAP draft"><EmptyState title="یادداشت SOAP در دسترس نیست" message="نبود پیش‌نویس به معنی تکمیل یا تایید مستندات نیست." /></CardChrome>;
  if (content == null) return <CardChrome className={className} title="یادداشت SOAP" trust={trust} aria-label="SOAP draft"><EmptyState title="یادداشت SOAP موجود نیست" message="هیچ محتوایی برای بازبینی یا تایید وجود ندارد." /></CardChrome>;

  return (
    <CardChrome className={className} title="یادداشت SOAP" trust={trust} aria-label="SOAP draft">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><div className="flex flex-wrap gap-1.5">{confirmed ? <ClinicalValueState state="confirmed-by-physician" announce /> : <><ClinicalValueState state="ai-generated" /><ClinicalValueState state="draft" /><StatusBadge state="warning">نیازمند بازبینی</StatusBadge></>}{mode === "review" ? <StatusBadge state="info">در حال بازبینی</StatusBadge> : null}{edited ? <ClinicalValueState state="draft" label="ویرایش‌شده؛ ذخیره نشده" announce /> : null}{state === "stale" ? <ClinicalValueState state="stale" announce /> : null}</div><div className="flex flex-wrap gap-1.5"><Button type="button" size="sm" variant={mode === "view" ? "primary" : "secondary"} onClick={() => setMode("view")}><Eye className="size-4" aria-hidden="true" />مشاهده</Button><Button type="button" size="sm" variant={mode === "review" ? "primary" : "secondary"} onClick={() => setMode("review")}><ShieldCheck className="size-4" aria-hidden="true" />بازبینی</Button><Button type="button" size="sm" variant={mode === "edit" ? "primary" : "secondary"} onClick={() => setMode("edit")} disabled={confirmed}><Edit3 className="size-4" aria-hidden="true" />ویرایش</Button></div></div>
      {confirmed ? <p className="mb-3 rounded-tai-md border border-[hsl(var(--tai-verified)/.35)] bg-[hsl(var(--tai-verified-surface))] p-3 text-xs text-[hsl(var(--tai-verified))]">این وضعیت فقط زمانی نمایش داده می‌شود که تایید صریح از قرارداد دریافت شود.</p> : <p className="mb-3 rounded-tai-md border border-[hsl(var(--tai-warning)/.35)] bg-[hsl(var(--tai-warning-surface))] p-3 text-xs text-[hsl(var(--tai-warning))]">این پیش‌نویس، نوشته یا تایید پزشک محسوب نمی‌شود. ویرایش محلی نیز به معنی تایید نیست.</p>}
      <div className="space-y-2.5" dir="rtl"><SoapSection title="شرح حال" value="" editing={false} unavailable /><SoapSection title="یافته‌ها" value="" editing={false} unavailable /><SoapSection title="ارزیابی" value={assessment} editing={mode === "edit"} onChange={setAssessment} /><SoapSection title="برنامه" value={plan} editing={mode === "edit"} onChange={setPlan} /></div>
      {mode === "edit" ? <div className="mt-3 flex flex-wrap items-center gap-2"><Button type="button" size="sm" variant="secondary" onClick={() => { setAssessment(content.assessment); setPlan(content.plan); }} disabled={!edited}><RotateCcw className="size-4" aria-hidden="true" />بازنشانی</Button><span className="text-xs text-tai-subdued">ویرایش‌ها فقط در این نما هستند و ذخیره نمی‌شوند.</span></div> : null}
      <ProvenanceDisclosure trust={provenance} scopeLabel="SOAP draft" />
      <div className="mt-3 border-t border-tai-border pt-3"><Button type="button" variant="primary" onClick={() => setConfirmOpen(true)} disabled={confirmed || !onConfirm || edited} title={!onConfirm ? "قرارداد فعلی عملیات تایید SOAP ندارد" : edited ? "ابتدا ویرایش‌ها باید از طریق قرارداد ذخیره شوند" : undefined} aria-label="Confirm SOAP"><CheckCircle2 className="size-4" aria-hidden="true" />{confirmed ? "تایید شده" : "تایید پزشک"}</Button>{!onConfirm ? <p data-semantic-state="unavailable" className="mt-2 text-xs text-tai-subdued">تایید در قرارداد فعلی پشتیبانی نمی‌شود؛ هیچ وضعیت تاییدی در رابط کاربری ایجاد نشده است.</p> : null}</div>
      <Dialog open={confirmOpen} onOpenChange={setConfirmOpen}><DialogContent dir="rtl"><DialogHeader><DialogTitle>تایید صریح SOAP</DialogTitle><DialogDescription>این اقدام پیش‌نویس را به عنوان محتوای تاییدشده توسط پزشک ثبت می‌کند. قبل از ادامه، Assessment و Plan را بازبینی کنید.</DialogDescription></DialogHeader><div className="rounded-tai-md border border-[hsl(var(--tai-warning)/.35)] bg-[hsl(var(--tai-warning-surface))] p-3 text-sm">ویرایش به تنهایی تایید نیست. تایید فقط پس از انتخاب دکمه نهایی انجام می‌شود.</div><DialogFooter><Button type="button" variant="secondary" onClick={() => setConfirmOpen(false)}>انصراف</Button><Button type="button" onClick={() => { onConfirm?.(currentContent); setConfirmOpen(false); }} aria-label="Explicitly confirm SOAP">تایید نهایی پزشک</Button></DialogFooter></DialogContent></Dialog>
    </CardChrome>
  );
}
