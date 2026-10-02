# PreVisit — Reality Audit Directive

## 0. Why this exists
Two independent investigations this week found the same failure: things
get built, pass their own tests, compile clean, and gate clean — but
never connect to the path a real user actually travels. It happened in
this session's frontend rebuild (Phase 3 components fully gate-verified,
mounted on no reachable page). It happened at least twice before in
backend history (Aug 4: Workspace architecture existed but
`clinicalContent` was never wired to the live route, cards rendered
empty; Aug 21: a runtime-integration fix was reportedly applied —
Inference Registry populated, Clinical Intelligence Orchestrator wired
in — but that fix has never been re-proven against the current
repository state). Three occurrences of the identical failure is a
pattern, not a coincidence — this document is a standing methodology
because of that, not a one-off instruction.

## 1. Structure of this document
Part I is the standing methodology — evidence standard, hard
constraints, failure patterns to check, report format. It applies to
any runtime-connectivity audit on this project, this one or a future
one. Part II is this specific pass's target: one path, scoped narrow.

---

# PART I — Standing Methodology

## 2. Ground rule: no claim without evidence
"Implemented," "done," "wired," or "working" are not statuses — they're
conclusions that must be earned per link in a chain. Every link gets
exactly one of four:
```
CONFIRMED     — real execution evidence attached
BROKEN        — traced and shown not to connect
NOT REACHED   — an upstream break prevents testing this link
UNKNOWN       — could not be determined; say so, don't guess
```
Banned as a status, in any report: "probably works," "appears
connected," "seems wired," "should work," "implemented" on its own,
"looks correct." A report using one of these instead of the four above
isn't finished.

Prior reports — including any claiming a fix was already applied — are
historical context, not proof of current repo state. Re-verify from
scratch regardless of what a past report says.

## 3. Evidence standard
A link is `CONFIRMED` only with real execution evidence, never static
inspection alone. Static inspection locates where the path *should*
run; it cannot confirm that it *does*.

Acceptable evidence by layer:
- **Backend:** actual application logs, actual function execution
  output, actual database state, actual API request/response, actual
  dependency-resolution output.
- **Frontend:** actual network request/response, actual browser
  console output, actual rendered DOM/state, a screenshot where
  tooling allows it.
- **Runtime over static, always** — prefer a real running application
  to source reading wherever possible.

**No evidence laundering.** These substitutions are forbidden:
```
pytest passed            ≠  browser displays the feature
TypeScript build passed  ≠  API data reaches the component
component test passed    ≠  the real route renders real data
endpoint exists           ≠  frontend actually consumes it
next build: passed        ≠  anything about runtime data flow
```
A green test suite is evidence about its own tested scope — nothing
past it. 250 passing tests have already coexisted with an empty UI
once in this project.

## 4. Hard constraints for a diagnostic pass
- **No source modification during diagnosis.** Don't fix imports,
  routes, APIs, mappings, DI, models, or tests to make the chain look
  better. This pass establishes current reality; fixing is a separate,
  later pass, explicitly authorized after this report is reviewed.
- **No rebuilding.** If a link is broken, find the smallest existing
  connection that should already make it work:
  ```
  WRONG:   Workspace cards are empty → design a new Workspace architecture
  CORRECT: Workspace cards are empty → trace the API response → find
           clinicalContent is never populated → identify the missing
           mapper → report the exact break
  ```
- **No manufacturing evidence.** Don't weaken assertions, skip failing
  tests, mock an integration test, or edit a golden dataset to make
  the chain appear to pass. Existing tests are evidence about their
  tested scope, not proof of the full runtime path.
- **Temporary instrumentation is allowed.** Request logging, tracing,
  or debug statements may be added if static inspection is
  insufficient — but instrumentation must not change application
  behavior, must be clearly marked temporary, and removed before the
  final report unless explicitly asked to leave it.

## 5. Recurring failure patterns — check for these by name
```
Dead implementation       — code exists, no runtime caller reaches it
Duplicate implementation  — two versions exist, the app uses the wrong one
Registration gap          — exists, never registered in the composition root
DI gap                    — correct service exists, runtime resolves another
API bypass                — frontend calls an older/different endpoint
Mapper bypass              — API returns data, frontend mapper discards it
Mock contamination          — production route receives fixture/default data
Route bypass                 — new route exists, navigation still points old
Build/runtime mismatch        — source has new code, running artifact doesn't
Empty-content fallback         — good response arrives, frontend defaults to empty
Contract mismatch               — compiles and tests agree, real payload fields don't map
Silent failure                   — exceptions/rejections get swallowed into empty UI
```
This project has already produced a confirmed "dead implementation"
(Phase 3 frontend components) and a historical "empty-content
fallback" (Aug 4: cards architecturally complete, `clinicalContent`
never populated). Check for these by name, not just in the abstract.

## 6. Break-point rule
The single most important output of any audit pass is the first
broken link. Once found:
```
1  CONFIRMED
2  CONFIRMED
3  CONFIRMED
4  CONFIRMED
5  BROKEN
6+ NOT REACHED
```
Do not mark downstream links as independently confirmed — execution
cannot cross a break. Inspecting downstream code for context is fine;
its status is `NOT REACHED`, not `CONFIRMED`, until the break above it
is fixed and re-verified.

