# Raidian Wise — Reading/Draw Lifecycle Implementation Design (Step 15)

# Document Information

Version: 1.0 (Draft for Review — Not Yet Approved)
Status: Proposed — Design and Inspection Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Determines exactly how the six `PRODUCT_DECISIONS.md` (Step 14) recommendations for Q2 (`SPREAD_COMPLETE`), Q3 (`SAVED`), and Q6 (reversibility) should eventually be implemented, based on direct inspection of the actual current repository — `app/models/reading.py`, `app/models/card_draw.py`, `app/models/spread.py`, `app/models/spread_position.py`, their tests, and every governing design document — not assumption or restatement of Step 14's prose. This document implements nothing; it is the bridge between "what was decided" (Step 14) and "what a future implementation step should actually write."

Audience:
Whoever implements the future Reading/Draw lifecycle work this document points to, and anyone auditing whether that future implementation matches what was actually decided and what the current schema actually requires.

Authority:
Operationalizes `PRODUCT_DECISIONS.md` (Step 14) Q2/Q3/Q6 exactly as approved — this document does not reopen or amend any of the three. Concretizes `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2's `reading_service.py`/`draw_service.py` sketch and `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 17 (Versioning/immutability) and Section 6 (Reading History) against the actual, current `app/models/` and `app/services/` layout. Does not override `READING_INTEGRATION_DESIGN.md` or `INTERPRETATION_API_DESIGN.md` — both are treated as settled and their boundaries (`reading_orchestration.py` scoped strictly to Interpretation/Narrative, never to Reading/Draw creation) are preserved, not crossed.

---

# 0. Scope

Design and inspection only. Does not implement any code, schema, migration, API route, or frontend change. Does not reopen `PRODUCT_DECISIONS.md` Q2/Q3/Q6 — Section 15 records the one genuine tension found against the actual schema (optional positions), without changing any approved decision. Does not design a general Reading/Draw creation API (Layout selection, question entry, card search/selection, digital draw) — only the specific seam where `PRODUCT_DECISIONS.md`'s three decisions attach to that not-yet-built surface.

---

# 1. Executive Summary

**The single most consequential finding of this document: no schema change, migration, or new database column is required to implement Q2, Q3, or Q6.** `ReadingStatus.SPREAD_COMPLETE` and `ReadingStatus.SAVED` already exist as enum values (defined at Step 1, unused since); `Reading.is_spread_complete` already exists as a correct, safe, derived property (Step 9); `Reading.status` is already a plain mutable column. Everything Step 14 approved is a **behavior gap in code that does not exist yet**, not a **schema gap**. This directly confirms this task's own instruction not to add a `spread_complete` boolean, an interpretation-pinning field, or any Interpretation/sequence change — none would have been justified by this investigation regardless.

