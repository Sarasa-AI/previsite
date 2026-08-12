import type { ReactNode } from "react";
import type { CardViewModel } from "../../presentation/viewmodels/types";
import type { CardPresenterProps } from "../../presentation/registry/types";
import { CardChrome } from "../shared/CardChrome";
import { PriorityBadge } from "../shared/PriorityBadge";
import { TrustBadge } from "../shared/TrustBadge";
import { EmptyState } from "../shared/EmptyState";
import { cx } from "../shared/cx";

/** Size → attention chrome only (never invents priority/slot). */
export function sizeClass(size: string): string {
  switch (size) {
    case "expanded":
      return "data-[size=expanded]:min-h-24";
    case "compressed":
      return "text-sm";
    case "badge":
      return "max-w-xs";
    default:
      return "";
  }
}

export type PresenterChromeProps = {
  card: CardViewModel;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  emptyTitle?: string;
  emptyMessage?: string;
  className?: string;
};

/** Shared framing for object_ids without a dedicated body component yet. */
export function PresenterChrome({
  card,
  title,
  children,
  actions,
  footer,
  emptyTitle,
  emptyMessage,
  className,
}: PresenterChromeProps) {
  return (
    <CardChrome
      className={cx(sizeClass(card.size), className)}
      title={title}
      subtitle={card.pinned ? "Pinned" : undefined}
      badges={<PriorityBadge priority={card.priority} />}
      trust={<TrustBadge trust={card.trust} />}
      actions={actions}
      footer={footer}
      aria-label={title}
    >
      <div data-object-id={card.objectId} data-size={card.size} data-priority={card.priority}>
        {children ?? (
          <EmptyState
            title={emptyTitle ?? title}
            message={emptyMessage ?? "Content will appear when clinical data is available."}
          />
        )}
      </div>
    </CardChrome>
  );
}

export function trustSlot(card: CardViewModel): ReactNode {
  return <TrustBadge trust={card.trust} />;
}

export type { CardPresenterProps };
