import type { ReactNode } from "react";
import { BidiText } from "@/components/shared/bidi-text";
import { cn } from "@/lib/utils";

/**
 * Acuity tier identity.
 *
 * Tier codes are derived, not invented — the two anchors are fixed and the rest
 * follows from the ordering `globals.css` already encodes:
 *
 * - `P0` is the top tier, mapped to `--acuity-critical`.
 * - §6 states "unknown never visually reads as P3/routine", which fixes `P3`
 *   as `--acuity-routine`.
 * - With both ends pinned and the ramp ordered, `P1`/`P2` can only be
 *   `--acuity-high` / `--acuity-moderate`.
 *
 * `unknown` deliberately carries **no P-number**. Numbering it "P4" would place
 * it one step below routine on the numeric ramp, which is the exact inference
 * §6 forbids — and it would contradict `--acuity-unknown` being violet, held
 * off the risk ramp on purpose. An absent value is not a low-urgency value; it
 * is an unranked one.
 *
 * The tier list itself is still marked DRAFT in `globals.css`. This union is the
 * shape that draft implies, and it is the thing to re-check first if the tier
 * list is ever revised.
 */
export type AcuityTier = "P0" | "P1" | "P2" | "P3" | "unknown";

/** The five silhouettes. Distinct outlines, so the ramp survives grayscale. */
type TierShape = "octagon" | "triangle" | "diamond" | "circle" | "square";

type TierPresentation = {
  /** `null` for `unknown` — see the note on AcuityTier. */
  code: string | null;
  label: string;
  shape: TierShape;
  edge: string;
  chip: string;
  tint: string;
};

/**
 * One row per tier, every class written as a complete literal — never composed
 * as `bg-acuity-${tier}`, which Tailwind's scanner cannot see and would silently
 * drop from the build, leaving a card with no tier colour at all.
 *
 * Persian labels are triage/urgency wording, never a diagnosis or a
 * recommendation (§5.4): they name where the item sits in the queue, and say
 * nothing about the patient's condition.
 */
const TIER_PRESENTATION: Record<AcuityTier, TierPresentation> = {
  P0: { code: "P0", label: "بحرانی", shape: "octagon", edge: "border-acuity-critical", chip: "bg-acuity-critical", tint: "text-acuity-critical" },
  P1: { code: "P1", label: "فوری", shape: "triangle", edge: "border-acuity-high", chip: "bg-acuity-high", tint: "text-acuity-high" },
  P2: { code: "P2", label: "متوسط", shape: "diamond", edge: "border-acuity-moderate", chip: "bg-acuity-moderate", tint: "text-acuity-moderate" },
  P3: { code: "P3", label: "معمول", shape: "circle", edge: "border-acuity-routine", chip: "bg-acuity-routine", tint: "text-acuity-routine" },
  unknown: { code: null, label: "نامشخص", shape: "square", edge: "border-acuity-unknown", chip: "bg-acuity-unknown", tint: "text-acuity-unknown" },
};

/**
 * The non-colour channel the §8 gate requires.
 *
 * Geometry is hand-written rather than pulled from an icon package on purpose:
 * the distinctness of these five outlines is a safety mechanism, and an upstream
 * icon redesign must not be able to quietly round the octagon toward the circle.
 * Every Phase 2 component draws its glyph inline for the same reason.
 *
 * Outlines and interior marks both differ, so no two tiers collapse into each
 * other at a glance:
 *
 *   P0 octagon + "!"   P1 triangle + "!"   P2 diamond   P3 circle
 *   unknown  square + "?"  — a silhouette shared with no ramp tier, so it
 *                            cannot be mistaken for the ramp's bottom step.
 *
 * `aria-hidden`: the visible chip text carries the meaning for assistive tech,
 * so announcing the glyph too would just duplicate it.
 */
