import type { TrustViewModel } from "../../presentation/viewmodels/types";
import { cx } from "./cx";

export type TrustBadgeProps = {
  trust: TrustViewModel;
  className?: string;
};

/** Presentation chrome only — does not embed into content ViewModels. */
export function TrustBadge({ trust, className }: TrustBadgeProps) {
  const confidenceLabel =
    trust.confidence === "unknown" ? "unknown" : `${Math.round(trust.confidence * 100)}%`;

  return (
    <span
      className={cx(
        "inline-flex items-center gap-1 rounded-tai-sm border border-tai-border bg-tai-surface px-1.5 py-0.5 text-[11px] font-medium text-tai-subdued",
        className,
      )}
      title={`${trust.primaryProvenance} · ${trust.verification}`}
      aria-label={`Trust: ${trust.verification}, confidence ${confidenceLabel}, source ${trust.primaryProvenance}`}
    >
      <span className="text-tai-navy">{trust.verification}</span>
      <span className="text-ink/60" aria-hidden="true">
        ·
      </span>
      <span>{confidenceLabel}</span>
    </span>
  );
}
