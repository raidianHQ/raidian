# Raidian Wise — Reading Creation & Ownership Propagation Design/Audit (Step 25)

# Document Information

Version: 1.0 (Draft for Review — Not Yet Approved)
Status: Proposed — Design and Audit Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Determines exactly what a future Reading/ReflectionSession-creation API needs to look like, how ownership must propagate into it, and whether the currently-approved product/architecture documents are sufficient to implement it — closing the specific gap `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` (Step 15, Section 10/13) and `AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` (Step 21, Section 4.5) both named but explicitly declined to design. This document implements nothing.

Audience:
Whoever eventually designs the concrete request/response contract and implements Reading creation, and anyone auditing whether that future work matches this project's own schema, lifecycle, and ownership architecture rather than inventing one unmoored from them.

Authority:
Extends `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 10/13 (the original "not designed here" boundary around Reading/Draw creation) and `AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` Section 4.5/16.1 (the ownership-propagation gap named as a prerequisite step 7 in that document's own implementation sequence). Does not override `docs/PRINCIPLES.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, or `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — per ADR-0006's governance hierarchy, this document's recommendations rank below all four and are offered as input to whoever eventually approves a concrete implementation step, not a substitute for that approval. Where the Product Spec itself has an unresolved owner-level question (Section 14), this document preserves that, it does not resolve it.

---

# 0. Scope

Read-only design and repository audit only. No code, schema, migration, API route, test, or frontend file is created or modified. Where a question is genuinely unresolved by the repository or governance stack (Section 14), this document preserves that ambiguity rather than resolving it.

---

# 1. Executive Summary

**No schema change is required.** `Reading` already has a direct, mandatory, one-to-one relationship to `ReflectionSession` (`reflection_session_id`, `unique=True`, `nullable=False`), and `ReflectionSession.owner_id` (Step 22) already gives that relationship an owner. Every field a Reading-creation operation needs already exists on the current models. The entire gap is **missing application code**, not missing schema — confirming, once again, this project's repeated "derive, don't invent a column" precedent holds here too.

**Confirmed by direct, fresh repository search (not assumed from any prior report): zero production code anywhere constructs a `Reading` or `ReflectionSession`.** The only production construction of any reference-data entity this feature touches is `Spread`, created exclusively by the idempotent seed script (`app/seed/seed.py::seed_spread()`), never by a live request. `CardDraw` has exactly one production creation path (`Reading.add_card_draw()`), already implemented (Step 16) but with no route wired to it yet — a second, deliberately out-of-scope gap this document does not close (Section 16).

**Ownership propagation requires no new mechanism.** The already-approved chain — `User` → `ReflectionSession.owner_id` → `Reading` (via the existing FK) → `CardDraw`/`Interpretation` (transitively, via `Reading`) — is already fully wired for *reading*; creation only needs to *populate* `ReflectionSession.owner_id` from `Depends(get_current_user)` at construction time, using infrastructure that has existed, unused for this purpose, since Step 22.

**The architecturally correct new piece is a small, focused service function** (mirroring `app/services/auth_service.py::register_user()`'s exact shape — a plain function taking a session and validated inputs, not a model method and not the large `reading_service.py`/`draw_service.py` surface `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2 sketches), because — unlike `Reading.add_card_draw()` or `Reading.mark_saved()` — creation needs session access to validate a client-supplied `spread_id` actually exists, which no existing session-free model method can do.

**Two genuinely unresolved product questions block nothing about *this* design but remain open, exactly as the Product Spec itself already flags them:** "Reading" vs. "Reflection Session" as the top-level entity (Product Spec Section 3.2, Q2 — never ruled on) and the Deck/question-domain taxonomy questions (Q4, Q6). This document does not resolve either; Section 14 restates them precisely.

