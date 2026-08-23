"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * The patient-side "please pay attention to this" callout — safety information,
 * consent notes, why a photo is being requested.
 *
 * Paints `--warning` text on `--warning-surface` (6.37:1, AA) and carries a
 * glyph plus a text heading, so the message never depends on the amber tint
 * being perceived. It states no diagnosis and makes no recommendation (§5.4);
 * all copy arrives from the caller.
 *
 * Deliberately not an acuity component: `--acuity-*` is clinician-only and is
 * never reused for patient-facing emphasis (§3).
 */

type AmberBoxProps = {
  /** Short heading, e.g. "قبل از ادامه بخوانید". Renders alongside the glyph. */
  title?: string;
  children: ReactNode;
  /**
   * Set when the box appears in response to something the patient just did, so
   * a screen reader announces it. Leave false for statically rendered notes —
   * a permanently live region gets announced on every unrelated update.
   */
  live?: boolean;
  className?: string;
};

export function AmberBox({ title, children, live = false, className }: AmberBoxProps) {
  return (
    <aside
      data-testid="amber-box"
      role={live ? "status" : "note"}
      aria-live={live ? "polite" : undefined}
      className={cn(
        "flex gap-3 rounded-2xl border border-warning/30 bg-warning-surface p-4",
        "text-base leading-relaxed text-warning",
        className,
      )}
    >
      {/* aria-hidden: the heading text carries the meaning, the glyph reinforces it. */}
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="mt-0.5 h-6 w-6 shrink-0"
      >
        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
        <line x1="12" y1="9" x2="12" y2="13" />
        <line x1="12" y1="17" x2="12.01" y2="17" />
      </svg>

      <div className="min-w-0">
        {title ? <p className="mb-1 font-semibold">{title}</p> : null}
        <div>{children}</div>
      </div>
    </aside>
  );
}
