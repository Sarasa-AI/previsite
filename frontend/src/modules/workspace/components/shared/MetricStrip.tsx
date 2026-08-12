import type { ReactNode } from "react";
import { cx } from "./cx";

export type MetricStripItem = {
  readonly id: string;
  readonly label: string;
  readonly value: ReactNode;
};

export type MetricStripProps = {
  items: readonly MetricStripItem[];
  className?: string;
  "aria-label"?: string;
};

/** Product-agnostic labeled metric cells (CBC panels, snapshot strips, etc.). */
export function MetricStrip({
  items,
  className,
  "aria-label": ariaLabel = "Metrics",
}: MetricStripProps) {
  return (
    <ul
      className={cx(
        "grid grid-cols-2 gap-2 lg:grid-cols-3 xl:grid-cols-6",
        className,
      )}
      aria-label={ariaLabel}
    >
      {items.map((item) => (
        <li
          key={item.id}
          className="rounded-md border border-trust/10 bg-clinical px-2 py-1.5"
        >
          <div className="text-xs font-medium text-trust">{item.label}</div>
          <div className="mt-0.5 text-sm text-ink">{item.value}</div>
        </li>
      ))}
    </ul>
  );
}