**One concrete, previously-unflagged implementation risk this audit surfaces: `Reading.validate_question()` raises a bare, uncaught `ValueError` for a blank question** — harmless today only because no route has ever constructed a `Reading` from client input. A future creation route must handle this at the request-validation boundary, exactly as Step 23 already had to do for a different bare-`ValueError` case (bcrypt's password-length limit) — named here as a concrete implementation requirement, not invented.

---

# 2. Current Production Creation Paths

Direct, fresh repository search (`grep -rn "Reading(\|ReflectionSession(\|CardDraw(\|Spread("`), not inferred from any prior step's report.

| Entity | Production construction site(s) | Test-only construction site(s) |
|---|---|---|
| `Reading` | **None.** Only the class definition (`app/models/reading.py:27`) exists anywhere in `app/`. | `tests/factories.py::make_reading()`, `tests/interpretation_helpers.py::build_reading()` — both construct `Reading(...)` directly, no factory/service wraps either call. |
| `ReflectionSession` | **None.** Only the class definition (`app/models/reflection_session.py:16`). | Same two test helpers — each constructs `ReflectionSession(owner=owner)` (Step 22, `owner` defaulting to `None`) immediately before the `Reading` that references it. |
| `CardDraw` | **One path**: `Reading.add_card_draw()` (`app/models/reading.py:152`) — a real, tested, production-ready model method (Step 16). No route calls it; nothing else in `app/` constructs a `CardDraw`. | Every reading-building test helper calls it indirectly via `add_card_draw()`; two tests (`test_only_one_card_per_position_at_the_database_level`, `test_draw_order_must_be_unique_within_a_reading`) construct `CardDraw(...)` directly, deliberately, to prove the database still enforces the same invariants if the sole path were ever bypassed. |
| `Spread` | **One path**: `app/seed/seed.py::seed_spread()` — idempotent (looks up by `Spread.name` first, updates in place if found, else inserts), driven from `app/reference_data/spreads/*.yaml`, invoked by `seed_all_spreads()` at dev/deploy setup time, never by a live request. | `tests/factories.py::make_spread()` constructs one directly, independent of the seed mechanism, for lightweight non-reference-data tests. |
| `SpreadPosition` | Same seed path, inside `seed_spread()`. | Same `make_spread()` helper. |

**`scripts/` is empty** (only `.gitkeep`) — no standalone script creates any of these entities either. This confirms `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 2.6's finding ("no API route exists anywhere that creates a Reading") and `SAVE_READING_DESIGN.md` Section 2.1's identical finding both still hold, unchanged, after re-verification against the current repository state (post Step 24).

---

# 3. Reading/ReflectionSession Relationship

Re-inspected directly against `app/models/reading.py` and `app/models/reflection_session.py` (current, post-Step-24):

- `Reading.reflection_session_id`: `ForeignKey("reflection_sessions.id", ondelete="CASCADE")`, **`nullable=False`**, **`unique=True`**.
- `ReflectionSession.reading`: `relationship(..., uselist=False, cascade="all, delete-orphan")`.

Together these enforce a **strict, mandatory one-to-one**: a `Reading` cannot exist without exactly one `ReflectionSession`, and a `ReflectionSession` can have at most one `Reading`. This is unchanged since the schema's original design and re-confirmed here, not assumed.

**Direct answer to this task's specific verification requirement: yes — ownership can be established at Reading-creation time using the relationship that already exists, with no new column.** `ReflectionSession.owner_id` (Step 22) is already the correct, only place ownership lives; a creation operation needs only to construct `ReflectionSession(owner=current_user)` and attach the new `Reading` to it — exactly the same two-object construction shape `tests/factories.py::make_reading()` and `tests/interpretation_helpers.py::build_reading()` already perform today, just with a real authenticated `owner` supplied instead of test-fixture convenience or `None`.

---

# 4. Ownership Propagation

## 4.1 The required flow, confirmed against the actual schema

```text
Authenticated User (current_user, from Depends(get_current_user))
  → ReflectionSession(owner=current_user)      -- new row, Step 22's owner_id populated at construction
      → Reading(reflection_session=..., ...)    -- new row, FK to the ReflectionSession above
          → CardDraw (future, via add_card_draw() -- Section 16, out of scope here)
          → Interpretation (already implemented, Step 9/11)
          → NarrativeModel (never persisted, unchanged)
```

No step in this chain requires a new column, a new table, or a new relationship direction. The chain is already fully wired for **reading** ownership (`get_owned_reading`, Step 22); this document's only conclusion is that **writing** ownership requires nothing more than populating the same field at construction time, from the same authenticated identity every other authenticated route already resolves.

## 4.2 Child tables remain owner-less — reconfirmed, not re-derived

**`CardDraw`, `Interpretation`, and `NarrativeModel` must not gain an `owner_id` of their own.** Re-confirming (not re-deriving) `READING_HISTORY_OWNERSHIP_DESIGN.md` Section 6 and `AUTHENTICATION_OWNERSHIP_DESIGN.md` Section 3.3's identical conclusion against the current schema: every one of these already resolves to an owner transitively through `Reading.reflection_session.owner_id`, and duplicating the column would violate this project's own repeatedly-applied "derive, don't store-and-risk-drift" precedent (`Spread.position_count`, `Reading.is_spread_complete`) for zero benefit. **This document does not introduce a duplicate `owner_id` anywhere.**

## 4.3 Security boundary: the client never supplies ownership

The future creation request body must **never** accept an `owner_id`, `user_id`, or any client-supplied identity field. Ownership is derived exclusively from `Depends(get_current_user)`, exactly matching this project's existing, unbroken posture since Step 22 (no route anywhere in this codebase accepts a caller-supplied identity for any purpose). This is not a new rule this document invents — it is the same rule already governing every existing authenticated route, restated here because it is the one place a *creation* endpoint specifically could be tempted to add a "for testing" owner override, which this document explicitly forecloses (Section 10).

---

# 5. Reading Creation Lifecycle

Direct answers to this task's audit checklist, each checked against the actual current model/schema rather than assumed.

| Question | Answer | Basis |
|---|---|---|
| Required `Reading` fields at construction | `reflection_session` (or `reflection_session_id`), `spread_id`, `deck_id`, `question` — all four are `nullable=False` in the current schema. | `app/models/reading.py` |
| Default status | `ReadingStatus.DRAFTING` — the model's own column default; a creation operation needs to do nothing to achieve this. | `app/models/reading.py`, `status: Mapped[ReadingStatus] = mapped_column(..., default=ReadingStatus.DRAFTING)` |
| `question`/`question_domain` behavior | `question` is required, non-blank (`@validates("question")` rejects empty/whitespace-only, raising a bare `ValueError` — Section 9 flags this as an unhandled-today risk). `question_domain` is optional (`String(60)`, `nullable=True`), free-form — **no canonical taxonomy exists anywhere in this repository** (Section 14). | `app/models/reading.py`; Product Spec Section 5 step 4, Q6 |
| `ReflectionSession` requirement | Mandatory, 1:1, created alongside the Reading (Section 3) — no independent `ReflectionSession`-only creation path is needed or proposed. | `app/models/reading.py`, `app/models/reflection_session.py` |
| `Spread` requirement | `spread_id` is `nullable=False` — **a Reading cannot exist in this schema without an already-chosen Spread.** This is a direct, unambiguous schema fact, not a product question requiring a decision (Section 6). | `app/models/reading.py` |
| `SpreadPosition` requirement | None directly on `Reading` — positions are reached only through `spread.positions`, needed only once drawing begins (`add_card_draw()`), not at Reading creation. | `app/models/spread_position.py` |
| Can a Reading exist before a Spread is selected? | **No** — the schema's `NOT NULL` constraint on `spread_id` makes this structurally impossible without a schema change, which this document does not propose (none was found necessary). | Direct schema fact |
| Can a Reading exist without any `CardDraw` rows? | **Yes** — this is precisely what `DRAFTING` already means, and is the expected starting state for every newly-created Reading. | `ReadingStatus` lifecycle, unchanged |
| Can a Reading exist without `Interpretation`? | **Yes** — `Interpretation` is a wholly separate table, added later via the already-existing `POST /readings/{id}/interpret`; a freshly-created Reading has zero rows in it by construction. | `app/models/interpretation.py`, unchanged |
| How does the existing lifecycle expect a Reading to begin? | `(none) → Reading created → DRAFTING`, already the first row of `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 8's transition matrix (Step 15) — this document adds nothing new here, it confirms creation is the *only* way to reach that first row, and that no route exists yet to trigger it. | Step 15 Section 8, reconfirmed |

**No product behavior is invented in this table** — every answer is either a direct schema fact or an explicit restatement of an already-approved document's own conclusion.

---

# 6. Spread Selection and Reference Data

## 6.1 Tracing the existing chain

```text
Reading.spread_id  --FK-->  Spread.id
Spread.positions   --1:N--> SpreadPosition (spread_id FK)
SpreadPosition.card_draws --1:N--> CardDraw (position_id FK, future draw-recording path)
```

`Spread.name` carries a real, database-enforced unique constraint (`uq_spreads_name`) — Spreads are genuine, uniquely-named reference data, not user-generated content. `SpreadPosition` similarly enforces `UniqueConstraint(spread_id, position_order)`.

## 6.2 The authoritative existing reference-data mechanism

**`app/seed/seed.py::seed_spread()`/`seed_all_spreads()`, driven from `app/reference_data/spreads/*.yaml` (`single_card.yaml`, `three_card.yaml`, `celtic_cross.yaml`).** This is idempotent by design (looks up by `name` first) and runs at dev/deploy setup time — it is not, and was never intended to be, a per-request operation. This confirms `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 2.4's finding, re-verified: three seeded Spreads exist today, every position in every one of them `required=True` (no `required=False` position exists anywhere in real reference data).

## 6.3 Should a creation API select by ID, by name, create one, or defer selection?

**Select an existing Spread by its `id` (UUID) — not by name, and never create one inline.**

- **By ID, not by name:** `Reading.spread_id` is the actual FK the schema requires; accepting a `spread_id` directly from the client is the smallest, most direct mapping from request to persisted row, with no extra name→ID lookup step to get wrong. A name-based lookup would add a translation layer for no benefit `Spread.name`'s own uniqueness doesn't already guarantee is safe, and would only reintroduce the very kind of "another source of truth to keep in sync" this project's own precedent avoids.
- **Never create a Spread inline:** no product or architecture document anywhere suggests a Reading-creation flow should also define new spread layouts — Spreads are pre-authored reference content (the same category as `Card`/`Deck`), seeded independently of any user action, exactly like every other reference-data entity in this schema.
- **Not deferred:** Section 5's schema fact (`spread_id` is `NOT NULL`) already forecloses deferring Spread selection past Reading creation — this is not a product-convenience recommendation, it is the only option the current schema permits without a migration (none is proposed).

## 6.4 A related, minor observation: `Deck` selection

Not asked directly by this task's Spread-specific questions, but directly relevant to "required Reading fields" (Section 5): `Reading.deck_id` is equally `NOT NULL`. `Deck.is_default` exists (`app/models/deck.py`) and today's seed data maintains exactly one `is_default=True` row (Rider-Waite-Smith) — but **`is_default` carries no database-level uniqueness constraint**, only convention. A future creation service could reasonably default `deck_id` to "the current default Deck" when the client doesn't specify one (consistent with Product Spec Q4's still-open "is a single hardcoded deck sufficient for MVP" framing, without resolving that question) — named as a reasonable implementation option, not decided here, and the `is_default` uniqueness gap is noted as a minor, pre-existing schema softness (Section 13), not something this document asks to be fixed.

---

# 7. Proposed API Boundary

## 7.1 Route

**`POST /readings`.** This is not a new naming decision — `app/api/reading.py` (Step 24) already declares `router = APIRouter(prefix="/readings", tags=["reading"])` with `GET /readings` (Reading History) as a sibling route on the exact same collection path. A creation route is the standard second verb on an already-existing collection route (`GET` = list, `POST` = create) — the file, router, and path prefix this route would live in already exist; only the route function itself does not.

## 7.2 Minimum request fields, derived from Section 5's table (not invented)

```text
spread_id        -- required, UUID, must reference an existing Spread
question         -- required, non-blank string
question_domain  -- optional, free-form string (no canonical taxonomy exists -- Section 14)
draw_method      -- optional, defaults to DrawMethod.PHYSICAL (the model's own existing column default)
deck_id          -- optional if a single-default-deck convention (Section 6.4) is adopted; required otherwise -- not decided here
```

**Never included:** any owner/user identity field (Section 4.3).

## 7.3 Minimum response shape

The existing `ReadingSummary` schema (`app/schemas/reading_api.py`, Step 24 — `id`, `status`, `question`, `question_domain`, `created_at`, `updated_at`) already covers the minimum useful confirmation of a newly-created Reading, and reusing it avoids inventing a duplicate shape for the same resource (this task's own instruction). **One open implementation question, not decided here:** a client that just created a Reading plausibly also needs `spread_id`/`deck_id`/`draw_method` to proceed to card entry — fields `ReadingSummary` deliberately omits (Step 24's own "no Reading Detail view exists yet to require them" reasoning). Whether creation's response should extend `ReadingSummary` or reuse it verbatim is left to the eventual implementation step to decide once the actual card-entry API (Section 16) is designed and its real needs are known — naming the question precisely rather than guessing.

## 7.4 Service/domain boundary

**A new, narrow service function is justified — not a model method, and not the full `reading_service.py`/`draw_service.py` surface.**

- **Not a model method**, unlike `add_card_draw()`/`mark_saved()`: both of those operate on an *already-loaded* `Reading` with no need to query the database. Creation must validate a client-supplied `spread_id` actually exists (a `SELECT`) before constructing anything — this requires `Session` access no session-free model method has.
- **Not `reading_orchestration.py`**: that module's own docstring scopes it strictly to combining database access with the Interpretation Engine and Narrative Layer (re-confirmed, `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 2.12) — Reading creation touches neither.
- **The closest existing precedent in this exact codebase is `app/services/auth_service.py::register_user()`**: a plain function, taking `session` plus already-validated inputs, doing a lookup, constructing a new row (here, two related rows), calling `session.flush()`, never `session.commit()`. A future `app/services/reading_service.py` (name illustrative, not prescribed) with a single function — illustratively `create_reading(session, *, owner, spread_id, deck_id, question, question_domain, draw_method) -> Reading` — matches this shape exactly.
- **This is deliberately narrower than `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2's `reading_service.py`/`draw_service.py` sketch**, which describes the much larger, still-undesigned surface (Layout selection UX, digital draw randomization, physical entry validation) — exactly the same distinction `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 4 already drew for `add_card_draw()`'s `SPREAD_COMPLETE` extension. This document's recommendation is only for the narrow "construct a new, owned Reading" seam, not the whole future surface.

**Not created by this document** — Section 15 names it as the next implementation step's first task.

---

# 8. Transaction Boundary

Re-audited directly against the current `app/db/session.py::get_db()` (unchanged since Step 11, re-verified fresh across Steps 22–24 and again here):

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

**The stated invariant ("either everything persists or nothing does") is already satisfied by this existing mechanism, with no new code required to enforce it.** A future creation service that follows this project's own unbroken convention — `session.add(reflection_session)`, `session.flush()`, `session.add(reading)`, `session.flush()`, **never `session.commit()`** — automatically inherits `get_db()`'s single commit point. If anything raises before that commit (an invalid `spread_id`, a blank `question`, an unexpected `IntegrityError`), `get_db()`'s `except Exception: db.rollback()` undoes the entire in-progress transaction, both the `ReflectionSession` and the `Reading` together, since neither was ever independently committed.

**No current model behavior was found that could violate this invariant.** Every existing mutator in this codebase (`add_card_draw()`, `mark_saved()`, `register_user()`, `save_interpretation()`) already follows the identical flush-only discipline; `ReflectionSession.reading`'s `cascade="all, delete-orphan"` relationship config is a deletion-cascade concern, not a creation-atomicity one, and does not interact with this invariant. **`get_db()` itself is not modified by this document**, per this task's explicit instruction.

---

# 9. Validation and Error Handling

## 9.1 Already determined by existing convention

| Case | Behavior | Basis |
|---|---|---|
| Unauthenticated request | `401`, uniform message, via unmodified `get_current_user` | Step 22, re-verified Step 23 |
| Inactive user | `401`, via unmodified `get_current_user` (checked on every request, not cached) | Step 22 |
| Malformed request body (wrong types, missing required fields) | `422`, FastAPI's automatic Pydantic validation | Existing convention, every route |
| Malformed `spread_id`/`deck_id` (not a valid UUID) | `422`, FastAPI's automatic path/body validation | Existing convention |
| Nonexistent `spread_id` (well-formed UUID, no matching row) | **`404`**, by direct analogy with this project's own existing `_READING_NOT_FOUND` pattern (a referenced resource that doesn't exist is already, consistently, a `404` everywhere else in this API) | Direct derivation from `app/api/interpretation.py`/`app/api/dependencies.py`'s established convention, not a new rule |
| Transaction failure of any kind | `get_db()`'s existing rollback-on-exception | Section 8 |

