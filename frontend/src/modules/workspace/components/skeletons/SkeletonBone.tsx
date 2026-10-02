import type { ReactNode } from "react";
import { cx } from "../shared/cx";

export type SkeletonBoneProps = {
  className?: string;
};

/** Token-only skeleton bone; pulse disabled under prefers-reduced-motion. */
export function SkeletonBone({ className }: SkeletonBoneProps) {
  return (
    <div
      className={cx(
        "rounded bg-trust/10 animate-pulse motion-reduce:animate-none",
        className,
      )}
      aria-hidden="true"
    />
  );
}

export type SkeletonFrameProps = {
  className?: string;
  "aria-label"?: string;
  children: ReactNode;
};

export function SkeletonFrame({
  className,
  "aria-label": ariaLabel = "Loading",
  children,
}: SkeletonFrameProps) {
  return (
    <div
      className={cx(
        "rounded-lg border border-trust/15 bg-white p-3 shadow-sm",
        className,
      )}
      role="status"
      aria-busy="true"
      aria-label={ariaLabel}
    >
      {children}
    </div>
  );
}
