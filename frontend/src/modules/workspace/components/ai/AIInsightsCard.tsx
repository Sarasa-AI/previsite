import { Bot, Sparkles } from "lucide-react";
import { BidiText, DateValue } from "@/components/ui/bidi";
import { Button, ClinicalValueState, StatusBadge } from "@/components/ui";
import type { ErrorViewModel, WorkspaceViewModel } from "../../presentation/viewmodels/types";
import type { WorkspaceUiState } from "../../presentation/state/workspaceUiState";
import { ProvenanceDisclosure } from "../shared/ProvenanceDisclosure";

export type AIInsightsCardProps = {
  viewModel: WorkspaceViewModel;
  uiState?: WorkspaceUiState;
  error?: ErrorViewModel | null;
  onRefresh: () => void;
  refreshPending?: boolean;
};

function storyTrust(viewModel: WorkspaceViewModel) {
  return [...viewModel.pinCards, ...viewModel.primaryCards, ...viewModel.secondaryCards, ...viewModel.deferredCards].find((card) => card.objectId === "story")?.trust;
}

export function AIInsightsCard({ viewModel, uiState = "Ready", error, onRefresh, refreshPending }: AIInsightsCardProps) {
  const story = viewModel.story;
  const trust = storyTrust(viewModel);
  const loading = refreshPending || (uiState === "Generating" && !story);
  const failed = error?.code === "WORKSPACE_COMPUTE_FAILED" && !story;
  const empty = story != null && !story.text.trim();
  const partial = story != null && (story.confidence === "unknown" || story.evidenceRefs.length === 0 || !viewModel.metadata.generatedAt || !viewModel.metadata.generatedBy || !trust);

  return (
    <article data-ai-insights data-stale={story?.stale ? "true" : "false"} className="overflow-hidden rounded-tai-lg border border-[hsl(var(--tai-ai)/.3)] bg-white shadow-tai-sm transition-shadow hover:shadow-tai-md" aria-label="AI insights">
      <div className="border-s-[3px] border-[hsl(var(--tai-ai))] p-3.5">
        <header className="flex flex-wrap items-start justify-between gap-3">
          <div className="flex min-w-0 items-start gap-2.5"><span className="grid size-8 shrink-0 place-items-center rounded-tai-md bg-[hsl(var(--tai-ai-surface))] text-[hsl(var(--tai-ai))]"><Sparkles className="size-4" aria-hidden="true" /></span><div><h2 className="text-sm font-bold text-tai-navy"><span className="sr-only">AI insights</span><span aria-hidden="true">داستان و بینش هوش مصنوعی</span></h2><p className="mt-0.5 text-[11px] text-tai-subdued">پیش‌نویس برای بازبینی؛ واقعیت بالینی یا تشخیص نیست</p></div></div>
          <div className="flex flex-wrap gap-1.5"><ClinicalValueState state="ai-generated" /><ClinicalValueState state="draft" /><StatusBadge state="warning">نیازمند بازبینی</StatusBadge>{story?.stale ? <ClinicalValueState state="stale" /> : null}{partial ? <StatusBadge state="unknown">ناقص</StatusBadge> : null}</div>
        </header>

        {loading ? <div role="status" aria-busy="true" className="mt-4 rounded-tai-md border border-tai-border bg-tai-surface p-4 text-sm">در حال تولید پیش‌نویس هوش مصنوعی...</div> : failed ? <div role="alert" className="mt-4 rounded-tai-md border border-[hsl(var(--tai-critical)/.35)] bg-[hsl(var(--tai-critical-surface))] p-4 text-sm text-[hsl(var(--tai-critical))]">تولید بینش هوش مصنوعی ناموفق بود.</div> : !story ? <div role="status" data-semantic-state="missing" className="mt-4 rounded-tai-md border border-dashed border-tai-border bg-tai-surface p-4"><p className="text-sm font-semibold">بینش هوش مصنوعی در دسترس نیست</p><p className="mt-1 text-xs text-tai-subdued">نبود خروجی AI هیچ نتیجه بالینی را تایید یا رد نمی‌کند.</p></div> : empty ? <div role="status" data-semantic-state="missing" className="mt-4 rounded-tai-md border border-dashed border-tai-border p-4 text-sm">پیش‌نویس تولیدشده خالی است.</div> : <><div className="mt-4 rounded-tai-md border border-[hsl(var(--tai-ai)/.25)] bg-[hsl(var(--tai-ai-surface))] p-4"><div className="mb-2 flex items-center gap-2 text-xs font-semibold text-[hsl(var(--tai-ai))]"><Bot className="size-4" aria-hidden="true" />پیش‌نویس برای بازبینی پزشک</div><BidiText className="tai-clinical-copy block text-sm leading-7 text-tai-text">{story.text}</BidiText></div><div className="mt-3 grid gap-2 text-xs sm:grid-cols-3"><div><span className="text-tai-subdued">اطمینان</span><div className="font-semibold">{story.confidence === "unknown" ? <span data-semantic-state="unknown">در دسترس نیست</span> : `${Math.round(story.confidence * 100)}٪`}</div></div><div><span className="text-tai-subdued">زمان تولید</span><div>{viewModel.metadata.generatedAt ? <DateValue>{viewModel.metadata.generatedAt}</DateValue> : <span data-semantic-state="missing">در دسترس نیست</span>}</div></div><div><span className="text-tai-subdued">تولیدکننده</span><div>{viewModel.metadata.generatedBy ? <BidiText>{viewModel.metadata.generatedBy}</BidiText> : <span data-semantic-state="missing">در دسترس نیست</span>}</div></div></div><ProvenanceDisclosure trust={trust} timestamp={viewModel.metadata.generatedAt || null} confidence={story.confidence} evidenceRefs={story.evidenceRefs} scopeLabel="AI insights" /></>}

        {story?.stale && viewModel.mutationsAllowed ? <Button type="button" size="sm" variant="secondary" loading={refreshPending} onClick={onRefresh} className="mt-3" aria-label="Refresh AI insights">به‌روزرسانی پیش‌نویس</Button> : null}
      </div>
    </article>
  );
}