## 9.2 A genuinely new finding this audit surfaces — not previously flagged anywhere

**`Reading.validate_question()` (`app/models/reading.py`) raises a bare `ValueError("question must not be empty")` for a blank/whitespace-only question, and nothing in this codebase catches or maps it to any HTTP status today** — harmless only because no route has ever constructed a `Reading` from client-supplied input before now. This is structurally the same class of gap Step 23 found and fixed for `hash_password()`'s bare `ValueError` on an over-length password: **a future creation route must not let a client-supplied blank `question` reach this validator uncaught**, or it will surface as an unhandled `500`, exactly as the bcrypt case did before remediation. The recommended fix (not implemented here, per this task's scope) is the same one Step 23 already established as this project's convention: reject a blank `question` at the **request-schema** validation layer (a Pydantic `field_validator`), producing a clean `422` before the model is ever touched — not a `try/except ValueError` wrapped around model construction.

## 9.3 Explicitly not resolved — requires a product decision (Section 14)

- What counts as a valid `question_domain` value (no taxonomy exists — Product Spec Q6, still open).
- Whether `deck_id` is client-required or server-defaulted (Product Spec Q4, still open — Section 6.4 names the implementation option without deciding the product question it rests on).

---

# 10. Security / Ownership Rules

Restated precisely, each directly checked against the current dependency implementations (`app/api/dependencies.py`, unchanged since Step 22, re-verified fresh this step):

