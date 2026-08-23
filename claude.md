# PreVisit — UI/UX & Frontend Standing Directive

## 0. How to use this file
This is the persistent directive for all UI/UX and frontend work in this
repo. Read it in full before starting any task, and re-check it before
marking any phase complete.

If a specialized design skill (e.g. a locally installed UI/UX skill) is
available in this environment, use it for aesthetic judgment — palette
refinement, motion choices, layout composition. The rules in this file are
the non-negotiable baseline that skill's output must still satisfy. They
are not optional style suggestions and are not superseded by any skill's
default behavior.

## 1. Mission
One sentence, never lose sight of it: **a physician must be able to
understand a complex patient's state from the dashboard in 3–5 seconds.**
Every UI decision is judged against whether it moves toward or away from
that.

## 2. Two personas — architecturally separate, never merged

| | Patient Portal | Clinician Dashboard |
|---|---|---|
| Audience | Patients, incl. elderly / low tech literacy | Doctors under time pressure / burnout |
| Design mode | Mobile-first, progressive disclosure | Desktop-first, data-dense |
| Route group | `frontend/app/(patient)/**` | `frontend/app/(clinician)/**` |
| Theme class | `.patient-theme` | `.clinician-theme` |
| Color tokens | `--primary`, `--accent`, `--warning`, `--critical` | `--acuity-critical` … `--acuity-unknown` |
| Failure mode if violated | Elderly patient overwhelmed / misreads urgency | Doctor misreads acuity → patient safety risk |

Never share a component between the two that carries persona-specific
color logic. Shared components (`components/shared/**`) take color via
`className` props from the calling route — they hold no theme opinion of
their own.

## 3. Token system — three-layer model (confirmed via Phase 1 execution)
Source of truth: `globals.css`, `tailwind.config.ts` — read them, don't
regenerate them. Path-prefix warning at the end of this section.

Layers, outside-in:
1. **Primitives** (`--pv-*`) — persona-neutral raw values (e.g.
   `--pv-red-600`, `--pv-red-700`). Live at `:root`. No `--primary`,
   `--acuity-*`, or any semantic name may appear among them — that's
   what makes "theme tokens never at :root" hold literally, not just by
   convention.
2. **Semantic role tokens** — `--primary`, `--accent`, `--warning`,
   `--critical` under `.patient-theme`; `--acuity-critical` …
   `--acuity-unknown` under `.clinician-theme`. Each references a
   primitive and may deliberately diverge from the "obvious" brand
   primitive when contrast measurement demands it — e.g. `--critical`
   maps to `--pv-red-700`, not brand `#DC2626`, because the brand red
   measured 3.95:1 against the critical surface (a real AA failure).
   `#DC2626` still exists as `--pv-red-600` for solid-fill use elsewhere.
3. **Role companions** — each semantic role carries `-foreground` and
   `-surface` variants (three tokens per role, not one), because a
   single hue can't serve both fill and text at AA. This is the correct
   model now — update expectations to match it rather than treating it
   as scope creep on the original one-token-per-role naming.

Rules:
- Semantic and companion tokens never appear at `:root`, and never
  cross into the other route group's files.
- `--acuity-*` is safety-critical. Never reused for decoration.
- Every semantic-to-primitive assignment carries a measured contrast
  ratio before approval. Unmeasured is unapproved.
- Two role tokens must never alias the *same* primitive across the two
  themes — even though the two themes never render on the same page, a
  shared raw value invites a wrong inference from anyone grepping the
  codebase later. Give each its own primitive. The real Phase 1 instance
  was patient `--critical` and clinician `--acuity-critical` both
  resolving to `--pv-red-700`; resolved by moving `--acuity-critical` to
  its own `--pv-red-800`. (`--acuity-unknown` was never red — it is
  `--pv-violet-700`, deliberately off the risk ramp.)
- Need a color not yet defined? Propose the primitive-and-semantic pair
  as its own diff with a measured ratio — don't invent inline hex.
- Logical direction properties only (`border-s`/`border-e`,
  `ps-`/`pe-`, `ms-`/`me-`) — never physical (`border-l/r`, `pl-/pr-`,
  `ml-/mr-`). Both route groups default to `dir="rtl"`.