**Second finding: no new service module is required.** `Reading.add_card_draw()` (already the sole, tested creation path for every `CardDraw`) is a session-free method that already has everything it needs — `self.spread.positions` and `self.card_draws` are already-loaded relationships — to check-and-advance `status` to `SPREAD_COMPLETE` in the exact same method call, with no new module, no new service class, and no new dependency. `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2's `reading_service.py`/`draw_service.py` sketch remains a reasonable eventual home for the *larger*, not-yet-designed surface (Layout selection, digital draw, physical entry validation) — but Step 14's specific decisions do not, on their own, justify creating either module now.

**Third finding: CardDraw immutability is currently satisfied by omission, not enforcement.** No code path anywhere in this repository updates or deletes an existing `CardDraw` row (confirmed by repository-wide search) — the only mutation is `add_card_draw()`'s creation path. This means the "immutable once spread is complete" requirement (Product Spec Section 17) has nothing to actively guard today; it becomes a real, enforceable requirement only once/if a future "edit-in-place" feature (Product Spec Section 6's own phrase, describing the Spread Review screen) is built. Section 7 designs the guard that future feature must include, at the point it is built — not before.

**Fourth finding, a genuine tension against the Product Spec surfaced by this inspection, not previously found:** `SpreadPosition.required` exists as a real, already-implemented column, but every seeded Spread (`single_card`, `three_card`, `celtic_cross`) sets every position `required: true` — the "optional position" case Section 3 must consider is schema-supported but has zero real data exercising it. This creates one small, genuinely open edge case for the future implementation (Section 15) — not a defect, and not something this document decides.

---

# 2. Current-State Findings (Direct Repository Inspection)

## 2.1 Reading creation and mutation paths

`Reading` (`app/models/reading.py`) is created via its constructor directly (no factory/service wraps it — `tests/factories.py::make_reading`, `tests/interpretation_helpers.py::build_reading` both call `Reading(...)` directly). The only mutation method on the model itself is `add_card_draw()` (Section 2.2). `status` is a plain `Mapped[ReadingStatus]` column with no validator, no property setter guard, no `@validates` — **anything holding a `Reading` instance can set `reading.status` to any value at all today**, including backward. The only place that currently changes it under any real code path is `app/services/interpretation/persistence.py::save_interpretation()`'s `if reading.status != ReadingStatus.SAVED: reading.status = ReadingStatus.INTERPRETED`.

## 2.2 CardDraw creation and mutation paths

`Reading.add_card_draw()` is the **sole** creation path (confirmed: no other constructor call site for `CardDraw` exists outside tests, and the two direct-constructor tests — `test_only_one_card_per_position_at_the_database_level`, `test_draw_order_must_be_unique_within_a_reading` — exist specifically to prove the *database* still enforces the same invariants if that sole path is bypassed, not to establish a second real path). It validates, in order: position belongs to `self.spread`; card belongs to `self.deck`; no duplicate card unless `self.spread.allow_duplicate_cards`. **No update or delete path exists for `CardDraw` anywhere in `app/` today** — confirmed by repository-wide search for any mutation of an existing draw's fields or any deletion of an individual `CardDraw` row (deleting an entire `Reading`, which cascades, is a distinct operation — Section 7.4).

## 2.3 Existing models, enums, relationships, constraints, timestamps

- `ReadingStatus` (`app/models/enums.py`): `DRAFTING`, `SPREAD_COMPLETE`, `INTERPRETED`, `SAVED` — all four values already exist; only `DRAFTING` and `INTERPRETED` are ever assigned today (Section 2.1).
- `CardDraw` (`app/models/card_draw.py`): `UniqueConstraint(reading_id, position_id)` — **at most one draw per position per reading, database-enforced**, independent of any application code. `UniqueConstraint(reading_id, draw_order)` — draw order is unique per reading, database-enforced. `CheckConstraint(draw_order >= 1)`. `TimestampMixin` gives every `CardDraw` its own `created_at`/`updated_at`, though nothing currently reads `updated_at` for any draw (no update path exists to change it — Section 2.2).
- `Spread`/`SpreadPosition` (`app/models/spread.py`, `spread_position.py`): `Spread.position_count` is derived (`len(self.positions)`), the exact precedent `Reading.is_spread_complete` (Step 9) already follows. `SpreadPosition.required: Mapped[bool]` (default `True`) exists and is real, queryable data — not a placeholder.

## 2.4 Existing spread definitions and required/optional representation

Direct inspection of `backend/app/reference_data/spreads/*.yaml` (`single_card.yaml`, `three_card.yaml`, `celtic_cross.yaml`): **every single seeded position across all three spreads sets `required: true`.** No optional position exists anywhere in the currently-seeded reference data. `required=False` is fully schema-supported and would work correctly with `is_spread_complete`'s existing logic (Section 3) if it were ever used — but it has never been exercised against real data. This is the basis for Section 15's one flagged edge case.

## 2.5 Existing service/repository layer

No `reading_service.py`, `draw_service.py`, or any Reading/Draw-scoped service module exists (confirmed, matching `READING_INTEGRATION_DESIGN.md` Section 1.2's original finding, unchanged through Steps 9–14). The only service-shaped module touching `Reading` at all is `app/services/reading_orchestration.py` — and its own docstring explicitly scopes it to combining database access with the Interpretation Engine and Narrative Layer only; it is **not** an appropriate home for Reading/Draw creation logic, and this document does not propose extending it that way (Section 5).

## 2.6 Existing API routes or other callers

The only API routes that exist at all are the four interpretation/narrative routes (`app/api/interpretation.py`, Step 11) — none of them create or mutate a `Reading` or `CardDraw`; each only reads an already-existing `Reading` by ID. **No route exists anywhere that creates a Reading, records a draw, or saves a Reading.** This confirms `READING_LIFECYCLE_DESIGN.md` Section 12's "Gap" rows are still accurate.

## 2.7 Existing transaction boundaries

Every existing mutator in this codebase follows one consistent convention, confirmed again here: **flush, never commit; the caller controls the transaction.** `Reading.add_card_draw()` doesn't even flush (callers flush explicitly — every test does). `save_interpretation()` flushes but does not commit. `app/db/session.py::get_db()` (Step 11) is the one place that commits, and only at the HTTP request boundary. Any future Reading/Draw lifecycle code is expected, per this established pattern, to do the same — flush at most, never commit, so a future API layer's `get_db()` remains the single commit point.

## 2.8 Existing tests covering Reading/CardDraw behavior

`test_reflection_session_and_reading.py` (8 tests) and `test_card_draw.py` (10 tests) cover: defaults, one-to-one `ReflectionSession`/`Reading`, cascade deletes, blank-question rejection, draw creation via `add_card_draw()`, cross-spread/cross-deck rejection, duplicate-card policy, database-level uniqueness (position, draw order), and restricted deletion of a still-referenced `Card`/`Spread`. **No existing test exercises `is_spread_complete` becoming `True` as a side effect of a specific draw being added, or any status transition triggered by draw creation** — `is_spread_complete` is currently only tested via `test_reading_orchestration.py`'s pre-built, already-complete or already-incomplete fixtures, never via the moment-of-transition itself. Section 13 names this gap explicitly.

## 2.9 Existing enforcement of immutability

**None exists today**, for the reason given in Section 2.2: there is nothing to enforce yet, because no mutation path exists to guard. This is not a defect; Section 7 designs the guard for when a mutation path is eventually built.

## 2.10 Existing use/assignment of each status value

Restated precisely from Section 2.1: `DRAFTING` (model default, never re-assigned), `SPREAD_COMPLETE` (never assigned by any production code), `INTERPRETED` (assigned exactly once, in `save_interpretation()`), `SAVED` (never assigned by any production code; only ever set directly by tests to exercise `persistence.py`'s preservation guard).

## 2.11 Product Spec requirements — completion, immutable draws, saving/history, transitions

`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 5 steps 8–9 (review before proceeding; explicit interpret trigger), Section 6 ("Spread Review... edit-in-place still available here"; "Reading History — list of **saved** Readings"), Section 17 ("Original Reading Evidence (immutable once the spread is complete)... A future 'Reinterpret with current engine' action should be able to overwrite/append... without touching any Card Draw row"). All already cited and reasoned from in `READING_LIFECYCLE_DESIGN.md` and `PRODUCT_DECISIONS.md`; this document adds no new Product Spec citation beyond what those two already established, per this task's instruction not to reopen the approved decisions.

## 2.12 Architecture/design documents constraining where this logic belongs

`RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2's `reading_service.py`/`draw_service.py` sketch (cited, not adopted wholesale — Section 5). `READING_INTEGRATION_DESIGN.md`'s repeated "derive, don't store-and-risk-drift" precedent (`Spread.position_count`, `Reading.is_spread_complete`) directly informs Section 3's conclusion not to invent a new completion rule. `reading_orchestration.py`'s own module docstring ("the only module permitted to combine database access with calls into the Interpretation Engine... and Narrative Layer") is a hard boundary this document's Section 5 respects rather than crosses.

---

# 3. Spread Completion Definition

**Conclusion: the existing definition is already correct, safe, and sufficient. No new completion rule is proposed.**

`Reading.is_spread_complete` (`app/models/reading.py`, Step 9): `{p.id for p in self.spread.positions if p.required}.issubset({d.position_id for d in self.card_draws})`. Checked against every consideration this task names:

- **Required positions:** the property already keys exclusively off `SpreadPosition.required` — an optional (`required=False`) position's absence never blocks completion. Correct as-is.
- **Number of required draws:** deliberately **not** used as a count comparison (`len(card_draws) >= required_count`) — Section 3.1 explains why a count-based rule would be a regression, not a simplification.
- **Optional positions:** fully supported by the existing set-subset logic without any change — an optional position may be filled or unfilled; either way, completion depends only on the required set. (Section 15 names the one real edge case this raises for *future draw entry*, not for this definition's correctness.)
- **Duplicate positions:** impossible by construction — `CardDraw`'s own `UniqueConstraint(reading_id, position_id)` guarantees at most one draw per position per reading at the database level, independent of any application code (Section 2.3). The property's use of Python `set`s over position **IDs** (not names or order) is already immune to any duplicate-*name* edge case too.
- **Does the current schema already guarantee completeness?** No single constraint guarantees it alone, but the *combination* already used (the FK from `CardDraw.position_id` to a real `SpreadPosition`, that position's own `spread_id` — validated by `add_card_draw()`, not the database, Section 7 — and the uniqueness constraint above) is sufficient for the derived property to be reliably correct. This is an existing, already-tested guarantee, not a new one.

## 3.1 Why a count-based rule was considered and rejected

An alternative, superficially simpler rule — "`len(reading.card_draws) >= reading.spread.position_count`" — was explicitly considered, per this task's instruction to compare against "number of required draws." It is **rejected**: it would count draws for *optional* positions toward completion of the *required* set, silently reporting a Reading complete when a required position is actually still empty (as long as some optional position was filled instead). The existing set-subset definition has no such failure mode. This document recommends the existing property remain completely unchanged.

---

# 4. Lifecycle Ownership Boundary

**Recommendation: no new service module. The extension point is `Reading.add_card_draw()` itself.**

Verified against Section 2.5/2.12 rather than assumed: `RAIDIAN_WISE_ARCHITECTURE_V1.md`'s `reading_service.py`/`draw_service.py` sketch describes a **much larger** surface (Layout selection, question entry, digital draw randomization, physical entry validation) that Step 14 never asked this document to build, and building either module now, for only the `SPREAD_COMPLETE` transition, would be exactly the "speculative functionality" this task prohibits. The actual, minimal seam Step 14's Q2 decision requires — "the moment `is_spread_complete` first becomes `True`, persist `SPREAD_COMPLETE`" — needs nothing that `add_card_draw()` doesn't already have in scope: `self.spread.positions` and `self.card_draws` are both already-loaded relationships at the point `add_card_draw()` runs; no session, no query, and no new module is required to check them.

This mirrors an already-established precedent exactly: `save_interpretation()` (a plain function, not a service class) already combines "create the primary row" with "check-and-advance `status`" in one call, guarded by a status check (`if reading.status != ReadingStatus.SAVED`) before assigning. `add_card_draw()` extended the same way — "create the primary row" (the `CardDraw`) plus "check-and-advance `status`" (to `SPREAD_COMPLETE`), guarded the same way — is not a new architectural pattern; it is the same one, applied one level up the lifecycle.

**What this recommendation explicitly does not cover, and defers:** the *larger* Reading/Draw creation surface (`reading_service.py`/`draw_service.py`'s full sketch — Layout selection, question entry, digital draw, physical card-entry validation) remains real, future, undesigned work. When that surface is eventually built, this document's recommendation is that it call into an extended `Reading.add_card_draw()` for the actual draw-recording step, exactly as it does today — not that it duplicate `SPREAD_COMPLETE`/immutability logic itself.

---

# 5. `SPREAD_COMPLETE` Transition Design

**Triggering operation:** `Reading.add_card_draw()` (extended), immediately after a new `CardDraw` is successfully appended to `self.card_draws` — not before (Section 5.1 explains the ordering).

**Precondition:** `self.is_spread_complete` is `True` (checked *after* the new draw is appended, so the just-added draw is already reflected in `self.card_draws`) **and** `self.status == ReadingStatus.DRAFTING` (the guard — Section 5.2).

**Exact status transition:** `self.status = ReadingStatus.SPREAD_COMPLETE`. Nothing else changes — no `CardDraw` field, no other `Reading` field.

**What happens if the operation fails:** every existing validation in `add_card_draw()` (`position.spread_id != self.spread_id`, `card.deck_id != self.deck_id`, `DuplicateCardError`) already raises **before** the draw is appended to `self.card_draws` — this ordering is unchanged, so a failed call never reaches the new completion check at all, and `self.status` is left untouched. If the *new* completion-check code itself were ever to raise (it should not — reading two already-loaded relationships and comparing sets cannot fail), the same guarantee holds by construction: the draw would already be appended in memory, but nothing would be flushed or committed unless the caller does so, and a caller-initiated rollback undoes it identically to any other uncommitted change (Section 10).

**Transaction behavior:** unchanged from every existing convention in this codebase (Section 2.7) — `add_card_draw()` still does not flush or commit; the caller does, exactly as every existing caller (all of `test_card_draw.py`) already does today.

**Idempotency:** guaranteed by the `self.status == ReadingStatus.DRAFTING` guard, not by accident. Once `status` has advanced past `DRAFTING`, `add_card_draw()` is expected to reject any further call outright (Section 7) — so the completion check can never run a second time for the same Reading under the recommended design. Even considered in isolation, re-assigning the same enum value twice is a semantic no-op; the guard exists primarily to prevent the transition from ever firing out of order, not merely to avoid redundant writes.

## 5.1 Why the check happens after the append, not before

`is_spread_complete` must see the draw that was *just* added to correctly detect the position where completion happens on the last required position. Checking before the append would always be one draw stale.

## 5.2 Why the guard is `status == DRAFTING`, not merely `is_spread_complete and status != SPREAD_COMPLETE`

Only `DRAFTING` is a valid "before" state for this specific transition (Section 9's transition table). A Reading already at `INTERPRETED` or `SAVED` whose `is_spread_complete` is (and always was) `True` must never have its `status` silently reset backward to `SPREAD_COMPLETE` by some later, unrelated code path re-checking the same condition — the guard's job is exactly to make that structurally impossible, consistent with Q6's "no backward transition" requirement.

## 5.3 Illustrative sketch — not implemented by this document

```python
# Illustrative signature and body -- not implemented by this document.
# app/models/reading.py, Reading.add_card_draw(), extended:

def add_card_draw(self, *, position, card, orientation, draw_order) -> "CardDraw":
    if self.status != ReadingStatus.DRAFTING:
        raise ReadingNotDraftingError(          # new domain error, mirrors DuplicateCardError
            f"reading {self.id} is not DRAFTING (status={self.status}); "
            "card draws can only be recorded while a reading is drafting"
        )
    if position.spread_id != self.spread_id:
        raise ValueError("position does not belong to this reading's spread")
    if card.deck_id != self.deck_id:
        raise ValueError("card does not belong to this reading's deck")
    if not self.spread.allow_duplicate_cards and any(
        existing.card_id == card.id for existing in self.card_draws
    ):
        raise DuplicateCardError(f"card {card.id} has already been drawn in this reading")

    draw = CardDraw(position=position, card=card, orientation=orientation, draw_order=draw_order)
    self.card_draws.append(draw)

    if self.is_spread_complete:            # status == DRAFTING already guaranteed by the guard above
        self.status = ReadingStatus.SPREAD_COMPLETE

    return draw
```

Note the new leading guard (`status != DRAFTING` → `ReadingNotDraftingError`) is Section 7's immutability enforcement, placed here because it is the same method — Sections 5 and 7 are two faces of one extension to one method, not two separate changes.

---

# 6. `SAVED` / Reading History Design

**Current state, confirmed by inspection (Section 2.6):** no Reading History mechanism exists in any form — no route, no query, no schema for one.

**Future boundary, per `PRODUCT_DECISIONS.md` Q3 (not reopened here):**
- **Saving:** a future, explicit action — illustratively, a `save_reading(reading)` step, most simply expressed as a guarded assignment (`if reading.status in {SPREAD_COMPLETE, INTERPRETED}: reading.status = ReadingStatus.SAVED`, per Section 9's transition table — both `SPREAD_COMPLETE` and `INTERPRETED` are valid "before" states, confirming saving does **not** require interpretation to have happened first). This document does not design the API route or service module that would call it — only the guard condition, since that is the piece Q2/Q6 constrain.
- **Unsaving:** **not allowed**, per Q6 (no backward transition) — restated here, not reopened.
- **Listing saved Readings:** a future query filtering `Reading.status == ReadingStatus.SAVED` — no new schema or index is identified as necessary by this investigation (an index on `status` is a plausible future performance detail, not a correctness requirement, and is not designed here as it would be premature without a real query pattern to measure against).
- **Can `SAVED` coexist with `INTERPRETED`?** Not as two simultaneous `status` values (the column is single-valued — a Reading is `SAVED` *or* `INTERPRETED`, never both at once). But the underlying **Interpretation history** (rows in the `interpretations` table) is a completely separate, independently-accumulating concern (Q3, unchanged) — a `SAVED` Reading can have any number of `Interpretation` rows, created before or after saving, with zero interaction with the `status` column. This is "coexistence" in the only sense that matters: saving never blocks, gates, or is gated by interpretation history.
- **Is an interpreted-but-unsaved Reading intentionally absent from History?** **Yes**, confirmed unchanged from `PRODUCT_DECISIONS.md` Q3, grounded in Product Spec Section 6's literal "list of saved Readings."

This document does not implement the Save workflow, per this task's explicit instruction — Section 14 names it as future work.

---

# 7. CardDraw Immutability Design

## 7.1 Enforcement layer comparison

| Mechanism | Verdict | Reasoning |
|---|---|---|
| **Model/domain-method enforcement** (a guard inside `add_card_draw()`, and inside any future edit/remove method) | **Recommended** | Matches the only pattern this codebase already uses for exactly this kind of invariant (`DuplicateCardError`, the cross-spread/cross-deck `ValueError`s already in `add_card_draw()`). Cannot be bypassed by any caller that goes through the model, which — per Section 2.2 — is the *only* path that exists today. |
| **Database constraints/triggers** | **Rejected** | This project has never used a database trigger anywhere (confirmed by inspection of every migration and model — `CheckConstraint`s are used only for simple, context-free invariants like `draw_order >= 1`, never for cross-table, status-dependent rules). Expressing "no update/delete once the *parent Reading's* status is past X" as a portable (SQLite + PostgreSQL) trigger would introduce an entirely new, unprecedented mechanism for this one rule alone — a large, disproportionate architectural change this document does not recommend introducing. |
| **API-layer enforcement only** | **Rejected as sole mechanism** | Exactly the reasoning `READING_INTEGRATION_DESIGN.md` and `INTERPRETATION_API_DESIGN.md` already applied to other rules: an API route is a thin translator, not the source of truth — any other caller (a test, a script, a future background job) that reaches the model directly would bypass an API-only check. Acceptable only as **defense-in-depth** once a real API exists for draw mutation (which it does not today). |
| **Service-layer enforcement** | **Not applicable given Section 4's conclusion** | Since no new service module is being introduced (Section 4), there is no service layer distinct from the model layer for this specific rule to live in. If the larger `reading_service.py`/`draw_service.py` surface is ever built, it would naturally call into the same model-level guard rather than duplicate it. |

**Recommended mechanism: model-level guard, exactly as sketched in Section 5.3.** No database trigger. No new service module. An API-layer check is a reasonable future addition purely as a UX nicety (returning a clean `409`-style error before ever reaching the model) once a real draw-mutation API exists — not a substitute for the model-level guard.

## 7.2 What "immutable" means — explicit definition

Per this task's explicit instruction not to assume "immutable" means only "no update," each sub-case is addressed:

- **Existing `CardDraw` rows cannot be updated.** Covered by the same guard (Section 5.3's `status != DRAFTING` check) applied to any future edit method — none exists today, so this is a requirement on a method that does not yet exist, not a retrofit of one that does.
- **Existing `CardDraw` rows cannot be deleted individually.** Same guard, applied to any future per-draw removal method — none exists today either.
- **New `CardDraw` rows cannot be added.** This is the one immutability sub-case that **is** already fully enforced by Section 5.3's sketch today (the leading guard in `add_card_draw()` itself) — the only case where this document's Section 5 and Section 7 recommendations are literally the same code path.
- **Relationships cannot be changed.** Subsumed under "cannot be updated" — `position_id`/`card_id` are ordinary fields from the guard's point of view.
- **Administrative correction/reversal is not designed.** No admin/back-office concept exists anywhere in this codebase (consistent with the already-documented absence of any auth/authz infrastructure — `INTERPRETATION_API_DESIGN.md` Sections 4–5). The recommended escape hatch for a genuine data-entry mistake discovered after `SPREAD_COMPLETE` is **deleting the entire Reading** (already fully supported — `test_deleting_reading_cascades_to_its_card_draws`) and starting a new one, not a partial-edit exception. A partial-edit exception would directly undermine the immutability guarantee Product Spec Section 17 asks for; whole-Reading deletion is a different operation (discarding a record entirely, not editing one in place) and is explicitly not restricted by this design.

## 7.3 Reconciliation with the Product Spec

Product Spec Section 17: "Original Reading Evidence (immutable once the spread is complete)." Section 6: "Spread Review... edit-in-place still available here." These two are not in tension once "edit-in-place" is read as describing the `DRAFTING` state (before the last required position is filled — a user can still be correcting earlier positions while later ones remain unfilled) rather than describing an action available *after* `SPREAD_COMPLETE`. This document adopts that reading explicitly, since it is the only one consistent with Section 17's own, more specific, and later-appearing immutability language — recorded as an interpretation this document is making, not a rewording of either section.

## 7.4 Whole-Reading deletion is a distinct operation, not an immutability exception

`test_deleting_reading_cascades_to_its_card_draws` already proves deleting an entire `Reading` deletes its `CardDraw` rows too, regardless of `status`. This is unaffected by, and not an exception to, the immutability design above — immutability (Section 7.2) is about *editing a Reading's evidence while keeping the Reading itself*, not about whether the Reading as a whole can ever be removed. This document does not restrict whole-Reading deletion in any way.

---

# 8. Complete Lifecycle Transition Matrix

Every row from this task's template, plus the rows needed for completeness, each marked **Existing** (implemented and tested today) or **Future** (requires the code this document designs, not yet implemented):

| Current | Event | Condition | Result | Status |
|---|---|---|---|---|
| *(none)* | Reading created | — | `DRAFTING` | **Existing** — model default |
| `DRAFTING` | draw added | incomplete | `DRAFTING` (unchanged) | **Existing** — `add_card_draw()` never touches `status` today; remains correct behavior after Section 5's extension too (the guard only fires when `is_spread_complete` becomes `True`) |
| `DRAFTING` | final required draw added | complete | `SPREAD_COMPLETE` | **Future** — Section 5 |
| `SPREAD_COMPLETE` | interpretation | complete | `INTERPRETED` | **Existing** — `test_spread_complete_transitions_to_interpreted` already passes against a manually-set `SPREAD_COMPLETE` fixture; will be exercised by real data once Section 5 ships |
| `DRAFTING` | interpretation | complete (`is_spread_complete` true despite `status` not yet reflecting it — e.g. data predating Section 5's mechanism) | `INTERPRETED` | **Existing** — `test_drafting_transitions_to_interpreted`; deliberately preserved, unchanged, as defensive allowance (Section 11) |
| `INTERPRETED` | reinterpretation | complete | `INTERPRETED` (unchanged) | **Existing** — `test_interpreted_stays_interpreted_on_reinterpretation` |
| `SPREAD_COMPLETE` | save | valid | `SAVED` | **Future** — Section 6 |
| `INTERPRETED` | save | valid | `SAVED` | **Future** — Section 6 |
| `SAVED` | reinterpretation | complete | `SAVED` (unchanged) | **Existing** — `test_saved_reading_remains_saved_after_reinterpretation`, re-confirmed Step 11/12 |
| `SAVED` | draw added | — | **rejected** (`ReadingNotDraftingError`) | **Future** — Section 7 (today, nothing prevents this at all — a real, currently-open gap this document's recommendation closes) |
| `SPREAD_COMPLETE`/`INTERPRETED` | draw added | — | **rejected** (`ReadingNotDraftingError`) | **Future** — Section 7, same gap |

## 8.1 Prohibited backward transitions (explicit, per Q6)

| From | To | Verdict |
|---|---|---|
| `SPREAD_COMPLETE`, `INTERPRETED`, or `SAVED` | `DRAFTING` | **Prohibited** — no code path today attempts this, and none is recommended |
| `SAVED` | any earlier value | **Prohibited** — no "unsave" action exists or is recommended |
| `INTERPRETED` | `SPREAD_COMPLETE` | **Prohibited** — not meaningful once interpretation has occurred; not attempted anywhere |

No row in this document, in either table, introduces a transition not already implied by `PRODUCT_DECISIONS.md` Q2/Q3/Q6 or by code already shipped and tested through Step 12.

---

# 9. Transaction/Error Semantics

Restating Sections 5 and 7's transaction behavior as one coherent whole, plus the new error type this design introduces:

- **New domain error, illustrative:** `ReadingNotDraftingError(ValueError)` — mirrors `DuplicateCardError`'s existing shape exactly (a `ValueError` subclass raised by the model itself, not by any service or API layer). Raised by `add_card_draw()` (Section 5.3) when `self.status != ReadingStatus.DRAFTING`, and by any future edit/remove method for the same reason (Section 7.2).
- **Flush/commit convention:** unchanged (Section 2.7) — `add_card_draw()` remains flush/commit-free; the caller controls the transaction boundary, exactly as every existing test and every existing service function already does.
- **Rollback behavior:** identical to the already-proven pattern in `test_interpret_reading_does_not_commit_the_session` (Step 9) — if a caller adds a draw (potentially triggering the `SPREAD_COMPLETE` transition in the same in-memory operation) and then rolls back before committing, both the new `CardDraw` row and the `status` change are undone together, since neither was ever flushed-and-committed. No new rollback mechanism is required; the existing SQLAlchemy session semantics already guarantee this.
- **Partial-failure behavior:** already covered by Section 5's "what happens if the operation fails" — every existing validation raises before the new draw is appended, so a failed call can never leave the `Reading` in a half-transitioned state.

---

# 10. API/Service Boundary

No API route exists for Reading/Draw creation today (Section 2.6), and this document does not design one. The boundary this document does fix, for whenever such a route is eventually built: **the route must call `Reading.add_card_draw()` (extended per Section 5/7) for the actual draw-recording step, and must not re-implement the `SPREAD_COMPLETE` check, the immutability guard, or the completion definition itself.** This mirrors `app/api/interpretation.py`'s own existing discipline exactly — call the model/orchestration layer, never duplicate its logic (`INTERPRETATION_API_DESIGN.md` Section 16's "must not duplicate orchestration logic," applied here one layer down, to the model instead of `reading_orchestration.py`). `reading_orchestration.py` itself remains untouched and out of scope — Reading/Draw creation is not an Interpretation or Narrative concern, and does not belong inside a module whose own docstring says otherwise (Section 2.12).

---

# 11. Migration/Schema Impact

**None.** Restating Section 1's headline finding with the explicit checklist this task requires:

- No field is added for convenience — none was found to be missing.
- No `spread_complete` boolean is added — `is_spread_complete` remains the sole, safely-derivable source of truth (Section 3).
- No interpretation-pinning field is added — out of scope for this document and not implied by Q2/Q3/Q6 in any case (already settled, `PRODUCT_DECISIONS.md` Q4).
- The `Interpretation` model and `sequence` mechanism are untouched — nothing in this investigation found any reason to alter either.
- No existing schema is redesigned — `ReadingStatus`, `Reading.status`, `CardDraw`'s constraints, and `SpreadPosition.required` are all used exactly as they already exist.

If a future implementation step's own investigation finds a genuine need for a migration (none is identified here), that would be a new finding requiring its own review — not something this document anticipates or pre-authorizes.

---

# 12. Testing Plan

Separated explicitly, per this task's instruction, into tests validating **existing** behavior (already passing, cited for completeness) and tests a **future** implementation must newly satisfy.

## 12.1 Existing behavior (already covered, cited, not proposed as new)

- Incomplete Reading remains `DRAFTING` after a partial draw — implicitly covered today (`add_card_draw()` never touches `status`); no test currently asserts this *as a lifecycle fact* (only as an absence of change), so one small, explicit test is recommended in Section 12.2 to close that gap even though the underlying behavior already exists.
- Interpretation from `SPREAD_COMPLETE` works — `test_spread_complete_transitions_to_interpreted`.
- Reinterpretation preserves `INTERPRETED` — `test_interpreted_stays_interpreted_on_reinterpretation`.
- Reinterpretation of `SAVED` preserves `SAVED` — `test_saved_reading_remains_saved_after_reinterpretation`, re-confirmed at the API/e2e layers.
- Transaction rollback leaves Reading interpretation state unchanged — `test_interpret_reading_does_not_commit_the_session` (Step 9), same underlying SQLAlchemy semantics this document's Section 9 relies on for the new draw-adding path.

## 12.2 Future — required once Section 5/7's mechanism is implemented

- The final required draw transitions `DRAFTING` → `SPREAD_COMPLETE` (a new, direct test of the moment of transition — not currently exercised, per Section 2.8's gap finding).
- An earlier (non-final) draw leaves status at `DRAFTING`, explicitly asserted as a lifecycle fact, not merely as an absence of a different value.
- Completion is idempotent — calling any further mutator against an already-`SPREAD_COMPLETE` Reading does not re-fire the transition or change `status` again (made structurally true by the guard, Section 5.2 — a regression test should still exist).
- Draws cannot be added after `SPREAD_COMPLETE`/`INTERPRETED`/`SAVED` — `ReadingNotDraftingError` raised, no `CardDraw` row created, `status` unchanged.
- (Only buildable once a future edit/remove method exists — recorded here as required tests for *that* future work, not for Section 5/7 alone): draws cannot be modified after completion; draws cannot be deleted after completion.
- Save does not alter Interpretation history — a Reading with N existing `Interpretation` rows still has exactly N after saving (trivial once Section 6's save mechanism exists, but should be asserted explicitly, mirroring the discipline already used in `test_reading_workflow_e2e.py`).
- Unsaved, interpreted Readings do not appear in a saved-history query result — once Section 6's history query exists, a direct test: build one `SAVED` and one merely-`INTERPRETED` Reading, query for `status == SAVED`, assert only the former is returned.
- No lifecycle operation produces a backward transition — a parametrized test asserting every row in Section 8.1's prohibited table cannot occur via any exposed method.
- Transaction rollback leaves both `Reading` and `CardDraw` state unchanged — build on a completed-but-uncommitted draw-adding call (potentially including a `SPREAD_COMPLETE` transition), roll back, assert both the draw and the status revert, mirroring `test_interpret_reading_does_not_commit_the_session`'s exact pattern one layer down.

---

# 13. Implementation Sequence for the Future Step

Recommended order for whoever eventually implements this design (not performed here):

1. Add `ReadingNotDraftingError` to `app/models/exceptions.py`, alongside `DuplicateCardError`.
2. Extend `Reading.add_card_draw()` per Section 5.3 (leading guard + trailing completion check) — no other file needs to change for Q2/Q7 alone.
3. Add the tests named in Section 12.2 that are buildable against step 2 alone (completion transition, idempotency, post-completion draw rejection, rollback).
4. Only once a real Reading/Draw creation API is separately designed and approved (out of scope here): wire a route to call the extended `add_card_draw()`, per Section 10's boundary.
5. Separately, once a "Save Reading" design is approved (out of scope here): add the guarded `status = SAVED` assignment (Section 6) and the saved-history query, plus their Section 12.2 tests.
6. Run the full test suite after each step; no step in this sequence should ever reduce the passing count below the running total at that point.

Steps 4 and 5 are **not** authorized by this document — they each require their own dedicated design step (mirroring how every prior layer in this series — Engine, Narrative, Orchestration, API — received one before implementation), consistent with this task's "do not implement anything yet" instruction covering the whole of Step 15, not just its earliest steps.

---

# 14. Risks and Edge Cases

- **The optional-position edge case (Section 2.4/15).** No real spread exercises `required=False` today; the moment one does, a question this document does not resolve becomes live: should a draw for a still-open *optional* position be accepted after all *required* positions are already filled (i.e., after `status` has already advanced to `SPREAD_COMPLETE`)? Section 5/7's recommended guard (`status != DRAFTING` rejects *all* further draws, optional positions included) answers this by default — simplest, safest, and consistent with treating `SPREAD_COMPLETE` as a hard evidence-freeze point — but is named here as a real product question a future spread with optional positions would surface, not silently pre-empted.
- **A Reading whose Spread has zero required positions.** `is_spread_complete` would be vacuously `True` immediately after creation, before any draw is ever added (`required_position_ids` would be the empty set, trivially a subset of anything). No such Spread exists today (Section 2.4), so this is a theoretical edge case, not an observed one — flagged, not fixed, since fixing a hypothetical is exactly the kind of speculative work this task prohibits.
- **Concurrent draw-adding against the same Reading.** Out of scope, consistent with `Interpretation.sequence`'s own documented acceptance of "no locking around... acceptable for its current single-writer-per-reading usage pattern" (`app/models/interpretation.py`) — the same assumption is inherited here without re-litigating it.

---

# 15. Open Questions / Explicitly Deferred Items

- **The optional-position-after-`SPREAD_COMPLETE` question (Section 14)** — recorded, not decided; the default behavior (reject) is recommended but not mandated as permanent.
- **Whether an API-layer check should eventually be added as defense-in-depth once a real draw-mutation route exists (Section 7.1)** — plausible, not designed, since no such route exists yet.
- **Whether `SpreadPosition.required=False` will ever actually be used by a real Spread** — a reference-data/content question, entirely outside this document's or this task's scope.
- **The full `reading_service.py`/`draw_service.py` surface (Layout selection, question entry, digital draw, physical entry validation)** — real, future, substantial work; this document only fixes the one seam Step 14's decisions touch, not the whole surface Architecture Section 2 sketches.

---

# 16. Final Recommendation

Implement Q2 (`SPREAD_COMPLETE`) and the CardDraw-addition half of Q6/immutability together, as a single, small extension to `Reading.add_card_draw()` (Section 5.3) plus one new exception class — no new service module, no schema change, no migration. Implement Q3 (`SAVED`)/Q6's save-related rows only once a dedicated "Save Reading" design step (mirroring this series' own established practice) has approved the actual API route and service boundary — this document fixes only the guard condition (`status in {SPREAD_COMPLETE, INTERPRETED}`) that step must use, not the route itself. Do not build the larger Reading/Draw creation surface as part of implementing either — that remains separate, future, and substantially larger work.

---

## Related Documents

- `PRODUCT_DECISIONS.md` — Q2, Q3, Q6, the decisions this document operationalizes without reopening.
- `READING_LIFECYCLE_DESIGN.md` — Section 6/7/11's original open questions, now resolved by `PRODUCT_DECISIONS.md` and made concrete here.
- `RAIDIAN_WISE_ARCHITECTURE_V1.md` — Section 2's `reading_service.py`/`draw_service.py` sketch, cited and deliberately not adopted wholesale (Section 4).
- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Sections 5, 6, 17 — the completion/immutability/history requirements this document reconciles against the actual schema.
- `READING_INTEGRATION_DESIGN.md` — the "derive, don't store-and-risk-drift" precedent this document extends to reaffirm `is_spread_complete`, and `reading_orchestration.py`'s scope boundary this document declines to cross.
- `INTERPRETATION_API_DESIGN.md` — Section 16's "must not duplicate orchestration logic" principle, applied here to the model/API boundary (Section 10).
- `app/models/reading.py`, `app/models/card_draw.py`, `app/models/spread.py`, `app/models/spread_position.py`, `app/models/exceptions.py` — the actual, current code this document's every recommendation is checked against.
