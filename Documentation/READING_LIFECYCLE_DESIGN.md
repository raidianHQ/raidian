# Raidian Wise — Reading Lifecycle & User Flow Design (Step 13)

# Document Information

Version: 1.0 (Draft for Review — Not Yet Approved)
Status: Proposed — Design Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Designs the user-facing Reading lifecycle — `Reading creation → drafting → spread completion → interpretation → review → narrative → save` — around the functionality that actually exists at baseline `1fa789b` (Steps 2–12: a fully implemented, validated Interpretation Engine, Narrative Assembly, Reading Integration orchestration, and Interpretation API). This document does not implement any of the lifecycle it describes; it states what the current code actually does, what a future Reading/Draw Service and frontend would need to do to complete the flow, and — per this task's explicit instruction — surfaces every contradiction found between `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` and the implemented system rather than resolving them.

Audience:
Software engineers and AI development agents who will eventually build the missing Reading/Draw Service (`reading_service.py`, sketched but never implemented — `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2) and the frontend that drives this lifecycle, and anyone — including whoever owns the Product Spec — who needs a single place naming exactly which lifecycle decisions are already made in code, which are still open, and which the Product Spec and the implementation currently disagree about.

Authority:
Concretizes `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Sections 5 (Core User Flow), 6 (Screen Structure), 7.5 (Reading), 17 (Versioning), and 18 (MVP Scope) against the actual, current `app/models/reading.py`, `app/models/enums.py`, `app/services/interpretation/persistence.py`, `app/services/reading_orchestration.py`, and `app/api/interpretation.py`. Builds directly on top of `READING_INTEGRATION_DESIGN.md` (Step 8) and `INTERPRETATION_API_DESIGN.md` (Step 10) rather than re-deriving their conclusions — every decision already settled there is treated as settled here too, and is cited, not repeated in full. Does not override the Product Spec; where this document and the Product Spec disagree, Section 9 records the disagreement explicitly rather than deciding which one is right.

---

# 0. Scope

This document defines **Step 13 only**: the user-facing lifecycle wrapped around the already-implemented Engine/Narrative/Orchestration/API layers. It does **not**:

- Implement any code, schema, migration, API route, or frontend/UI.
- Add authentication, authorization, or any ownership model — `INTERPRETATION_API_DESIGN.md` Sections 4–5's "missing infrastructure" finding is unchanged and is not re-litigated here.
- Change any interpretation rule, reference data, `InterpretiveModel`, or `NarrativeModel` — all are treated as fixed, already-approved contracts.
- Design AI/LLM wording of any kind, including for the Narrative Generation path Product Spec Section 3.3/11 describes as AI-driven (Section 9.3 records why this matters without resolving it).
- Silently resolve any contradiction found between the Product Spec and the implemented system (Section 9) — every one is recorded as an open decision point.

---

# 1. Repository Inspection Summary

## 1.1 The state model as actually defined in code

`app/models/enums.py::ReadingStatus` — four values: `DRAFTING`, `SPREAD_COMPLETE`, `INTERPRETED`, `SAVED`. `app/models/reading.py::Reading.status` defaults to `ReadingStatus.DRAFTING` at construction (confirmed by `test_reflection_session_and_reading.py::test_...` and used, unchanged, throughout Steps 8–12).

## 1.2 What actually assigns each status value — checked by direct, repository-wide search, not assumed

A search for every place `reading.status = ReadingStatus....` or an `Interpretation(...)` constructor's status side effect occurs in `app/` (not `tests/`) finds exactly **one** production assignment:

```python
# app/services/interpretation/persistence.py, save_interpretation()
if reading.status != ReadingStatus.SAVED:
    reading.status = ReadingStatus.INTERPRETED
```

That is the **entire** set of status-mutating production code in this repository today. Concretely:

- **`DRAFTING`** — the model-level default. Nothing ever explicitly (re-)assigns it; a Reading is `DRAFTING` simply because it was just created and nothing has interpreted it yet.
- **`SPREAD_COMPLETE`** — **never assigned anywhere in production code.** The only place this value appears in `app/` is its own enum definition. This is not a new finding — `READING_INTEGRATION_DESIGN.md` Section 1.2 already found and recorded exactly this ("the status enum's own middle value has never once been used") — but it remains true, unchanged, through Steps 9–12, and is directly relevant to this document's Section 2/6.
- **`INTERPRETED`** — assigned automatically, as a side effect, every time `save_interpretation()` succeeds and the Reading's prior status was not already `SAVED`. This is the only status transition currently reachable through any real code path (API included).
- **`SAVED`** — **never assigned anywhere in production code either.** `persistence.py`'s `if reading.status != ReadingStatus.SAVED` guard *checks for* `SAVED` (to avoid regressing it) but nothing anywhere ever *sets* it. `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 9's illustrative `POST /readings/{id}/save` route was never built (confirmed again here; `INTERPRETATION_API_DESIGN.md` Section 0 already named this route as explicitly out of that step's scope). **This means that, as of baseline `1fa789b`, no Reading in this system can ever actually reach `SAVED` status through any implemented path — only by a test, or a raw database write, setting it directly.**

## 1.3 `Reading.is_spread_complete` is a separate mechanism from `ReadingStatus.SPREAD_COMPLETE`

`Reading.is_spread_complete` (Step 9, a derived `@property`: every required `SpreadPosition` has a drawn `CardDraw`) is what `interpret_reading()` actually checks before invoking the engine (`READING_INTEGRATION_DESIGN.md` Section 3's explicit, deliberate decision: `reading.status`'s value is "not a precondition" for interpretation at all). This property and the `ReadingStatus.SPREAD_COMPLETE` enum value are **not the same thing** and are not wired together anywhere: a Reading can have `is_spread_complete == True` while `status` is still (and, per Section 1.2, will remain) `DRAFTING`, since nothing ever promotes `status` in response to the evidence becoming complete. Section 2/6 treat whether these two should ever be connected as an open decision.

## 1.4 Product Spec passages this document validates against

- Section 5 (Core User Flow), steps 8–14 — the review → interpret → narrative → save sequence.
- Section 6 (Screen Structure) — `Spread Review`, `Interpreting`, `Reading Result`, `Reading History`, `Reading Detail`.
- Section 7.5 (Reading) — the `Reading` entity's field list, including `interpretive_model`, `narrative`, `interpretation_engine_version` as *columns on Reading*.
- Section 17 (Versioning) — the evidence-vs-interpretation separation principle.
- Section 18 (MVP Scope) — "Save Reading" listed as in-scope; "Reinterpretation... UI deferred" listed as future scope.
- Section 3.3 (Reconciling the Interpretation Engine with ADR-0005) — the originally-specified AI-via-Reflection-Engine narrative path.

Section 9 records where the actual implementation now disagrees with these passages.

---

# 2. Lifecycle / State Model

```
                 (default at creation)
                          │
                          ▼
                    ┌───────────┐
                    │ DRAFTING  │
                    └─────┬─────┘
                          │  [evidence becomes complete --
                          │   is_spread_complete becomes True;
                          │   PROPOSED whether status itself
                          │   ever moves here -- Section 6]
                          ▼
              ┌───────────────────────┐
              │ SPREAD_COMPLETE       │   <-- CONFIRMED: enum value exists.
              │ (never assigned by    │       PROPOSED: whether/how it is
              │  any code today)      │       ever assigned. See Section 6.
              └───────────┬───────────┘
                          │  [user explicitly triggers
                          │   "Interpret My Reading" --
                          │   POST /readings/{id}/interpret]
                          ▼
                 ┌─────────────────┐
                 │  INTERPRETED    │  <-- CONFIRMED: the only status
                 └────────┬────────┘      transition any real code path
                          │                can currently produce.
                          │  [user explicitly "saves" the Reading --
                          │   NO IMPLEMENTED PATH TODAY. Section 7.]
                          ▼
                   ┌─────────────┐
                   │   SAVED     │  <-- CONFIRMED: enum value exists,
                   └──────┬──────┘      and reinterpretation-preserves-
                          │             SAVED logic already exists and
                          │             is tested. PROPOSED: how a
                          │             Reading ever gets here at all.
                          │
                          │  [reinterpretation -- allowed from ANY
                          │   status, including SAVED itself --
                          │   READING_INTEGRATION_DESIGN.md Section 5]
                          ▼
                 back to INTERPRETED (if not already SAVED)
                 or stays SAVED (if already SAVED) --
                 CONFIRMED, tested (Step 9/11/12).
```

**Key structural fact this diagram makes visible:** the four-value enum describes a state machine whose *middle* transition (`DRAFTING`/`SPREAD_COMPLETE` → `INTERPRETED`) and *terminal* transition (`INTERPRETED` → `SAVED`) are asymmetric in how completely they're implemented today. The first is fully implemented (triggered by a real API call, tested end-to-end — Step 12). The second does not exist at all yet — not partially, not behind a flag, simply absent.

---

# 3. Transition Table

| From | To | Trigger | Status |
|---|---|---|---|
| *(none)* | `DRAFTING` | Reading created | **Confirmed** — model default |
| `DRAFTING` | `SPREAD_COMPLETE` | Evidence becomes complete, or an explicit user/service action | **Proposed** — Section 6 names two candidate designs, does not choose one |
| `DRAFTING` or `SPREAD_COMPLETE` | `INTERPRETED` | `POST /readings/{id}/interpret` succeeds (`is_spread_complete` must be `True`, checked at the orchestration layer, independent of `status`) | **Confirmed** — implemented, tested (`persistence.py`, `test_drafting_transitions_to_interpreted`, `test_spread_complete_transitions_to_interpreted`) |
| `INTERPRETED` | `INTERPRETED` | Reinterpretation (`POST /interpret` again) | **Confirmed** — idempotent no-op on `status` itself; a new `Interpretation` row is still created every time (`test_interpreted_stays_interpreted_on_reinterpretation`) |
| `INTERPRETED` | `SAVED` | User explicitly "saves" the Reading | **Proposed** — no implemented trigger exists (Section 7) |
| `SAVED` | `SAVED` | Reinterpretation (`POST /interpret` again) | **Confirmed** — implemented, tested; status is never regressed (`test_saved_reading_remains_saved_after_reinterpretation`, re-confirmed at the API layer in Step 11/12) |
| `SAVED` | *(any earlier value)* | "Unsave" / reopen for editing | **Deferred** — no such action is named anywhere in the Product Spec or any prior design document; not proposed here either (Section 8) |
| `SPREAD_COMPLETE` | `DRAFTING` | Removing a previously-drawn card | **Deferred** — Card Draw mutation after spread completion is not designed by any existing document (Section 8) |

No transition in this table was invented for this document beyond what Section 6/7 explicitly propose as open designs — every "Confirmed" row cites an existing, passing test.

---

# 4. Interpretation Trigger Rules

**Fully confirmed, unchanged from `READING_INTEGRATION_DESIGN.md` Section 3 and `INTERPRETATION_API_DESIGN.md` Section 2/7, re-validated end-to-end in Step 12:**

1. **Explicit user action only.** `POST /readings/{id}/interpret` — never automatic, never triggered by evidence becoming complete, never triggered by a reference-data change. This matches Product Spec Section 5 step 9 exactly ("interpretation is never automatic on spread completion... a deliberate UX gate").
2. **Gated by evidence, not by `status`.** The precondition is `reading.is_spread_complete` (every required `SpreadPosition` has a drawn `CardDraw`) — `reading.status`'s current value is never consulted. A Reading can be interpreted while `status == DRAFTING`, as long as the evidence is actually complete.
3. **Callable from every lifecycle state, including `SAVED`.** No status value blocks interpretation. This is answers task item #4 directly: **yes, confirmed** — reinterpretation is possible from every status, `SAVED` included, and is already tested at the orchestration (Step 9), API (Step 11), and full end-to-end (Step 12) layers.
4. **Not idempotent; not deduplicated.** Every successful call creates a new `Interpretation` row (`sequence` = global max + 1), even against unchanged evidence. `INTERPRETATION_API_DESIGN.md` Section 13 already re-affirms this is deliberate, not an oversight.

---

# 5. Reinterpretation Behavior (Task Item 5)

**What happens to status after reinterpretation — fully confirmed by existing tests, not a new decision:**

| Status before reinterpretation | Status after |
|---|---|
| `DRAFTING` | `INTERPRETED` |
| `SPREAD_COMPLETE` | `INTERPRETED` |
| `INTERPRETED` | `INTERPRETED` (unchanged) |
| `SAVED` | `SAVED` (unchanged — never regressed) |

History is always preserved: every call adds a new row to `reading.interpretations`; no prior row is ever modified or deleted (Step 8 Section 5/6, re-confirmed Step 9/12). "Current" is always the highest-`sequence` row, computed fresh on every read — there is no `is_current` flag anywhere to go stale.

**A consequence worth naming explicitly (feeds directly into Section 7's open question):** because reinterpretation is allowed after `SAVED` and does not create a new status, a Reading's "current interpretation" can silently change *after* the user saved it, without the Reading ever leaving `SAVED` status. Whether this is the intended product behavior, or whether "saving" should someday freeze *which* interpretation is "the saved one," is Section 7's central open question — this document does not decide it.

---

# 6. What Makes a Reading `SPREAD_COMPLETE`? (Task Items 1–2)

**Confirmed:** nothing does, today (Section 1.2/1.3). Two candidate designs exist for closing this gap; this document names both and does not choose between them, per this task's explicit instruction that a decision requiring product judgment should be recorded, not made arbitrarily.

**Option A — Automatic, derived-and-assigned.** A future Reading/Draw Service, on every Card Draw write, checks `reading.is_spread_complete` and assigns `status = SPREAD_COMPLETE` the moment it first becomes `True` (mirroring the "derive, don't store-and-risk-drift" precedent this project already uses for `is_spread_complete` itself and `Spread.position_count` — except here the *derived* value would additionally be *written* to a *stored* field, which is a different, weaker guarantee: the stored `status` could drift from the live evidence if a Card Draw is later removed, unless every mutation path re-checks it). Advantage: the status column would then accurately reflect evidence completeness at all times, matching its own name. Disadvantage: introduces exactly the "two sources of truth" risk `is_spread_complete` was designed to avoid, and duplicates information already available live via the property.

**Option B — Explicit, user/UI-driven.** `status` moves to `SPREAD_COMPLETE` only when the user reaches and confirms the "Spread Review" screen (Product Spec Section 6) — an explicit action distinct from merely having filled the last position (a user could fill the last position and immediately navigate away without "reviewing," in which case `status` would arguably still be meaningful as `DRAFTING` even though `is_spread_complete` is already `True`). Advantage: keeps `status` as a genuine user-journey marker ("has this user consciously reached spread review") rather than a redundant mirror of derived evidence state. Disadvantage: requires a UI/service concept ("confirm spread") that does not exist anywhere yet, and Product Spec Section 6's "Spread Review... edit-in-place still available here" suggests review is not necessarily a one-way gate either.

**A third possibility, worth naming for completeness:** `SPREAD_COMPLETE` could simply remain permanently unused, and `is_spread_complete` (the derived property) could be treated as the sole, sufficient signal forever — i.e., the enum value is legacy/aspirational and nothing should ever be built to assign it. `READING_INTEGRATION_DESIGN.md` came close to this position for the *engine's own precondition* ("deliberately not a precondition"), but never extended that conclusion to say the *status value itself* should never be assigned for any purpose (e.g., a Reading History list filter, or UI state). This document does not extend it either — recorded as **Deferred**, not decided.

---

# 7. What Does "Save Reading" Mean Now? (Task Item 10)

**Confirmed:** no code implements "Save Reading" in any form today (Section 1.2). This is the single largest gap this document surfaces.

**Confirmed, and directly relevant to what "save" *can* mean going forward:** unlike when Product Spec Section 7.5/17 was written, an Interpretation is no longer something that only exists "if saved" — **every successful `POST /interpret` call durably persists a new `Interpretation` row immediately, regardless of whether the user ever saves anything.** There is no draft/unsaved interpretation state; persistence and "saving" are already fully decoupled by the implemented schema (Step 8's Decision, Section 1.1: a related table, not columns on `Reading`).

This decoupling means "Save Reading" can no longer mean what Product Spec Section 5 step 13/14 originally implied ("the saved record preserves... interpretation engine version — permanently" — read literally, this describes saving as the act that makes the interpretation durable). That act already happens automatically and immediately on interpretation, saved or not. Three candidate meanings remain open, named here rather than chosen:

1. **Pure user-curation bookmark.** `SAVED` means "the user has flagged this Reading as one they want to keep/revisit," with zero effect on what is or isn't persisted (everything already is) and zero effect on whether reinterpretation remains possible (it already does, and already preserves `SAVED` — Section 5). Under this reading, "save" is closer to a favorite/pin than an archival action.
2. **A snapshot-pinning action.** `SAVED` additionally records *which* `Interpretation` row (by `id`/`sequence`) was current *at the moment of saving*, so a "Reading Detail" view can always show "the interpretation the user actually saw and saved," even if later reinterpretation adds newer rows. This would require a new field or mechanism not designed by this document (it would very likely need to live on `Reading`, e.g. a `saved_interpretation_id`, or be inferred by timestamp — either is a schema question out of this design-only step's scope) and directly contradicts nothing implemented today, but is **not implemented, and not even sketched, anywhere**.
3. **A lifecycle terminal-state marker with no special semantics beyond ordering.** `SAVED` simply means "further down the same linear lifecycle than `INTERPRETED`," used only for filtering/sorting a future Reading History list (e.g. "show only Readings the user has saved"), with no pinning and no curation meaning beyond that.

Options 1 and 3 are compatible with the schema and behavior already implemented and would require **no code change beyond adding the missing trigger** (an API route, e.g. the already-sketched-but-unbuilt `POST /readings/{id}/save`, and the orchestration/service function behind it). Option 2 would require a small, currently-undesigned schema addition. This document does not recommend one — it is a product decision, not an engineering one, and is recorded as **Unresolved** in Section 10.

---

# 8. What the User Sees When an Interpretation Does Not Yet Exist (Task Item 6)

No frontend exists (confirmed, unchanged since every prior step). This section proposes UX behavior only; nothing here is implemented.

**Confirmed API behavior already in place to build against:**
- `GET /readings/{id}/interpretations/current` → `404` if the Reading has never been interpreted.
- `GET /readings/{id}/narrative` → `404` for the same reason.
- `GET /readings/{id}/interpretations` → `200` with `[]` (never `404`) — a history list's "nothing yet" state is empty, not missing.

**Proposed (not implemented) UX behavior consistent with the above and with Product Spec Section 6's screen inventory:**
- A Reading Detail view for a Reading that has never been interpreted should not attempt to render a "Reading Result" section at all — it should present the "Interpreting" screen's *inverse*: an explicit "Interpret My Reading" call-to-action, distinct from a loading or error state. The `404` from `current`/`narrative` is a normal, expected response in this state, not an error to surface to the user.
- A Reading whose evidence is not yet complete (`is_spread_complete == False`) should not offer that call-to-action at all (or should offer it disabled) — attempting the call would correctly receive `409`, but a well-designed frontend should not need to rely on that response to know not to show the button in the first place. This is a UI-layer responsibility; the API's `409` remains the authoritative backstop regardless (`INTERPRETATION_API_DESIGN.md` Section 6).

---

# 9. Presenting Current vs. Historical Interpretations (Task Item 7)

Proposed only — no frontend exists to implement this against.

- **Current interpretation** (`GET .../interpretations/current`) is the natural default view for "Reading Result" (Product Spec Section 6) — it always carries the complete `InterpretiveModel`, and its paired `GET .../narrative` call supplies the rendered prose. A frontend should treat these as two calls for one logical "current result" view, not as unrelated data.
- **Historical interpretations** (`GET .../interpretations`, newest-first, lightweight entries only — `INTERPRETATION_API_DESIGN.md` Section 12) are proposed as a secondary, explicitly-opted-into view (e.g. "View past interpretations of this Reading"), not shown by default alongside the current one — the lightweight `InterpretationHistoryEntry` shape (no embedded `InterpretiveModel`) already signals this is meant for a list, not a detail view. A per-entry detail fetch (viewing one *specific* historical interpretation's full content) has **no implemented endpoint** — `INTERPRETATION_API_DESIGN.md` Section 2's noted extension point (`GET /readings/{id}/interpretations/{interpretation_id}`) remains unbuilt and is not designed further here.
- **Section 3.3's finding directly affects this section:** since `sequence` is a global counter, not a per-reading version number, any UI numbering historical entries for display (e.g. "Version 1," "Version 2") must derive that number from the entry's *position in the returned list*, never from `sequence`'s raw value (`READING_WORKFLOW_VALIDATION.md` Section 3.3, restated here because it is directly load-bearing for this proposed presentation).

---

# 10. Narrative Generation Timing (Task Items 8–9)

**Confirmed, unchanged through Steps 6–12:** the `NarrativeModel` is never persisted or cached anywhere. It is recomputed, from scratch, from the current `Interpretation` row, on every single `GET /readings/{id}/narrative` call — proven repeatable and side-effect-free at the orchestration level (Step 9), the API level (Step 11), and the full end-to-end level (Step 12, `test_narrative_generation_creates_no_rows_and_does_not_mutate_the_reading`).

**Whether this should remain the permanent design (task item 9):** the existing design documents already commit to this as intentional, not provisional — `READING_INTEGRATION_DESIGN.md` Section 9 (Resolved Q4) and `INTERPRETATION_API_DESIGN.md` Section 9 both treat "never persisted" as a considered decision (cost is negligible — `INTERPRETATION_API_DESIGN.md` Section 8's determinism/speed argument — and it trivially guarantees the narrative can never drift from its source `Interpretation`). This document finds no reason to reopen that decision and treats it as **Confirmed, standing**, not merely proposed.

**One genuinely open question this document adds, not previously asked:** `POST /interpret`'s response (`InterpretationSummary`) does **not** include the narrative — a client must always issue a *second*, separate `GET .../narrative` call to display prose after interpreting. Product Spec Section 5 steps 10–11 describe interpretation and narrative generation as one continuous flow ("The Interpretation Engine analyzes... produces... Interpretive Model. The Narrative Generation layer converts..."), which could be read as implying the user should see narrative immediately, without waiting on a second round-trip. Whether the frontend should issue that second call automatically and immediately (functionally equivalent to the spec's continuous flow, just implemented as two sequential requests instead of one), or whether `POST /interpret`'s response should someday be extended to optionally embed the narrative, is **Unresolved** — recorded in Section 12, not decided here (extending `InterpretationSummary`'s shape would be a schema change, explicitly out of this design-only step's scope regardless).

---

# 11. Reversibility of Transitions (Task Item 11)

Per Section 3's transition table: **only two transitions are implemented at all, and neither is reversible in the sense of moving backward.** `DRAFTING`/`SPREAD_COMPLETE` → `INTERPRETED` and `SAVED` → `SAVED` (reinterpretation) are the only real code paths; nothing anywhere moves a Reading's `status` to an *earlier* value than it currently holds. This is consistent with — not contradicted by — `ReadingStatus`'s own docstring, which frames the enum as a forward lifecycle.

No document in this project's history, including this one, proposes an "unsave" or "reopen a saved Reading for editing" action. This is recorded as **Deferred**, not rejected: Product Spec Section 6's "Reading Detail... MVP does not require re-interpretation, but the schema must not block it" explicitly anticipates reinterpretation staying possible (which it does, unconditionally, per Section 4), but says nothing about *status* ever moving backward, and no later document introduces the idea either. Whether a saved Reading's evidence (`CardDraw` rows) should ever become editable again is a distinct, larger question this document does not raise on its own authority — Product Spec Section 17 already establishes evidence as "immutable once the spread is complete," which, read together with the fact that `status` never actually reaches a real `SPREAD_COMPLETE` transition today (Section 6), leaves *when exactly* evidence becomes immutable also somewhat undefined in practice, not just in status terms. Recorded as **Deferred**.

---

# 12. User-Flow Sequence, Annotated Against What Exists

Product Spec Section 5's 14 steps, annotated with Confirmed/Proposed/Gap against the current implementation:

| # | Product Spec step | Status against current implementation |
|---|---|---|
| 1–7 | Start Reading, select Layout, question, domain, draw method, physical/digital card entry | **Gap** — no Reading/Draw Service or frontend exists at all (`READING_INTEGRATION_DESIGN.md` Section 1.2, unchanged); entirely out of this document's scope to design |
| 8 | User reviews the completed spread before proceeding | **Proposed** — corresponds to `is_spread_complete` becoming `True`; whether/how `status` reflects this is Section 6's open question |
| 9 | User explicitly triggers "Interpret My Reading" | **Confirmed, implemented** — `POST /readings/{id}/interpret` |
| 10 | Engine produces the Interpretive Model | **Confirmed, implemented** — `engine.interpret()`, persisted via `save_interpretation()` |
| 11 | Narrative Generation converts the model to prose, via the Reflection Engine | **Contradiction** — see Section 9.3. What's implemented (`assemble_narrative()`) is deterministic and does not call the Reflection Engine or any AI provider at all |
| 12 | Scripture for Reflection shown if enabled | **Gap** — no Scripture Engine integration exists in this codebase at all; entirely outside this document's and this project's Interpretation-track scope to date |
| 13 | User can save the Reading | **Gap** — no implemented trigger (Section 7) |
| 14 | Saved record preserves evidence + interpretation engine version permanently | **Contradiction** — see Section 9.1/9.4. Evidence is preserved (Card Draw is never touched by reinterpretation), but "the" interpretation engine version is not a single frozen value — every reinterpretation adds another `engine_version`-bearing row, and nothing pins one as "the saved one" (Section 7, option 2) |

---

# 13. API Interactions Using the Existing Routes

A concrete call sequence a future frontend would make, using only routes that exist today (`INTERPRETATION_API_DESIGN.md`, Step 11):

```
1. [Reading created, cards drawn -- NO ROUTE EXISTS FOR THIS YET, Section 12]

2. POST /readings/{id}/interpret
   -> 201 InterpretationSummary   (spread complete)
   -> 409                          (spread incomplete -- frontend should
                                    prevent reaching this state via UI,
                                    Section 8, but the API enforces it
                                    regardless)
   -> 404                          (reading_id does not exist)

3. GET /readings/{id}/narrative
   -> 200 NarrativeModel           (render "Reading Result")
   -> 404                          (should not occur immediately after a
                                    successful step 2 in the same flow --
                                    would only occur if narrative were
                                    fetched for a Reading interpretation
                                    never actually ran for)

4. [User reviews the result; optionally repeats step 2 -- reinterpretation,
    always allowed, always creates new history]

5. [User "saves" -- NO ROUTE EXISTS FOR THIS YET, Section 7]

6. GET /readings/{id}/interpretations
   -> 200 [InterpretationHistoryEntry, ...]   (newest first; [] if step 2
                                                was never called)

7. GET /readings/{id}/interpretations/current
   -> 200 InterpretationSummary    (re-fetch the current full model, e.g.
                                     returning to a previously-created
                                     Reading's detail view later)
   -> 404                          (never interpreted)
```

Steps 1 and 5 are named here only to show exactly where they'd slot into an otherwise-real sequence — neither has an implemented route, and this document does not design one (that would be an API route addition, explicitly out of scope for this design-only step).

---

# 14. Confirmed vs. Proposed Behavior — Summary

| Behavior | Status |
|---|---|
| `DRAFTING` is the creation default | **Confirmed** |
| `SPREAD_COMPLETE` is ever assigned by any code | **Not implemented** — Section 6 proposes two options, decides neither |
| Interpretation requires `is_spread_complete`, not `status` | **Confirmed** |
| Interpretation trigger is explicit-only, never automatic | **Confirmed** |
| Interpretation is possible from every status including `SAVED` | **Confirmed** |
| Reinterpretation preserves history, never deletes/overwrites | **Confirmed** |
| Reinterpretation's effect on `status` (transition table, Section 3) | **Confirmed** |
| `SAVED` is ever assigned by any code | **Not implemented** — Section 7 proposes three meanings, decides none |
| Narrative is generated on demand, never persisted/cached | **Confirmed**, and treated as a settled decision, not merely proposed |
| Narrative generation goes through the Reflection Engine / AI | **Contradicts the Product Spec** — see Section 9.3; not designed here |
| `POST /interpret` response embeds the narrative | **Not implemented** — Section 10 names this as newly open |
| Any status transition is reversible (moves backward) | **Not implemented anywhere** |
| A "Reading Service" / Draw entry API exists | **Does not exist** (unchanged since Step 8) |
| A per-interpretation-ID detail route exists | **Does not exist** (named, not designed, since Step 10) |

---

# 15. Contradictions and Gaps Between the Product Spec and the Implemented System

Presented as findings, not resolutions, per this task's explicit instruction.

## 15.1 `Reading`'s own field list (Product Spec Section 7.5) no longer matches the schema

Product Spec Section 7.5 lists `interpretation_engine_version`, `interpretive_model`, and `narrative` as **columns on `Reading` itself**. The implemented schema (Step 1's `INTERPRETATION_ENGINE_DESIGN.md` Decision, Section 1.1) instead uses a separate, one-to-many `Interpretation` table, and `narrative` is never persisted anywhere at all (Section 10). `READING_INTEGRATION_DESIGN.md` Section 1.3 already flagged this exact drift once (comparing against `RAIDIAN_WISE_ARCHITECTURE_V1.md`'s schema sketch) and declined to fix the source document; this document re-confirms the same drift is still present in the Product Spec itself, one level up, and — per this task's boundary — likewise does not fix it.

## 15.2 The status enum's two middle/terminal values are currently unreachable — a bigger gap than "not yet built"

Section 1.2/6/7 establish that `SPREAD_COMPLETE` and `SAVED` are not merely *pending implementation* in the ordinary sense (a route sketched but not yet written) — there is currently **no design document anywhere in this project, including this one, that commits to a specific mechanism for assigning either value.** `READING_INTEGRATION_DESIGN.md` addressed *half* of the `SPREAD_COMPLETE` question (why the engine doesn't need it as a precondition) without addressing the other half (whether the status value itself should ever be assigned for any other purpose). This document extends that finding to `SAVED` as well, and to the explicit statement that both remain fully open.

## 15.3 Narrative Generation's actual architecture contradicts Product Spec Section 3.3/5(11)

Product Spec Section 3.3 states, as a specific, reasoned architectural decision: "The Narrative Generation layer is the one component permitted to reach an AI provider, and it must do so exclusively through the existing Reflection Engine service (per ADR-0005)... Its system prompt (to live in `prompts/system/reflection_engine.md` and `prompts/interpretation.md`, both currently empty) must constrain it to *rephrase, not reconsider* the model." Section 5 step 11 repeats this as an MVP flow step.

What was actually built (Steps 6–7, `app/services/narrative/`) is a **fully deterministic, template-based prose assembler with zero AI, zero Reflection Engine call, and zero use of the named prompt files** — confirmed still empty (`prompts/interpretation.md`, `prompts/system/reflection_engine.md`, `prompts/system/safety.md`, `prompts/system/tone.md` are all 0 lines as of this document). `NARRATIVE_LAYER_DESIGN.md` reconciles this by introducing a three-tier split — `[A]` (deterministic, built), `[B]` (presentation, unbuilt), `[A']` (an *optional future* AI rewrite pass, explicitly not designed, sitting *on top of* `[A]`'s output) — and frames `[A]` as sitting "entirely upstream of where ADR-0005's boundary applies," with `[A']` remaining "optional... never a hard dependency."

**The contradiction this document surfaces, not previously stated this plainly:** Product Spec Section 3.3/5(11) describes a single-step, AI-mandatory narrative flow as *the* MVP behavior. The actual, currently-shippable MVP narrative (what a `GET /readings/{id}/narrative` call returns today, and what Step 12 validated end-to-end) is `[A]` alone — deterministic, no AI — with `[A']` remaining entirely hypothetical. `NARRATIVE_LAYER_DESIGN.md`'s framing implicitly treats this as sufficient for MVP ("[A]'s output must remain a complete, servable narrative on its own"), but that is an engineering design document's framing, not a Product Spec amendment. **Whether deterministic-only narrative (no AI, no Reflection Engine) is acceptable as *the* MVP "Narrative Generation" step Product Spec Section 5 describes, or whether Section 5 step 11 still requires an `[A']`-equivalent AI pass before MVP is considered complete, is an open product decision this document does not make** (Section 16, Q3).

## 15.4 "Saved record... permanently" (Section 5, step 14) assumes a snapshot model the implementation does not provide

Product Spec Section 5 step 14 describes saving as fixing "the interpretation engine version" as part of a permanent record. The implemented system instead allows unlimited reinterpretation after saving, with no mechanism pinning which specific `Interpretation` row was "the one that was saved" (Section 7, option 2 vs. 1/3). This is not a bug — `READING_INTEGRATION_DESIGN.md` Section 5 deliberately chose to allow post-save reinterpretation — but it does mean Section 5 step 14's literal "permanently preserves... interpretation engine version" (singular) no longer describes what the system actually does once more than one interpretation exists for a saved Reading. Recorded as a contradiction between the Product Spec's snapshot framing and the implementation's always-current framing; not resolved here.

---

# 16. Unresolved Decisions Requiring Product Judgment

Recorded, not decided, consistent with this task's explicit instruction:

**Q1 — Should `ReadingStatus.SPREAD_COMPLETE` ever be assigned, and if so, automatically (derived from evidence) or by an explicit user/UI action?** (Section 6) Both options are named; neither chosen. A third option (leave it permanently unused) is also live.

**Q2 — What should "Save Reading" actually do, now that persistence and saving are already decoupled?** (Section 7) Three candidate meanings named (pure bookmark, snapshot-pinning, ordering-only terminal marker); the first and third need no schema change, the second does. No API route or service function exists for any of them yet.

**Q3 — Is a deterministic-only Narrative Generation step (no AI, no Reflection Engine) acceptable as the MVP behavior Product Spec Section 5/3.3 describes, or does true MVP completion still require an `[A']`-equivalent AI rewrite pass?** (Section 15.3) This is the highest-authority open question in this document — it is a disagreement about what the Product Spec itself still requires, not merely an engineering gap.

**Q4 — Should `POST /interpret`'s response embed the narrative, or should a client always be expected to make a second `GET .../narrative` call?** (Section 10) Newly raised by this document; not previously asked by any prior design step. Answering "yes, embed it" would be a schema change to `InterpretationSummary`, out of scope for this document to make.

**Q5 — Should any status transition ever move backward** (an "unsave," a "reopen for editing")**, and if so, does evidence (`CardDraw`) ever become mutable again once `is_spread_complete` is reached?** (Section 11) No document, including this one, proposes a mechanism; Product Spec Section 17's "immutable once the spread is complete" is itself only loosely anchored given Section 6's finding that `status` never actually reaches a real `SPREAD_COMPLETE` transition today.

---

# 17. Explicit Boundaries

This document adds no code, schema, migration, or API route. It does not design:

- Any frontend/UI component, screen, or interaction beyond citing Product Spec Section 6's existing screen inventory for reference.
- Any AI/LLM prompt, wording, or Reflection Engine integration — Section 15.3 names the open question about whether one is still required; this document takes no position on how one would be built if the answer is yes.
- Any authentication, authorization, or ownership mechanism — unchanged from `INTERPRETATION_API_DESIGN.md` Sections 4–5.
- A `reading_service.py`/Draw entry API, a `POST /readings/{id}/save` route, a per-interpretation-ID detail route, or a `SPREAD_COMPLETE`-assignment mechanism — all are named as gaps (Sections 6, 7, 9, 12) but none is specified in enough detail to implement directly from this document; each would need its own dedicated design step, mirroring how every prior layer in this series (Engine, Narrative, Orchestration, API) received one.

---

## Related Documents

- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Sections 5, 6, 7.5, 17, 18, 3.3 — the specification this document validates against and finds several points of drift from (Section 15).
- `RAIDIAN_WISE_ARCHITECTURE_V1.md` — Section 2 (the unbuilt `reading_service.py`), Section 9 (the unbuilt `POST /readings/{id}/save` and general Reading CRUD sketch).
- `INTERPRETATION_ENGINE_DESIGN.md` — Q1's decision to model Interpretation as a related table, not Reading columns; the origin of `ReadingStatus.INTERPRETED`.
- `NARRATIVE_LAYER_DESIGN.md` — the `[A]`/`[B]`/`[A']` split this document's Section 15.3 finding is framed against.
- `READING_INTEGRATION_DESIGN.md` — Section 1.2's original discovery that `SPREAD_COMPLETE` is never assigned; Section 3's "not a precondition" decision; Section 5's transition table this document's Section 3/5 extends.
- `INTERPRETATION_API_DESIGN.md` — the four existing routes this document's Section 13 sequences; Sections 4–5's auth/authz gap, unchanged and not re-designed here.
- `READING_WORKFLOW_VALIDATION.md` — Section 3.3's global-`sequence`-vs-per-reading-version finding, directly load-bearing for this document's Section 9.
- `docs/DECISIONS.md` — ADR-0005 (AI exclusively through the Reflection Engine), the boundary Section 15.3's contradiction is about.
