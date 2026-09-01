"use client";

import { useState, type ReactNode } from "react";
import { Eye, FileText } from "lucide-react";
import { BidiText, DateValue } from "@/components/ui/bidi";
import { Button, StatusBadge } from "@/components/ui/design-system";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import type { DocumentsContent } from "../types";
import type { TrustViewModel } from "../../presentation/viewmodels/types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { ProvenanceDisclosure } from "../shared/ProvenanceDisclosure";
import { ErrorState } from "../shared/ErrorState";

export type SourceDocumentsCardProps = {
  content: DocumentsContent | null;
  trust?: ReactNode;
  provenance?: TrustViewModel;
  state?: "ready" | "loading" | "error" | "unavailable";
  className?: string;
};

function confidenceLabel(confidence: number | "unknown"): string {
  if (confidence === "unknown") return "نامشخص";
  return `${Math.round(confidence * 100)}٪`;
}

function documentType(name: string): string | null {
  const extension = name.match(/\.([a-z0-9]+)$/i)?.[1];
  return extension ? extension.toUpperCase() : null;
}

export function SourceDocumentsCard({ content, trust, provenance, state = "ready", className }: SourceDocumentsCardProps) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = content?.items.find((item) => item.id === selectedId) ?? null;
  if (state === "loading") return <CardChrome className={className} title="اسناد منبع" trust={trust} aria-label="Source documents"><div role="status" aria-busy="true" className="rounded-tai-md border border-tai-border bg-tai-surface p-4 text-sm">در حال بارگذاری اسناد...</div></CardChrome>;
  if (state === "error") return <CardChrome className={className} title="اسناد منبع" trust={trust} aria-label="Source documents"><ErrorState title="بارگذاری اسناد ناموفق بود" message="اطلاعات سند در حال حاضر قابل نمایش نیست." /></CardChrome>;
  if (state === "unavailable") return <CardChrome className={className} title="اسناد منبع" trust={trust} aria-label="Source documents"><EmptyState title="اسناد در دسترس نیست" message="این وضعیت به معنی نبود سند در پرونده اصلی نیست." /></CardChrome>;
  if (content == null || content.items.length === 0) {
    return (
      <CardChrome
        className={className}
        title="اسناد منبع"
        subtitle="Source Documents"
        trust={trust}
        aria-label="Source documents"
      >
        <EmptyState title="سندی ثبت نشده است" message="نبود سند ثبت‌شده به معنی نبود مدرک بالینی نیست." />
      </CardChrome>
    );
  }

  return (
    <CardChrome
      className={className}
      title="اسناد منبع"
      subtitle="Source Documents"
      trust={trust}
      aria-label="Source documents"
    >
      <ul className="divide-y divide-tai-border rounded-tai-md border border-tai-border">
        {content.items.map((item) => (
          <li key={item.id} className="p-3">
            <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
              <div className="flex min-w-0 items-start gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-tai-md bg-tai-surface text-tai-navy"><FileText className="size-4" aria-hidden="true" /></span>
                <div className="min-w-0">
                  <BidiText className="block break-words text-sm font-bold text-tai-text">{item.name}</BidiText>
                  <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-tai-subdued">
                    <span>نوع: {documentType(item.name) || <span data-semantic-state="unknown">نامشخص</span>}</span>
                    <span>تاریخ: <DateValue>{item.uploadedAt}</DateValue></span>
                    <span>منبع: {provenance?.primaryProvenance ? <BidiText>{provenance.primaryProvenance}</BidiText> : <span data-semantic-state="missing">موجود نیست</span>}</span>
                  </div>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge state={item.confidence === "unknown" ? "unverified" : "info"}>{item.confidence === "unknown" ? "تایید نشده" : "فراداده موجود"}</StatusBadge>
                <Button type="button" size="sm" variant="secondary" onClick={() => setSelectedId(item.id)} aria-label={`View details ${item.name}`}><Eye className="size-4" aria-hidden="true" />جزئیات</Button>
              </div>
            </div>
            <ProvenanceDisclosure trust={provenance} timestamp={item.uploadedAt} confidence={item.confidence} scopeLabel={item.name} />
          </li>
        ))}
      </ul>
      <Dialog open={selected != null} onOpenChange={(open) => { if (!open) setSelectedId(null); }}><DialogContent dir="rtl" className="max-w-2xl"><DialogHeader><DialogTitle><BidiText>{selected?.name ?? "جزئیات سند"}</BidiText></DialogTitle><DialogDescription>نمایش جزئیات موجود در قرارداد فضای کار</DialogDescription></DialogHeader>{selected ? <div className="space-y-4"><dl className="grid gap-3 rounded-tai-md border border-tai-border bg-tai-surface p-3 text-sm sm:grid-cols-2"><div><dt className="text-xs text-tai-subdued">نوع سند</dt><dd className="font-semibold">{documentType(selected.name) || "نامشخص"}</dd></div><div><dt className="text-xs text-tai-subdued">تاریخ</dt><dd><DateValue>{selected.uploadedAt}</DateValue></dd></div><div><dt className="text-xs text-tai-subdued">اطمینان</dt><dd aria-label={`Confidence ${selected.confidence === "unknown" ? "unknown" : `${Math.round(selected.confidence * 100)}%`}`}>{confidenceLabel(selected.confidence)}</dd></div><div><dt className="text-xs text-tai-subdued">وضعیت دسترسی</dt><dd><StatusBadge state="unverified">پیش‌نمایش اصل سند در دسترس نیست</StatusBadge></dd></div></dl><div><h4 className="text-xs font-semibold text-tai-subdued">جزئیات پردازش‌شده</h4>{selected.detail ? <BidiText className="mt-1 block rounded-tai-md border border-tai-border p-3 text-sm leading-7">{selected.detail}</BidiText> : <p data-semantic-state="missing" className="mt-1 text-sm text-tai-subdued">جزئیاتی موجود نیست.</p>}</div><p className="text-xs text-tai-subdued">قرارداد فعلی شناسه فایل یا نشانی قابل مشاهده ارائه نمی‌کند؛ بنابراین اصل سند از این نما باز نمی‌شود.</p></div> : null}</DialogContent></Dialog>
    </CardChrome>
  );
}
