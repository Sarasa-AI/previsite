# TreatAI Design System

TreatAI's frontend foundation is Persian-first, RTL by default, clinically explicit, and compatible with the existing patient and clinician themes.

## Tokens

Raw tokens live in `app/globals.css` under the `--tai-*` namespace. Tailwind exposes stable `tai.*` foundation colors and `semantic.*` foreground colors. Existing `clinical`, `trust`, `mint`, `danger`, patient-theme, and clinician acuity tokens remain compatibility contracts.

Token groups cover brand navy/teal/white, neutral surfaces, semantic states, spacing, radii, borders, shadows, Persian/Latin font stacks, and tabular numerals. Components should use semantic roles instead of raw hues.

## Clinical states

`StatusBadge` supports success, warning, critical, info, unknown, missing, unverified, verified, conflict, resolved, stale, and AI-generated. Every state includes visible text plus a symbol; color must never be the only carrier of meaning. Callers must provide the exact clinical label and must not translate unknown into negative, missing into normal, conflict into resolved, or generated content into verified fact.

## RTL and bidi

Persian prose inherits RTL and Vazirmatn. Use `BidiText` for unknown-direction source text, `MrnValue` for identifiers, `DateValue` for dates, `NumericValue` for numbers, `DoseValue` for dose strings, and `UnitValue` for units. These wrappers use `bdi`, LTR isolation and tabular numerals so mixed Persian/English content does not reorder adjacent punctuation.

## Primitives

Import from `@/components/ui`: `Button`, `IconButton`, `Badge`, `StatusBadge`, `Card`, `Input`, `Select`, `Tooltip`, `Tabs`, `Alert`, `Skeleton`, and `StatePanel`. Buttons cover hover, focus, active, disabled and loading. Inputs/selects cover hover, focus and disabled. Motion respects `prefers-reduced-motion` through Tailwind's `motion-reduce` variants.

The design system is additive. It does not determine Workspace layout, clinical meaning, visibility, priority, or data availability. Feature components remain responsible for choosing truthful labels from existing ViewModels.