## 7. Report format
```
A. Executive Finding
   One paragraph, one verdict: CONFIRMED / PARTIALLY CONNECTED /
   BROKEN / UNKNOWN.

B. Evidence Chain — per link:
     Source:
     Destination:
     Expected mechanism:
     Actual mechanism:
     Status:              (one of the four in §2)
     Evidence:
     Exact file/function/route:
     Execution command:
     Relevant output:

C. First Break
   Link N — why, where, what should connect it, what connects instead,
   architectural or merely wiring.

D. Runtime vs Static Matrix
   | Layer | Exists | Runtime caller | Executed | Real data | Evidence |

E. Tests vs Runtime Reality
   What the existing test suite proves, separated explicitly from what
   this pass's runtime execution proves. Name any false sense of
   completion the passing tests created.

F. Scope Expansion
   If upstream tracing entered another subsystem: why it was
   necessary, which link required it, what was inspected, whether it
   was confirmed. No general audit of that subsystem.

G. Fix Boundary (recommendation only — do not apply)
   Recommended smallest fix / files likely involved / why this is the
   smallest fix / what must not be rebuilt.
```

## 8. Relationship to CLAUDE.md
This document governs runtime-connectivity audits; `CLAUDE.md` governs
the frontend UI/UX rebuild (token architecture, patient/clinician
persona separation, the §7 gate, §11's gate-clean-is-not-app-visible
rule). Where an audit touches frontend code, both apply — this
document adds the real-data requirement on top, it doesn't relax
anything CLAUDE.md already requires.

---

# PART II — This Pass's Target

## 9. Scope: one path only
```
Real ClinicalContext
   → Workspace generation/orchestration
   → WorkspacePlan
   → Workspace API
   → Frontend API client/query
   → Frontend mapper/state
   → Clinical Content ViewModel
   → Workspace cards
   → primary doctor route
   → visible clinical information in the browser
```
This is the path flagged as broken twice in project history (Aug 4,
Aug 21) and it's the MVP-critical path per the last product
recommendation. It directly overlaps with this session's frontend
work: `frontend/app/(clinician)/dashboard/page.tsx` was wired with
mock data last turn — replacing that mock with real Workspace API data
is this audit's frontend deliverable for this path, not a separate task.

**Out of scope** unless tracing this path genuinely requires it:
rebuilding OCR, Inference Runtime, Intelligence, or Workspace;
redesigning frontend architecture; a new API; a second ClinicalContext
or Workspace implementation; broad refactoring; visual redesign; new
clinical rules; performance work. If upstream tracing must enter OCR,
inference, or intake to explain a break: state why, trace only the
minimum required, don't turn it into a general audit of that subsystem.

## 10. Initial reconnaissance (before tracing)
Read `CLAUDE.md` and this document in full. Identify — without
modifying anything — the canonical implementation at each layer:
`ClinicalContext`, Workspace orchestration entry point, `WorkspacePlan`,
the Workspace API route, the frontend API client, the frontend
Workspace route, the clinical content mapper, the card components, and
the primary doctor route. Where duplicates exist (old dashboard vs.
new, legacy route vs. current), identify which one the running
application actually uses before tracing further — this is exactly
where "duplicate implementation" (§5) tends to hide.

## 11. The chain for this path
Ten links, using the template in §7.B:
```
1.  Real clinical data → ClinicalContext        (real construction, not a fixture)
2.  ClinicalContext → Workspace orchestration    (same object instance, not a substitute)
3.  Workspace orchestration → WorkspacePlan      (actual execution, populated fields)
4.  WorkspacePlan → Workspace API                (real HTTP request/response captured)
5.  Workspace API → frontend API client          (actual request, not inferred from source)
6.  API response → frontend state/mapping        (accepted vs. discarded vs. defaulted —
                                                   check clinicalContent, ETag handling,
                                                   plan replacement, mapper fallbacks)
7.  Frontend state → Clinical Content ViewModel  (representative real values, not empty)
8.  ViewModel → Workspace cards                  (which cards receive real data — full
                                                   population isn't required, proof the
                                                   canonical path reaches the cards is)
9.  Workspace cards → primary doctor route       (canonical implementation, not a legacy
                                                   page, placeholder, or duplicate route)
10. Primary doctor route → browser               (route resolves, request fires, response
                                                   arrives, cards render — screenshot if
                                                   tooling allows; mark UNKNOWN rather than
                                                   inferred if browser evidence is unavailable)
```

## 12. Acceptance scenario
```
Open/create patient → enter intake → upload a real document → OCR
executes → extraction executes → ClinicalContext changes → inference
executes → intelligence executes → Workspace API returns a populated
plan → frontend fetches it → clinical cards receive real data → a
doctor viewing the dashboard sees the result.
```
Demonstrate this live in a browser — screenshot or precisely described
DOM state, at a stated URL. If a step can't be completed for a
concrete reason (no test document, auth blocking), stop and report
exactly where and why — don't substitute a mocked version of that step
and call the scenario passed.

## 13. Completion criteria for this pass
Done only when: CLAUDE.md and this document were read; the canonical
implementation at each layer was identified; all ten links were
investigated with real evidence where obtainable; the first break was
identified or the chain was proven fully connected; no source was
modified; no test was modified to manufacture evidence; nothing was
rebuilt; no subsystem outside this path was generally audited; every
status is one of the four in §2, nothing vaguer. The report must be
reproducible by another engineer from the evidence alone.

## 14. Absolute rule
```
GATE-CLEAN     is not RUNTIME-CONFIRMED.
IMPLEMENTED    is not CONNECTED.
CONNECTED      is not EXECUTED.
EXECUTED       is not USER-VISIBLE.
```
Final proof reaches all the way: real clinical data → real runtime
execution → real API response → real frontend consumption → real
clinical view model → real Workspace cards → real primary doctor route
→ real browser visibility. Don't claim success until the evidence
chain supports every link of that, not most of it.