import { Badge, Button } from "@/components/ui";
import type { WorkspaceViewModel } from "../../presentation/viewmodels/types";

type Props = {
  viewModel: WorkspaceViewModel;
  onAcknowledge: (objectId: string) => void;
  onResolve?: (objectId: string) => void;
  onDismiss?: (objectId: string) => void;
  acknowledgePending?: boolean;
  resolvePending?: boolean;
  dismissPending?: boolean;
};

export function DecisionQueue({
  viewModel,
  onAcknowledge,
  onResolve,
  onDismiss,
  acknowledgePending,
  resolvePending,
  dismissPending,
}: Props) {
  if (!viewModel.queue.length) return null;

  return (
    <section
      id="workspace-decisions"
      data-workspace-band="queue"
      aria-label="Decision queue"
      className="scroll-mt-4 rounded-tai-lg border border-tai-border bg-white p-3 shadow-tai-sm"
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h2 className="text-sm font-bold text-tai-navy">
          <span className="sr-only">Decision queue</span>
          <span aria-hidden="true">صف تصمیم</span>
        </h2>
        <Badge>{viewModel.queue.length}</Badge>
      </div>
      <ol className="space-y-2.5">
        {viewModel.queue.map((item) => (
          <li
            key={`queue-${item.rank}-${item.objectId}`}
            data-queue-rank={item.rank}
            className="rounded-tai-md border border-transparent p-1.5 transition-colors hover:border-tai-border hover:bg-tai-surface"
          >
            <div className="flex items-start gap-2">
              <Badge className="shrink-0">{item.rank}</Badge>
              <div className="min-w-0">
                <div
                  dir="ltr"
                  className="truncate text-start text-sm font-medium text-tai-text"
                >
                  {item.objectId}
                </div>
                <p dir="auto" className="mt-1 text-xs leading-5 text-tai-subdued">
                  {item.explanation}
                </p>
              </div>
            </div>
            {viewModel.mutationsAllowed ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {item.acknowledgeRequired ? (
                  <Button
                    type="button"
                    size="sm"
                    loading={acknowledgePending}
                    onClick={() => onAcknowledge(item.objectId)}
                    aria-label="Acknowledge"
                  >
                    تأیید مشاهده
                  </Button>
                ) : null}
                {onResolve ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="secondary"
                    loading={resolvePending}
                    onClick={() => onResolve(item.objectId)}
                    aria-label="Resolve"
                  >
                    حل‌شده
                  </Button>
                ) : null}
                {onDismiss ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="ghost"
                    loading={dismissPending}
                    onClick={() => onDismiss(item.objectId)}
                    aria-label="Dismiss"
                  >
                    بستن
                  </Button>
                ) : null}
              </div>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}
