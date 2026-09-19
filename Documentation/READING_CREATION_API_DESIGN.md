# Raidian Wise — Reading Creation API Contract & Implementation Design/Audit (Step 26)

# Document Information

Version: 1.0 (Draft for Review — Not Yet Approved)
Status: Proposed — Design and Audit Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Turns `READING_CREATION_OWNERSHIP_DESIGN.md`'s (Step 25) architectural conclusions into an implementation-ready request/response contract for `POST /readings` — exact fields, exact validation, exact status codes, exact service-function signature, exact file layout — while explicitly preserving every product decision Step 25 identified as genuinely unresolved. This document implements nothing.

Audience:
Whoever implements `POST /readings` next, and anyone auditing whether that implementation matches this contract rather than inventing one.

Authority:
Operationalizes `READING_CREATION_OWNERSHIP_DESIGN.md` (Step 25) without reopening any of its architectural conclusions (ownership placement, service-vs-model-method boundary, Spread-by-ID-only, no schema change). Does not override `docs/PRINCIPLES.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, or `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — per ADR-0006, this document's recommendations rank below all four and are offered as implementation-ready input, not a substitute for product sign-off on anything still genuinely open.

---

# 0. Scope

Read-only design and audit only. No code, schema, migration, test, or frontend file is created or modified — only this document. Where Step 25 left a product question open, this document does not resolve it; it determines precisely whether that openness blocks a precise API contract (Section 6) and, where it does not, specifies an explicit, clearly-labeled implementation default.

---

# 1. Current Models — Constraints Re-Verified

Direct, fresh re-read of `app/models/reading.py`, `app/models/reflection_session.py`, `app/models/spread.py`, `app/models/spread_position.py`, `app/models/deck.py`, `app/db/session.py` — not assumed from Step 25's own summary.

| Field | Column | Nullable | Notes |
|---|---|---|---|
| `Reading.reflection_session_id` | FK → `reflection_sessions.id`, `CASCADE` | No | `unique=True` — strict 1:1 |
| `Reading.spread_id` | FK → `spreads.id`, `RESTRICT` | No | |
| `Reading.deck_id` | FK → `decks.id`, `RESTRICT` | No | |
| `Reading.question` | `Text` | No | **No DB-level length limit** — re-confirmed by direct read, not assumed; `@validates("question")` rejects empty/whitespace-only with a bare `ValueError` |
| `Reading.question_domain` | `String(60)` | Yes | No taxonomy/enum anywhere in this schema |
| `Reading.draw_method` | enum, `default=DrawMethod.PHYSICAL` | No | Model-level default |
| `Reading.status` | enum, `default=ReadingStatus.DRAFTING` | No | Model-level default |
| `ReflectionSession.owner_id` | FK → `users.id`, `CASCADE` | Yes (Step 22 transitional) | Becomes the ownership anchor when populated |
| `Deck.is_default` | `Boolean`, `default=False` | No | **No DB-level uniqueness constraint** — convention-only (Step 25 Section 6.4, re-confirmed) |
| `Spread.name` | `String(120)` | No | Real, DB-enforced `UniqueConstraint` |

`app/db/session.py::SessionLocal` is configured `autoflush=False, autocommit=False, expire_on_commit=False` (re-confirmed by direct read) — relevant to Section 8's transaction design.

**No new fact contradicts Step 25's conclusions.** Everything needed for a precise contract already exists on these models.

---

# 2. Ownership Propagation Path — Confirmed

```text
Depends(get_current_user)          -- app/api/dependencies.py, unmodified since Step 22
  → current_user: User             -- resolved, active, or the request already failed 401
      → ReflectionSession(owner=current_user)   -- new row, owner_id populated at construction
          → Reading(reflection_session=..., spread=..., deck=..., question=..., ...)
```

Re-verified directly against `app/api/dependencies.py::get_current_user` (unchanged) — no modification to it is needed or proposed. `get_owned_reading` is **not** used by this route (there is no pre-existing `reading_id` to resolve — this is the operation that produces one), exactly the same structural reason `GET /readings` (Step 24) also uses `get_current_user` alone.

