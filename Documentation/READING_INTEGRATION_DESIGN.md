# Raidian Wise — Reading Integration Design (Step 8)

# Document Information

Version: 1.1 (Draft for Review — all four follow-on questions resolved)
Status: Proposed — Design Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Defines the lifecycle that connects a completed `Reading` to the already-implemented, already-validated Interpretation Engine (`app/services/interpretation/`) and Narrative Layer (`app/services/narrative/`): when interpretation is triggered, what persists, how history is retained, how the narrative is supplied, and where the remaining orchestration, error-handling, and transaction-boundary gaps are. This document designs the **integration** between three already-complete pieces — it does not redesign any of them.

Audience:
Software engineers and AI development agents who will implement the orchestration layer this document specifies (a future step, not this one), and anyone auditing what of "Reading → Interpretation → Narrative" already works today versus what remains to be built.

Authority:
Concretizes `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 17 (Versioning) and Section 18 (MVP Scope's "Interpret My Reading" flow) and `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2 (Backend Module Layout) and Section 9 (API Sketch) against the actual, current implementation (`app/models/`, `app/services/interpretation/`, `app/services/narrative/`), the same way each prior design document in this series concretized its predecessor. Does not override `INTERPRETATION_ENGINE_DESIGN.md`, `INTERPRETATION_RULES_DESIGN.md`, or `NARRATIVE_LAYER_DESIGN.md` — it assumes their decisions as settled and does not revisit them.

---

# 0. Scope

This document defines **Step 8 only**: the lifecycle design connecting `Reading` to interpretation and narrative assembly. It does **not**:

- Implement any orchestration code, API route, or migration.
- Add a frontend or UI of any kind.
- Add LLM/AI logic or design an LLM prompt.
- Add, activate, or modify any interpretation rule (`INTERPRETATION_RULES_DESIGN.md`'s supported/proposed/deferred classification is unchanged).
- Modify `InterpretiveModel` or `NarrativeModel` — both are treated as fixed, already-approved contracts.
- Introduce a schema change unless this document explicitly concludes one is justified (Section 9 explicitly concludes one is **not**).

---

# 1. Repository Inspection Summary

## 1.1 What already exists, implemented and tested — more than the task's framing might suggest

A close inspection of `app/services/interpretation/persistence.py`, `app/models/reading.py`, `app/models/interpretation.py`, and their existing tests (`test_interpretation_engine.py`) shows that **most of the data-layer half of this lifecycle is already built and passing 202 tests**, not merely designed:

- `engine.interpret(reading, session) -> InterpretiveModel` — pure except one reference-data read, already proven deterministic (`INTERPRETATION_ENGINE_VALIDATION.md`).
- `persistence.save_interpretation(session, reading, model) -> Interpretation` — already creates a new `Interpretation` row, already sets `reading.status = ReadingStatus.INTERPRETED`, already calls `session.flush()` (not `session.commit()` — commit is left to the caller, a convention this document adopts unchanged in Section 14).
- **Reinterpretation already works and is already tested**: `test_reinterpreting_preserves_the_prior_interpretation` proves that calling `interpret()` + `save_interpretation()` a second time against the same `Reading` creates a second `Interpretation` row, leaves the first row and all `CardDraw` rows untouched, and both rows remain reachable via `reading.interpretations`. Section 5/6 below describe this as **existing**, not proposed.
- `NarrativeModel` assembly (`assembler.assemble_narrative`) is implemented, tested, and provably database-free (`INTERPRETATION_RULES_DESIGN.md`... — actually `NARRATIVE_LAYER_DESIGN.md`/Step 7's own test suite, including a static source-inspection test proving no `sqlalchemy`/`Session`/`app.models` reference exists in the narrative package at all).

## 1.2 What does not exist yet — the actual gap this document addresses

- **No orchestration function connects them.** Nothing in the repository calls `engine.interpret()` and `persistence.save_interpretation()` together in response to anything. Nothing calls `assembler.assemble_narrative()` against a *persisted* `Interpretation` row — the only callers today are tests that build an `InterpretiveModel` directly.
- **No API layer exists at all.** `backend/app/api/` does not exist (confirmed by directory search); `backend/app/main.py` remains the bare FastAPI stub. `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 9's `POST /readings/{id}/interpret` is an illustrative sketch, not a route.
- **No Reading Service exists.** `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2 sketches `services/reading_service.py` (create/update Reading, transition status); no such file exists. Nothing in the codebase ever assigns `ReadingStatus.SPREAD_COMPLETE` — confirmed by a repository-wide search: the only place that value appears at all is its own enum definition. This means **the status enum's own middle value has never once been used**, a concrete, verifiable gap Section 3 below addresses directly.
- **`engine.interpret()`'s only precondition is "at least one CardDraw exists"** (`if not reading_context.draws: raise ValueError`) — this is weaker than "the spread is complete." A Reading with 3 of a Celtic Cross's 10 required positions filled currently passes this check and would be silently (partially) interpreted. Section 3 treats this as the central precondition gap.

## 1.3 Documentation drift noticed, not fixed here

`RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 4's schema sketch still shows `interpretive_model`/`narrative` as columns directly on `reading` — this predates, and was already superseded by, `INTERPRETATION_ENGINE_DESIGN.md` Q1's related-table decision (`Interpretation`, actually implemented). This document uses the actual, current schema throughout, exactly as `INTERPRETATION_ENGINE_DESIGN.md` Section 1.3 already flagged the same class of drift for `layout`/`layout_position` naming. Fixing the architecture doc is out of scope here.

---

# 2. The Lifecycle

```
Reading (drafting)
   |
   | [user fills in CardDraws via a future Reading/Draw Service -- not built yet]
   v
Reading (spread complete -- EVIDENCE state, Section 3; ReadingStatus.SPREAD_COMPLETE
          is never actually assigned by any existing code today, Section 1.2)
   |
   | [1. EXPLICIT user trigger -- "Interpret My Reading", Section 3]
   v
[precondition check -- Section 3, PROPOSED, does not exist yet]
   |
   v
engine.interpret(reading, session) -> InterpretiveModel      [EXISTING, Section 4]
   |
   v
persistence.save_interpretation(session, reading, model)     [EXISTING, Section 5]
   -> new Interpretation row (reading_id, engine_version,
      reference_data_version, interpretive_model JSON)
   -> reading.status = ReadingStatus.INTERPRETED
   |
   v
[caller commits the transaction -- Section 14]
   |
   v
   ... later, on demand (a Reading Detail view, an API GET) ...
   |
   v
[retrieval -- Section 8, PROPOSED, does not exist yet]
   fetch latest Interpretation row for reading_id
   -> InterpretiveModel.model_validate(row.interpretive_model)  [EXISTING round-trip,
                                                                  already tested]
   |
   v
assembler.assemble_narrative(model) -> NarrativeModel        [EXISTING, Section 7's
                                                                pure function, Step 7]
   |
   v
(returned to caller -- NOT persisted, Section 9)
   |
   v
[future: API response / frontend rendering -- out of scope, NARRATIVE_LAYER_DESIGN.md
 Section 12's [B] presentation layer]
```

---

# 3. When Interpretation Is Triggered, and Required Preconditions

**Decision: explicit user action only — "Interpret My Reading" (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 18). Never automatic.** Concretely: no background job, no "auto-interpret when the last required position is filled," no trigger tied to reference-data changes (Section 12). This is stated explicitly even though it may seem obvious, because **nothing currently enforces it** — no orchestration code exists yet to enforce or violate it (Section 1.2). Automatic triggering would also conflict with `INTERPRETATION_ENGINE_DESIGN.md` Section 2.1's framing of `status` as "a trigger condition, not an analytical input": if interpretation ran automatically, a user could never review or amend a Card Draw before its cards are analyzed, and reinterpretation cost (Section 12) would be spent without the user asking for it.

**Preconditions — two layers, currently only the weaker one exists:**

1. **Existing (engine-level, weak):** `engine.interpret()` raises `ValueError` if `reading.card_draws` is empty. This guards against the degenerate empty case but nothing more.
2. **Proposed (orchestration-level, the actual "spread complete" check — does not exist yet):** every `SpreadPosition` with `required=True` on `reading.spread` must have exactly one `CardDraw` in `reading.card_draws`. Sketched here as a derived property, following the same "derive, don't store-and-risk-drift" precedent this project has used consistently (`Spread.position_count`, `INTERPRETATION_ENGINE_DESIGN.md` Q1's "current interpretation" derivation):

   ```python
   # Illustrative signature, not final code -- would live on Reading (app/models/reading.py)
   @property
   def is_spread_complete(self) -> bool:
       required_position_ids = {p.id for p in self.spread.positions if p.required}
       drawn_position_ids = {d.position_id for d in self.card_draws}
       return required_position_ids.issubset(drawn_position_ids)
   ```

   The orchestration layer (Section 13) must check this **before** calling `engine.interpret()` and raise a distinct, caller-facing error (e.g. `ReadingNotReadyForInterpretationError`, illustrative name) with a clearer message than the engine's own generic `ValueError` — the engine's existing check remains as defense-in-depth, not the primary guard.

**Deliberately not a precondition:** `reading.status`'s current value. The engine reads `Reading` + `CardDraw` + `Spread` structure only, never `status` itself (`INTERPRETATION_ENGINE_DESIGN.md` Section 2.1: status is a trigger condition, not an analytical input) — so interpretation is triggerable regardless of whether `status` is currently `DRAFTING`, `SPREAD_COMPLETE`, `INTERPRETED`, or `SAVED`, as long as the *evidence* precondition (`is_spread_complete`) holds. Reinterpreting an already-`SAVED` Reading is explicitly **allowed**, not policy-blocked — see Section 5 for the resolved decision on how its status must (and must not) change as a result.

---

# 4. How the Engine Result Is Persisted — Existing, Unchanged

Already fully implemented by `persistence.save_interpretation` (Section 1.1). Nothing in this document changes it: one `Interpretation` row per call, `reading_id` FK, `engine_version`/`reference_data_version` duplicated as queryable columns, `interpretive_model` as the full JSON payload via `model.model_dump(mode="json")`. This document's only contribution here is specifying *when* and *by what* this function gets called (Sections 3, 13) — not changing what it does.

---

# 5. How `ReadingStatus.INTERPRETED` Is Assigned — Existing Base Case, Plus a Resolved Refinement

**Existing:** `save_interpretation` unconditionally sets `reading.status = ReadingStatus.INTERPRETED` on every successful call — including a second, third, etc. call against the same Reading (already exercised by `test_reinterpreting_preserves_the_prior_interpretation`, which calls it twice, in both cases starting from a not-yet-`SAVED` Reading). This existing behavior is correct and unchanged for every status this document allows it to run from — see the resolved rule below.

**Resolved (was Section 16, Q1): reinterpretation is allowed from `SAVED`, but must never regress a Reading's status away from `SAVED`.**

**Decision:** interpretation may be triggered (Section 3) regardless of the Reading's current status — `SAVED` included, since a user may reasonably want to see what a newer engine version concludes about a reading they already saved. But the status assignment inside the persistence step must become **transition-aware** rather than unconditional, so that reinterpreting a `SAVED` Reading creates a new `Interpretation` row (full history, unchanged — Section 6) **without** silently moving the Reading backward in its lifecycle:

```python
# Illustrative refinement to persistence.save_interpretation -- not implemented by
# this document (Section 0's boundary: no code changes here). The INSERT of the
# new Interpretation row is unconditional in every case; only the status
# assignment below becomes conditional.
if reading.status != ReadingStatus.SAVED:
    reading.status = ReadingStatus.INTERPRETED
# else: leave reading.status == ReadingStatus.SAVED untouched.
```

**Resulting transition table:**

| `reading.status` before reinterpretation | `reading.status` after |
|---|---|
| `DRAFTING` or `SPREAD_COMPLETE` | `INTERPRETED` (existing, unchanged behavior — first-time advancement) |
| `INTERPRETED` | `INTERPRETED` (existing, unchanged — idempotent no-op reassignment) |
| `SAVED` | `SAVED` (**new** — status is preserved; only a new `Interpretation` row is added) |

**Rationale:** `ReadingStatus`'s own docstring already implies a forward lifecycle (`drafting → spread_complete → interpreted → saved`, `INTERPRETATION_ENGINE_DESIGN.md` Q1). Letting reinterpretation silently move a Reading backward from `SAVED` to `INTERPRETED` would contradict that ordering and would be a surprising, user-visible regression (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 17's versioning principle — the *evidence* and the user's save/archival intent are separate concerns; reinterpreting must update the former's *interpretation* without disturbing the latter's *lifecycle marker*). This mirrors Section 3's existing conclusion that interpretation reads `Reading` structure but must never be *gated* by `status` — the new addition here is that persisting a reinterpretation result must also never *mutate* `status` in a lifecycle-regressing direction.

**Implementation timing:** deferred to whichever future step implements `reading_orchestration.py` / a real `persistence.save_interpretation` change (Section 13) — this document only fixes the intended behavior, consistent with every other "illustrative signature, not final code" sketch elsewhere in this series. No code, schema, or test is touched by this decision today.

---

# 6. What Happens When Interpretation Is Run Again — Existing, Already Tested

Already fully covered by `test_reinterpreting_preserves_the_prior_interpretation`: a new `Interpretation` row is created; the prior row is untouched; every `CardDraw` row is untouched (evidence is never mutated by interpretation, per `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 17). The orchestration layer (Section 13) needs **no special-case "is this a rerun?" logic** — calling the same `interpret()` + `save_interpretation()` pair again is already the entire mechanism, by construction of the one-to-many, no-`is_current`-flag shape `INTERPRETATION_ENGINE_DESIGN.md` Q1 chose. This is a case where the integration design is simply: "do the same thing again" — nothing new to build here beyond the trigger itself (Section 3).

---

# 7. How Historical Interpretations Are Retained, and How the Current One Is Identified

**Retention — existing:** `Interpretation.reading` relationship with `cascade="all, delete-orphan"` on the `Reading` side means interpretations are deleted only if their parent `Reading` is deleted — never by a subsequent reinterpretation. Full history is retained for free, as `INTERPRETATION_ENGINE_DESIGN.md` Q1 designed.

**"Current" identification — existing mechanism, with a resolved secondary-ordering gap found during this inspection.** The documented rule is "the row with the latest `created_at`" (no `is_current` flag, by design). `Reading.interpretations` is already ordered by `Interpretation.created_at` ascending, so `reading.interpretations[-1]` is the existing, working way to get it *when `created_at` values are distinct*. **The gap:** `TimestampMixin.created_at` uses `server_default=func.now()` on a plain `DateTime(timezone=True)` column, and on SQLite (dev/test), `CURRENT_TIMESTAMP` has **second-level resolution, not microsecond** — confirmed by inspecting `app/db/base.py`. Combined with `UUIDPrimaryKeyMixin`'s `uuid.uuid4()` (random, not time-ordered, so unusable as a secondary sort key), two `Interpretation` rows created within the same wall-clock second on SQLite would have identical `created_at` values and no deterministic tiebreak. PostgreSQL (prod, per `docs/DECISIONS.md` ADR-0004) does not have this problem on its own — `now()` there has microsecond precision — but this document resolves the ambiguity portably, for both engines, rather than relying on a precision difference between dev and prod.

**Resolved (was Section 16, Q2): add a monotonic `sequence` column as the deterministic secondary (in practice, primary) ordering key.**

**Decision:** propose a new, additive, database-generated monotonically increasing integer column on `Interpretation` — `sequence` — assigned automatically on insert (a standard SQL identity/autoincrement column, portable across SQLite and PostgreSQL; not a replacement for the existing UUID `id`, which remains the primary key per this project's established convention, `app/db/base.py`'s `UUIDPrimaryKeyMixin`).

```python
# Illustrative addition to app/models/interpretation.py -- not implemented by this
# document (Section 0's boundary). Additive only: a new column on an existing
# table, no ALTER of any other column, no redesign of the UUID primary key.
sequence: Mapped[int] = mapped_column(Integer, autoincrement=True, unique=True, nullable=False)
```

**Revised "current interpretation" rule:** the current interpretation for a `reading_id` is the row with the **highest `sequence` value** (equivalently: `ORDER BY sequence DESC LIMIT 1`, or `reading.interpretations` re-ordered/indexed by `sequence` instead of `created_at`). `created_at` is retained on every row for audit/display purposes (when a given interpretation run happened) but is **no longer the field "current" is determined by** — `sequence` is immune to timestamp resolution by construction, since it is assigned by the database as a strictly increasing counter at insert time, not derived from wall-clock time at all.

**Rationale — why this still fits the "derive, don't store-and-risk-drift" precedent this project has consistently used (`Spread.position_count`, the "no `is_current` flag" decision itself):** a monotonic `sequence` is not a redundant, driftable flag like a boolean `is_current` would be (which could be forgotten-to-update on a future code path and silently point at the wrong row) — it is a value the database itself guarantees is strictly increasing and unique, assigned exactly once, with no possible later inconsistency. It resolves the ambiguity *portably*: the same `ORDER BY sequence DESC` query is correct on SQLite and PostgreSQL alike, rather than relying on PostgreSQL's finer timestamp resolution to paper over a SQLite-specific gap that would otherwise remain latent in dev/test.

**Implementation timing:** deferred — this is an additive migration (one new column, `NOT NULL`, backfillable in insertion order for any pre-existing rows) to be implemented alongside whichever future step builds `reading_orchestration.py` (Section 13), not implemented, migrated, or tested by this document today.

---

# 8. How the Persisted `InterpretiveModel` Is Supplied to the Narrative Layer

**Proposed — does not exist yet.** A thin retrieval function (illustrative sketch, not final code, following the same "sketch before implementation" convention every prior design document in this series has used):

```python
# Illustrative signature -- would live alongside persistence.py or in a new
# retrieval module; not narrative/assembler.py itself, which must stay
# database-free per NARRATIVE_LAYER_DESIGN.md Section 2/4.
#
# "Latest" here means highest `sequence` (Section 7's resolved ordering key),
# not list-position -- once `sequence` exists, `reading.interpretations`'
# relationship-level ordering should itself move from `created_at` to
# `sequence`, so `[-1]` and "latest" mean the same thing again.
def get_narrative_for_reading(session: Session, reading: Reading) -> NarrativeModel | None:
    latest = reading.interpretations[-1] if reading.interpretations else None
    if latest is None:
        return None
    model = InterpretiveModel.model_validate(latest.interpretive_model)
    return assemble_narrative(model)
```

The critical design constraint: this function performs the **only** database read in the entire narrative path (fetching the row, already-loaded via the `reading.interpretations` relationship or a direct query), and hands off an already-fully-materialized `InterpretiveModel` object to the pure `assemble_narrative()` — exactly the boundary `NARRATIVE_LAYER_DESIGN.md` Section 2/4 requires. `InterpretiveModel.model_validate(...)` reconstructing the stored JSON is **already proven lossless** by `test_save_interpretation_round_trips_the_model_through_json` — this function introduces no new round-trip risk, it only reuses an already-tested one.

---

# 9. Whether `NarrativeModel` Should Be Persisted — Evaluated and Rejected

Per this task's explicit instruction to evaluate on-demand generation rather than assume a new table is needed: **on-demand generation, no persistence, no new table.** Reasoning:

- `assemble_narrative()` is a pure, in-memory, no-I/O function (Step 7's own static test already proves it touches no database) — its computational cost is negligible (string formatting over an already-small, already-in-memory object), unlike an AI call, which *would* justify caching.
- Persisting it would require its own invalidation strategy: `narrative_template_version` changing (a template wording fix) would silently leave stale persisted narratives unless every persisted row were also versioned and compared against the current template version on every read — solving a caching-invalidation problem that recomputation avoids for free, since recomputation always reflects the currently-deployed template.
- This is the same "derive, don't store-and-risk-drift" reasoning this project has already applied repeatedly (`Spread.position_count`, `reference_data_version`, the "current interpretation" lookup itself, Section 7) — a `NarrativeModel` is deterministically, cheaply re-derivable from an already-persisted `Interpretation` row at any time, so storing a second copy of derivable information would be exactly the kind of unnecessary schema addition this task's boundaries prohibit.
**Resolved (was Section 16, Q4): DEFERRED. No cache, no persistence, no new table — `NarrativeModel` stays generated on demand.**

`get_narrative_for_reading()` (Section 8) always recomputes via `assemble_narrative()` on every call; nothing is stored, memoized, or persisted between calls as part of this design. **If** a future performance profile ever shows recomputation is actually a bottleneck (implausible given its cost profile, but not this document's place to assume it never will be), the correct fix would be an ordinary **read-through cache** (e.g. keyed by `(interpretation_id, narrative_template_version)`), not a new source-of-truth table — `NarrativeModel` would remain fully re-derivable, so a cache could be dropped and rebuilt at any time with no data-loss risk. **This document does not design that cache, does not pick a cache key beyond the illustrative example above, and does not authorize building one** — it only notes the schema-safe path stays open if a real need is ever demonstrated. Implementation timing: not before Step 8, and only ever in response to measured need, never speculatively.

---

# 10. Error / Failure Behavior and Status Handling

No error-handling code exists yet (no orchestration layer exists, Section 1.2) — this section specifies the required behavior for when one is built.

| Failure point | Required behavior |
|---|---|
| Precondition fails (`is_spread_complete` is False, Section 3) | Raise before calling `engine.interpret()` at all. No `Interpretation` row created. `reading.status` unchanged. |
| `engine.interpret()` raises (its own `ValueError`, or an unexpected bug) | Propagate the exception. `persistence.save_interpretation()` is never reached (it is a separate, subsequent call — Section 4), so no partial/corrupt `Interpretation` row can exist. `reading.status` unchanged (the assignment happens inside `save_interpretation`, never reached). This is already true **by construction** of the existing two-function split; the orchestration layer must simply not collapse them into one that catches and half-recovers from a mid-computation failure. |
| `persistence.save_interpretation()` fails partway (e.g. a DB constraint violation on flush) | Must not leave the row inserted without the status update, or vice versa — see Section 14 (Transaction Boundaries): both must be part of one atomic unit that the caller can roll back as a whole. |
| `get_narrative_for_reading()` / `assemble_narrative()` fails (Section 8) | Must **never** invalidate or roll back an already-successfully-persisted `Interpretation`. Narrative assembly is a read-path, presentation-adjacent concern (`NARRATIVE_LAYER_DESIGN.md` Section 3's `[A]`), strictly downstream and separable from the write-path (interpretation persistence) that already succeeded independently. A caller (e.g. a future API route) should be able to degrade gracefully — e.g. return the persisted `InterpretiveModel`/citations even if narrative text generation itself is temporarily broken — rather than treat a narrative-assembly bug as an interpretation-persistence failure. |

---

# 11. Idempotency / Reproducibility Requirements

**Existing:** `engine.interpret()` is already proven deterministic — identical `Reading` evidence plus identical reference data produces structurally identical `InterpretiveModel` content (`INTERPRETATION_ENGINE_VALIDATION.md`, every determinism check). `assemble_narrative()` is likewise already proven deterministic (Step 7's own test suite).

**Not idempotent, by design, at the orchestration level:** triggering interpretation twice does **not** deduplicate — it always creates a second `Interpretation` row (Section 6), even if its content would be byte-identical to the prior row's content (same evidence, same `engine_version`, same `reference_data_version`). This is consistent with the existing, tested, approved behavior (`test_reinterpreting_preserves_the_prior_interpretation`) and is **not** something this document proposes changing.

**Resolved (was Section 16, Q3): DEFERRED. Step 8 does not skip, deduplicate, or short-circuit identical interpretation runs.**

**Decision:** a "skip creating a duplicate row if nothing has changed since the last interpretation" optimization is explicitly **not** part of this design and must **not** be implemented as part of Step 8 or its eventual implementation. Every trigger (Section 3) runs the full pipeline and persists a new row, unconditionally, exactly as `test_reinterpreting_preserves_the_prior_interpretation` already exercises.

**Rationale:** nothing in the Product Spec or Architecture doc asks for run deduplication; adding it now would be exactly the kind of unrequested complexity this task's boundaries caution against, and it would introduce a genuine new design surface of its own (what exactly counts as "nothing changed" — evidence, `engine_version`, `reference_data_version`, all three? — and how a skip should be reported back to a caller expecting an `Interpretation` row). None of that is justified by any current requirement.

**Implementation timing:** not before Step 8, and not implied by anything in this document. If ever revisited, it would need its own dedicated design pass (its own trigger/inputs/output specification, per this series' established rule-specification discipline) rather than being folded in as a side effect of the orchestration layer's first implementation.

---

# 12. Reference-Data Version Handling

**Existing, fully self-contained:** `compute_reference_data_version(session)` runs fresh inside every `engine.interpret()` call and is stored on the resulting `Interpretation` row (`INTERPRETATION_ENGINE_DESIGN.md` Q2). The orchestration layer needs to do nothing extra to make this work — it is already correct by construction.

**Explicitly not proposed:** reference-data content changing (e.g. a future card-content edit) must **never** automatically trigger reinterpretation of existing Readings. This follows directly from Section 3's "explicit trigger only" decision — an automatic reinterpretation-on-reference-data-change mechanism would silently change a user's past reading without their action, which both violates the explicit-trigger principle and would be surprising/undesirable product behavior (a saved reading's meaning changing underneath the user with no visible cause). If a future "your interpretations may be out of date" notice is ever wanted, that would compare a Reading's latest `Interpretation.reference_data_version` against a freshly-computed current value and surface a prompt — a real, separate feature, not designed here.

---

# 13. API / Service Boundaries

**Nothing here is implemented — this is a proposed layering, following the naming and shape `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2 already sketched, refined against what Steps 2–7 actually built:**

```
app/services/
  reading_orchestration.py     (PROPOSED, new -- the only module allowed to combine
                                 DB reads/writes with calls into the pure engine/narrative
                                 layers, mirroring the loader/seed and compute/persist
                                 separations already established elsewhere in this project)
    interpret_reading(session, reading) -> Interpretation
        1. check reading.is_spread_complete (Section 3) -- raise if not
        2. model = engine.interpret(reading, session)
        3. return persistence.save_interpretation(session, reading, model)
        (caller commits -- Section 14)

    get_narrative_for_reading(session, reading) -> NarrativeModel | None
        (Section 8's sketch)

  interpretation/    -- UNCHANGED, pure/DB-light as already built (Steps 2-5)
  narrative/         -- UNCHANGED, pure/DB-free as already built (Step 7)
```

A future API layer (still entirely unbuilt, Section 1.2) would call only `reading_orchestration`, never `engine.interpret()` or `assembler.assemble_narrative()` directly — this keeps the pure layers' testability (fixed fixtures, no database needed for `assemble_narrative`'s own unit tests, Step 7) fully intact regardless of what the eventual API/route layer looks like. `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 9's `POST /readings/{id}/interpret` sketch remains the natural future route for `interpret_reading`; a `GET` on the Reading (or a dedicated narrative sub-route) would be the natural future caller of `get_narrative_for_reading`. **No route, schema, or controller is designed in more detail than this here** — per this task's explicit boundary.

---

# 14. Transaction Boundaries

**Required guarantee (proposed, since `interpret_reading` doesn't exist yet, but the convention it must follow is already established and proven correct by existing code):** the entire `interpret_reading()` sequence — precondition check, `engine.interpret()`'s reference-data read, `save_interpretation()`'s `INSERT` and `reading.status` `UPDATE` — must execute within **one** session/transaction scope, with the **caller** responsible for the final `commit()` (or `rollback()` on any exception). This is not a new pattern to invent: `persistence.save_interpretation` already calls only `session.flush()`, never `session.commit()` — commit is already left to the caller in every existing test (`test_save_interpretation_creates_a_row_and_updates_reading_status` calls `seeded_session.commit()` itself, after the function returns). `interpret_reading()` must preserve this exact convention: no internal commit, so that a caller wrapping it in a larger unit of work (e.g. a future API request handler) can roll back the *entire* request atomically if anything downstream of interpretation also fails, and so that Section 10's "no partial state" guarantee holds structurally, not just by convention.

---

# 15. Provenance Preservation Through the Complete Lifecycle

Tracing the full chain, noting which hops are already proven and which are new:

```
CardDraw (card_draw_id, position, orientation)
   |  [EXISTING -- context.py's build_reading_context]
   v
Citation objects inside InterpretiveModel.Explained[T].citations
   |  [EXISTING, proven complete -- INTERPRETATION_ENGINE_VALIDATION.md Section 4]
   v
Interpretation.interpretive_model (JSON column, full model.model_dump(mode="json"))
   |  [EXISTING, proven lossless round-trip -- test_save_interpretation_round_trips_the_model_through_json]
   v
InterpretiveModel.model_validate(row.interpretive_model)   [Section 8's retrieval step -- PROPOSED,
   |                                                         but reuses an already-tested round-trip]
   v
NarrativeStatement.citations (copied verbatim)
   |  [EXISTING, proven -- NARRATIVE_LAYER_DESIGN.md Section 8 / Step 7's citation-identity tests]
   v
(future: presentation layer -- out of scope)
```

**Conclusion: provenance is already end-to-end intact from `CardDraw` through to `NarrativeModel`, proven at every existing hop by an existing test.** The only genuinely new hop this document introduces (Section 8's retrieval function) does not add a new transformation — it only re-applies an already-validated deserialization (`InterpretiveModel.model_validate`) that a different existing test already exercises in the opposite direction (serialize-then-deserialize within one test, rather than across a "later, on demand" retrieval) — so no new provenance risk is introduced by this design, only a new *caller* of already-proven code.

---

# 16. Resolved Follow-On Decisions

The four questions the first draft of this document left open have all been resolved. Recorded here as an index back to each full decision, with implementation timing restated for quick reference — none of these four decisions changes any code, schema, migration, or test today; each is a design resolution for a future implementation step, exactly as the rest of this document already is.

**Resolved Q1 — Reinterpreting a `SAVED` Reading is allowed, and must never regress its status.** Full decision and transition table: Section 5. Implementation timing: deferred to the future `persistence.save_interpretation` change / `reading_orchestration.py` (Section 13).

**Resolved Q2 — A monotonic `sequence` column on `Interpretation` is the deterministic ordering key for "latest," portable across SQLite and PostgreSQL.** Full decision: Section 7. Implementation timing: deferred to an additive future migration, alongside `reading_orchestration.py` (Section 13).

**Resolved Q3 — DEFERRED. No duplicate-run-skip optimization is designed, implied, or authorized by Step 8.** Full decision: Section 11. Implementation timing: not before Step 8; only ever via its own separately-scoped design pass, if ever.

**Resolved Q4 — DEFERRED. No `NarrativeModel` caching or persistence layer is designed, implied, or authorized by Step 8; `NarrativeModel` remains fully on-demand.** Full decision: Section 9. Implementation timing: not before Step 8; only ever in response to measured, not assumed, performance need.

---

# 17. Summary: Existing vs. Proposed vs. Deferred

## Already implemented and tested (nothing to build)
- `engine.interpret()` — the deterministic pipeline itself.
- `persistence.save_interpretation()` — Interpretation row creation, `ReadingStatus.INTERPRETED` assignment, no-internal-commit convention.
- Full reinterpretation history retention (new row per run, prior rows and all `CardDraw` rows untouched).
- `reference_data_version`/`engine_version` computation and storage.
- `assembler.assemble_narrative()` — pure, deterministic, database-free narrative assembly.
- End-to-end provenance (citations) from `CardDraw` through to `NarrativeModel`, proven at every hop.

## Proposed by this document (design only, not implemented)
- `Reading.is_spread_complete` derived property (Section 3).
- `reading_orchestration.interpret_reading()` and `get_narrative_for_reading()` (Sections 8, 13).
- The precondition-check-before-engine-call ordering and its distinct error type (Sections 3, 10).
- The no-persistence decision for `NarrativeModel` (Section 9).
- The single-transaction-scope, caller-commits requirement for the orchestration function (Section 14).
- The transition-aware `ReadingStatus` assignment in `save_interpretation` — never regress `SAVED` (Section 5, Resolved Q1).
- The additive `Interpretation.sequence` column and the `sequence`-based "current interpretation" ordering rule (Section 7, Resolved Q2).

## Deferred (considered and explicitly declined for Step 8 — not merely unmentioned)
- Any duplicate-run-skip / interpretation-deduplication optimization (Section 11, Resolved Q3).
- Any `NarrativeModel` caching or persistence layer (Section 9, Resolved Q4).
- Any API route or frontend/UI.
- The reinterpretation UI itself (MVP-deferred per Product Spec Section 18).
- Any LLM/AI wording layer (`NARRATIVE_LAYER_DESIGN.md` Section 13's `[A']`).
- Any new interpretation rule, or activation of any currently-deferred rule (`INTERPRETATION_RULES_DESIGN.md` Section 12.3 — unchanged by this document).

---

## Related Documents

- `INTERPRETATION_ENGINE_DESIGN.md` — Q1 (the `Interpretation` table shape this document's persistence sections rely on unchanged), Q2 (reference-data versioning, Section 12 above).
- `INTERPRETATION_RULES_DESIGN.md` — unchanged by this document; Section 12.3's deferred-rule list is re-affirmed, not revisited.
- `INTERPRETATION_ENGINE_VALIDATION.md` — the determinism proof this document's Section 11 relies on rather than re-deriving.
- `NARRATIVE_LAYER_DESIGN.md` — Sections 2/4 (the database-free purity requirement Section 8 above preserves) and Section 12 (the persistence-vs-on-demand question Section 9 above resolves).
- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Section 17 (Versioning, the evidence/interpretation separation this entire document assumes) and Section 18 (MVP Scope, the explicit-trigger flow Section 3 adopts).
- `RAIDIAN_WISE_ARCHITECTURE_V1.md` — Section 2 (Backend Module Layout, the `reading_service`/API sketch Section 13 refines) and Section 9 (API Sketch).
- `app/services/interpretation/persistence.py`, `app/services/narrative/assembler.py` — the actual, already-implemented code this document integrates rather than redesigns.