function TierGlyph({ shape, className }: { shape: TierShape; className?: string }) {
  const bang = (
    <>
      <line x1="12" y1="8.5" x2="12" y2="13.5" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </>
  );

  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {shape === "octagon" ? (
        <>
          <path d="M8 2h8l6 6v8l-6 6H8l-6-6V8Z" />
          {bang}
        </>
      ) : null}
      {shape === "triangle" ? (
        <>
          <path d="M12 3 21.8 20.5H2.2Z" />
          <line x1="12" y1="9.5" x2="12" y2="14" />
          <line x1="12" y1="17.5" x2="12.01" y2="17.5" />
        </>
      ) : null}
      {shape === "diamond" ? <path d="M12 2.5 21.5 12 12 21.5 2.5 12Z" /> : null}
      {shape === "circle" ? <circle cx="12" cy="12" r="9.5" /> : null}
      {shape === "square" ? (
        <>
          <rect x="3.5" y="3.5" width="17" height="17" rx="2" />
          <path d="M9.7 9.4a2.4 2.4 0 1 1 4.3 1.6c-.8 1-2 1.4-2 2.8" />
          <line x1="12" y1="17" x2="12.01" y2="17" />
        </>
      ) : null}
    </svg>
  );
}

type AcuityCardProps = {
  tier: AcuityTier;
  /** Lead line — the patient or the finding this card stands for. */
  title: string;
  /**
   * Secondary line: record number, age, visit time. Latin-script and numeric
   * fragments must arrive already wrapped in `<BidiText>` (§3) — this component
   * can't wrap what it can't see inside a ReactNode.
   */
  subtitle?: ReactNode;
  children?: ReactNode;
  className?: string;
};

/**
 * A single acuity-bearing card for the clinician dashboard.
 *
 * Reads `--acuity-*` and nothing else from the theme layer (§3); the neutral
 * `ink` brand value carries body text, and it is not a persona token.
 *
 * **Why the tier is stated three ways.** §8 measured this scale's relative
 * luminance spanning only 0.076–0.163, with high/moderate/routine sitting
 * 1.05:1 and 1.02:1 apart — separated by hue almost alone, so the ramp
 * collapses under deuteranopia or in grayscale. Colour therefore cannot be the
 * channel that carries acuity. Each card states its tier as:
 *
 *   1. a glyph with a tier-specific outline (survives grayscale),
 *   2. the tier code and Persian label as text (survives both, and is the only
 *      channel a screen reader gets),
 *   3. the tier colour, as reinforcement only.
 *
 * Remove any one of the first two and this component stops satisfying the
 * Phase 3 gate condition.
 *
 * The card sits on `bg-white`, which is the background every `--acuity-*` ratio
 * in `globals.css` was measured against — tier text is AA or better here, and
 * the filled chip pairs each tier with `--acuity-foreground` (white), also
 * measured. Re-measure before moving these onto a tinted surface.
 *
 * Deliberately presentational: no handlers, no client boundary. Making the card
 * itself focusable would put a keyboard stop on every card in the grid whether
 * or not it leads anywhere; the interactive wrapper and its focus ring belong to
 * `priority-grid.tsx`, alongside the ranking §8 requires it to carry.
 *
 * Renders an `<h3>`, so the grid that lays these out owns the `<h2>` above them.
 */
export function AcuityCard({ tier, title, subtitle, children, className }: AcuityCardProps) {
  const presentation = TIER_PRESENTATION[tier];

  return (
    <article
      data-testid="acuity-card"
      data-tier={tier}
      className={cn(
        "rounded-2xl border border-ink/10 border-s-4 bg-white p-4 shadow-glass",
        presentation.edge,
        className,
      )}
    >
      <div className="flex items-start gap-3">
        <TierGlyph shape={presentation.shape} className={cn("mt-0.5 h-6 w-6 shrink-0", presentation.tint)} />

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span
              className={cn(
                "inline-flex items-center gap-1.5 rounded-lg px-2 py-0.5",
                "text-sm font-semibold text-acuity-foreground",
                presentation.chip,
              )}
            >
              {/* Gives the code and label a field name when read aloud. */}
              <span className="sr-only">سطح فوریت: </span>
              {presentation.code ? <BidiText className="font-bold">{presentation.code}</BidiText> : null}
              <span>{presentation.label}</span>
            </span>

            <h3 className="min-w-0 flex-1 truncate text-base font-semibold text-ink">{title}</h3>
          </div>

          {subtitle ? <p className="mt-1 text-sm text-ink/70">{subtitle}</p> : null}
          {children ? <div className="mt-3 text-sm text-ink">{children}</div> : null}
        </div>
      </div>
    </article>
  );
}
