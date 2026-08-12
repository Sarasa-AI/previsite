import type { ReactNode } from "react";
import { ChevronDown } from "lucide-react";
import { cx } from "./cx";

export type ExpandableBlockProps = {
  summary: ReactNode;
  children: ReactNode;
  open?: boolean;
  className?: string;
  summaryClassName?: string;
};

/**
 * Native details/summary — no React state.
 * Supports controlled `open` when parent-driven.
 */
export function ExpandableBlock({
  summary,
  children,
  open,
  className,
  summaryClassName,
}: ExpandableBlockProps) {
  return (
    <details
      className={cx("group border-b border-trust/10 last:border-b-0", className)}
      open={open}
    >
      <summary
        className={cx(
          "flex cursor-pointer list-none items-center gap-2 py-2 text-sm text-ink marker:content-none",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-trust",
          "[&::-webkit-details-marker]:hidden",
          summaryClassName,
        )}
      >
        <ChevronDown
          className="size-4 shrink-0 text-trust transition-transform motion-reduce:transition-none group-open:rotate-180"
          aria-hidden="true"
        />
        <span className="min-w-0 flex-1 text-start">{summary}</span>
      </summary>
      <div className="pb-2 ps-6 text-xs text-ink/80">{children}</div>
    </details>
  );
}
