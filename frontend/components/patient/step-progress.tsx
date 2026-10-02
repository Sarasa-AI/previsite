"use client";

import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Owns wizard step state AND the step-to-step transition, so no individual
 * wizard component carries enter/exit animation logic of its own (§6, Phase 2).
 * Children read the current step and travel direction from context; the single
 * place motion is applied is <StepTransition>.
 */

type Direction = 1 | -1;

type StepProgressValue = {
  /** 1-based index of the visible step. */
  step: number;
  total: number;
  /** 1 = advancing, -1 = going back. Drives the transition's slide sign. */
  direction: Direction;
  /** Mirrors prefers-reduced-motion so consumers never re-query it (§5.3). */
  reduced: boolean;
};

const StepProgressContext = createContext<StepProgressValue | null>(null);

export function useStepProgress(): StepProgressValue {
  const value = useContext(StepProgressContext);
  if (!value) {
    throw new Error("useStepProgress must be used inside <StepProgressProvider>");
  }
  return value;
}

type StepProgressProviderProps = {
  /** 1-based. The parent wizard owns this; the provider only derives direction. */
  step: number;
  total: number;
  children: ReactNode;
};

export function StepProgressProvider({ step, total, children }: StepProgressProviderProps) {
  const reduced = useReducedMotion() ?? false;

  // Direction is derived from the step prop changing. Adjusting state during
  // render (rather than in an effect) keeps the transition and the new content
  // in the same commit — an effect would render one frame with a stale sign.
  const [tracker, setTracker] = useState<{ step: number; direction: Direction }>({
    step,
    direction: 1,
  });
  if (tracker.step !== step) {
    setTracker({ step, direction: step > tracker.step ? 1 : -1 });
  }

  const value = useMemo<StepProgressValue>(
    () => ({
      step,
      total: Math.max(1, total),
      direction: tracker.step === step ? tracker.direction : 1,
      reduced,
    }),
    [step, total, tracker, reduced],
  );

  return <StepProgressContext.Provider value={value}>{children}</StepProgressContext.Provider>;
}

const PERSIAN_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

/** Same curve as tailwind's `ease-spring` / the `--spring-easing` CSS var. */
const SPRING_EASE: [number, number, number, number] = [0.22, 1, 0.36, 1];

/**
 * Locale-free digit mapping. `toLocaleString("fa-IR")` depends on the runtime's
 * ICU data, which differs between the Node render and the browser — that is a
 * hydration mismatch, so the table is explicit instead.
 */
function toPersianDigits(value: number): string {
  return String(value).replace(/\d/g, (d) => PERSIAN_DIGITS[Number(d)]);
}

type StepProgressProps = {
  /** Optional per-step names, used for the current step's caption. */
  labels?: string[];
  className?: string;
};

/** The visible progress bar. Reads everything from context — takes no step prop. */
export function StepProgress({ labels, className }: StepProgressProps) {
  const { step, total, reduced } = useStepProgress();
  const clamped = Math.min(Math.max(step, 1), total);
  const percent = (clamped / total) * 100;
  const caption = labels?.[clamped - 1];

  return (
    <div className={cn("w-full", className)} data-testid="step-progress">
      <div className="mb-2 flex items-baseline justify-between gap-3 text-sm">
        <span className="font-semibold">
          {`مرحله ${toPersianDigits(clamped)} از ${toPersianDigits(total)}`}
        </span>
        {caption ? <span className="truncate text-slate-500">{caption}</span> : null}
      </div>

      <div
        role="progressbar"
        aria-valuemin={1}
        aria-valuemax={total}
        aria-valuenow={clamped}
        aria-valuetext={`مرحله ${toPersianDigits(clamped)} از ${toPersianDigits(total)}`}
        aria-label="پیشرفت تکمیل پرسش‌ها"
        className="h-2 w-full overflow-hidden rounded-full bg-primary-surface"
      >
        {/* Width, not transform: a scaled bar would need a transform-origin flip
            per direction, and width animates identically under either dir. */}
        <motion.div
          className="h-full rounded-full bg-primary"
          initial={false}
          animate={{ width: `${percent}%` }}
          transition={reduced ? { duration: 0 } : { duration: 0.35, ease: SPRING_EASE }}
        />
      </div>
    </div>
  );
}

/** Horizontal travel of the entering/leaving panel, in px. */
const SLIDE_PX = 24;

type StepTransitionProps = {
  children: ReactNode;
  className?: string;
};

/**
 * The only place a wizard step animates. `x` is a physical transform because
 * Framer Motion has no logical equivalent — the signs below are chosen for the
 * RTL default: advancing brings the new panel in from the inline-end (visually
 * the left), matching a right-to-left filmstrip.
 */
export function StepTransition({ children, className }: StepTransitionProps) {
  const { step, direction, reduced } = useStepProgress();
  const offset = direction === 1 ? -SLIDE_PX : SLIDE_PX;

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={step}
        data-testid="step-transition"
        className={cn("w-full", className)}
        initial={reduced ? { opacity: 0 } : { opacity: 0, x: offset }}
        animate={reduced ? { opacity: 1 } : { opacity: 1, x: 0 }}
        exit={reduced ? { opacity: 0 } : { opacity: 0, x: -offset }}
        transition={reduced ? { duration: 0 } : { duration: 0.28, ease: SPRING_EASE }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  );
}
