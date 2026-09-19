# Reading Result / Interpretation Flow — Design Decision (Step 54)

**Status:** Read-only design/decision step. No frontend, backend, schema, migration, or dependency file was modified in producing this report. Nothing was committed or pushed. This document resolves the open questions Step 53 (`INTERPRETATION_NARRATIVE_FRONTEND_DESIGN.md`) deliberately left open, using only the actual, current repository as source — re-verified directly for this step, not restated from Step 53's own report without re-checking the underlying files.

**Labeling convention used throughout:** every claim is tagged **[Verified fact]** (directly confirmed against current source), **[Existing decision]** (already settled by a prior, approved document — cited by name), **[Recommendation]** (this document's own implementation-readiness choice, not mandated by any governing document), or **[Open]** (genuinely unresolved, not decided here).

---

## 1. Executive Summary

Three of Step 53's open questions are resolved here with an explicit implementation recommendation; none is silently decided without being labeled as such.

- **Sequencing (Section 4): the Product Spec settles this.** `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6 names three distinct entries — Spread Review, Interpreting, Reading Result — in that order. Sequence **B** (navigate to an Interpreting state, run both calls, then arrive at Reading Result) is the spec-faithful sequence; Sequence A (stay on Spread Review, no distinct Interpreting state) is not.
- **Route boundary (Section 5): not settled by the Product Spec** — the spec names screens, not URLs, and this project's own established precedent already treats that as a routing decision left to the frontend (e.g. Home/History/New Reading map to routes the spec never specifies). This document **recommends** one new route, `/readings/:id/result`, reused both immediately after interpreting and when later revisiting an interpreted Reading — leaving `/readings/:id` (Spread Review / evidence) exactly as it is today, unmodified.
- **Interpretation-presence detection (Section 6): the smallest existing-contract answer is a direct `GET /interpretations/current` call, treating `404` as "not yet interpreted."** No backend field is needed or proposed.
- **Save behavior (Section 7): fully traced, no backend gap found.** Save requires no interpretation to exist; a saved Reading can be reinterpreted without losing its saved status; History's saved-only scope (Step 52) is the same, already-documented, already-approved behavior — not a new finding.

No code was written. No AI-generated content is introduced anywhere in this design (Section 9).

---

## 2. Product Spec Requirements

Re-read directly from `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6 (Screen/Application Structure) for this step.

- **"Interpreting"** — *"transient state while the Interpretation Engine + Narrative Generation run."* **[Verified fact]** This is explicitly a *state*, named separately from both "Spread Review" and "Reading Result" in the same flat screen-inventory list. It covers **both** the interpretation call and the narrative call — the spec does not describe an intermediate state between them.
- **"Reading Result"** — *"narrative sections (Central Theme, Tension, What the Spread Shows, Trajectory, What May Be Unclear, Advice, Clarification, Overall Reflection), optional Scripture for Reflection block (visually separated), optional 'How did Raidian Wise arrive at this?' explainability panel, Save action."* **[Verified fact]** One screen, combining narrative prose, optional structured/citation content, and the Save action.
- **"Reading Detail"** — *"a saved Reading's full record (evidence + interpretation as generated); MVP does not require re-interpretation, but the schema must not block it."* **[Verified fact]** Explicitly scoped to a **saved** Reading, explicitly covering both evidence and interpretation together, and explicitly **not** requiring reinterpretation UI for MVP.
- **Save** (Section 3, step 13) — *"User can save the Reading."* Flow-ordered after narrative generation (step 11) and optional Scripture (step 12) in the spec's numbered walkthrough, but see Section 7 below: this ordering describes the *typical* journey, not an enforced precondition.
- **History** — *"list of saved Readings, searchable/filterable"* (Section 6), unchanged, already implemented (Step 52).
- **Revisiting completed readings:** the spec's only named mechanism is History → Reading Detail. It does not describe a "revisit an interpreted-but-unsaved Reading" path at all — consistent with `PRODUCT_DECISIONS.md` Q3's own already-approved conclusion that History is saved-only by design.

**Does the spec require one route or separate routes for Result vs. Detail?** **[Open — the spec does not decide this.]** It names two conceptually distinct screens with two different entry conditions (Result: reached immediately after interpreting; Detail: reached later, only for a *saved* Reading) and two different requirement sets (Result always has fresh narrative content; Detail's own text says MVP doesn't require reinterpretation), but the Product Spec's screen inventory is explicitly "illustrative, not final IA" (its own heading qualifier, Section 6) and specifies no URL structure, no component boundary, and no reuse/non-reuse rule anywhere. Section 5 below makes an explicit, labeled recommendation rather than treating this silence as a decision either way.

---

## 3. Actual Backend API Contracts

Re-verified directly against current source for this step (`backend/app/api/interpretation.py`, `backend/app/api/reading.py`, `backend/app/services/reading_orchestration.py`, `backend/app/services/interpretation/persistence.py`, `backend/app/models/reading.py`) — all **[Verified fact]**, not restated from Step 53 without re-checking.

| Endpoint | Request | Response | Auth/Ownership | Status requirement | Repeat-call behavior | Mutates `Reading`? | Error statuses |
|---|---|---|---|---|---|---|---|
| `POST /readings/{id}/interpret` | none | `InterpretationSummary` (embeds full `InterpretiveModel`) | `get_owned_reading` | `reading.is_spread_complete` must be `True` | **Not idempotent** — always creates a new `Interpretation` row, even against unchanged evidence | Yes — sets `status = INTERPRETED` unless already `SAVED` (preserved, not regressed) | `401`, `404`, `409` (`is_spread_complete` false), `500` (uncaught) |
| `GET /readings/{id}/interpretations/current` | none | `InterpretationSummary` or `404` | `get_owned_reading` | none | Always returns the current (highest-`sequence`) row fresh; never generates | No | `401`, `404` (not found, or never interpreted) |
| `GET /readings/{id}/narrative` | none | `NarrativeModel` or `404` | `get_owned_reading` | none (requires a current Interpretation to exist, else `404`) | **Recomputed on every call** — never persisted, never cached (`READING_INTEGRATION_DESIGN.md` Section 9, re-confirmed unchanged) | No | `401`, `404` (not found, or never interpreted), `500` (uncaught) |
| `POST /readings/{id}/save` | none | `ReadingSummary` | `get_owned_reading` | `reading.status != DRAFTING` (else `409`) | Idempotent — a no-op if already `SAVED` | Yes — sets `status = SAVED` | `401`, `404`, `409` (`ReadingNotSaveableError`) |
| `GET /readings` | none | `list[ReadingSummary]` | `get_current_user` | — | Read-only, always fresh | No | `401` |
| `GET /readings/{id}` | none | `ReadingDetail` (evidence only — spread, positions, card_draws; **no interpretation field of any kind**) | `get_owned_reading` | none | Read-only, always fresh | No | `401`, `404` |

**Interpretation persistence:** **[Verified fact]** Yes, permanently — one `Interpretation` row per `POST /interpret` call, retained forever (deleted only if the parent `Reading` is deleted).

**Narrative persistence:** **[Verified fact]** No — `NarrativeModel` is always recomputed from the current `Interpretation` row, on every `GET /narrative` call. `READING_INTEGRATION_DESIGN.md` Section 9 explicitly evaluated and rejected persisting it.

**Does Save change Reading status?** **[Verified fact]** Yes — unconditionally to `SAVED`, from `SPREAD_COMPLETE` or `INTERPRETED` only (`409` from `DRAFTING`).

**Does narrative require interpretation?** **[Verified fact]** Yes, structurally — `GET /narrative` resolves the current `Interpretation` row internally and returns `404` if none exists; there is no way to fetch a narrative without a persisted interpretation behind it.

**Can an existing interpretation be safely "resumed"?** **[Verified fact]** There is nothing to resume in the sense of an in-progress operation — `POST /interpret` is synchronous, completes or fails within one request, and leaves no partial state (`Interpretation` is only ever inserted on full success, never partially). "Resuming" in practice means simply re-fetching the already-persisted result via `GET /interpretations/current` + `GET /narrative` — both safe, side-effect-free, repeatable reads.

---

## 4. Interpretation Sequencing Decision

**[Existing decision — the Product Spec settles this, not a preference of this document.]**

Comparing the three named options against Section 2's direct evidence:

- **Sequence A** (stay on Spread Review; call `POST /interpret` then `GET /narrative` inline; navigate only once both succeed) **contradicts** the Product Spec's own screen inventory, which names "Interpreting" as a distinct entry, separate from "Spread Review." If the user never leaves Spread Review while both calls run, no "Interpreting" state — as the spec names it — is ever actually shown.
- **Sequence B** (navigate to an Interpreting state → `POST /interpret` → `GET /narrative` → Reading Result) **matches** the spec's own three-entry ordering exactly: Spread Review → Interpreting → Reading Result.
- **Sequence C:** no other sequence is established anywhere in the repository — `FRONTEND_INTEGRATION_DESIGN.md` Section 6's "two viable sequencing shapes" question was about call-ordering *within* rendering Reading Result (structured-content-first vs. both-before-render), not about whether a distinct Interpreting state exists at all; it does not conflict with or supersede Section 6's screen-inventory naming.

**Decision: Sequence B.** Click "Interpret My Reading" on Spread Review → an Interpreting state is shown → `POST /interpret` is called and must succeed → `GET /narrative` is called and must succeed → the user is shown Reading Result. Evaluated against the task's own criteria:

- **Product Spec language:** directly satisfied (above).
- **Existing backend behavior:** both calls are synchronous and fast (`INTERPRETATION_API_DESIGN.md` Section 8, re-confirmed: no I/O beyond local reference-data reads, no network call, no background job) — an Interpreting state will typically be visible only briefly, which is consistent with it being a transient loading state rather than a page requiring its own persisted, resumable identity.
- **Refresh behavior:** because neither call has a meaningful "in progress" state to resume (Section 3), there is nothing lost by treating Interpreting as **[Recommendation]** a transient *render state* of the same route Reading Result lives on, rather than a separate URL — refreshing mid-flight simply re-runs the same page's initial load, which is the same "not yet interpreted" or "already interpreted" detection logic Section 6 defines, not a special case.
- **Duplicate/repeated interpretation behavior:** because `POST /interpret` is only ever called from this one, explicit, user-triggered transition — never from a page-load/refresh check (Section 6) — there is no risk of the Interpreting state itself causing accidental duplicate rows.
- **Error recovery:** see Section 10 — a failure at either call is recoverable without needing to distinguish "Interpreting" as a separate addressable page from "Reading Result."
- **Existing architecture:** consistent with every other async action in this codebase (`CardEntryPage.tsx`'s own draw submission, `NewReadingPage.tsx`'s own reading creation) — a loading/transient condition rendered inline within a page component, not a dedicated route, is the established pattern here.

**[Recommendation, not mandated by the spec]:** "Interpreting" is implemented as a loading render-state of the Reading Result route (Section 5), not a separate URL. The Product Spec names it as a screen/state conceptually; it does not require a distinct address, and no existing routing precedent in this app assigns a URL to a purely transient loading condition (e.g. Card Entry's own "Loading…" state has no route of its own either).

---

## 5. Reading Result vs. Reading Detail Boundary

**What the Product Spec requires:** two conceptually distinct screens (Section 2) — but no routing mechanics of any kind (confirmed: the word "route" or "URL" does not appear anywhere in Section 6).

**What the existing frontend already does:** **[Verified fact]** `/readings/:id` (`SpreadReviewPage.tsx`) already serves *both* "Spread Review" (pre-completion) and the evidence portion of "Reading Detail" (post-completion, including `SAVED` Readings — re-confirmed: `isComplete = reading.status !== 'drafting'` already renders a "complete" banner for any non-drafting status, `SAVED` included) from **one route**, on the explicit precedent already set by `READING_DETAIL_API_DESIGN.md` Section 4.2 ("one endpoint, two consuming screens"). This project has already, once, made exactly the kind of route-consolidation decision this section is being asked to make again.

**Minimum route change needed:** exactly **one new route**, since evidence display is already fully solved and unmodified. **[Recommendation]** `/readings/:id/result` — serving:
- The immediately-after-interpreting "Reading Result" experience (Sequence B's destination), **and**
- The later "revisit an already-interpreted Reading's interpretation" need (whether or not that Reading has since been saved) — i.e., the interpretation-content portion of the Product Spec's "Reading Detail," mirroring exactly the same one-route/two-moments pattern `/readings/:id` itself already uses for evidence.

This produces a two-route split, not three:

| Route | Serves | Change needed |
|---|---|---|
| `/readings/:id` | Evidence — Spread Review (pre-completion) and the evidence half of Reading Detail (post-completion/post-save) | **None** — already correct, unmodified |
| `/readings/:id/result` | Interpretation + narrative content — Reading Result (first arrival) and the interpretation half of Reading Detail (later revisits) | **New route**, new page |

This is closer to **Option 2** than Option 1, but collapses Option 2's third bullet ("another route for saved Reading Detail") into the same route as Reading Result, rather than adding a third URL — on the grounds that Section 6's detection logic (below) already makes that route correct for both moments with no additional code path, exactly mirroring `/readings/:id`'s own precedent.

**[Open — genuinely not resolved by this document]:** whether `/readings/:id/result` should require the Reading to be spread-complete/interpreted to render meaningfully (and what it should show for a `drafting` Reading reached by a stray/typed URL) is an implementation detail for whoever builds it, not decided here. Also open: the exact link/button placement from Spread Review and from History into this route.

---

## 6. Interpretation Presence Detection

**[Recommendation, using only the existing contract — no backend change.]**

Compared directly:

| Mechanism | Verdict |
|---|---|
| `GET /interpretations/current` | **Recommended.** One call, `200` with full content if an interpretation exists, `404` if not — the negative case *is* the presence signal, and the positive case already returns everything needed to start rendering structured content immediately (no second call needed just to detect presence). |
| Information already in `GET /readings/{id}` | **Not usable.** `ReadingDetail` carries no interpretation-related field at all (re-confirmed directly, Section 3) — this path does not exist today. |
| Adding a new backend field | **Not proposed.** Would require a backend/schema change, out of this step's scope, and `READING_DETAIL_API_DESIGN.md` already declined to add one for lack of a demonstrated consumer — this document is that consumer now, but adding the field is a decision for a future backend-facing step, not this one. |
| `GET /interpretations` (history list) | **Not recommended as the presence check** — usable (non-empty list ⇒ interpreted), but strictly worse than `/current` for this purpose: detecting presence via the list still requires a *second* call to `/current` to get actual content, where `/current` alone already answers both questions in one round trip. |

**Recommended detection logic**, satisfying every scenario the task names:
- **First-time interpretation:** `GET /interpretations/current` → `404` → show the "Interpret My Reading" trigger (on Spread Review) / show a "not yet interpreted" state (if `/readings/:id/result` is reached directly).
- **Revisiting an interpreted reading:** → `200` → render Reading Result/Detail content directly from the response, then fetch `GET /narrative` for prose.
- **Refreshing the page:** identical logic re-runs on every load — no special-cased "first load" vs. "reload" branch needed.
- **Avoiding accidental regeneration:** detection **never** calls `POST /interpret` — only a `GET`. The only code path that calls `POST /interpret` is the explicit, user-clicked trigger (Section 4) — page load/refresh/navigation can never trigger it.

---

## 7. Save Behavior

Traced directly against `Reading.mark_saved()` and `save_interpretation()` (Section 3) — every question the task poses, answered from source:

- **Endpoint:** `POST /readings/{reading_id}/save` **[Verified fact]**.
- **Status change:** → `SAVED`, from `SPREAD_COMPLETE` or `INTERPRETED` (never from `DRAFTING`) **[Verified fact]**.
- **Is Save required before interpretation/narrative?** **No.** **[Verified fact]** Nothing gates `POST /interpret` on `status == SAVED`; interpretation is gated only on `is_spread_complete`, entirely independent of Save.
- **Is Save available only after narrative?** **No.** **[Verified fact]** Save requires only `SPREAD_COMPLETE` — `mark_saved()`'s own docstring states plainly: *"SPREAD_COMPLETE + zero Interpretation rows is a valid, supported path to SAVED."*
- **Can a saved Reading be interpreted again?** **Yes.** **[Verified fact]** `save_interpretation()`'s conditional status assignment (`if reading.status != SAVED: reading.status = INTERPRETED`) exists specifically to let reinterpretation happen from `SAVED` without regressing the status — re-confirmed directly in source, matching `READING_INTEGRATION_DESIGN.md` Section 5 (Resolved Q1) and `PRODUCT_DECISIONS.md` Q4's "no pinning, current interpretation always means highest-sequence" decision.
- **Does History only expose saved Readings because of this transition?** **Yes, restated, not a new finding.** `GET /readings` filters `status == SAVED` unconditionally (Step 51/52, re-confirmed unchanged in Section 3's table) — an interpreted-but-unsaved Reading is fully persisted (both its evidence and its Interpretation row) but will not appear in History until the user explicitly saves it. This is `PRODUCT_DECISIONS.md` Q3's already-approved, intentional design, not a gap.

**Does the current implementation contradict the Product Spec?** **[Verified fact, not a defect]** The Product Spec's *numbered flow* (Section 3, steps 9–13) describes Save as happening after narrative generation in the typical journey, but nowhere states Save must be *blocked* until narrative exists — and `PRODUCT_DECISIONS.md` Q3 already explicitly resolved SAVED as "a pure user-curation/retention marker... no effect on Interpretation or Narrative." The backend is *looser* than the spec's narrative-order illustration, not in conflict with any stated requirement. **No backend gap is identified here.**

---

## 8. Frontend State Model

Built only from `ReadingStatus`'s four actual values plus one frontend-only transient render state (Section 4) — no status is invented.

| State | Route(s) reachable | Actions available | API calls allowed | On refresh | Returning via History |
|---|---|---|---|---|---|
| `drafting` | `/readings/:id/draw` (Card Entry, active); `/readings/:id` (evidence, shows remaining positions) | Draw cards | `GET /readings/{id}`, `GET /cards`, `POST /readings/{id}/draws` | Same state re-derived from `GET /readings/{id}` | Not reachable — `GET /readings` never returns a `drafting` Reading (Section 3/7) |
| `spread_complete` | `/readings/:id` (evidence, complete banner); `/readings/:id/result` (not-yet-interpreted state, Section 6) | Interpret; Save | `GET /readings/{id}`, `POST /interpret`, `POST /save` | Same state; presence check (Section 6) correctly reports "not yet interpreted" | Not reachable — still unsaved (Section 7) |
| *(interpreting)* — **frontend-only, not a `ReadingStatus` value** | Rendered as a state of `/readings/:id/result` (Section 4/5) | None (in-flight) | `POST /interpret` then `GET /narrative`, already initiated | N/A — refreshing mid-flight simply re-loads `/readings/:id/result`, which re-runs the presence check (Section 6) and lands on whichever real state the backend now reflects | N/A |
| `interpreted` | `/readings/:id` (evidence); `/readings/:id/result` (Reading Result — narrative + optional citations + Save action) | Reinterpret; Save | `GET /readings/{id}`, `GET /interpretations/current`, `GET /narrative`, `POST /interpret`, `POST /save` | Presence check reports "interpreted" — renders result directly, no re-trigger | Not reachable — still unsaved |
| `saved` | `/readings/:id` (evidence, complete banner); `/readings/:id/result` (Reading Detail's interpretation half, if one exists — Section 5) | Reinterpret (status stays `saved`, Section 7) | Same as `interpreted`, plus `POST /save` is now an idempotent no-op | Same presence-check logic; a `saved` Reading with zero interpretations correctly shows "not yet interpreted" (Section 7's valid path) | **Reachable** — the only status `GET /readings` (History) ever returns |

No fifth backend status and no persisted "interpreting" status are introduced anywhere in this table.

---

## 9. Refresh and Resume Behavior

Each of the task's twelve scenarios, traced to actual backend behavior (Section 3) rather than invented:

1. **Complete a spread, remain on Spread Review** — `status` is already `spread_complete` (automatic, on the qualifying draw). `/readings/:id` already renders this correctly today (Step 50), unaffected by this design.
2. **Click Interpret** — Sequence B fires: navigate to the Interpreting render-state of `/readings/:id/result`.
3. **Interpretation succeeds** — a new `Interpretation` row persists; `status` → `interpreted` (or stays `saved`, Section 7). Frontend proceeds to the narrative call.
4. **Narrative succeeds** — `NarrativeModel` returned, nothing persisted by this call itself.
5. **User sees Reading Result** — both calls' results are already in hand; no further fetch needed to render.
6. **User refreshes Reading Result** — `/readings/:id/result` re-runs its initial load: `GET /interpretations/current` → `200` (Section 6) → renders result content directly, then `GET /narrative` for prose. **No `POST /interpret` is ever re-issued by a refresh.**
7. **User leaves and later returns through History** — only reachable once `saved` (Section 7). History → `/readings/:id` (existing) or → `/readings/:id/result` (new) depending on which link the History entry offers — a UI-affordance choice, not decided by this document (Section 5's Open note).
8. **User opens a saved reading that already has interpretation** — `/readings/:id/result`'s presence check → `200` → renders directly. No difference in mechanism from scenario 6.
9. **User opens a completed reading before interpretation** — `/readings/:id/result`'s presence check → `404` → shows the "not yet interpreted" state with the trigger available (identical to reaching it fresh from Spread Review).
10. **User encounters an interpretation failure** (`409` incomplete-spread, or `500`) — **[Recommendation]** show the error inline on the Interpreting/result render-state with a way back to Spread Review; **no `Interpretation` row was created** (Section 3), so nothing needs to be undone — a retry is simply re-clicking the trigger, safe to do.
11. **User encounters a narrative failure** (`500` from `assemble_narrative()`) — **[Verified fact, from Step 53]** the already-persisted `Interpretation` row is unaffected (narrative assembly failure cannot invalidate or roll back an already-successful interpretation). **[Recommendation]** the frontend should retry only `GET /narrative`, never re-issue `POST /interpret` — re-fetching interpretation content (which already succeeded) is unnecessary and would not fix a narrative-assembly bug in any case.
12. **User attempts to interpret an already-interpreted reading** — allowed by the backend unconditionally (Section 3/7) and creates a new row every time. **[Recommendation]** if a "Reinterpret" action is ever exposed (not required for MVP per Section 2's exact "Reading Detail" quote), it should be a clearly distinct, deliberate action from merely viewing an existing result — but building that affordance is out of this document's scope; MVP's Reading Result screen only needs the one-time, first-interpretation trigger.

---

## 10. Error and Repeat-Generation Behavior

Restated from Step 53 Section 13 (re-verified unchanged in Section 3 above), applied specifically to the Sequence-B flow this document defines:

| Failure point | Backend behavior | Frontend implication under Sequence B |
|---|---|---|
| `POST /interpret` → `409` (not spread-complete) | No row created, `status` untouched | Should not be reachable in practice — the trigger only appears once Spread Review already shows `spread_complete`; if hit anyway (a race with another tab, say), show the backend's own `detail` message and return to Spread Review |
| `POST /interpret` → `500` | No row created (exception before persistence) | Show a generic failure state with a retry option — retrying is exactly re-running the same safe operation |
| `GET /narrative` → `404` (no interpretation yet) | — | Should not occur immediately after a successful `POST /interpret` in the same flow; only relevant if reached via presence-detection misuse, which Section 6 avoids by construction |
| `GET /narrative` → `500` | Persisted `Interpretation` unaffected | Retry `GET /narrative` only (Section 9, scenario 11) |
| `POST /interpret` called twice | Two distinct `Interpretation` rows, both retained | Not a failure — an accepted, existing, non-idempotent behavior (Section 3); the frontend's own job is only to avoid *accidentally* double-firing the trigger (ordinary button-disable-while-in-flight UI discipline), not to rely on the backend to deduplicate |

No retry or idempotency semantics are invented beyond what Section 3 already documents as true today.

---

## 11. Preserve Deterministic Architecture

**[Verified fact, explicitly checked for this step]** Nothing in this design introduces, assumes, or calls an AI provider. `POST /interpret` invokes only `engine.interpret()` (deterministic, Section 4 of `INTERPRETATION_NARRATIVE_FRONTEND_DESIGN.md`, re-confirmed unchanged here) and `GET /narrative` invokes only `assemble_narrative()` (deterministic, template-based, database-free). Both remain exactly as implemented — this document proposes no change to either. Per `PRODUCT_DECISIONS.md` Q1 (restated, not revisited): the deterministic narrative is the interim MVP substitute for the Product Spec's originally-described AI/Reflection-Engine pass, which remains unbuilt and out of scope. **The Reading Result screen this document designs the flow for must present the narrative as Raidian Wise's own deterministic reflection — not as AI-generated content** — consistent with this project's ADR-0005 boundary and with `PRODUCT_DECISIONS.md` Q1's own still-outstanding governance caveat.

---

## 12. Route Map

Combining Sections 4/5, the complete post-Step-54 intended route set (only `/readings/:id/result` is new; every other route is unchanged from Step 52):

```
/login, /register        (public)
/                         Home
/readings                 Reading History (saved only)
/readings/new             New Reading
/readings/:id/draw        Card Entry
/readings/:id             Spread Review / evidence half of Reading Detail   (UNCHANGED)
/readings/:id/result      Reading Result / interpretation half of Reading Detail   (NEW — not built by this step)
```

---

## 13. Open Decisions

Explicitly not resolved by this document:

- **Whether the Product Spec's separate "Reading Result" and "Reading Detail" concepts should ever diverge into two different routes** if a future need (e.g. a materially different layout for "just generated" vs. "revisiting") emerges — Section 5's recommendation treats them as one route today; this could change without contradicting anything decided here.
- **Exact link/button placement:** where on Spread Review the "Interpret My Reading" trigger sits; where on History (and on `/readings/:id`) a link to `/readings/:id/result` appears once an interpretation exists.
- **Whether `/readings/:id/result` should redirect, show an empty state, or offer the trigger inline when reached directly for a still-`drafting`/never-interpreted Reading** (Section 5's open note).
- **Whether a "Reinterpret" UI affordance is ever built** — explicitly not required for MVP per the Product Spec's own "Reading Detail" text (Section 2); not designed here.
- **API sequencing micro-shape within Reading Result's own render** (render structured content immediately from `POST /interpret`'s response vs. waiting for narrative too before showing anything) — `FRONTEND_INTEGRATION_DESIGN.md` Section 6's original question, still a pure rendering-strategy choice, not resolved here.

---

## 14. Deferred Issues

Carried forward, explicitly not touched or expanded by this step:

- Card artwork source/hosting/architecture (`CARD_IMAGE_ASSET_DESIGN.md`).
- Roman-numeral card search aliasing (`FRONTEND_INTEGRATION_AUDIT.md` Section 6).
- Whether Reading History should ever include unsaved/in-progress Readings (`FRONTEND_INTEGRATION_DESIGN.md` Section 7.3).
- The `Reading`/`Interpretation` timestamp-serialization characteristic (Step 52's finding, Step 53's confirmation that `Interpretation.created_at` shares it while `generated_at` fields do not) — unrelated to any decision made in this document; no timestamp field is load-bearing for any sequencing/detection/state-model decision above.
- The AI/Reflection-Engine narrative drift (`PRODUCT_DECISIONS.md` Q1's still-outstanding governance action) — restated in Section 11, not resolved.

---

## 15. Verification Evidence

- **Direct source re-reads performed for this step:** `backend/app/api/interpretation.py`, `backend/app/api/reading.py`, `backend/app/services/reading_orchestration.py`, `backend/app/services/interpretation/persistence.py`, `backend/app/models/reading.py` (`mark_saved`, `is_spread_complete`), `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6, `PRODUCT_DECISIONS.md` Q3/Q4, `frontend/src/pages/SpreadReviewPage.tsx`'s current `isComplete` logic. Cross-checked against, and found fully consistent with, Step 53's own `INTERPRETATION_NARRATIVE_FRONTEND_DESIGN.md`, which was itself independently source-verified one step earlier in this same series.
- **`git status` before this step:** confirmed identical to Step 53's end state (55 total status lines, only the expected carried-forward set).
- **`git status` after this step:** only `Documentation/READING_RESULT_FLOW_DESIGN.md` added — see the Step 54 final report for the exact listing.
- **`git diff --check`:** run after creating this document — see the Step 54 final report for the exact output.
- No code was written, executed, or modified. No migration, schema, or dependency change of any kind. Backend test suite not re-run, per this step's own instruction (no executable code changed) — the most recently established count (474 passed, 2 pre-existing warnings, unchanged since Step 50) stands.
