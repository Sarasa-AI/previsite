import type { EmptyStateContent } from "../types";
import { cx } from "./cx";

export type EmptyStateProps = EmptyStateContent & {
  className?: string;
};

/** Presentation-only empty state — no retry / fetch logic. */
export function EmptyState({ title, message, className }: EmptyStateProps) {
  return (
    <div
      className={cx(
        "rounded-lg border border-dashed border-trust/20 bg-clinical px-3 py-6 text-center",
        className,
      )}
      role="status"
      aria-label={title}
    >
      <p className="text-sm font-medium text-trust">{title}</p>
      <p className="mt-1 text-xs text-ink/70">{message}</p>
    </div>
  );
}