A minor implementation-flexibility note, checked directly against `SessionLocal`'s `autoflush=False` configuration: because every primary key in this schema is a client-generated UUID (`default=uuid.uuid4`, not a DB-generated identity), `Reading(reflection_session=reflection_session, ...)` already has a valid, in-memory `reflection_session_id` the instant `reflection_session` is constructed — an intermediate `session.flush()` between constructing the `ReflectionSession` and the `Reading` is **not required for correctness** (SQLAlchemy's unit-of-work orders the two INSERTs correctly at whatever flush eventually happens, based on the object graph, not manual sequencing). This document still recommends flushing after each step anyway (Section 8), purely to match this project's own existing, unbroken convention (`tests/factories.py::make_reading`, `tests/interpretation_helpers.py::build_reading` both do this) and to fail fast/legibly if something is wrong — not because it is structurally necessary.

---

# 3. Proposed Route: `POST /readings`

Lives in the existing `app/api/reading.py` (Step 24), as a new sibling to the already-implemented `GET /readings` and `POST /readings/{reading_id}/save` on the same `APIRouter(prefix="/readings", tags=["reading"])`.

## 3.1 Request schema — `ReadingCreateRequest` (new, added to the existing `app/schemas/reading_api.py`)

```python
class ReadingCreateRequest(BaseModel):
    spread_id: UUID
    question: str
    question_domain: str | None = None
    draw_method: DrawMethod = DrawMethod.PHYSICAL
    deck_id: UUID | None = None
```

No `owner_id`/`user_id` field of any kind (Section 12).

## 3.2 Illustrative route sketch — not implemented by this document

```python
@router.post(
    "",
    response_model=ReadingSummary,
    status_code=status.HTTP_201_CREATED,
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Spread not found, or Deck not found"},
        422: {"description": "Validation error"},
    },
)
def create_reading_route(
    body: ReadingCreateRequest,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> ReadingSummary:
    try:
        reading = create_reading(
            session,
            owner=current_user,
            spread_id=body.spread_id,
            deck_id=body.deck_id,
            question=body.question,
            question_domain=body.question_domain,
            draw_method=body.draw_method,
        )
    except SpreadNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Spread not found") from exc
    except DeckNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Deck not found") from exc
    return _to_summary(reading)
```

Reuses `_to_summary()` (already defined in `app/api/reading.py`, Step 24) verbatim — no new mapping helper needed.

## 3.3 Response

`201 Created`, body: `ReadingSummary` (Section 7).

---

# 4. Request-Schema Validation — Field by Field

