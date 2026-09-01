"use client";

import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import { AlertCircle, Bot, CheckCircle2, CircleHelp, Clock3, FileQuestion, Info, Loader2, ShieldAlert, TriangleAlert, UserCheck, XCircle, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export type SemanticState =
  | "success" | "warning" | "critical" | "info"
  | "unknown" | "missing" | "unverified" | "verified"
  | "conflict" | "resolved" | "stale" | "ai-generated"
  | "normal" | "abnormal" | "unavailable" | "draft" | "physician-confirmed";

const stateStyles: Record<SemanticState, string> = {
  success: "border-[hsl(var(--tai-success)/.35)] bg-[hsl(var(--tai-success-surface))] text-[hsl(var(--tai-success))]",
  warning: "border-[hsl(var(--tai-warning)/.35)] bg-[hsl(var(--tai-warning-surface))] text-[hsl(var(--tai-warning))]",
  critical: "border-[hsl(var(--tai-critical)/.35)] bg-[hsl(var(--tai-critical-surface))] text-[hsl(var(--tai-critical))]",
  info: "border-[hsl(var(--tai-info)/.35)] bg-[hsl(var(--tai-info-surface))] text-[hsl(var(--tai-info))]",
  unknown: "border-[hsl(var(--tai-unknown)/.35)] bg-[hsl(var(--tai-unknown-surface))] text-[hsl(var(--tai-neutral-700))]",
  missing: "border-[hsl(var(--tai-missing)/.35)] bg-[hsl(var(--tai-missing-surface))] text-[hsl(var(--tai-missing))]",
  unverified: "border-[hsl(var(--tai-unverified)/.35)] bg-[hsl(var(--tai-unverified-surface))] text-[hsl(var(--tai-unverified))]",
  verified: "border-[hsl(var(--tai-verified)/.35)] bg-[hsl(var(--tai-verified-surface))] text-[hsl(var(--tai-verified))]",
  conflict: "border-[hsl(var(--tai-conflict)/.35)] bg-[hsl(var(--tai-conflict-surface))] text-[hsl(var(--tai-conflict))]",
  resolved: "border-[hsl(var(--tai-resolved)/.35)] bg-[hsl(var(--tai-resolved-surface))] text-[hsl(var(--tai-resolved))]",
  stale: "border-[hsl(var(--tai-stale)/.35)] bg-[hsl(var(--tai-stale-surface))] text-[hsl(var(--tai-stale))]",
  "ai-generated": "border-[hsl(var(--tai-ai)/.35)] bg-[hsl(var(--tai-ai-surface))] text-[hsl(var(--tai-ai))]",
  normal: "border-[hsl(var(--tai-success)/.35)] bg-[hsl(var(--tai-success-surface))] text-[hsl(var(--tai-success))]",
  abnormal: "border-[hsl(var(--tai-critical)/.35)] bg-[hsl(var(--tai-critical-surface))] text-[hsl(var(--tai-critical))]",
  unavailable: "border-tai-border bg-tai-surface text-tai-subdued",
  draft: "border-[hsl(var(--tai-unverified)/.35)] bg-[hsl(var(--tai-unverified-surface))] text-[hsl(var(--tai-unverified))]",
  "physician-confirmed": "border-[hsl(var(--tai-verified)/.35)] bg-[hsl(var(--tai-verified-surface))] text-[hsl(var(--tai-verified))]",
};

const stateSymbols: Record<SemanticState, string> = {
  success: "✓", warning: "!", critical: "!", info: "i", unknown: "?",
  missing: "–", unverified: "?", verified: "✓", conflict: "!", resolved: "✓",
  stale: "↻", "ai-generated": "AI",
  normal: "✓", abnormal: "!", unavailable: "×", draft: "D", "physician-confirmed": "✓",
};

export type ClinicalValueStateKind =
  | "confirmed" | "normal" | "abnormal" | "unknown" | "missing" | "unavailable"
  | "not-verified" | "conflict" | "resolved" | "stale" | "ai-generated" | "draft"
  | "confirmed-by-physician";

const clinicalStateConfig: Record<ClinicalValueStateKind, { semantic: SemanticState; label: string; Icon: LucideIcon }> = {
  confirmed: { semantic: "verified", label: "تاییدشده", Icon: CheckCircle2 },
  normal: { semantic: "normal", label: "طبیعی", Icon: CheckCircle2 },
  abnormal: { semantic: "abnormal", label: "غیرطبیعی", Icon: AlertCircle },
  unknown: { semantic: "unknown", label: "نامشخص", Icon: CircleHelp },
  missing: { semantic: "missing", label: "ثبت نشده", Icon: FileQuestion },
  unavailable: { semantic: "unavailable", label: "در دسترس نیست", Icon: XCircle },
  "not-verified": { semantic: "unverified", label: "تایید نشده", Icon: ShieldAlert },
  conflict: { semantic: "conflict", label: "تعارض حل‌نشده", Icon: TriangleAlert },
  resolved: { semantic: "resolved", label: "حل‌شده", Icon: CheckCircle2 },
  stale: { semantic: "stale", label: "قدیمی", Icon: Clock3 },
  "ai-generated": { semantic: "ai-generated", label: "تولیدشده با AI", Icon: Bot },
  draft: { semantic: "draft", label: "پیش‌نویس", Icon: FileQuestion },
  "confirmed-by-physician": { semantic: "physician-confirmed", label: "تاییدشده توسط پزشک", Icon: UserCheck },
};

export function ClinicalValueState({ state, label, announce = false, className, ...props }: Omit<React.HTMLAttributes<HTMLSpanElement>, "children"> & { state: ClinicalValueStateKind; label?: React.ReactNode; announce?: boolean }) {
  const config = clinicalStateConfig[state];
  return <span role={announce ? "status" : undefined} aria-live={announce ? "polite" : undefined} aria-label={`وضعیت بالینی: ${typeof label === "string" ? label : config.label}`} data-clinical-value-state={state} data-semantic-state={config.semantic} className={cn("inline-flex items-center gap-1.5 rounded-tai-sm border px-2 py-0.5 text-xs font-semibold", stateStyles[config.semantic], className)} {...props}><config.Icon className="size-3.5 shrink-0" aria-hidden={true} />{label ?? config.label}</span>;
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(function Button(
  { className, variant = "primary", size = "md", loading = false, disabled, children, ...props }, ref,
) {
  const variants = {
    primary: "border-tai-navy bg-tai-navy text-white hover:bg-tai-navy-strong active:bg-tai-navy-strong",
    secondary: "border-tai-border bg-white text-tai-navy hover:bg-tai-surface active:bg-tai-muted",
    ghost: "border-transparent bg-transparent text-tai-navy hover:bg-tai-muted active:bg-tai-border/60",
    danger: "border-semantic-critical bg-semantic-critical text-white hover:opacity-90 active:opacity-80",
  };
  const sizes = { sm: "min-h-8 px-2.5 text-xs", md: "min-h-10 px-3.5 text-sm", lg: "min-h-11 px-4 text-base" };
  return <button ref={ref} disabled={disabled || loading} aria-busy={loading || undefined} className={cn("inline-flex items-center justify-center gap-2 rounded-tai-md border font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-tai-navy focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50", variants[variant], sizes[size], className)} {...props}>{loading ? <Loader2 className="size-4 animate-spin motion-reduce:animate-none" aria-hidden="true" /> : null}{children}</button>;
});

export const IconButton = React.forwardRef<HTMLButtonElement, ButtonProps & { "aria-label": string }>(function IconButton({ className, children, ...props }, ref) {
  return <Button ref={ref} size="sm" className={cn("size-9 shrink-0 p-0", className)} {...props}>{children}</Button>;
});

export function Badge({ className, children, ...props }: React.HTMLAttributes<HTMLSpanElement>) {
  return <span className={cn("inline-flex items-center rounded-tai-sm border border-tai-border bg-tai-surface px-2 py-0.5 text-xs font-medium text-tai-text", className)} {...props}>{children}</span>;
}

export function StatusBadge({ state, children, className, ...props }: React.HTMLAttributes<HTMLSpanElement> & { state: SemanticState }) {
  return <span className={cn("inline-flex items-center gap-1.5 rounded-tai-sm border px-2 py-0.5 text-xs font-semibold", stateStyles[state], className)} data-semantic-state={state} {...props}><span aria-hidden="true" className="min-w-3 text-center font-bold">{stateSymbols[state]}</span>{children}</span>;
}

export const Card = React.forwardRef<HTMLElement, React.HTMLAttributes<HTMLElement>>(function Card({ className, ...props }, ref) {
  return <article ref={ref} className={cn("rounded-tai-lg border border-tai-border bg-white p-4 text-tai-text shadow-[var(--tai-shadow-sm)]", className)} {...props} />;
});

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(function Input({ className, ...props }, ref) {
  return <input ref={ref} className={cn("min-h-10 w-full rounded-tai-md border border-tai-border bg-white px-3 text-sm text-tai-text outline-none placeholder:text-tai-subdued hover:border-tai-subdued focus-visible:border-tai-navy focus-visible:ring-2 focus-visible:ring-tai-navy/20 disabled:cursor-not-allowed disabled:bg-tai-muted disabled:opacity-70", className)} {...props} />;
});

export const Select = React.forwardRef<HTMLSelectElement, React.SelectHTMLAttributes<HTMLSelectElement>>(function Select({ className, ...props }, ref) {
  return <select ref={ref} className={cn("min-h-10 w-full rounded-tai-md border border-tai-border bg-white px-3 text-sm text-tai-text outline-none hover:border-tai-subdued focus-visible:border-tai-navy focus-visible:ring-2 focus-visible:ring-tai-navy/20 disabled:cursor-not-allowed disabled:bg-tai-muted disabled:opacity-70", className)} {...props} />;
});

export function Tooltip({ label, children }: { label: string; children: React.ReactNode }) {
  const tooltipId = React.useId();
  return <span className="group relative inline-flex"><span tabIndex={0} aria-describedby={tooltipId}>{children}</span><span id={tooltipId} role="tooltip" className="pointer-events-none absolute bottom-full start-1/2 z-50 mb-2 hidden w-max max-w-64 -translate-x-1/2 rounded-tai-sm bg-tai-text px-2 py-1 text-xs text-white shadow-md group-hover:block group-focus-within:block">{label}</span></span>;
}

export const Tabs = TabsPrimitive.Root;
export const TabsList = React.forwardRef<React.ElementRef<typeof TabsPrimitive.List>, React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>>(function TabsList({ className, ...props }, ref) { return <TabsPrimitive.List ref={ref} className={cn("inline-flex min-h-10 items-center gap-1 rounded-tai-md border border-tai-border bg-tai-muted p-1", className)} {...props} />; });
export const TabsTrigger = React.forwardRef<React.ElementRef<typeof TabsPrimitive.Trigger>, React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>>(function TabsTrigger({ className, ...props }, ref) { return <TabsPrimitive.Trigger ref={ref} className={cn("rounded-tai-sm px-3 py-1.5 text-sm font-medium text-tai-subdued outline-none hover:text-tai-text focus-visible:ring-2 focus-visible:ring-tai-navy data-[state=active]:bg-white data-[state=active]:text-tai-navy data-[state=active]:shadow-sm disabled:opacity-50", className)} {...props} />; });
export const TabsContent = React.forwardRef<React.ElementRef<typeof TabsPrimitive.Content>, React.ComponentPropsWithoutRef<typeof TabsPrimitive.Content>>(function TabsContent({ className, ...props }, ref) { return <TabsPrimitive.Content ref={ref} className={cn("mt-3 outline-none focus-visible:ring-2 focus-visible:ring-tai-navy", className)} {...props} />; });

export function Alert({ state = "info", title, children, className }: React.HTMLAttributes<HTMLDivElement> & { state?: "success" | "warning" | "critical" | "info"; title: React.ReactNode }) {
  const Icon = state === "success" ? CheckCircle2 : state === "warning" ? TriangleAlert : state === "critical" ? AlertCircle : Info;
  return <div role={state === "critical" ? "alert" : "status"} className={cn("flex items-start gap-3 rounded-tai-md border p-3", stateStyles[state], className)}><Icon className="mt-0.5 size-4 shrink-0" aria-hidden="true" /><div className="min-w-0"><div className="text-sm font-semibold">{title}</div>{children ? <div className="mt-1 text-sm text-current/90">{children}</div> : null}</div></div>;
}

export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={cn("animate-pulse rounded-tai-sm bg-tai-muted motion-reduce:animate-none", className)} {...props} />;
}

export type ClinicalUiState = "loading" | "empty" | "partial" | "error" | "unknown" | "missing" | "unavailable" | "conflict" | "not-verified" | "stale";

const panelClinicalState: Partial<Record<ClinicalUiState, ClinicalValueStateKind>> = {
  partial: "unknown", unknown: "unknown", missing: "missing", unavailable: "unavailable",
  conflict: "conflict", "not-verified": "not-verified", stale: "stale",
};

export function StatePanel({ kind, title, message, action, className }: { kind: ClinicalUiState; title: string; message?: string; action?: React.ReactNode; className?: string }) {
  const urgent = kind === "error" || kind === "conflict";
  const clinicalState = panelClinicalState[kind];
  return <div role={urgent ? "alert" : "status"} aria-live={urgent ? "assertive" : "polite"} aria-busy={kind === "loading" || undefined} data-clinical-ui-state={kind} className={cn("rounded-tai-md border border-dashed border-tai-border bg-tai-surface px-4 py-6 text-center", kind === "error" && "border-[hsl(var(--tai-critical)/.35)] bg-[hsl(var(--tai-critical-surface))]", className)}>{kind === "loading" ? <Loader2 className="mx-auto mb-2 size-5 animate-spin text-tai-navy motion-reduce:animate-none" aria-hidden="true" /> : null}{clinicalState ? <ClinicalValueState state={clinicalState} className="mb-2" /> : null}<p className="text-sm font-semibold text-tai-text">{title}</p>{message ? <p className="mt-1 text-xs text-tai-subdued">{message}</p> : null}{action ? <div className="mt-3 flex justify-center">{action}</div> : null}</div>;
}
