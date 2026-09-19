# Raidian Wise — Save Reading Design & Repository Audit (Step 17)

# Document Information

Version: 1.0 (Draft for Review — Not Yet Approved)
Status: Proposed — Audit and Design Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Audits the actual current repository (post Step 16, baseline `bb53c1c`) and determines the smallest, cleanest future implementation surface for `ReadingStatus.SAVED` to behave exactly as `PRODUCT_DECISIONS.md` Q3 already approved: a pure user-curation/retention marker, the sole gate for Reading History visibility, with no effect on Interpretation creation/history or Narrative generation. This document implements nothing — every finding below was checked directly against the current code, not inferred from any prior report.

Audience:
Whoever eventually implements Save Reading and Reading History, and anyone auditing whether that future implementation matches Step 14's approved Q3 decision and the actual, current schema.

Authority:
Operationalizes `PRODUCT_DECISIONS.md` Q3 and Q6 exactly as approved — does not reopen either. Concretizes `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6 (Screen Structure — Reading History) and Section 18 (MVP Scope) against the actual, current `app/models/reading.py`, `app/services/`, and `app/api/` layout. Builds directly on `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md`'s (Step 15) precedent — no new service module was justified there, and this document reaches the same kind of conclusion here, checked independently rather than assumed.

---

# 0. Scope

Audit and design only. No production code, schema, migration, API route, or test file is modified by this document. Does not reopen `PRODUCT_DECISIONS.md` Q3/Q6. Does not invent authentication, ownership, or a placeholder single-tenant assumption. Does not implement "unsave." Does not touch `ReadingStatus`, the Interpretation Engine, or the Narrative Layer.

---

# 1. Executive Summary

**The Save operation itself requires no schema change, no migration, and no new service module** — `ReadingStatus.SAVED` already exists (unused since Step 1); the smallest correct implementation is a single, self-contained model method on `Reading` (mirroring `add_card_draw()`'s existing pattern from Step 15/16 exactly), not a new "Reading Service."

**The more consequential finding is about Reading History, not Save itself:** no code anywhere in this repository has ever queried for a *list* of Readings — every existing Reading lookup is a single-row fetch by primary key. Building the Reading History query Product Spec Section 6 describes ("list of saved Readings") **before** ownership infrastructure exists would not produce a working personal history feature at all — it would produce one global list of every saved Reading from every caller, since nothing in this codebase or in the Product Spec itself defines what "belongs to a user" means yet. This document recommends implementing the Save *transition* now (or in a small, focused follow-up step) while explicitly deferring the Reading History *query and route* until that dependency is resolved — building it early would ship something that cannot correctly do what it exists to do.

---

# 2. Repository Findings

Checked by direct inspection of `app/models/reading.py` (current, post-Step-16), `app/models/reflection_session.py`, `app/models/enums.py`, `app/services/`, `app/api/`, and a repository-wide search — not inferred from any prior document.

## 2.1 How Readings are currently created and retrieved

**Created:** only via the `Reading(...)` constructor directly — no factory, no service wraps it (`tests/factories.py::make_reading`, `tests/interpretation_helpers.py::build_reading` both construct it directly). No `reading_service.py` exists.

**Retrieved:** exactly one pattern exists anywhere in `app/`: `session.get(Reading, reading_id)` — a single-row lookup by primary key, used only in `app/api/interpretation.py::_get_reading_or_404`. **A repository-wide search for `select(Reading)` returns zero matches.** No list, filter, or search query against `Reading` exists anywhere in this codebase today, in application code or tests.

## 2.2 Does any existing code distinguish "saved" from merely persisted?

No. Every `Reading` row is durably persisted at `commit()` time regardless of `status` — there is no draft/at-risk state for any Reading's evidence or its interpretations. This was already established at the orchestration layer (`PRODUCT_DECISIONS.md` Q3) and is reconfirmed here at the model layer: nothing in `app/models/reading.py` or anywhere else treats `SAVED` as a persistence concept.

## 2.3 Does any existing history/list query exist?

No (Section 2.1). This is a stronger finding than "the route doesn't exist yet" — there is no query, no repository function, and no test exercising one, at any layer.

## 2.4 Is `ReadingStatus.SAVED` currently assigned anywhere in production code?

**No.** A repository-wide search for `SAVED` finds it only in: `app/services/interpretation/persistence.py`'s `if reading.status != ReadingStatus.SAVED` guard (a *check*, never an *assignment*), and in five test files (`test_reading_lifecycle.py`, `test_reading_orchestration.py`, `test_reading_workflow_e2e.py`, `test_api_interpretation.py`) that set it directly (`reading.status = ReadingStatus.SAVED`) purely to exercise that guard.

## 2.5 Can `SAVED` currently be reached through any production path?

**No.** Confirmed by 2.4 — the only way a `Reading` in this system today reaches `SAVED` is a test setting it directly.

## 2.6 Does any existing code assume `INTERPRETED` is terminal?

**No.** `save_interpretation()`'s guard (`if reading.status != ReadingStatus.SAVED`) explicitly treats `INTERPRETED` as a *non-final*, re-enterable state — reinterpreting an `INTERPRETED` Reading is idempotent on `status` (stays `INTERPRETED`) and always creates a new `Interpretation` row, already implemented and tested (`test_interpreted_stays_interpreted_on_reinterpretation`). Nothing anywhere blocks further transitions after `INTERPRETED`.

## 2.7 Could any existing query accidentally expose unsaved Readings as Reading History?

Not applicable today — no such query exists to make the mistake (2.3). This is a risk entirely for whoever builds the future query (addressed directly in Section 7).

## 2.8 `ReflectionSession`

Direct inspection confirms `READING_INTEGRATION_DESIGN.md`'s and `INTERPRETATION_API_DESIGN.md`'s prior findings, unchanged: one-to-one with `Reading`, "identity and timestamps only" by its own docstring, no `user_id` or any ownership field, no list/query helper of its own either.

## 2.9 Timestamps and metadata

`Reading` has `TimestampMixin`'s `created_at` (set once) and `updated_at` (`onupdate=func.now()`, updates on *any* column change to the row). Relevant to Section 7: today, the only things that ever mutate an already-created `Reading` row are its own status transitions (`SPREAD_COMPLETE` via `add_card_draw()`, `INTERPRETED` via `save_interpretation()`, and — once built — `SAVED`) — no Reading-level *editing* feature exists. This means `updated_at` happens, today, to coincide with "the last lifecycle transition," including a future save — but this is a property of today's limited mutation surface, not a guaranteed semantic (Section 7.2).

## 2.10 Existing API routes and schemas

Only the four interpretation/narrative routes exist (`app/api/interpretation.py`, Step 11) — none creates, lists, or mutates a `Reading`; each only reads one by ID. `app/schemas/interpretation_api.py` has no Reading-shaped schema of any kind. Confirmed unchanged from every prior step's finding.

## 2.11 Existing tests

`test_reading_lifecycle.py` (Step 16, 11 tests) covers `DRAFTING`↔`SPREAD_COMPLETE` and the CardDraw immutability guard — no `SAVED`-transition test exists there (out of that step's scope). `test_reading_orchestration.py`/`test_api_interpretation.py`/`test_reading_workflow_e2e.py` each have exactly one test asserting reinterpretation preserves an already-`SAVED` status (`test_saved_reading_remains_saved_after_reinterpretation` and its API/e2e counterparts) — all set `SAVED` manually, none exercises reaching it. No test anywhere covers a Save *operation*, a Reading History *query*, or an "already SAVED" idempotency case for saving itself.

---

# 3. Product Spec Requirements

Every statement found with implementation consequences for Save/History, cited exactly, then classified.

- **Section 6:** "**Reading History** — list of **saved** Readings, searchable/filterable." **Section 18:** "Reading History + Reading Detail" listed under MVP "In" scope. **Section 6 continued:** "**Reading Detail** — a saved Reading's full record (evidence + interpretation as generated); MVP does not require re-interpretation, but the schema must not block it."
- **Section 5, steps 13–14:** "User can save the Reading... The saved record preserves: cards, positions, question, orientation, layout, deck, draw method, and interpretation engine version — permanently."
- **Section 17 (Versioning):** the evidence-vs-interpretation separation principle, already settled and unchanged.
- **No user/session/ownership concept anywhere.** A repository-wide search of the Product Spec for `user_id`/`owner`/session-as-identity finds only the unrelated "Reading vs. Reflection Session" naming question (Section 3.2) — confirming the absence of any ownership model is not just an implementation gap, it is a **specification gap**: the Product Spec itself never defines whose Readings a "Reading History" screen should list.

**Classification:**
- *Existing implemented behavior:* none of the above — no History, no Detail, no Save.
- *Approved Step 14 decisions:* `SAVED` = pure curation/retention marker; sole gate for History visibility (Q3); no backward transitions (Q6).
- *Unresolved infrastructure dependency:* the ownership gap above — genuinely blocking, not merely unbuilt (Section 9).
- *Ambiguity, not resolved here:* "searchable/filterable" (Section 6) names no actual search/filter criteria anywhere in the Product Spec — recorded as a real gap (Section 13), not designed.

---

# 4. Approved Q3 Interpretation (Restated, Not Reopened)

Per `PRODUCT_DECISIONS.md` Q3: `SAVED` is a pure user-curation/retention marker; it is the sole gate for Reading History visibility; it has no effect on Interpretation creation/history; it has no effect on Narrative generation; saving does not pin an interpretation (Q4). This document treats every clause of that decision as fixed input, not as something to re-derive.

---

# 5. Proposed Save Operation

- **Status transition allowed:** `-> SAVED` only.
- **From which statuses:** `SPREAD_COMPLETE` or `INTERPRETED`. **Not `DRAFTING`** — a Reading whose spread is not yet complete is not the "completed record" Reading History exists to list (Product Spec Section 6's "saved Reading's full record"), and nothing in any approved transition matrix (Step 14's own Section G table) names `DRAFTING -> save`.
- **Idempotent:** yes. Saving an already-`SAVED` Reading is a no-op **success**, not an error — consistent with this codebase's one existing precedent for the same shape of guard (`save_interpretation()`'s `if status != SAVED` never raises when re-called against a `SAVED` Reading; it simply declines to regress).
- **If the Reading is already `SAVED`:** no-op — `status` unchanged, no new row of any kind, no error raised.
- **If an `INTERPRETED` Reading is saved:** `status -> SAVED`. Nothing else changes.
- **If a `SPREAD_COMPLETE`-but-not-yet-interpreted Reading is saved:** `status -> SAVED` directly, skipping `INTERPRETED` entirely — legitimate per the already-approved transition matrix (`SPREAD_COMPLETE -> save -> SAVED` is its own named row, distinct from `INTERPRETED -> save -> SAVED`). **Consequence worth naming (Section 13):** this Reading can be `SAVED` while owning zero `Interpretation` rows, ever. A future Reading Detail view must handle that gracefully, not assume interpretation content exists just because a Reading is saved.
- **New database row:** none. Saving is a single-column `UPDATE` on the existing `Reading` row — no new table, no new row anywhere.
- **Interpretation history:** unaffected, by design (Q3) — a Reading's `interpretations` collection is untouched by saving, before or after.
- **Narrative behavior:** unaffected, by design (Q3) — narrative generation reads only the current `Interpretation`, never `Reading.status`.
- **"Unsave":** **not designed or implemented here.** Per Q6 (no backward transition), an "unsave" action would move `status` from `SAVED` to an earlier value — this document does not invent one. If product ever wants this, it requires its own separate, dedicated decision (mirroring how Q3/Q6 themselves were resolved) — named in Section 14, not decided here.

## 5.1 Illustrative sketch — not implemented by this document

```python
# Illustrative signature and body -- not implemented by this document.
# app/models/reading.py, a new method alongside add_card_draw():

