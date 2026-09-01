import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Legacy brand scale — consumed by existing pages, left as-is.
        clinical: "#F8F9FA",
        trust: "#1B3B5A",
        mint: "#A8E6CF",
        danger: "#DC2626",
        ink: "#0F172A",
        tai: {
          navy: "hsl(var(--tai-navy) / <alpha-value>)",
          "navy-strong": "hsl(var(--tai-navy-strong) / <alpha-value>)",
          teal: "hsl(var(--tai-teal) / <alpha-value>)",
          "teal-bright": "hsl(var(--tai-teal-bright) / <alpha-value>)",
          "teal-soft": "hsl(var(--tai-teal-soft) / <alpha-value>)",
          surface: "hsl(var(--tai-neutral-25) / <alpha-value>)",
          muted: "hsl(var(--tai-neutral-100) / <alpha-value>)",
          border: "hsl(var(--tai-neutral-200) / <alpha-value>)",
          subdued: "hsl(var(--tai-neutral-500) / <alpha-value>)",
          text: "hsl(var(--tai-neutral-950) / <alpha-value>)",
        },
        semantic: {
          success: "hsl(var(--tai-success) / <alpha-value>)",
          warning: "hsl(var(--tai-warning) / <alpha-value>)",
          critical: "hsl(var(--tai-critical) / <alpha-value>)",
          info: "hsl(var(--tai-info) / <alpha-value>)",
          unknown: "hsl(var(--tai-unknown) / <alpha-value>)",
          missing: "hsl(var(--tai-missing) / <alpha-value>)",
          unverified: "hsl(var(--tai-unverified) / <alpha-value>)",
          verified: "hsl(var(--tai-verified) / <alpha-value>)",
          conflict: "hsl(var(--tai-conflict) / <alpha-value>)",
          resolved: "hsl(var(--tai-resolved) / <alpha-value>)",
          stale: "hsl(var(--tai-stale) / <alpha-value>)",
          ai: "hsl(var(--tai-ai) / <alpha-value>)",
        },

        // Patient semantic tokens — resolve only under .patient-theme.
        primary: {
          DEFAULT: "hsl(var(--primary) / <alpha-value>)",
          hover: "hsl(var(--primary-hover) / <alpha-value>)",
          foreground: "hsl(var(--primary-foreground) / <alpha-value>)",
          surface: "hsl(var(--primary-surface) / <alpha-value>)",
        },
        accent: {
          DEFAULT: "hsl(var(--accent) / <alpha-value>)",
          foreground: "hsl(var(--accent-foreground) / <alpha-value>)",
        },
        warning: {
          DEFAULT: "hsl(var(--warning) / <alpha-value>)",
          foreground: "hsl(var(--warning-foreground) / <alpha-value>)",
          surface: "hsl(var(--warning-surface) / <alpha-value>)",
        },
        critical: {
          DEFAULT: "hsl(var(--critical) / <alpha-value>)",
          foreground: "hsl(var(--critical-foreground) / <alpha-value>)",
          surface: "hsl(var(--critical-surface) / <alpha-value>)",
        },

        // Safety-critical. Resolves only under .clinician-theme, and is never
        // used decoratively anywhere (§3). Tier list approved per §9.
        acuity: {
          critical: "hsl(var(--acuity-critical) / <alpha-value>)",
          high: "hsl(var(--acuity-high) / <alpha-value>)",
          moderate: "hsl(var(--acuity-moderate) / <alpha-value>)",
          routine: "hsl(var(--acuity-routine) / <alpha-value>)",
          unknown: "hsl(var(--acuity-unknown) / <alpha-value>)",
          foreground: "hsl(var(--acuity-foreground) / <alpha-value>)",
        },

        ring: "hsl(var(--ring) / <alpha-value>)",
      },
      boxShadow: {
        soft: "0 20px 45px -30px rgba(27, 59, 90, 0.35)",
        glass: "0 12px 30px -18px rgba(15, 23, 42, 0.18)",
        "tai-sm": "var(--tai-shadow-sm)",
        "tai-md": "var(--tai-shadow-md)",
      },
      fontFamily: {
        sans: ["var(--tai-font-sans)"],
        latin: ["var(--tai-font-latin)"],
      },
      spacing: {
        "tai-1": "var(--tai-space-1)",
        "tai-2": "var(--tai-space-2)",
        "tai-3": "var(--tai-space-3)",
        "tai-4": "var(--tai-space-4)",
        "tai-5": "var(--tai-space-5)",
        "tai-6": "var(--tai-space-6)",
        "tai-8": "var(--tai-space-8)",
      },
      borderRadius: {
        medical: "1.5rem",
        "tai-sm": "var(--tai-radius-sm)",
        "tai-md": "var(--tai-radius-md)",
        "tai-lg": "var(--tai-radius-lg)",
      },
      keyframes: {
        blink: {
          "0%, 100%": { opacity: "0.35", transform: "scale(0.92)" },
          "50%": { opacity: "1", transform: "scale(1.08)" },
        },
        wave: {
          "0%": { transform: "translateX(-45%)" },
          "100%": { transform: "translateX(0%)" },
        },
        shakeX: {
          "0%, 100%": { transform: "translateX(0)" },
          "20%": { transform: "translateX(-4px)" },
          "40%": { transform: "translateX(4px)" },
          "60%": { transform: "translateX(-3px)" },
          "80%": { transform: "translateX(3px)" },
        },
        fadeIn: {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        blink: "blink 1.4s ease-in-out infinite",
        wave: "wave 2.4s linear infinite",
        shakeX: "shakeX 420ms ease-in-out",
        fadeIn: "fadeIn 260ms ease-out forwards",
      },
      transitionTimingFunction: {
        spring: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
