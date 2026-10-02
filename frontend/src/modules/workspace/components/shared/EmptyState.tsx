import type { EmptyStateContent } from "../types";
import { ClinicalValueState, type ClinicalValueStateKind } from "@/components/ui";
import { cx } from "./cx";

export type EmptyStateProps = EmptyStateContent & {
  className?: string;
  state?: Extract<ClinicalValueStateKind, "missing" | "unknown" | "unavailable"> | "empty";
};

/** Presentation-only empty state — no retry / fetch logic. */
export function EmptyState({ title, message, className, state = "empty" }: EmptyStateProps) {
  return (
    <div
      className={cx(
        "rounded-tai-md border border-dashed border-tai-border bg-tai-surface/70 px-3 py-3.5 text-center",
        className,
      )}
      role="status"
      aria-live="polite"
      aria-label={title}
      data-clinical-ui-state={state}
    >
      {state !== "empty" ? <ClinicalValueState state={state} className="mb-2" /> : null}
      <p className="text-sm font-semibold text-tai-navy/80">{title}</p>
      <p className="mx-auto mt-1 max-w-xl text-xs leading-5 text-tai-subdued">{message}</p>
    </div>
  );
}
