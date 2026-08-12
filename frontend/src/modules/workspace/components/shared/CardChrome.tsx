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
        "rounded-lg border border-trust/15 bg-white p-3 text-ink shadow-sm",
        className,
      )}
      aria-label={ariaLabel}
    >
      {hasHeader ? (
        <header className="mb-2 flex flex-wrap items-start gap-2">
          <div className="min-w-0 flex-1">
            {title != null ? (
              <div className="text-sm font-semibold text-trust">{title}</div>
            ) : null}
            {subtitle != null ? (
              <div className="mt-0.5 text-xs text-ink/70">{subtitle}</div>
            ) : null}
          </div>
          {badges != null ? (
            <div className="flex flex-wrap items-center gap-1">{badges}</div>
          ) : null}
          {trust != null ? <div className="shrink-0">{trust}</div> : null}
          {actions != null ? (
            <div className="flex shrink-0 flex-wrap items-center gap-1">{actions}</div>
          ) : null}
        </header>
      ) : null}
      {children != null ? <div className="min-w-0">{children}</div> : null}
      {footer != null ? (
        <footer className="mt-2 border-t border-trust/10 pt-2 text-xs text-ink/70">
          {footer}
        </footer>
      ) : null}
    </article>
  );
}
