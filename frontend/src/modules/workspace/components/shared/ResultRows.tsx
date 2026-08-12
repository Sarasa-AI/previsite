import type { ReactNode } from "react";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";
import type { TrendDirection } from "../types";
import { ExpandableBlock } from "./ExpandableBlock";
import { cx } from "./cx";

export type ResultRowItem = {
  readonly id: string;
  readonly name: string;
  readonly value: string;
  readonly unit?: string;
  readonly referenceRange?: string;
  readonly flagged?: boolean;
  readonly trend?: TrendDirection;
  readonly detail?: ReactNode;
};

export type ResultRowsProps = {
  rows: readonly ResultRowItem[];
  className?: string;
  "aria-label"?: string;
};

function TrendIcon({ trend }: { trend: TrendDirection }) {
  if (trend === "up") {
    return <ArrowUp className="size-3.5 text-danger" aria-label="Trend up" />;
  }
  if (trend === "down") {
    return <ArrowDown className="size-3.5 text-trust" aria-label="Trend down" />;
  }
  if (trend === "stable") {
    return <Minus className="size-3.5 text-ink/50" aria-label="Trend stable" />;
  }
  return <span className="text-xs text-ink/50" aria-label="Trend unknown">—</span>;
}

/** Product-agnostic name/value/range/flag/trend expandable rows (labs, CBC, etc.). */
export function ResultRows({
  rows,
  className,
  "aria-label": ariaLabel = "Results",
}: ResultRowsProps) {
  return (
    <div className={cx("rounded-md border border-trust/10", className)} aria-label={ariaLabel}>
      {rows.map((row) => {
        const summary = (
          <span className="flex w-full flex-wrap items-baseline justify-between gap-2">
            <span className={cx("font-medium", row.flagged ? "text-danger" : "text-ink")}>
              {row.name}
            </span>
            <span className="flex items-center gap-2 text-xs">
              <span className={cx(row.flagged ? "font-semibold text-danger" : "text-ink")}>
                {row.value}
                {row.unit ? ` ${row.unit}` : ""}
              </span>
              {row.referenceRange ? (
                <span className="text-ink/50">[{row.referenceRange}]</span>
              ) : null}
              {row.trend ? <TrendIcon trend={row.trend} /> : null}
            </span>
          </span>
        );

        if (row.detail == null) {
          return (
            <div key={row.id} className="border-b border-trust/10 px-2 py-2 last:border-b-0">
              {summary}
            </div>
          );
        }

        return (
          <ExpandableBlock key={row.id} summary={summary} className="px-2">
            {row.detail}
          </ExpandableBlock>
        );
      })}
    </div>
  );
}
