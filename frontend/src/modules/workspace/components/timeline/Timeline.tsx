import type { ReactNode } from "react";
import { CalendarDays, ChevronDown, Circle } from "lucide-react";
import { BidiText, DateValue } from "@/components/ui/bidi";
import type { TimelineContent } from "../types";
import type { TrustViewModel } from "../../presentation/viewmodels/types";
import { CardChrome } from "../shared/CardChrome";
import { EmptyState } from "../shared/EmptyState";
import { SourceIndicator } from "../shared/SourceIndicator";
import { ProvenanceDisclosure } from "../shared/ProvenanceDisclosure";
import { ErrorState } from "../shared/ErrorState";

export type TimelineProps = {
  content: TimelineContent | null;
  trust?: ReactNode;
  provenance?: TrustViewModel;
  state?: "ready" | "loading" | "error" | "unavailable";
  className?: string;
};

function TimelineGroup({ group, provenance }: { group: TimelineContent["groups"][number]; provenance?: TrustViewModel }) {
  return (
    <section aria-label={`Events on ${group.date}`}>
      <h3 className="mb-2 flex items-center gap-2 rounded-tai-sm bg-tai-surface px-3 py-2 text-xs font-bold text-tai-navy"><CalendarDays className="size-4 text-tai-teal" aria-hidden="true" /><DateValue>{group.date}</DateValue><span className="ms-auto font-normal text-tai-subdued">{group.events.length} رویداد</span></h3>
      <ol className="relative ms-2 border-s border-tai-border ps-4">
        {group.events.map((event) => (
          <li key={event.id} className="relative pb-3 last:pb-0"><Circle className="absolute -start-[1.3rem] top-1 size-2.5 fill-tai-teal text-tai-teal" aria-hidden="true" /><article className="rounded-tai-md border border-tai-border bg-white p-3 transition-colors hover:border-tai-teal/30"><div className="flex flex-wrap items-start justify-between gap-2"><div className="min-w-0"><div className="text-[11px] text-tai-subdued">نوع رویداد: <span data-semantic-state="unknown">در قرارداد موجود نیست</span></div><BidiText className="mt-0.5 block text-sm font-bold text-tai-text">{event.title}</BidiText></div><SourceIndicator source={event.source} /></div>{event.detail ? <BidiText className="mt-2 block text-xs leading-6 text-tai-text">{event.detail}</BidiText> : <p data-semantic-state="missing" className="mt-2 text-xs text-tai-subdued">خلاصه رویداد موجود نیست.</p>}<ProvenanceDisclosure trust={provenance} source={event.source} timestamp={group.date} scopeLabel={event.title} /></article></li>
        ))}
      </ol>
    </section>
  );
}

export function Timeline({ content, trust, provenance, state = "ready", className }: TimelineProps) {
  if (state === "loading") return <CardChrome className={className} title="خط زمانی بالینی" trust={trust} aria-label="Timeline"><div role="status" aria-busy="true" className="rounded-tai-md border border-tai-border bg-tai-surface p-4 text-sm">در حال بارگذاری خط زمانی...</div></CardChrome>;
  if (state === "error") return <CardChrome className={className} title="خط زمانی بالینی" trust={trust} aria-label="Timeline"><ErrorState title="بارگذاری خط زمانی ناموفق بود" message="رویدادها در حال حاضر قابل نمایش نیستند." /></CardChrome>;
  if (state === "unavailable") return <CardChrome className={className} title="خط زمانی بالینی" trust={trust} aria-label="Timeline"><EmptyState title="خط زمانی در دسترس نیست" message="این وضعیت به معنی نبود رویداد بالینی نیست." /></CardChrome>;
  if (content == null || content.groups.length === 0) {
    return (
      <CardChrome className={className} title="خط زمانی بالینی" subtitle="Clinical Timeline" trust={trust} aria-label="Timeline">
        <EmptyState title="رویدادی ثبت نشده است" message="نبود رویداد ثبت‌شده به معنی نبود سابقه بالینی نیست." />
      </CardChrome>
    );
  }

  return (
    <CardChrome className={className} title="خط زمانی بالینی" subtitle="Clinical Timeline" trust={trust} aria-label="Timeline">
      <div className="space-y-4">
        {content.groups.slice(0, 2).map((group) => <TimelineGroup key={group.date} group={group} provenance={provenance} />)}
        {content.groups.length > 2 ? <details className="group rounded-tai-md border border-tai-border bg-tai-surface/50"><summary className="flex min-h-10 cursor-pointer list-none items-center gap-2 px-3 text-sm font-semibold text-tai-navy marker:content-none [&::-webkit-details-marker]:hidden">نمایش {content.groups.length - 2} تاریخ دیگر<ChevronDown className="ms-auto size-4 transition-transform group-open:rotate-180 motion-reduce:transition-none" aria-hidden="true" /></summary><div className="space-y-4 border-t border-tai-border p-3">{content.groups.slice(2).map((group) => <TimelineGroup key={group.date} group={group} provenance={provenance} />)}</div></details> : null}
      </div>
    </CardChrome>
  );
}