- Wrap every Latin-script or numeric clinical value (doses, lab units,
  dates) in `<BidiText>` from `components/shared/bidi-text.tsx`. Never
  wrap a whole mixed-language sentence — value only.

**Path-prefix note (RESOLVED, Phase 1 execution):** verified against the
working tree. `frontend/` is the app root and sits directly at the repo
root. A `src/` layer **does** exist beneath it (`frontend/src/`), so the
answer is not a clean "no src/ layer" — but `frontend/src/app/` is *not*
the router: Next.js uses root `app/` whenever both exist, so
`frontend/app/` is live and `frontend/src/app/` (api routes only) is dead
code. `frontend/src/` otherwise holds pre-existing non-router modules
(`modules/workspace/`, `hooks/`, `lib/`, `schemas/`, `shared/`).
UI work therefore lands in `frontend/app/` and `frontend/components/`.
Note `frontend/hooks/` and `frontend/types/` do not exist; `frontend/lib/`
does. §4 and §7 below are corrected to match.

## 4. Folder structure — scaffolded, extend it, don't restructure it
```
frontend/app/(patient)/…        wizard steps, upload flows
frontend/app/(clinician)/…      dashboard, patient detail, SOAP review
frontend/components/ui/         shadcn primitives — generated, don't hand-edit
frontend/components/patient/…   wizard, voice, upload
frontend/components/clinician/… dashboard, data-table, soap, shortcuts
frontend/components/shared/…    bidi-text, unknown-field, cross-persona utils
frontend/lib/                   cn helper, api clients
```
Pre-existing, not part of this scaffold — extend only with cause:
`frontend/src/modules/workspace/**` (clinician workspace module),
`frontend/src/{hooks,lib,schemas,shared}/`, `frontend/src/app/api/**`
(dead — Next ignores it while root `app/` exists).

Import alias: `@/*` → `frontend/*` (per `frontend/tsconfig.json`), so
`@/lib/utils` resolves to `frontend/lib/utils.ts`, not `frontend/src/lib/`.

If a new file doesn't obviously belong in one of these, stop and ask
where it goes rather than guessing.

## 5. Non-negotiable rules for every phase
1. **Fail-closed over guessing.** If a design or data-mapping decision is
   ambiguous (which acuity tier, which token, which persona a component
   belongs to), stop and ask. Do not pick the plausible-looking answer
   and continue.
2. **No blank fields for missing data.** Render the literal text
   "نامشخص" / "ثبت نشده" via a dedicated component, never an empty div —
   this mirrors the OCR pipeline's confidence-gated fallback and must
   hold in the UI too.
3. **Accessibility floor, unannounced but always met:** visible keyboard
   focus rings, `aria-label` on every icon-only control, `prefers-reduced-motion`
   respected on all Framer Motion transitions, full keyboard reachability
   for every clinician action (this dashboard's users are burned-out
   doctors — mouse-only flows are a regression).
4. **No clinical claims in copy.** UI text organizes and surfaces data;
   it never phrases anything as a diagnosis or recommendation. This
   matches the platform's current "no DDx, no treatment suggestion" scope.

## 6. Phase gates — execute in order, do not skip ahead

**Phase 1 — Foundation: COMPLETE.**
`globals.css`, `tailwind.config.ts`, root `layout.tsx`, both route-group
layouts, `bidi-text.tsx`, `lib/utils.ts`. Re-run the verification gate
below before touching Phase 2; don't assume it's still valid unmodified.

**Phase 2 — Patient Wizard**
`question-card.tsx`, `amber-box.tsx`, `step-progress.tsx`,
`voice/waveform.tsx` + `voice/listening-indicator.tsx` (Framer Motion,
respects reduced-motion), `upload/drug-photo-capture.tsx`,
`upload/lab-photo-capture.tsx`. Constraints: 1–2 questions visible per
screen, `h-14` minimum touch targets, transitions between wizard steps
use the shared step-progress state, not per-component animation logic.

