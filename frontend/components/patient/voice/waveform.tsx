"use client";

import { motion, useReducedMotion, type TargetAndTransition, type Transition } from "framer-motion";
import { cn } from "@/lib/utils";

const DEFAULT_BAR_COUNT = 24;

/** Floor scale — a bar that collapses to nothing reads as a dead microphone. */
const MIN_SCALE = 0.12;

/** Symmetric envelope, tallest in the middle, so the row reads as a waveform. */
function envelope(index: number, total: number): number {
  return 0.4 + 0.6 * Math.sin((Math.PI * (index + 0.5)) / total);
}

/** Deterministic per-bar phase — Math.random here would break SSR hydration. */
function phase(index: number): number {
  return ((index * 37) % 11) / 11;
}

function barMotion(
  index: number,
  peak: number,
  { active, amplitude, reduced }: { active: boolean; amplitude: number | null; reduced: boolean },
): { animate: TargetAndTransition; transition: Transition } {
  // Reduced motion: hold a static row and let opacity carry the active state.
  if (reduced) {
    return {
      animate: { scaleY: active ? peak * 0.65 : MIN_SCALE },
      transition: { duration: 0 },
    };
  }

  if (!active) {
    return {
      animate: { scaleY: MIN_SCALE },
      transition: { duration: 0.25, ease: "easeOut" },
    };
  }

  // Tracking real input: follow the amplitude closely enough to feel live.
  if (amplitude !== null) {
    return {
      animate: { scaleY: Math.max(MIN_SCALE, amplitude * peak) },
      transition: { duration: 0.12, ease: "easeOut" },
    };
  }

  // Listening, but no amplitude source wired yet — ambient idle loop.
  return {
    animate: { scaleY: [MIN_SCALE * 1.6, peak] },
    transition: {
      duration: 0.9,
      delay: phase(index) * 0.6,
      repeat: Infinity,
      repeatType: "mirror",
      ease: "easeInOut",
    },
  };
}

type WaveformProps = {
  /** true while audio is being captured. */
  active?: boolean;
  /**
   * Live normalized amplitude, 0–1. Omit it and the bars run an ambient idle
   * loop instead of tracking real input.
   */
  level?: number;
  barCount?: number;
  /**
   * Bars paint with `currentColor`, so the calling route picks the hue with a
   * text token class. This component carries no color of its own.
   */
  className?: string;
};

export function Waveform({
  active = false,
  level,
  barCount = DEFAULT_BAR_COUNT,
  className,
}: WaveformProps) {
  const reduced = useReducedMotion() ?? false;
  const total = Math.max(1, Math.trunc(barCount));
  const amplitude = typeof level === "number" ? Math.min(1, Math.max(0, level)) : null;

  return (
    <div
      data-testid="voice-waveform"
      data-active={active ? "true" : "false"}
      // Decorative. The spoken status belongs to listening-indicator, so keeping
      // this out of the a11y tree avoids announcing the same state twice.
      aria-hidden="true"
      role="presentation"
      className={cn(
        "pointer-events-none flex h-16 w-full items-center justify-center gap-1 overflow-hidden transition-opacity duration-300",
        active ? "opacity-100" : "opacity-40",
        className,
      )}
    >
      {Array.from({ length: total }, (_, index) => {
        const { animate, transition } = barMotion(index, envelope(index, total), {
          active,
          amplitude,
          reduced,
        });
        return (
          <motion.span
            key={index}
            className="h-full w-1.5 shrink-0 origin-center rounded-full bg-current will-change-transform"
            initial={{ scaleY: MIN_SCALE }}
            animate={animate}
            transition={transition}
          />
        );
      })}
    </div>
  );
}
