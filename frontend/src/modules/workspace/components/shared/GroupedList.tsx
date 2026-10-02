import type { ReactNode } from "react";
import { cx } from "./cx";

export type GroupedListItem = {
  readonly id: string;
  readonly primary: ReactNode;
  readonly secondary?: ReactNode;
  readonly meta?: ReactNode;
};

export type GroupedListGroup = {
  readonly id: string;
  readonly label: string;
  readonly items: readonly GroupedListItem[];
};

export type GroupedListProps = {
  groups: readonly GroupedListGroup[];
  className?: string;
  "aria-label"?: string;
};

/** Product-agnostic labeled groups of rows. */
export function GroupedList({
  groups,
  className,
  "aria-label": ariaLabel = "Grouped list",
}: GroupedListProps) {
  return (
    <div className={cx("space-y-3", className)} aria-label={ariaLabel}>
      {groups.map((group) => (
        <section key={group.id} aria-label={group.label}>
          <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-trust">
            {group.label}
          </h3>
          <ul className="divide-y divide-trust/10 rounded-md border border-trust/10">
            {group.items.map((item) => (
              <li
                key={item.id}
                className="flex flex-wrap items-baseline justify-between gap-2 px-2 py-1.5"
              >
                <div className="min-w-0">
                  <div className="text-sm text-ink">{item.primary}</div>
                  {item.secondary != null ? (
                    <div className="text-xs text-ink/70">{item.secondary}</div>
                  ) : null}
                </div>
                {item.meta != null ? (
                  <div className="shrink-0 text-xs text-ink/60">{item.meta}</div>
                ) : null}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