- **The authenticated user is the sole source of ownership.** `Depends(get_current_user)` is the only mechanism a creation route should use to determine `owner`; the request body must never contain an owner/user identity field (Section 4.3).
- **`ReflectionSession` and `Reading` are created within one transaction** (Section 8) — not two separate requests, not two separate commits. This is a direct consequence of the schema's own mandatory 1:1 relationship (Section 3): a `Reading` cannot be flushed without an already-flushed (or cascaded) `ReflectionSession` to reference, and per this project's convention, both flush within the same uncommitted transaction the API boundary controls.
- **No existing dependency needs modification.** `get_current_user` already does exactly what a creation route needs (resolve the authenticated identity); `get_owned_reading` is not applicable here at all (there is no existing `reading_id` to resolve — this is the operation that produces one), exactly mirroring how Reading History (Step 24) also uses `get_current_user` alone rather than `get_owned_reading`, for the identical structural reason.
- **No new ownership model, no duplicate `owner_id`, no client-supplied override of any kind** — every one of this task's explicit prohibitions is already satisfied by continuing to use the existing, unmodified Step 22 dependencies exactly as they are.

---

# 11. Test Plan (Not Implemented)

Concrete, for the eventual implementation step — mirroring this project's own established fixture conventions (`db_session`/`seeded_session` from `tests/conftest.py`, the self-contained `client`/`api_seeded_session` pattern every API test file already duplicates per Step 11's precedent).

