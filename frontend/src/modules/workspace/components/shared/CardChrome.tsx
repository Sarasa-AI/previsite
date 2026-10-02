import type { ReactNode } from "react";
import { cx } from "./cx";

export type CardChromeProps = {
  title?: ReactNode;
  subtitle?: ReactNode;
  badges?: ReactNode;
  trust?: ReactNode;
  actions?: ReactNode;
  footer?: ReactNode;
  children?: ReactNode;
  className?: string;
  "aria-label"?: string;
};

/**
 * Canonical reusable card frame.
 * Slot-based; product-agnostic — migratable to shared/components.
 */
export function CardChrome({
  title,
  subtitle,
  badges,
  trust,
  actions,
  footer,
  children,
  className,
  "aria-label": ariaLabel,
}: CardChromeProps) {
  const hasHeader = title != null || subtitle != null || badges != null || trust != null || actions != null;

  return (
    <article
      className={cx(
        "min-w-0 overflow-x-clip rounded-tai-lg border border-tai-border bg-white p-3.5 text-tai-text shadow-tai-sm transition-[border-color,box-shadow,transform] duration-200 [overflow-wrap:anywhere] hover:border-tai-teal/30 hover:shadow-tai-md motion-reduce:transition-none sm:p-4",
        className,
      )}
      aria-label={ariaLabel}
    >
      {hasHeader ? (
        <header className="mb-3 flex flex-wrap items-start gap-2 border-b border-tai-border pb-2.5">
          <div className="min-w-0 flex-1">
            {title != null ? (
              <h2 className="text-sm font-bold text-tai-navy">{title}</h2>
            ) : null}
            {subtitle != null ? (
              <div className="mt-0.5 text-[11px] font-medium text-tai-subdued">{subtitle}</div>
            ) : null}
          </div>
          {badges != null ? (
            <div className="flex flex-wrap items-center gap-1">{badges}</div>
          ) : null}
          {trust != null ? <div className="shrink-0 opacity-85 transition-opacity hover:opacity-100">{trust}</div> : null}
          {actions != null ? (
            <div className="flex shrink-0 flex-wrap items-center gap-1">{actions}</div>
          ) : null}
        </header>
      ) : null}
      {children != null ? <div className="min-w-0">{children}</div> : null}
      {footer != null ? (
        <footer className="mt-3 border-t border-tai-border pt-2.5 text-xs text-tai-subdued">
          {footer}
        </footer>
      ) : null}
    </article>
  );
}