def mark_saved(self) -> None:
    """User-initiated retention marker (Documentation/PRODUCT_DECISIONS.md
    Q3) -- has no effect on Interpretation or Narrative. Idempotent: a
    no-op if already SAVED. Does not flush or commit -- the caller
    controls the transaction, exactly as add_card_draw() and
    save_interpretation() already do.
    """
    if self.status == ReadingStatus.SAVED:
        return
    if self.status not in (ReadingStatus.SPREAD_COMPLETE, ReadingStatus.INTERPRETED):
        raise ReadingNotSaveableError(   # new domain error, mirrors ReadingNotDraftingError
            f"reading {self.id} cannot be saved from status={self.status.value}"
        )
    self.status = ReadingStatus.SAVED
```

Named `mark_saved()`, not `save()` — deliberately, to avoid confusion with a SQLAlchemy `Session.add()`/persistence sense of "save"; this method only ever mutates the in-memory `status` attribute, exactly like `add_card_draw()`'s existing, unflushed, uncommitted convention.

---

# 6. Allowed Status Transitions

| From | To | Allowed? |
|---|---|---|
| `DRAFTING` | `SAVED` | **No** — not a completed record; no approved matrix row names this |
| `SPREAD_COMPLETE` | `SAVED` | **Yes** |
| `INTERPRETED` | `SAVED` | **Yes** |
| `SAVED` | `SAVED` | **Yes** — idempotent no-op |
| `SAVED` | any earlier value | **No** — Q6, not reopened |

Cross-checked against Step 16's actual implementation: `mark_saved()` as sketched never touches `CardDraw`, never calls `is_spread_complete`, never invokes the Interpretation Engine or `assemble_narrative()`, and never creates a duplicate `Reading` row — none of Section 5's "must not accidentally imply" list (interpretation, narrative generation, interpretation pinning, draw mutation, status regression, duplicate Reading creation) is triggered by the sketch above, checked line by line.

---

# 7. Reading History Semantics

- **Which statuses qualify:** `SAVED` only, per Q3's "sole gate."
- **Ordering field:** neither `created_at` (evidence-creation time, unrelated to when a Reading was saved) nor a dedicated "saved at" field (none exists) is a perfect fit. **Recommended for now: `updated_at`, descending (newest-first).** This is an approximation, stated explicitly as one (Section 7.2) — not a guaranteed "time of save," but the closest existing field, given today's actual mutation surface (Section 2.9).
- **Newest-first:** yes — matches the established convention `INTERPRETATION_API_DESIGN.md` Section 12 already set for the interpretation-history list, for consistency across this codebase's list-endpoint conventions.
- **Do interpretations affect ordering?** No — ordering is purely a `Reading`-level concern. `Interpretation.sequence` has no role here.
- **Does a Reading with multiple interpretations appear once or multiple times?** **Once**, trivially, as long as the future query selects from `Reading` alone (`WHERE status = 'saved' ORDER BY updated_at DESC`) and never joins `Interpretation` for this listing. **Explicit implementation pitfall named for whoever builds this:** a naive `JOIN interpretations` without a `DISTINCT`/aggregate would return one row *per Interpretation*, not per Reading — a real, easy-to-introduce bug this document flags in advance rather than after the fact.
- **Are unsaved interpreted Readings excluded?** Yes, by construction of the `status = 'saved'` filter — confirmed, unchanged from Q3.
- **Pagination:** **deferred**, applying `INTERPRETATION_API_DESIGN.md`'s own precedent (Q3 there) rather than re-deriving a new one: "not designed here... nothing in this project's current scale... suggests it is needed yet."
- **Empty history response:** `200` with `[]`, never `404` — applying the same reasoning `INTERPRETATION_API_DESIGN.md` Section 7 already established for the interpretation-history list ("a list endpoint returning 'no items yet' is not a `404`").

---

# 8. API/Service Boundary

**Recommendation: no new service module for the Save transition itself — a self-contained `Reading` model method (Section 5.1), exactly mirroring the precedent Step 15/16 already established and validated for `add_card_draw()`'s `SPREAD_COMPLETE` transition.** Verified, not assumed: `mark_saved()`'s entire logic is a status check against `self.status` alone — it needs no session, no cross-model orchestration, and no call into the Interpretation Engine or Narrative Layer. This is structurally *simpler* than the `SPREAD_COMPLETE` transition (which at least reads `is_spread_complete`), so if that transition didn't justify a new service (Step 15's own conclusion), this one certainly does not either. `reading_orchestration.py` remains the wrong home regardless — its own docstring scopes it to combining database access with the Interpretation Engine and Narrative Layer, neither of which this operation touches.

**Is the existing unauthenticated API infrastructure sufficient to expose Save Reading?** For the *transition* alone (a `POST`-shaped mutation against one already-known `reading_id`), it is exactly as sufficient — or insufficient — as every existing route already is: unauthenticated, but scoped to a single caller-supplied ID, matching the already-accepted interim posture `INTERPRETATION_API_DESIGN.md` Sections 4–5 established. **For Reading History specifically, it is not sufficient in a much more direct, feature-breaking sense**, not merely a hardening gap: a `GET` that lists "saved Readings" with no ownership filter would list *every* saved Reading in the database, from every caller, indiscriminately. This is not "insecure but functional" (the way an unauthenticated `GET .../interpretations/current` at least returns the *correct* data for its one named Reading) — it is a route that **cannot correctly implement the feature it is named for** without ownership scoping. This document recommends treating Reading History's route/query as blocked on that dependency, not merely as a security concern to flag and ship anyway.

No placeholder mechanism (a fake "current user," a single-tenant assumption baked into a query) is proposed, per this task's explicit instruction.

---

# 9. Auth/Ownership Dependency

Restates and sharpens `INTERPRETATION_API_DESIGN.md` Sections 4–5's already-documented finding (no authentication, no authorization, no `user_id` anywhere in `Reading` or `ReflectionSession`) for this specific feature: **Reading History is the first feature in this project's history where the missing ownership model isn't just a security gap on an otherwise-correct feature — it is the difference between the feature existing and not existing in any meaningful sense.** A `POST .../save` transition can be built and tested correctly today, in isolation, exactly as designed above, with the same interim unauthenticated posture every other route already accepts. A `GET` for Reading History cannot be *meaningfully* built until ownership exists, because there is no current definition of "whose history." This document names that dependency precisely rather than routing around it with an invented placeholder.

---

# 10. Persistence Impact

**None required for the Save transition itself.** `ReadingStatus.SAVED` already exists; `Reading.status` is already a plain mutable column; `mark_saved()` (Section 5.1) needs no new field. **No migration.**

**A plausible, not-decided future need:** if Reading History's ordering (Section 7) is ever found insufficient using `updated_at`'s approximation — e.g., once a future Reading-editing feature exists and starts mutating `updated_at` for unrelated reasons — a dedicated `saved_at` timestamp might become justified. Not proposed now; named only so a future investigator does not have to rediscover the reasoning in Section 7.2 from scratch. Similarly, whatever ownership mechanism eventually gets built (Section 9) will very likely need its own schema addition (a `user_id` on `Reading` or `ReflectionSession`, or an ADR-driven alternative) — that is a dependency of the *auth* work already flagged elsewhere in this project, not new schema work this document invents or requires for Save itself.

---

# 11. Idempotency & Error Behavior

- **`SAVED -> SAVED`:** idempotent success, no error, no write (Section 5.1's leading `if self.status == ReadingStatus.SAVED: return`).
- **`DRAFTING -> SAVED` (attempted):** rejected with a new domain error, illustratively `ReadingNotSaveableError(ValueError)`, mirroring `ReadingNotDraftingError`'s exact existing convention (same file, same base class, same "explain the current status in the message" style).
- **A nonexistent `reading_id` (once an API route exists):** `404`, via the same `_get_reading_or_404` pattern `app/api/interpretation.py` already uses — not designed further here, since no route is being built by this document.
- **Transaction behavior:** unchanged from every existing convention (`add_card_draw()`, `save_interpretation()`) — `mark_saved()` only flushes or commits if its caller does; a caller that rolls back after calling it leaves `status` exactly as it was before, via the same SQLAlchemy session-expiry mechanics already proven in `test_rollback_of_the_completing_draw_undoes_both_the_draw_and_the_transition` (Step 16) and `test_interpret_reading_does_not_commit_the_session` (Step 9).

---

# 12. Test Plan for Future Implementation

Already covered by existing, passing tests (cited, not proposed as new): reinterpretation of a `SAVED` Reading preserves `SAVED` and still creates a new `Interpretation` row (`test_saved_reading_remains_saved_after_reinterpretation` and its API/e2e counterparts, Steps 9/11/12) — this document's `mark_saved()` sketch does not change or need to re-verify that behavior.

**New, required once `mark_saved()` (or equivalent) is implemented:**
- `SPREAD_COMPLETE -> SAVED` succeeds.
- `INTERPRETED -> SAVED` succeeds.
- `DRAFTING -> SAVED` raises `ReadingNotSaveableError`; `status` unchanged.
- `SAVED -> SAVED` is a true no-op: no exception, `status` unchanged, no new `Interpretation` row, no other field touched.
- Saving does not change `len(reading.interpretations)` before/after, for a Reading with zero, one, or several prior interpretations.
- Saving does not change the content a subsequent `GET .../narrative`-equivalent call would produce (a narrative fetch before and after saving, holding the current Interpretation fixed, is identical).
- No `CardDraw` mutation occurs as a side effect of saving (a Reading's `card_draws` are untouched, count and content, before/after).
- Transaction rollback of a save operation leaves `status` at its pre-save value (mirroring Step 16's own rollback-test idiom exactly).

**New, required once a Reading History query/route exists (blocked on Section 9):**
- Only `SAVED` Readings are returned; `DRAFTING`/`SPREAD_COMPLETE`/`INTERPRETED` Readings are excluded.
- A `SAVED` Reading with multiple `Interpretation` rows appears exactly once.
- Newest-`updated_at`-first ordering holds.
- An empty result set returns `200 []`, not `404`.
- (Once ownership exists) a caller only ever sees their own saved Readings, never another user's.

---

# 13. Contradictions / Gaps

1. **The ownership gap (Section 3/9) is the single largest finding of this audit.** Neither the Product Spec nor any implementation names what "belongs to a user" means for a Reading — Reading History cannot be correctly built until this is resolved, and this document does not resolve it, per its explicit instructions.
2. **A `SAVED` Reading can have zero Interpretation rows** (Section 5's `SPREAD_COMPLETE -> save` path) — in mild tension with Product Spec Section 6's "Reading Detail... evidence + interpretation as generated" phrasing, which reads as assuming interpretation content always exists for a saved Reading. Not a contradiction this document resolves; named as an edge case a future Reading Detail view must handle.
3. **No field reliably captures "time of save"** (Section 7.2) — `updated_at` is a today-only, coincidentally-correct approximation, not a designed one.
4. **"Searchable/filterable"** (Product Spec Section 6) names no actual search/filter criteria anywhere in any governing document — recorded, not designed.

---

# 14. Deferred Questions

- **"Unsave"** — explicitly not designed (Section 5); if ever wanted, requires its own dedicated product decision, the same way Q3/Q6 themselves required one, not an extension of this document.
- **Whether a dedicated `saved_at` timestamp becomes necessary** — contingent on a future Reading-editing feature that does not exist today (Section 10).
- **How ownership will scope Reading History once it exists** — entirely gated on the Authentication Service work already named as missing platform infrastructure elsewhere (`INTERPRETATION_API_DESIGN.md` Sections 4–5).
- **What "searchable/filterable" concretely requires** — no criteria named anywhere yet.
- **Whether Reading Detail needs a distinct rendering path for a saved-but-never-interpreted Reading** — named in Section 13, not decided.

---

# 15. Recommended Implementation Sequence

1. Add `ReadingNotSaveableError` to `app/models/exceptions.py`, alongside `DuplicateCardError` and `ReadingNotDraftingError`.
2. Add `Reading.mark_saved()` per Section 5.1 — no other file needs to change for the Save transition alone.
3. Add the tests named in Section 12's first group (transitions, idempotency, rejection, non-interference with Interpretation/Narrative/CardDraw, rollback) — all buildable against step 2 alone, using the exact same `db_session`/`tests/factories.py` pattern `test_reading_lifecycle.py` (Step 16) already established.
4. **Do not** build a Reading History query, route, or schema until a separate, dedicated design step resolves the ownership dependency named in Section 9 — attempting it earlier would ship a feature that cannot correctly do what it exists to do.
5. Once ownership infrastructure is separately designed and approved: build the Reading History query following Section 7's semantics, plus the second group of tests in Section 12.

Steps 4–5 are not authorized by this document, consistent with this task's "audit/design only" scope covering the whole of Step 17.

---

# 16. Conclusion

`SAVED`'s Save *transition* is a small, low-risk, immediately-implementable piece of work: one new domain error, one new self-contained model method, no schema change, no new service — the same minimal-footprint pattern Step 15/16 already established and proved out for `SPREAD_COMPLETE`. Reading History, the feature `SAVED` exists to serve, is a different matter: this audit found zero existing list-query infrastructure of any kind for `Reading`, and — more importantly — found that the Product Spec itself never defines whose Readings such a list should show. Implementing Save now (or in a small, focused next step) while explicitly deferring Reading History until ownership infrastructure exists is this document's recommendation, not a compromise forced by convenience — building the query early would not satisfy Q3's own stated purpose ("the sole gate for Reading History visibility") in any user-meaningful sense.

---

## Related Documents

- `PRODUCT_DECISIONS.md` — Q3, Q4, Q6, the decisions this document operationalizes without reopening.
- `READING_LIFECYCLE_DESIGN.md` — Section 7's original candidate meanings for `SAVED`, since sharpened into Q3.
- `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` — the no-new-service precedent (Section 4 there) this document independently re-verifies and applies to Save.
- `INTERPRETATION_API_DESIGN.md` — Sections 4–5's auth/ownership gap, sharpened here (Section 9) into a feature-blocking dependency rather than a general hardening concern; Section 7/12's `404`-vs-`200 []` and pagination precedents, reapplied in Section 7.
- `READING_WORKFLOW_VALIDATION.md` — the global-`sequence` finding, cited implicitly by this document's insistence that Interpretation ordering must never leak into Reading History ordering (Section 7).
- `app/models/reading.py`, `app/models/exceptions.py`, `app/models/reflection_session.py`, `app/models/enums.py`, `app/services/`, `app/api/interpretation.py` — the actual, current code every finding in this document was checked against.