Every client-supplied field, designed so **no invalid input can reach the model or the database as a bare `ValueError` or `IntegrityError`** — directly closing the gap `READING_CREATION_OWNERSHIP_DESIGN.md` Section 9.2 flagged (the same class of defect Step 23 found and fixed for bcrypt's password-length limit).

| Field | Validation | Mechanism | Failure mode |
|---|---|---|---|
| `spread_id` | Must be a syntactically valid UUID | Pydantic's built-in `UUID` type | `422`, automatic |
| `spread_id` | Must reference an existing `Spread` | Service-layer `session.get(Spread, spread_id)` (Section 9) | `404`, `SpreadNotFoundError` |
| `deck_id` (if supplied) | Must be a syntactically valid UUID | Pydantic's built-in `UUID` type | `422`, automatic |
| `deck_id` (if supplied) | Must reference an existing `Deck` | Service-layer `session.get(Deck, deck_id)` | `404`, `DeckNotFoundError` |
| `deck_id` (if omitted) | Resolved to the current default Deck | Service-layer `session.scalars(select(Deck).where(Deck.is_default.is_(True))).one()` | See Section 5's deployment-integrity note |
| `question` | Rejected if blank or whitespace-only **after stripping** | A `field_validator` on `ReadingCreateRequest`, mirroring `Reading.validate_question()`'s exact rule but enforced *before* the model is ever touched | `422`, clean Pydantic validation-error shape — never reaches `Reading.validate_question()`'s bare `ValueError` |
| `question` | Rejected above a maximum length | `Field(max_length=4000)` — **an implementation-safety default this document proposes, not a Product Spec requirement** (none exists — `question` is an unbounded `Text` column). 4000 characters comfortably exceeds any realistic reflection question while guarding against a pathological payload. Named explicitly as adjustable, not derived from any governing document. | `422`, automatic |
| `question_domain` | Rejected above 60 characters | `Field(max_length=60)` — **this one is not arbitrary**: it exactly matches `Reading.question_domain`'s `String(60)` column. Validating it at the schema layer, at the identical bound, prevents a real, concrete environment-inconsistency risk this audit surfaces: SQLite (dev/test) does not enforce `VARCHAR` length at all, so a too-long value would silently succeed locally and only fail — as an unhandled `IntegrityError` → likely `500` — against PostgreSQL (production). Matching the bound at the schema layer makes both environments behave identically, and turns a would-be prod-only `500` into a `422` everywhere. | `422`, automatic |
| `question_domain` | No taxonomy/enum validation | None — no canonical value list exists anywhere in this repository (Section 6, Q6 still open); any free-form string ≤60 chars is accepted, exactly matching what the column itself permits today | N/A |
| `draw_method` | Must be a valid `DrawMethod` value | Pydantic enum validation (already-existing `DrawMethod` enum) | `422`, automatic |

**No field in this table can reach the database or the model layer in a state that would raise an unhandled exception.** This is the direct, concrete answer to this task's item 4 requirement.

---

# 5. Defaults: Implementation-Safe vs. Product-Decision

| Default | Source | Classification |
|---|---|---|
| `draw_method = DrawMethod.PHYSICAL` | The model's own existing column default; Product Spec Section 8 independently describes physical as "the default and primary path" | **Safely derivable** — not invented |
| `status = ReadingStatus.DRAFTING` | The model's own existing column default; the service must not set it explicitly | **Safely derivable** — not invented |
| `question_domain = None` when omitted | The column is already nullable | **Safely derivable** |
| `deck_id` → current default `Deck` when omitted | `Deck.is_default` already exists and today's seed data maintains exactly one such row | **Implementation-safe default, not a resolved product decision.** Product Spec Q4 ("is a single hardcoded deck sufficient for MVP") remains genuinely open — this default only says "when the client doesn't specify a deck, use the one the seed script already designates as default," which requires no answer to Q4 either way and does not foreclose a future multi-deck UI (which would simply start passing `deck_id` explicitly). |
| Response shape = `ReadingSummary` | Existing schema (Step 24), reused verbatim | **Recommendation grounded in existing convention** (Section 7), not invented for convenience beyond what already exists |

**A genuine edge case worth naming, not resolved here:** if a deployment's seed data were ever missing a default Deck (`Deck.is_default.is_(True)` matching zero rows) or had more than one (the missing uniqueness constraint, Section 1), the service's `.one()` lookup would raise `NoResultFound`/`MultipleResultsFound` — a deployment/seed-data integrity failure, not a client input error. This document does not design a specific client-facing status code for it (a generic unhandled-exception `500` is the same posture this codebase already takes for any other "the deployment itself is broken" condition), since it is not reachable by any client action and inventing bespoke handling for an unreachable state would be speculative.

---

# 6. Step 25's Unresolved Questions — Re-Audited: Do They Block This Contract?

| Question | Blocks the `POST /readings` contract? | Why |
|---|---|---|
| "Reading" vs. "Reflection Session" product terminology (Product Spec Q2) | **No** | A naming/conceptual question about the Product Spec's own prose, not the schema — the schema is already committed to "Reading is the top-level persisted entity, ReflectionSession wraps it 1:1," and this contract is written against that already-implemented shape. |
| Deck scope/default (Q4) | **No** | Section 5's implementation-safe default resolves *this contract's* behavior without resolving the underlying product question. |
| question-domain taxonomy (Q6) | **No** | Section 4 validates only what the column itself already enforces (≤60 chars); no taxonomy validation is invented or required for this contract to be precise. |
| Whether `question`/`question_domain` are editable after creation | **No** | Orthogonal to creation's own contract — this endpoint only defines what happens *at* creation; an update endpoint, if ever built, is separate, future, undesigned work (Section 16 of Step 25, unchanged). |
| Exact creation response shape | **No — resolved by this document** (Section 7) | Not a genuinely open product question; a derivable API-design conclusion from existing convention. |

**Conclusion: none of Step 25's five flagged open questions block a precise, implementable contract.** This is a direct, checked finding, not an assumption — every one of Section 4/5/7's concrete specifications was reachable without needing any of them resolved.

---

# 7. Response Shape — `ReadingSummary`, Reused Verbatim

Compared directly against the actual current API conventions, not decided from convenience:

- `POST /readings/{id}/save` (Step 24) — a Reading-mutating `POST` — already returns `ReadingSummary`. Creation is structurally the same category of operation (a `POST` producing/mutating one `Reading`, returning its current representation) — reusing the identical schema is the direct, convention-consistent choice, not an invented one.
- `POST /readings/{id}/interpret` (Step 11) returns `InterpretationSummary` — a *different* resource's full representation, because interpretation's whole purpose is to hand back newly-generated content. Reading creation generates no comparable rich content (`DRAFTING`, zero draws, zero interpretations) — there is nothing a fuller representation would usefully add yet.
- **A fuller `Reading` representation (including `spread_id`/`deck_id`/`draw_method`) was considered and explicitly not recommended for this contract**, because its only plausible consumer — a future card-entry/draw-recording client — is itself explicitly out of scope and undesigned (Step 25 Section 16). Inventing those fields now, for a consumer that doesn't exist yet, would be exactly the kind of speculative addition this task's own scope rules prohibit. **If the eventual draw-recording API design finds `ReadingSummary` insufficient, extending it (or introducing a distinct `ReadingDetail`) is that future step's decision to make — named here, not made here.**

**Recommendation: `ReadingSummary`, unmodified, reused exactly as Step 24 already defined it.**

---

# 8. Transaction Behavior

Re-audited directly against `app/db/session.py::get_db()` (unchanged since Step 11; re-verified fresh in Step 25 and again here — not modified by this document, per this task's explicit instruction).

- **When flushed:** the service (Section 9) calls `session.add()` + `session.flush()` once after constructing the `ReflectionSession`, and again after constructing the `Reading` — matching every existing mutator's convention in this codebase (`register_user()`, `add_card_draw()`, `mark_saved()`: flush, never commit).
- **When committed:** never inside the service or the route — `get_db()`'s single `db.commit()` at the end of a successful request is the sole commit point, exactly as every other route already relies on.
- **Rollback on validation failure:** a `SpreadNotFoundError`/`DeckNotFoundError` raised by the service happens **before** either row is constructed (Section 9's lookup-first ordering) — nothing has been added to the session yet, so there is nothing to roll back; `get_db()`'s `except Exception: db.rollback()` still fires harmlessly on the propagated `HTTPException`, identical to every existing error path.
- **Rollback on database failure:** if a genuine `IntegrityError` occurred after both objects were added but before commit (not expected in the ordinary case, since Section 4's validation already prevents every client-reachable cause), `get_db()`'s existing rollback-on-exception undoes both the `ReflectionSession` and the `Reading` together — no new mechanism required.
- **Route vs. service persistence:** the route **must not** call `session.add()`/`session.flush()` itself — it only resolves `current_user` and calls the service, exactly mirroring `app/api/auth.py::register_route()`'s existing discipline (the route never touches the session directly beyond passing it through).

---

# 9. Creation Service Boundary — `create_reading()`

New file: `app/services/reading_service.py` (does not exist today — confirmed by direct repository search, Step 25 Section 2). One function, mirroring `app/services/auth_service.py::register_user()`'s exact shape.

```python
def create_reading(
    session: Session,
    *,
    owner: User,
    spread_id: UUID,
    deck_id: UUID | None,
    question: str,
    question_domain: str | None,
    draw_method: DrawMethod,
) -> Reading:
    spread = session.get(Spread, spread_id)
    if spread is None:
        raise SpreadNotFoundError(f"spread {spread_id} does not exist")

    if deck_id is not None:
        deck = session.get(Deck, deck_id)
        if deck is None:
            raise DeckNotFoundError(f"deck {deck_id} does not exist")
    else:
        deck = session.scalars(select(Deck).where(Deck.is_default.is_(True))).one()

    reflection_session = ReflectionSession(owner=owner)
    session.add(reflection_session)
    session.flush()

    reading = Reading(
        reflection_session=reflection_session,
        spread=spread,
        deck=deck,
        question=question,
        question_domain=question_domain,
        draw_method=draw_method,
    )
    session.add(reading)
    session.flush()
    return reading
```

- **Inputs:** an already-authenticated `owner: User` (non-optional — Section 12), an already-Pydantic-validated `spread_id`/`deck_id`/`question`/`question_domain`/`draw_method`. The service does **not** re-validate `question`'s blankness or length — that is the request schema's job (Section 4); the service's own validation responsibility is strictly *existence* (`spread_id`, `deck_id`), which only a database lookup can answer.
- **Outputs:** the newly-constructed, flushed (not committed) `Reading` ORM object.
- **Validation responsibilities:** existence of `spread_id`/`deck_id` only.
- **Transaction responsibilities:** flush after each construction step, never commit — identical to Section 8.
- **New domain errors** (added to the existing `app/models/exceptions.py`, alongside `EmailAlreadyRegisteredError`/`InvalidCredentialsError`/etc. — the established single location for every domain error in this codebase, regardless of which service raises it): `SpreadNotFoundError(ValueError)`, `DeckNotFoundError(ValueError)`.

**Not created by this document**, per this task's explicit scope rule.

---

# 10. Spread/Deck: Must Already Exist — Reconfirmed, No Alternative Designed

Directly re-auditing this task's explicit instruction to reject any design that creates them inline or accepts names instead of IDs:

- **By ID only** (Section 9's `session.get(Spread, spread_id)` / `session.get(Deck, deck_id)`) — both are the actual FK columns `Reading` requires; no name-based lookup is designed anywhere in this contract.
- **Never created by this route.** `create_reading()` (Section 9) never constructs a `Spread`, `SpreadPosition`, or `Deck` — only looks them up. This is a hard design boundary, not merely a preference: Spreads and Decks are pre-authored reference data (`app/seed/seed.py`, Step 25 Section 6.2), seeded independently of any user-facing action, exactly like `Card`. Nothing in this contract, if implemented exactly as specified, could ever create a `Spread` or `Deck` row.

---

# 11. Lifecycle State on Creation

- **Exact initial status: `ReadingStatus.DRAFTING`.** Not set explicitly by `create_reading()` — it is the model's own column default (Section 1), consistent with `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 8's transition matrix row `(none) → Reading created → DRAFTING`.
- **Can creation ever produce `SPREAD_COMPLETE`?** **No, by construction** — `create_reading()` never calls `Reading.add_card_draw()` and never evaluates `is_spread_complete`; a newly created Reading always has zero `CardDraw` rows. The one theoretical exception named (not re-decided) by `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 14 — a Spread with zero required positions, which would make `is_spread_complete` vacuously `True` — remains purely theoretical (no such Spread exists in this repository's reference data, Section 1) and is, in any case, irrelevant to *this* contract, since nothing in `create_reading()` ever reads `is_spread_complete` at all.

---

# 12. Ownership Isolation — Cannot Be Created Without an Owner

- `create_reading()`'s `owner: User` parameter is **non-optional** (no default, not `User | None`) — a structural, type-level guard against ever constructing an owner-less `ReflectionSession` from this code path.
- The route's only source for `owner` is `Depends(get_current_user)`, which itself either returns a real, resolved, active `User` or raises `401` before the route body executes at all (unchanged since Step 22, re-verified Step 23).
- **No request field can substitute for or override this** (Section 3.1's schema has no owner-shaped field at all) — the client cannot supply, spoof, or omit ownership; it is derived exclusively from the authenticated session, exactly matching the same rule already governing every other authenticated mutation in this codebase (Save, Steps 22–24).
- **Net result: it is structurally impossible for this contract, implemented as specified, to ever produce a `Reading` whose `ReflectionSession.owner_id` is `NULL`.** (Existing, pre-production-path `owner_id IS NULL` rows remain possible only via direct test/database manipulation — Step 22's already-accepted, already-tested "fails closed for everyone" behavior, unchanged and not reachable through this new route.)

---

# 13. Test Plan (Not Implemented)

Mirrors this project's established fixture conventions (self-contained `client`/`api_seeded_session`, per `tests/test_api_reading.py`'s own Step 24 precedent).

1. Authenticated user creates a Reading with a valid `spread_id` → `201`; response is `ReadingSummary`-shaped; `status == "drafting"`.
2. Unauthenticated creation request → `401`; no row of any kind persisted.
3. Nonexistent `spread_id` (well-formed UUID, no matching row) → `404`; no row persisted.
4. Nonexistent `deck_id` (explicitly supplied, well-formed UUID, no matching row) → `404`; no row persisted.
5. Blank `question` (`""`) → `422`.
6. Whitespace-only `question` (`"   "`) → `422`.
7. Over-limit `question` (> 4000 characters) → `422`.
8. Over-limit `question_domain` (> 60 characters) → `422`.
9. Malformed `spread_id` (not a valid UUID string) → `422`.
10. Created `Reading.reflection_session.owner_id` equals the authenticated user's `id` — the core ownership-propagation proof.
11. A request body containing an extraneous `owner_id`/`user_id` field has no effect — the created Reading's owner is always the authenticated caller.
12. Initial lifecycle status is exactly `DRAFTING`, confirmed both via the API response and a direct DB read.
13. A forced failure between the two service-level flushes (e.g., monkeypatching the `Reading` construction step to raise) leaves **neither** a `ReflectionSession` **nor** a `Reading` row behind after the request — the atomicity proof.
14. Two distinct authenticated users each create a Reading; each can access only their own afterward via the existing `get_owned_reading`-gated routes (reusing `tests/test_ownership.py`'s established two-user pattern) — ownership isolation.
15. Omitting `deck_id` resolves to the seeded default Deck.
16. Omitting `question_domain` stores `None`.

---

# 14. Hidden-Assumption Search

Directly searched for anything this repository's existing code or tests assume that introducing the *first* production Reading/ReflectionSession creation path could disturb.

- **`get_owned_reading`'s `None`-owner handling** (`reading.reflection_session.owner_id != current_user.id`) already fails closed for a `None` `owner_id` against every user (Step 22/23, re-verified) — a newly-created, always-owned production Reading does not change or depend on this; no regression risk.
- **`Deck.is_default` lookup pattern** (`tests/interpretation_helpers.py::get_default_deck()`) already assumes exactly one `is_default=True` row via `.one()` — the proposed service's own default-deck resolution (Section 9) uses the identical pattern and inherits the identical (pre-existing, not newly introduced) assumption; not a new risk this feature creates.
- **`reading_orchestration.interpret_reading()`** already correctly rejects a `DRAFTING`, zero-draw Reading with `ReadingNotReadyForInterpretationError` → `409` — a freshly created Reading hitting `POST .../interpret` immediately behaves exactly as this existing, already-tested guard expects; no hidden incompatibility.
- **No test anywhere assumes it is the only Reading/User in the database** in a way a real, production-created row would violate — every existing test builds its own isolated in-memory database per test run (Step 22's `StaticPool` convention); production Reading creation is orthogonal to test isolation.
- **No global uniqueness constraint is at risk** — each new `ReflectionSession` gets its own UUID; `Reading.reflection_session_id`'s `unique=True` is satisfied trivially by construction (one `Reading` per newly-created `ReflectionSession`).
- **No code path anywhere queries `Reading`/`ReflectionSession` without an ownership or explicit-ID filter** that this new, real data could now leak through — every existing Reading-facing route is already ownership-gated (`get_owned_reading`) or explicitly scoped (`GET /readings`'s `owner_id` filter, Step 24); introducing real, owned rows does not create a new exposure surface.

**No hidden assumption was found that this feature would violate.**

---

# 15. Contradiction Check

Checked directly against every document this task names:

- `PRODUCT_DECISIONS.md` — Q2/Q3/Q6 (status transitions) are unaffected; this contract never sets `SPREAD_COMPLETE`, `INTERPRETED`, or `SAVED` (Section 11). No contradiction.
- `READING_CREATION_OWNERSHIP_DESIGN.md` (Step 25) — every recommendation in that document is followed exactly (ownership placement, service-not-model-method boundary, Spread-by-ID-only, no schema change, `POST /readings` route path). No contradiction; this document is its direct, planned continuation.
- `AUTHENTICATION_OWNERSHIP_DESIGN.md` / `AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` — ownership mechanism, dependency shapes, and 404-not-403 posture are all reused unmodified. No contradiction.
- `SAVE_READING_DESIGN.md` — unaffected; this contract does not touch `mark_saved()` or Reading History's own semantics. No contradiction.
- `READING_LIFECYCLE_DESIGN.md` / `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` — the `(none) → DRAFTING` transition row is honored exactly, and Section 10 of the latter's own "no route exists, none designed here" boundary is the one this document now fills, without altering anything that document already decided (`add_card_draw()`'s own design is untouched — Section 16 of Step 25, reaffirmed).
- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` / `RAIDIAN_WISE_ARCHITECTURE_V1.md` / ADR-0003/0004/0005 — Section 6's table shows every genuinely open Product Spec question preserved, not resolved; the service boundary (Section 9) remains deliberately narrower than `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2's larger `reading_service.py`/`draw_service.py` sketch, exactly as Step 25 already concluded it should be.

**No contradiction found with any listed document.**

---

# 16. Recommended Implementation Sequence

1. Add `SpreadNotFoundError`, `DeckNotFoundError` to `app/models/exceptions.py`.
2. Add `ReadingCreateRequest` to `app/schemas/reading_api.py` (Section 3.1/4).
3. Add `create_reading()` to a new `app/services/reading_service.py` (Section 9).
4. Wire `POST /readings` in the existing `app/api/reading.py` (Section 3.2).
5. Add the tests named in Section 13.
6. Run the full existing suite to confirm no regression, exactly as every prior implementation step in this series has.

No step in this sequence is authorized by this document.

---

## Related Documents

- `READING_CREATION_OWNERSHIP_DESIGN.md` (Step 25) — the architectural conclusions this document turns into an exact contract without reopening any of them.
- `AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` (Step 21) — the `get_current_user`/`get_owned_reading` dependency shapes reused unmodified.
- `SAVE_READING_DESIGN.md` (Step 17), `READING_HISTORY_OWNERSHIP_DESIGN.md` (Step 19) — the `ReadingSummary`/API-boundary precedents this document's Section 7 reasons from.
- `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` (Step 15) — the `add_card_draw()`/`SPREAD_COMPLETE` design this document's Section 11 confirms is unaffected.
- `PRODUCT_DECISIONS.md` (Step 14) — Q2/Q3/Q6, reconfirmed unaffected.
- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Section 3.2 (Q2), 5, 6, 7.5, 8, the source of every still-open product question named in Section 6.
- `app/models/reading.py`, `app/models/reflection_session.py`, `app/models/spread.py`, `app/models/deck.py`, `app/db/session.py`, `app/api/reading.py`, `app/api/dependencies.py`, `app/schemas/reading_api.py`, `app/services/auth_service.py` — the actual, current code every finding and contract detail in this document was checked against.
