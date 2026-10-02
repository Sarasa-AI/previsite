"use client";

import { useMemo, useState } from "react";
import { AlertCircle } from "lucide-react";

export type SoapCitation = {
  index?: number;
  marker?: string;
  source?: string | null;
  source_title?: string | null;
  content?: string | null;
  source_excerpt?: string | null;
  verified?: boolean;
  verification_status?: string;
  similarity_score?: number | null;
};

type SoapCitationTextProps = {
  text: string;
  citations?: SoapCitation[];
};

const CITATION_MARKER_RE = /\[(\d+)\]/g;

function citationKey(citation: SoapCitation): number | null {
  if (typeof citation.index === "number") return citation.index;
  if (citation.marker) {
    const match = citation.marker.match(/^\[(\d+)\]$/);
    if (match) return Number(match[1]);
  }
  return null;
}

function isVerified(citation: SoapCitation | undefined): boolean {
  if (!citation) return false;
  if (typeof citation.verified === "boolean") return citation.verified;
  return citation.verification_status === "verified";
}

export default function SoapCitationText({ text, citations = [] }: SoapCitationTextProps) {
  const [openMarker, setOpenMarker] = useState<number | null>(null);

  const citationMap = useMemo(() => {
    const map = new Map<number, SoapCitation>();
    for (const citation of citations) {
      const key = citationKey(citation);
      if (key != null) map.set(key, citation);
    }
    return map;
  }, [citations]);

  const segments = useMemo(() => {
    const parts: Array<{ type: "text"; value: string } | { type: "marker"; index: number }> = [];
    let lastIndex = 0;
    const matches = text.matchAll(CITATION_MARKER_RE);

    for (const match of matches) {
      const start = match.index ?? 0;
      if (start > lastIndex) {
        parts.push({ type: "text", value: text.slice(lastIndex, start) });
      }
      parts.push({ type: "marker", index: Number(match[1]) });
      lastIndex = start + match[0].length;
    }

    if (lastIndex < text.length) {
      parts.push({ type: "text", value: text.slice(lastIndex) });
    }

    return parts;
  }, [text]);

  if (!text) return null;

  return (
    <span className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
      {segments.map((segment, i) => {
        if (segment.type === "text") {
          return <span key={`t-${i}`}>{segment.value}</span>;
        }

        const citation = citationMap.get(segment.index);
        const verified = isVerified(citation);
        const title = citation?.source_title || citation?.source || "منبع نامشخص";
        const excerpt =
          citation?.source_excerpt || citation?.content || "گزیده‌ای برای این ارجاع ثبت نشده است.";
        const isOpen = openMarker === segment.index;

        return (
          <span key={`m-${segment.index}-${i}`} className="relative inline-block align-baseline">
            <button
              type="button"
              className={`mx-0.5 inline-flex items-center gap-0.5 rounded px-1 py-0.5 text-xs font-semibold underline-offset-2 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-trust/40 ${
                verified
                  ? "bg-trust/10 text-trust"
                  : "bg-amber-100 text-amber-800"
              }`}
              aria-expanded={isOpen}
              aria-label={verified ? `ارجاع ${segment.index}` : `ارجاع تأییدنشده ${segment.index}`}
              onMouseEnter={() => setOpenMarker(segment.index)}
              onMouseLeave={() => setOpenMarker((current) => (current === segment.index ? null : current))}
              onClick={() =>
                setOpenMarker((current) => (current === segment.index ? null : segment.index))
              }
            >
              [{segment.index}]
              {!verified ? <AlertCircle className="h-3 w-3" aria-hidden /> : null}
            </button>
            {isOpen ? (
              <span
                role="tooltip"
                className="absolute bottom-full left-1/2 z-20 mb-2 w-64 -translate-x-1/2 rounded-xl border border-slate-200 bg-white p-3 text-right shadow-lg"
                onMouseEnter={() => setOpenMarker(segment.index)}
                onMouseLeave={() => setOpenMarker(null)}
              >
                <span className="block text-xs font-semibold text-slate-900">{title}</span>
                <span className="mt-1 block text-xs leading-5 text-slate-600">{excerpt}</span>
                {!verified ? (
                  <span className="mt-2 flex items-center gap-1 text-[11px] font-medium text-amber-700">
                    <AlertCircle className="h-3 w-3" />
                    نیاز به بررسی دستی پزشک
                  </span>
                ) : null}
              </span>
            ) : null}
          </span>
        );
      })}
    </span>
  );
}
