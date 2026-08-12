import type { ErrorStateContent } from "../types";
import { cx } from "./cx";

export type ErrorStateProps = ErrorStateContent & {
  className?: string;
};

/** Presentation-only error surface — no retry handlers. */
export function ErrorState({ title, message, className }: ErrorStateProps) {
  return (
    <div
      className={cx(
        "rounded-lg border border-danger/30 bg-white px-3 py-4 text-start",
        className,
      )}
      role="alert"
      aria-label={title}
    >
      <p className="text-sm font-semibold text-danger">{title}</p>
      <p className="mt-1 text-xs text-ink/80">{message}</p>
    </div>
  );
}
