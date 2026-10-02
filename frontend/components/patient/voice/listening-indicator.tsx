"use client";

import { motion, useReducedMotion } from "framer-motion";
import { cn } from "@/lib/utils";
import { Waveform } from "./waveform";

/**
 * The spoken-answer status surface: what the microphone is doing right now, in
 * words, with the waveform as reinforcement rather than as the signal.
 *
 * The waveform itself is `aria-hidden`, so this component owns the single live
 * region describing the state — otherwise the same change gets announced twice.
 * An indicator only: it renders no record/stop control, so the wizard keeps the
 * mic button (and its permission prompt) in one place.
 */

export type ListeningState = "idle" | "listening" | "processing" | "error";

/** Plain-language status text. No clinical phrasing, no diagnosis (§5.4). */
const STATE_TEXT: Record<ListeningState, string> = {
  idle: "برای شروع صحبت، دکمه میکروفون را بزنید",
  listening: "در حال شنیدن… حالا صحبت کنید",
  processing: "در حال آماده‌سازی پاسخ شما…",
  error: "صدا ضبط نشد. لطفاً دوباره تلاش کنید",
};

type ListeningIndicatorProps = {
  state: ListeningState;
  /** Live normalized amplitude 0–1, if an analyser is wired up. */
  level?: number;
  /** Overrides the default status line — e.g. a specific permission message. */
  message?: string;
  className?: string;
};

export function ListeningIndicator({
  state,
  level,
  message,
  className,
}: ListeningIndicatorProps) {
  const reduced = useReducedMotion() ?? false;
  const listening = state === "listening";
  const text = message ?? STATE_TEXT[state];

  // The waveform paints with currentColor, so the tone is set here on the
  // wrapper: critical for a failed capture, primary for everything else.
  const tone = state === "error" ? "text-critical" : "text-primary";

  return (
    <div
      data-testid="listening-indicator"
      data-state={state}
      className={cn("flex flex-col items-center gap-3", tone, className)}
    >
      <Waveform active={listening} level={listening ? level : undefined} className="max-w-xs" />

      <p
        // polite, not assertive: these updates should queue behind whatever the
        // patient is currently having read to them, not interrupt it.
        role="status"
        aria-live="polite"
        className="flex items-center gap-2 text-center text-base font-medium leading-relaxed"
      >
        <motion.span
          aria-hidden="true"
          className={cn(
            "h-2.5 w-2.5 shrink-0 rounded-full",
            state === "idle" ? "bg-slate-300" : "bg-current",
          )}
          animate={listening && !reduced ? { opacity: [0.35, 1], scale: [0.9, 1.1] } : { opacity: 1, scale: 1 }}
          transition={
            listening && !reduced
              ? { duration: 0.7, repeat: Infinity, repeatType: "mirror", ease: "easeInOut" }
              : { duration: 0 }
          }
        />
        {text}
      </p>
    </div>
  );
}