**Phase 3 — Clinician Dashboard Core**
`dashboard/acuity-card.tsx` (reads `--acuity-*` only), `dashboard/priority-grid.tsx`
(P0 sorts to top, unknown never visually reads as P3/routine),
`data-table/medication-table.tsx` + `data-table/lab-table.tsx`
(TanStack Table + shadcn table primitive, `tabular-nums` on all numeric
columns), `shortcuts/command-palette.tsx` (⌘K).

**Phase 4 — SOAP & Clinical Documentation**
`soap/soap-editor.tsx`, `soap/citation-popover.tsx`, one-click
approve/edit actions on generated SOAP notes, citations rendered
inline and traceable to source.

**Phase 5 — Cross-Cutting Audit**
Accessibility pass, reduced-motion pass, responsive pass — patient side
down to a 360px viewport, clinician side desktop-first with graceful
degradation to tablet, not phone.

Each phase ends with the gate in §7 before starting the next. Report the
gate result explicitly — pass or fail with specifics — never proceed
past a fail silently.

## 7. Verification gate (run at the end of every phase)
```
grep -rn "acuity-" frontend/app/\(patient\)/                  # expect: no matches
grep -rnE "primary|warning|critical" frontend/app/\(clinician\)/ \
  --include="*.tsx" | grep -v "acuity"                        # expect: no matches
grep -rnE "border-l|border-r|\bpl-|\bpr-|\bml-|\bmr-" \
  frontend/app/\(patient\)/ frontend/app/\(clinician\)/        # expect: no matches
```
Any match is a failure. Report it and stop — do not auto-fix and
continue in the same pass; fixes get reviewed as their own diff.

**PROPOSED EXTENSION — not yet approved, do not treat as the gate.**
The three commands above scan only the route groups. Every persona
component actually lives under `frontend/components/patient/**` and
`frontend/components/clinician/**`, which those paths never reach — so as
written the gate inspects layouts and pages only and would pass a
persona-token violation sitting in any component. Proposed replacement
scope, pending sign-off:
```
PATIENT="frontend/app/(patient)/ frontend/components/patient/"
CLINICIAN="frontend/app/(clinician)/ frontend/components/clinician/"
grep -rn "acuity-" $PATIENT                                   # expect: no matches
grep -rnE "primary|warning|critical" $CLINICIAN \
  --include="*.tsx" | grep -v "acuity"                        # expect: no matches
grep -rnE "border-l|border-r|\bpl-|\bpr-|\bml-|\bmr-" \
  $PATIENT $CLINICIAN                                         # expect: no matches
```
Note `border-r` also matches `border-red-*`; use `border-r-` or
`border-r\b` to avoid false positives when reading results.

## 8. Known Issues — Blocking Phase 3
- **Acuity scale luminance separation.** The five-tier `--acuity-*`
  scale (critical/high/moderate/routine/unknown) separates almost
  entirely by hue: machine-measured relative luminance spans only
  0.076–0.163, with adjacent tiers 1.02–1.60:1 apart — and the
  high→moderate→routine run is 1.05:1 and 1.02:1, effectively
  indistinguishable without hue. Under deuteranopia or in grayscale that
  ramp collapses. Given this scale's own stated failure mode
  ("doctor misreads acuity → patient safety risk"), color cannot be the
  only channel carrying that signal. `acuity-card.tsx` and
  `priority-grid.tsx` must ship with a tier glyph plus text label, and
  `priority-grid` must rank by position, not tint alone. This is a hard
  gate condition for Phase 3 sign-off, not a nice-to-have — it survives
  here even if the CSS comment referencing it gets lost in a refactor.

## 9. When to stop and ask (non-exhaustive)
- A new color/token is needed that isn't in `globals.css`.
- An acuity mapping is ambiguous (is this finding P1 or P2?).
- A component could plausibly belong to `shared/`, `patient/`, or
  `clinician/` and the right answer isn't obvious from context.
- A design skill's suggested output would violate §3 or §5.

When in doubt, the question costs one message. A silent wrong guess in
a clinical-safety-adjacent UI costs a debugging session, or worse, a
misread dashboard.