1. An authenticated user creates a Reading → `201`, response reflects `DRAFTING` status.
2. The created `Reading.reflection_session.owner_id` equals the authenticated user's `id` — the core ownership-propagation proof.
3. A request body containing a client-supplied `owner_id`/`user_id` field is ignored (or rejected if the schema forbids extra fields, matching `app/schemas/auth.py`'s `extra="forbid"`-adjacent discipline) — the created Reading's owner is always the authenticated caller, never anything from the body.
4. Unauthenticated creation request → `401`, no row of any kind persisted.
5. A malformed `spread_id` (not a valid UUID) → `422`.
6. A well-formed but nonexistent `spread_id` → `404`, no row persisted.
7. The newly created Reading's `status` is exactly `DRAFTING` — the sole approved starting lifecycle state.
8. A newly created Reading has zero `Interpretation` rows and zero `CardDraw` rows.
9. A forced failure mid-creation (e.g., a blank `question`, or a monkeypatched exception between the two flushes) leaves **neither** a `ReflectionSession` **nor** a `Reading` row behind after the request — the atomicity proof (Section 8).
10. Two distinct authenticated users each create a Reading; each can access only their own afterward (via the existing `get_owned_reading`-gated routes) — ownership isolation, reusing the exact two-user pattern `tests/test_ownership.py` already established.
11. A freshly created (never-saved) Reading does **not** appear in `GET /readings` (Reading History, Step 24) — confirms creation does not accidentally satisfy the `SAVED`-only history gate.
12. The owner can reach the newly created Reading through the existing `get_owned_reading`-gated routes (e.g. `GET /readings/{id}/interpretations` returns `200 []`, not `404`) — proves the new Reading is a fully real, ownable resource from the moment of creation, not a special or partial one.
13. A different, authenticated user requesting the newly created Reading via any existing route still receives `404` — cross-user isolation, unchanged.
14. No child table (`CardDraw`, `Interpretation`) gains an `owner_id` column as part of this work — a schema-inspection assertion, not a behavioral one, guarding against future scope creep.

**Not written by this document**, per this task's explicit instruction.

---

# 12. Architectural Alternatives Considered

| Alternative | Verdict | Reasoning |
|---|---|---|
| A model method on `Reading` (e.g. a classmethod `Reading.create(...)`) | **Rejected** | Needs `Session` access to validate `spread_id` exists — every other model method in this codebase (`add_card_draw`, `mark_saved`) is deliberately session-free; introducing the first session-aware model method for this one operation would be a new, unprecedented pattern, not a reuse of an existing one. |
| Extending `reading_orchestration.py` | **Rejected** | Its own docstring scopes it to Interpretation/Narrative orchestration only; Reading creation touches neither (Section 7.4, `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 2.12, reconfirmed). |
| Building the full `reading_service.py`/`draw_service.py` surface now | **Rejected** | Speculative — this task, like Step 15 before it, asks for the one seam actually needed (ownership-propagating creation), not the larger, still-undesigned Layout-selection/digital-draw/physical-entry-validation surface `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2 only sketches. |
| A new, narrow service function (`app/services/reading_service.py`, one function) | **Recommended** | Matches `auth_service.py::register_user()`'s already-proven shape exactly; smallest addition that satisfies the actual requirement (session-aware validation + two-row construction). |
| Selecting a Spread by name instead of ID | **Rejected** | `spread_id` is the real FK; a name-based lookup adds a translation layer with no correctness or usability benefit the ID-based approach doesn't already provide (Section 6.3). |
| Allowing the creation route to also define a new Spread inline | **Rejected** | No product or architecture basis anywhere; Spreads are pre-authored reference data, not user-generated content (Section 6.3). |
| Deferring Spread selection to a later "attach spread" step | **Rejected** | `spread_id` is `NOT NULL` — the current schema does not support a Spread-less Reading at all; this is not a preference, it is a hard constraint (Section 5/6.3). |

---

# 13. Contradictions / Gaps

1. **`Reading.validate_question()`'s uncaught bare `ValueError`** (Section 9.2) — the single most concrete, previously-unflagged implementation risk this audit found; not a contradiction with any approved document, but a real gap a future creation route must not walk into unguarded.
2. **`Deck.is_default` has no database-level uniqueness constraint** (Section 6.4) — today harmless (exactly one `is_default=True` row exists via seed-script convention), but a soft spot a future multi-deck feature (or a bug in a future seed change) could silently violate; named, not fixed, since no current behavior depends on it being enforced.
3. **No contradiction was found between this design and any approved architecture/lifecycle document** — every conclusion here is either a direct schema fact or a reconfirmation of an already-approved decision (Step 15's `add_card_draw()` design, Step 19/20's ownership placement, Step 22's dependency shapes). Nothing here required silently overriding or reinterpreting any prior step's approved conclusion.

---

# 14. Unresolved Product Decisions

Explicitly preserved, not resolved, per this task's instruction — several are pre-existing, unresolved Product Spec questions this audit re-confirms are still open, not new findings:

- **"Reading" vs. "Reflection Session" as the top-level entity (Product Spec Section 3.2, Q2).** The Product Spec's own text states: *"Until the owner rules on Q2/Q3, this document uses Reading and Layout as defined in the brief."* Never ruled on anywhere in this repository's history. This document does not need it resolved to proceed (the current schema already commits to "Reading is the top-level persisted entity, ReflectionSession wraps it"), but the *naming*/conceptual question Q2 raises remains genuinely open at the product-documentation level.
- **Whether `ReflectionSession` represents the user's entire reflective activity or specifically one Reading.** Restated, not re-derived, from `READING_HISTORY_OWNERSHIP_DESIGN.md` Section 3 — the *enforced* schema (strict 1:1 with `Reading` today) and the model's own docstring *aspiration* (generalizing to future non-tarot activities) remain in the same, deliberately preserved tension this document does not resolve.
- **Does the Product Spec define a creation workflow precisely enough to pin an exact request/response contract?** No — Section 5's "Core User Flow" describes a *UX sequence* (start Reading → select Layout → enter question → ...), not an API/persistence contract. This document infers the *minimum schema-required* fields (Section 7.2) from that sequence without inventing a workflow the spec doesn't actually specify.
- **Should a new Reading immediately create a `ReflectionSession`?** Structurally, yes — the schema requires it (Section 3), so there is no meaningful alternative without a migration. Whether the *product* ever wants a `ReflectionSession` that outlives or precedes its Reading (per the still-open Q2/Section 3 tension above) is a separate, unresolved question this document does not need to answer to make this specific recommendation.
- **Is there an existing intended frontend workflow?** No — re-confirmed (`AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` Section 2.2/11, unchanged): `frontend/` remains the untouched Vite scaffold, with no screens, router, or API client of any kind.
- **Does "Start Reading" / "New Reading" exist in product documentation?** Yes, as a *UX step* only (Product Spec Section 5 step 1, Section 6's Home screen: "start new Reading") — never as an API or persistence specification.
- **Can the user edit `question`/`question_domain` after creation?** Not addressed anywhere — no update-Reading route or mutation method exists for these fields, and the Product Spec is silent. Genuinely undecided; not invented here.
- **Must Reading creation and the first `CardDraw` be separate operations?** Structurally, yes, by construction: `add_card_draw()` validates against an already-persisted `self.spread`/`self.deck`, so the `Reading` must already exist first. Whether they are exposed as one combined API call or two sequential ones is an API-design choice for the (separately scoped, still undesigned — Section 16) draw-recording work, not decided here.
- **Deck selection default (Product Spec Q4)** and **question-domain taxonomy (Product Spec Q6)** — both still open, exactly as the Product Spec itself already states; this document does not rule on either.

**None of these block the architectural conclusions in Sections 3–10 above** — they affect exact request-field defaults and validation content, not whether ownership can propagate correctly or where the operation belongs.

---

# 15. Recommended Implementation Sequence

Sequenced so each step is independently reviewable, mirroring this series' own established practice:

1. **A dedicated request/response contract design step** resolving Section 7.2/7.3's open field-default and response-shape questions, and Section 14's Deck/question-domain product questions to whatever extent the eventual implementer needs them pinned — this document intentionally stops short of that level of detail.
2. **Add the request-validation guard for blank `question`** (Section 9.2) as part of that same step's schema design — the one concrete implementation requirement this audit surfaces.
3. **Implement the narrow `create_reading()` service function** (Section 7.4) — `ReflectionSession` + `Reading` construction, flush-only, no commit.
4. **Wire `POST /readings`** in the existing `app/api/reading.py` (Step 24) — `Depends(get_current_user)`, resolve/validate `spread_id` (404 if missing), call the service, return `ReadingSummary` (or its eventual superset).
5. **Add the tests named in Section 11.**
6. **Only afterward, separately:** the draw-recording API (`add_card_draw()` already implemented per Step 16; no route exists — Section 16, explicitly out of scope for this document and the sequence above).

No step in this sequence is authorized by this document.

---

# 16. Explicit Non-Goals

Per this task's own scope and this document's own findings, all of the following remain out of scope and are not designed, implied, or pre-approved by anything above:

- Draft autosave.
- Deleting a Reading via an API (the model/cascade behavior already supports whole-Reading deletion — `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 7.4 — but no route exists or is designed here).
- Duplicating a Reading.
- Sharing or collaboration on a Reading.
- Reading templates.
- New Spread types or a Spread-authoring API.
- New `ReadingStatus` lifecycle states.
- Pagination, search, or filtering on creation or on Reading History (`GET /readings`, Step 24, already explicitly deferred these; unchanged).
- Any UI/frontend route or screen.
- **The draw-recording API** (`POST /readings/{id}/draws` or equivalent) — `Reading.add_card_draw()` is already fully implemented and tested (Step 16), but no route calls it anywhere, and designing that route is a distinct, separately-scoped piece of future work this document deliberately does not fold into "Reading creation." Section 15 names it as a later, separate step.
- Editing `question`/`question_domain` after creation (Section 14, unresolved).
- Any resolution of Product Spec Q2 (Reading vs. Reflection Session), Q4 (Deck scope), or Q6 (question-domain taxonomy).

---

## Related Documents

- `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` (Step 15) — the original `add_card_draw()`/`SPREAD_COMPLETE` design and its own explicit "Reading/Draw creation API is not designed here" boundary (Section 10/13), which this document is the direct continuation of.
- `SAVE_READING_DESIGN.md` (Step 17) — Section 2's original finding that no Reading list/creation query existed anywhere, re-confirmed unchanged.
- `READING_HISTORY_OWNERSHIP_DESIGN.md` (Step 19) — Section 2.5's ownership-placement decision (`ReflectionSession.owner_id`) this document builds directly on without reopening.
- `AUTHENTICATION_OWNERSHIP_DESIGN.md` (Step 20), `AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` (Step 21) — Section 4.5/16.1's explicit naming of this exact gap ("a future Reading-creation route must set owner_id... not built here") as a required future step, which this document now designs.
- `PRODUCT_DECISIONS.md` (Step 14) — Q2/Q3/Q6, the lifecycle decisions this document's Section 5 table reconfirms without reopening.
- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Sections 3.2 (Q2, Reading vs. Reflection Session), 5 (Core User Flow), 6 (screen inventory), 7.5 (Reading fields), the source of every product-level fact and open question cited in Sections 5–7/14.
- `RAIDIAN_WISE_ARCHITECTURE_V1.md` — Section 2's `reading_service.py`/`draw_service.py` sketch, cited and deliberately not adopted wholesale (Section 7.4/12), the same posture Step 15 already took.
- `docs/DECISIONS.md` (ADR-0003, ADR-0004, ADR-0005, ADR-0006), `docs/PRINCIPLES.md`, `docs/ROADMAP.md` — the governance stack re-checked directly, not assumed, for this step.
- `app/models/reading.py`, `app/models/reflection_session.py`, `app/models/spread.py`, `app/models/spread_position.py`, `app/models/deck.py`, `app/models/card_draw.py`, `app/seed/seed.py`, `app/api/reading.py`, `app/api/dependencies.py`, `app/db/session.py`, `app/services/auth_service.py`, `tests/factories.py`, `tests/interpretation_helpers.py` — the actual, current code every finding in this document was checked against.
