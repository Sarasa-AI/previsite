"use client";

import { useEffect, useState } from "react";
import { AlertTriangle, Loader2, X } from "lucide-react";
import { ApiError } from "@/lib/api";
import { frontendApi } from "@/lib/client";

export type ClinicalDocumentViewerProps = {
  /** File id used for on-demand GET /api/documents/{id}/ocr */
  documentId: number;
  /** Proxied image URL (thumbnail + lightbox) */
  imageUrl: string;
  /** e.g. filename or lab name */
  documentTitle: string;
};

type OcrStatus = "idle" | "loading" | "error" | "empty" | "ready";

const PERSIAN_LETTER_RE = /[\u0600-\u06FF]/g;

function isMostlyPersian(text: string): boolean {
  const letters = text.replace(/[^\p{L}]/gu, "");
  if (!letters) return false;
  const persianCount = (letters.match(PERSIAN_LETTER_RE) ?? []).length;
  return persianCount / letters.length >= 0.5;
}

export default function ClinicalDocumentViewer({
  documentId,
  imageUrl,
  documentTitle,
}: ClinicalDocumentViewerProps) {
  const [showOcr, setShowOcr] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [ocrText, setOcrText] = useState<string | null>(null);
  const [ocrStatus, setOcrStatus] = useState<OcrStatus>("idle");

  useEffect(() => {
    if (!lightboxOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setLightboxOpen(false);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [lightboxOpen]);

  const fetchOcr = async () => {
    setOcrStatus("loading");
    setOcrText(null);
    try {
      const response = await frontendApi.getDocumentOcr(documentId);
      const text = response.data?.ocr_text?.trim() ?? "";
      if (!text) {
        setOcrStatus("empty");
        setOcrText(null);
        setShowOcr(false);
        return;
      }
      setOcrText(text);
      setOcrStatus("ready");
    } catch (error) {
      const isNoOcr =
        error instanceof ApiError && error.message === "no_ocr_available";
      if (isNoOcr) {
        setOcrStatus("empty");
        setOcrText(null);
        setShowOcr(false);
        return;
      }
      setOcrStatus("error");
      setOcrText(null);
    }
  };

  const ocrUnavailable = ocrStatus === "empty";

  const handleToggleOcr = () => {
    if (ocrUnavailable) return;
    const next = !showOcr;
    setShowOcr(next);
    if (next && (ocrStatus === "idle" || ocrStatus === "error")) {
      void fetchOcr();
    }
  };

  const ocrIsPersian = ocrText ? isMostlyPersian(ocrText) : false;

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white p-2">
      <button
        type="button"
        onClick={() => setLightboxOpen(true)}
        className="group block w-full overflow-hidden rounded-xl text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-trust"
        aria-label={`Open full view: ${documentTitle}`}
      >
        <img
          src={imageUrl}
          alt={documentTitle}
          className="h-48 w-full rounded-xl object-cover transition group-hover:opacity-95"
        />
      </button>

      <div className="mt-2 space-y-2 px-1">
        <p className="truncate font-mono text-xs font-medium text-slate-700">{documentTitle}</p>

        {ocrUnavailable ? (
          <div className="space-y-1.5">
            <button
              type="button"
              disabled
              className="w-full cursor-not-allowed rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-trust opacity-50"
              aria-disabled="true"
            >
              View System Draft (OCR)
            </button>
            <p className="text-center text-xs font-medium text-slate-500">Raw OCR Not Available</p>
          </div>
        ) : (
          <button
            type="button"
            onClick={handleToggleOcr}
            className={`w-full rounded-xl border px-3 py-2 text-sm font-semibold transition ${
              showOcr
                ? "border-amber-300 bg-amber-50 text-amber-800"
                : "border-slate-200 bg-slate-50 text-trust hover:border-trust/30"
            }`}
            aria-pressed={showOcr}
          >
            View System Draft (OCR)
          </button>
        )}

        {showOcr && ocrStatus === "loading" ? (
          <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 font-mono text-sm text-slate-600">
            <Loader2 className="h-4 w-4 animate-spin" />
            Loading OCR draft…
          </div>
        ) : null}

        {showOcr && ocrStatus === "error" ? (
          <div className="space-y-2 rounded-xl border border-red-200 bg-red-50/60 p-3">
            <p className="font-mono text-sm text-red-600">Failed to load — retry</p>
            <button
              type="button"
              onClick={() => void fetchOcr()}
              className="rounded-lg border border-red-200 bg-white px-3 py-1.5 text-xs font-semibold text-red-700 hover:bg-red-50"
            >
              Retry
            </button>
          </div>
        ) : null}

        {showOcr && ocrStatus === "ready" && ocrText ? (
          <div className="space-y-2 rounded-xl border border-amber-200 bg-amber-50/60 p-3">
            <div
              role="alert"
              dir="ltr"
              className="flex items-start gap-2 rounded-lg border border-amber-400 bg-amber-50 px-3 py-2 text-left text-amber-800"
            >
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" aria-hidden />
              <p className="text-left font-mono text-xs font-semibold leading-relaxed">
                ⚠️ AI-Generated Draft — Physician Review Required. Verify with the original document.
              </p>
            </div>

            <pre
              dir={ocrIsPersian ? "rtl" : "ltr"}
              className={`max-h-64 overflow-auto whitespace-pre-wrap rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 ${
                ocrIsPersian ? "text-right font-sans" : "text-left font-mono"
              }`}
            >
              {ocrText}
            </pre>
          </div>
        ) : null}
      </div>

      {lightboxOpen ? (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/80 p-4"
          role="dialog"
          aria-modal="true"
          aria-label={documentTitle}
          onClick={() => setLightboxOpen(false)}
        >
          <button
            type="button"
            className="absolute right-4 top-4 rounded-full bg-white/90 p-2 text-slate-800 shadow hover:bg-white"
            aria-label="Close"
            onClick={() => setLightboxOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
          <img
            src={imageUrl}
            alt={documentTitle}
            className="max-h-[90vh] max-w-[95vw] rounded-lg object-contain shadow-2xl"
            onClick={(event) => event.stopPropagation()}
          />
        </div>
      ) : null}
    </div>
  );
}
