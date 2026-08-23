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
| Route group | `src/app/(patient)/**` | `src/app/(clinician)/**` |
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
  ratio before approval. Unmeasured is unapproved. Text/fill pairings
  target WCAG AA 4.5:1 (AAA 7:1 preferred). Non-text UI elements —
  focus rings, borders, icons — target WCAG 1.4.11's 3:1 non-text
  minimum instead; don't hold `--ring` to the 4.5:1 text bar.
- Two role tokens must never alias the *same* primitive across the two
  themes — this includes non-color-role tokens like `--ring`, not just
  `--primary`/`--critical`/etc. (Confirmed real instance, Phase 2: patient
  `--primary` and clinician `--ring` both resolved to `--pv-navy-800`.
  Fix is a distinct primitive for clinician `--ring`, own diff, measured
  against both page and card background.) Even though the two themes
  never render on the same page, a shared raw value invites a wrong
  inference from anyone grepping the codebase later. Give each its own
  primitive.
- Need a color not yet defined? Propose the primitive-and-semantic pair
  as its own diff with a measured ratio — don't invent inline hex.
- Logical direction properties only (`border-s`/`border-e`,
  `ps-`/`pe-`, `ms-`/`me-`) — never physical (`border-l/r`, `pl-/pr-`,
  `ml-/mr-`). Both route groups default to `dir="rtl"`.
- Wrap every Latin-script or numeric clinical value (doses, lab units,
  dates) in `<BidiText>` from `components/shared/bidi-text.tsx`. Never
  wrap a whole mixed-language sentence — value only.

**Accepted exception:** Framer Motion `x`/`translateX` values are
inherently physical — the library has no direction-agnostic transform
primitive. Sign is chosen deliberately for RTL (forward motion enters
from the left) and must be commented in-code as intentional. This is
the only place physical motion-sign logic is permitted; it does not
extend to Tailwind physical classes anywhere.

**Path prefix (confirmed):** the repo root for this app is `frontend/`,
with no `src/` layer beneath it. §4 and §7 below use `frontend/...`
paths accordingly.

## 4. Folder structure — scaffolded, extend it, don't restructure it
```
frontend/app/(patient)/…        wizard steps, upload flows
frontend/app/(clinician)/…      dashboard, patient detail, SOAP review
frontend/components/ui/         shadcn primitives — generated, don't hand-edit
frontend/components/patient/…   wizard, voice, upload
frontend/components/clinician/… dashboard, data-table, soap, shortcuts
frontend/components/shared/…    bidi-text, unknown-field, cross-persona utils
frontend/hooks/, frontend/lib/, frontend/types/
```
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
grep -rn "acuity-" "frontend/app/(patient)/" "frontend/components/patient/"

grep -rnE "\-(primary|warning|critical)\b" \
  "frontend/app/(clinician)/" "frontend/components/clinician/" \
  --include="*.tsx" | grep -v "acuity"

grep -rnE "border-l|border-r|\bpl-|\bpr-|\bml-|\bmr-" \
  "frontend/app/(patient)/" "frontend/app/(clinician)/" \
  "frontend/components/patient/" "frontend/components/clinician/"
```
Any match is a failure. Report it and stop — do not auto-fix and
continue in the same pass; fixes get reviewed as their own diff.

**Gate scope (hard rule):** the forbidden pattern is CSS/Tailwind token
*syntax* — a hyphen immediately before the name (`-primary`,
`--critical`, `bg-warning`, `border-s-acuity-critical`) — not the bare
English word. `className="primary-button"` (an unrelated legacy class)
correctly does not match; `bg-primary` or a comment containing
`--acuity-critical` does. This applies inside comments and doc-strings
too, not just executable code — describe a role in plain prose if you
need to reference it without the token syntax.

**Gate implementation rule:** never pass multiple paths through an
unquoted shell variable (`PATHS="a b"; grep ... $PATHS`) — bash and zsh
word-split unquoted variables differently, and this exact pattern
silently produces a gate that always passes regardless of shell. Spell
out every path explicitly in each grep invocation, as above.

## 8. Known Issues — Blocking Phase 3
- **Acuity scale luminance separation.** Machine-measured (Phase 2):
  the five-tier `--acuity-*` scale separates almost entirely by hue —
  relative luminance spans only 0.076–0.163, and the middle of the ramp
  is the worst part: high-vs-moderate is 1.05:1 and moderate-vs-routine
  is 1.02:1. Three of five tiers are effectively one color without hue.
  RESOLVED in `acuity-card.tsx` (Phase 3): tier is now stated three
  ways — glyph shape (octagon/triangle/diamond/circle, unknown as an
  off-ramp square), text code+label, color as reinforcement only.
  `priority-grid.tsx` still owes rank-by-position, not tint alone.

## 9. Settled Content/Copy Conventions
- **Acuity tier codes:** P0=critical and P3=routine are the fixed
  anchors (P0 from clinical convention, P3 forced by "unknown never
  reads as P3/routine"); P1/P2 are therefore forced to high/moderate.
  `unknown` carries no P-number — numbering it P4 would place it one
  step below routine on the numeric ramp, exactly the wrong inference
  the anchors forbid.
- **Labels are Persian**, not literal English — both route groups are
  `dir="rtl"` on Vazirmatn. Format is `{code} · {Persian word}` with
  the code wrapped in `<BidiText>`. An English-language code+word
  example given earlier specified structure only, not literal English
  content.
- **Tier wording avoids diagnostic-sounding language** per §5's "no
  clinical claims in copy" rule — e.g. a procedural/triage word over a
  dramatic risk word for the high tier. Persian medical register is a
  native-speaker judgment call each time; flag new tier or status
  copy for review rather than deciding it unilaterally.
- **`UnknownField` defaults to "value not determined," never "not
  recorded."** The two are different claims — "not recorded" asserts
  the record is empty; "not determined" only says the value isn't
  known. Defaulting to the weaker, more honest claim is the fail-closed
  choice. Don't reuse this string constant for other safety-critical
  labels (e.g. an acuity tier) even if the wording currently matches —
  keep them as separate constants so an unrelated copy edit can't
  silently change both.

## 10. When to stop and ask (non-exhaustive)
- A new color/token is needed that isn't in `globals.css`.
- An acuity mapping is ambiguous (is this finding P1 or P2?).
- A component could plausibly belong to `shared/`, `patient/`, or
  `clinician/` and the right answer isn't obvious from context.
- A design skill's suggested output would violate §3 or §5.

When in doubt, the question costs one message. A silent wrong guess in
a clinical-safety-adjacent UI costs a debugging session, or worse, a
misread dashboard.