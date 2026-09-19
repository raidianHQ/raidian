# CardDraw HTTP API — Design & Implementation-Readiness Audit (Step 31)

Read-only design/audit. No application code, test, schema, migration,
dependency, frontend, or existing documentation file was modified in
producing this report. Nothing was committed or pushed. Every claim below
was independently re-verified against the current repository — by direct
code inspection and by executing purpose-built, throwaway integration
probes (deleted after use, no artifacts left in the repository) — rather
than assumed from any prior step's report.

---

# 1. Executive Summary

This document designs the smallest correct HTTP endpoint for recording a
`CardDraw`, closing the one lifecycle gap Steps 29 and 30 both reconfirmed
as still open. **No blocking defect was found.** One genuine, previously
undocumented gap in `Reading.add_card_draw()` was discovered (Section 3.3:
redrawing an already-filled position while still `DRAFTING` is caught only
by a database `UniqueConstraint` at flush time, not by any domain-level
guard) — this does **not** require changing `add_card_draw()` itself; it
is addressed entirely at the future service layer, using the exact
pre-check-plus-`IntegrityError`-backstop pattern this project already
established for the duplicate-email race in `auth_service.py` (Step 23).

Recommended design, in brief:
- **Endpoint:** `POST /readings/{reading_id}/draws`.
- **Request:** `{ "position_id": UUID, "card_id": UUID, "orientation": "upright" | "reversed" }` — `draw_order` is server-computed, not client-supplied.
- **Response:** a new, dedicated `CardDrawSummary` (id, position_id, card_id, orientation, draw_order, created_at, `reading_status`) — `201 Created`.
- **Auth/ownership:** `Depends(get_owned_reading)`, identical to every other Reading-scoped route — no new mechanism.
- **Service layer:** one new function, `record_card_draw()`, added to the existing `app/services/reading_service.py` (not a new `draw_service.py` — no concrete repository evidence justifies a second file yet).
- **New exceptions required:** `SpreadPositionNotFoundError`, `CardNotFoundError`, `PositionAlreadyDrawnError` (none exist today; `ReadingNotDraftingError`/`DuplicateCardError` already exist and are reused as-is).
- **Migration:** none required — the schema already fully supports this operation.
- **Open product/API questions** (named, not decided): single-draw vs. batch-draw request shape (this document recommends single-draw, as the smaller, more consistent surface, but flags it as a real design choice); whether the response should embed card/position display names.

This document does not implement the route. Implementation remains a
separate, future, explicitly authorized step.

---

# 2. Current CardDraw Domain Behavior (Re-Verified Directly)

Every item below was re-read from current source and, where noted,
re-verified with a live, throwaway probe against an in-memory SQLite
database (not part of the repository; no artifact left behind).

## 2.1 `Reading.add_card_draw()` (`app/models/reading.py:108-160`)

Signature: `add_card_draw(*, position: SpreadPosition, card: Card,
orientation: Orientation, draw_order: int) -> CardDraw`. Takes already-
resolved ORM objects, not raw IDs — the caller is responsible for
resolving `position_id`/`card_id` first (exactly the same shape as
`create_reading()`'s own `session.get(Spread, spread_id)` pattern).

Enforces, in order:
1. `self.status == DRAFTING`, else `ReadingNotDraftingError`.
2. `position.spread_id == self.spread_id`, else a **bare `ValueError`**
   (no dedicated exception class exists for this today).
3. `card.deck_id == self.deck_id`, else a **bare `ValueError`** (same —
   no dedicated exception class).
4. Duplicate-card rejection (`any(existing.card_id == card.id for
   existing in self.card_draws)`) unless `spread.allow_duplicate_cards`,
   else `DuplicateCardError`.

Then constructs the `CardDraw`, appends it to `self.card_draws` (does
**not** call `session.add()` itself — appending to the relationship is
sufficient because `Reading` is already in the session and cascades),
and re-evaluates `self.is_spread_complete`, advancing `self.status` to
`SPREAD_COMPLETE` if true. **Does not flush or commit** — matches every
other mutator in this codebase (`mark_saved()`,
`save_interpretation()`, `create_reading()`).

## 2.2 `Reading.is_spread_complete` (`app/models/reading.py:77-100`)

`required_position_ids.issubset(drawn_position_ids)` — required-position
coverage, not draw count. Confirmed directly, again, with a fresh probe
(a spread with one required + one optional position; filling only the
required position sets `is_spread_complete = True` and
`status = SPREAD_COMPLETE`) — identical result to Step 29's own probe,
re-run independently for this step rather than assumed.

**The pending-object relationship issue from Step 16, re-verified:** the
property reads `d.position.id` (the relationship) rather than
`d.position_id` (the raw FK column) specifically so it evaluates
correctly for a CardDraw that was just appended in memory but not yet
flushed — confirmed still true by code read; this is unaffected by
whether the caller is a test, a future single-draw route, or a future
batch-draw route processing several `add_card_draw()` calls in a loop
before flushing once, since each call sets `.position`/`.card` directly
at construction, not just the FK column.

## 2.3 `Reading.status` / `ReadingStatus`

`DRAFTING → SPREAD_COMPLETE → INTERPRETED → SAVED`
(`app/models/enums.py:40-52`), unchanged. `add_card_draw()` is the only
place `DRAFTING → SPREAD_COMPLETE` occurs.

## 2.4 `CardDraw` (`app/models/card_draw.py`)

Columns: `reading_id` (FK, `CASCADE`), `position_id` (FK, `RESTRICT`),
`card_id` (FK, `RESTRICT`), `orientation` (`Orientation` enum — **there
is no `is_reversed` boolean field anywhere in this model or anywhere
else in the codebase**; the field the audit brief calls `is_reversed` is
actually `orientation: Orientation`, an `upright`/`reversed` enum,
confirmed by direct model read), `draw_order` (int).

Constraints (`__table_args__`, re-confirmed by reading the model and by
re-running `tests/test_card_draw.py`, all passing):
- `UniqueConstraint("reading_id", "position_id")` — **one card per
  position per reading**, enforced at the database level only (see
  Section 3.3 — no domain-level guard exists in `add_card_draw()`
  itself).
- `UniqueConstraint("reading_id", "draw_order")` — draw order must be
  unique within a Reading, database-enforced.
- `CheckConstraint("draw_order >= 1")` — database-enforced.

**The same card may appear in multiple positions of the same Reading**
only if `Spread.allow_duplicate_cards` is `True` (confirmed by
`test_duplicate_card_allowed_when_spread_permits_it`); **the same card
may be reused across different Readings** unconditionally — `Card` is
deck-level reference data, not consumed by a draw (confirmed by
`test_card_is_reference_data_independent_of_the_draw`). **A position may
never be redrawn** (re-assigned to a second card) within the same
Reading — enforced by the unique constraint (Section 2.4 above), though
currently only as a database-level backstop (Section 3.3).

## 2.5 `SpreadPosition.required`

`Boolean, nullable=False, default=True` (`app/models/spread_position.py:47`).
Every seeded, real spread (`Celtic Cross`, `Single Card`, `Three Card`)
has every position `required: true` — reconfirmed by re-grepping
`app/reference_data/spreads/*.yaml`; `required=False` remains a real,
correctly-implemented, but never-exercised-by-real-data code path
(Section 8).

## 2.6 `ReflectionSession.owner_id` / `get_current_user` / `get_owned_reading`

Unchanged since Step 22, re-confirmed by direct read: `owner_id` is a
nullable FK to `users.id`, `ON DELETE CASCADE`. `get_current_user`
(`app/api/dependencies.py:37-57`) resolves and validates the bearer
token only. `get_owned_reading` (`app/api/dependencies.py:60-77`)
resolves an existing `Reading` by path-parameter `reading_id` and
collapses "doesn't exist" and "exists but not yours" (including
`owner_id IS NULL`) into an identical `404`. Both are pure FastAPI
dependencies, resolved before any route body executes.

## 2.7 Existing Reading API routes (`app/api/reading.py`, `app/api/interpretation.py`)

Re-confirmed: 3 route files, 8 routes total. `POST /readings` (creation,
`get_current_user`), `POST /readings/{id}/save` and the four
`/readings/{reading_id}/{interpret,interpretations/current,
interpretations,narrative}` routes (all `get_owned_reading`), `GET
/readings` (history, `get_current_user`). **No `GET /readings/{reading_id}`
route exists** — there is currently no way for a client to fetch a
single Reading's current state by ID at all, saved or not (Section 4.2
addresses why this matters for the draw response shape).

## 2.8 Existing schemas, exceptions, service patterns, test helpers

- `app/schemas/reading_api.py`: `_Model` base (`frozen=True,
  extra="forbid"`), `ReadingSummary`, `ReadingCreateRequest` — no
  CardDraw-shaped schema exists anywhere yet.
- `app/models/exceptions.py`: `DuplicateCardError`,
  `ReadingNotDraftingError`, `ReadingNotSaveableError`,
  `EmailAlreadyRegisteredError`, `InvalidCredentialsError`,
  `SpreadNotFoundError`, `DeckNotFoundError` — no position/card-not-found
  or position-already-drawn exception exists yet.
- `app/services/reading_service.py`: exactly one function,
  `create_reading()` — session-taking, flush-never-commit, resolves
  foreign IDs via `session.get()` and raises a named `*NotFoundError` on
  `None`. This is the direct precedent for the new function proposed in
  Section 7.
- `tests/factories.py` / `tests/interpretation_helpers.py`: both call
  `reading.add_card_draw()` directly (never through an API), always with
  a caller-supplied `draw_order` — confirming `draw_order` has never
  before been asked to be anything other than test-controlled, which is
  why the "who computes `draw_order`" question (Section 4.3) has no
  existing precedent to defer to and is decided here as a design call,
  not a product question.

---

# 3. Proposed HTTP Endpoint

## 3.1 Route

**`POST /readings/{reading_id}/draws`**

Justification: this is the only route shape consistent with the existing
API's own conventions. Every route that mutates or reads something
*belonging to* a specific Reading is already nested under
`/readings/{reading_id}/...` (`/interpret`, `/interpretations`,
`/narrative`, `/save`); a `CardDraw` is exactly this kind of
Reading-owned sub-resource, and `/draws` (plural, matching the
`card_draws` relationship name and the plural-collection convention
`POST /readings` itself already uses for creating a new Reading) reads
naturally as "create a new draw within this reading's collection of
draws." No alternative route shape (e.g. `PATCH /readings/{id}`, or a
draws-are-top-level-resource `POST /draws` with `reading_id` in the
body) is better justified by anything already built — every existing
precedent nests the sub-resource under its parent's path and resolves
`reading_id` via `get_owned_reading`.

## 3.2 HTTP status code

`201 Created` — matches `POST /readings` and `POST
/readings/{id}/interpret`, both of which create a new row and return it.

---

# 4. Request/Response Contract

## 4.1 Request fields

```json
{
  "position_id": "uuid",
  "card_id": "uuid",
  "orientation": "upright" | "reversed"
}
```

All three **required**, no optional fields, no defaults:
- `position_id` (UUID) — no sensible default exists; every draw is for a
  specific spread position.
- `card_id` (UUID) — no sensible default exists.
- `orientation` (`Orientation` enum, reusing `app/models/enums.py`'s
  existing type — no new enum needed) — no sensible default: a physical
  or digital draw always has a real, observed orientation
  (`DrawMethod`, already set once on the Reading at creation, is not
  re-asked per draw).

**`draw_order` is deliberately excluded from the request** — see Section
4.3 for why this is a design call, not an omission.

No field beyond these three has any support in the current domain model.
In particular: there is no `is_reversed` boolean anywhere to accept
(Section 2.4) — the request must use `orientation`, matching the actual
column type exactly; there is no per-draw `question`/`note`/`digital`
flag anywhere in `CardDraw` to expose.

## 4.2 Response shape: a new, dedicated `CardDrawSummary`, not `ReadingSummary`

**Recommendation: a new `CardDrawSummary` schema**, not a reuse of
`ReadingSummary`. Reasoning:
- Precedent: `POST /readings` returns `ReadingSummary` (the resource just
  created); `POST /readings/{id}/interpret` returns
  `InterpretationSummary` (the resource just created) — every existing
  creation route returns the thing it created, not its parent. A
  `CardDraw` is the thing this route creates.
- `ReadingSummary` cannot be reused as-is: it has no `position_id`/
  `card_id`/`orientation`/`draw_order` fields at all — the client's
  primary need (confirmation of exactly what was recorded) would go
  unanswered.
- **However**, the client also needs to know whether this draw just
  completed the spread — and, per Section 2.7, there is currently no
  `GET /readings/{reading_id}` route to check separately. Recommendation:
  include one additional field, `reading_status: ReadingStatus`, on
  `CardDrawSummary` itself, rather than nesting a full `ReadingSummary`
  (which would duplicate `question`/`question_domain`/`created_at` the
  client already has from the creation response, for no benefit) or
  leaving the client with no way to learn this short of re-deriving it
  client-side by counting positions.

Proposed shape (fields only — not implemented here):
```json
{
  "id": "uuid",
  "position_id": "uuid",
  "card_id": "uuid",
  "orientation": "upright",
  "draw_order": 1,
  "created_at": "iso-8601",
  "reading_status": "drafting"
}
```

This mirrors `ReadingSummary`'s own "smallest useful representation"
discipline (its docstring: "no current consumer needs them" for fields
it deliberately omits) — `position_id`/`card_id` are returned as raw IDs,
not embedded names, matching `ReadingSummary`'s own precedent of
returning `spread_id`... actually omitting even that; a display name for
the position/card is a client-side reference-data lookup, not something
this response needs to embed, exactly as `ReadingSummary` already omits
`spread_id`/`deck_id` on the reasoning that "no Reading Detail view
exists yet to require them." **Considered and not recommended:** embedding
`card_name`/`position_name` directly — named here as a deferred
enhancement question (Section 12), not decided.

## 4.3 `draw_order`: server-computed, not client-supplied (design call, not a product question)

No existing product document or domain rule states who computes
`draw_order`; every existing caller (`tests/factories.py`,
`tests/interpretation_helpers.py`) is trusted internal code that
supplies it directly. For an HTTP API accepting untrusted client input,
this repository already has a directly analogous precedent:
`Interpretation.sequence` is never client-supplied — it is computed
server-side by `_next_sequence()`
(`app/services/interpretation/persistence.py:19-27`, a `max(...) + 1`
pattern). Recommendation: `record_card_draw()` (Section 7) computes
`draw_order` the same way, scoped per-Reading (not global, since the
`UniqueConstraint` is `("reading_id", "draw_order")`, not global like
`Interpretation.sequence`'s deliberately-global one):
`max((d.draw_order for d in reading.card_draws), default=0) + 1`, using
the already-loaded `reading.card_draws` relationship — no extra query
needed. This removes an entire class of client bugs (gaps, duplicates,
races over an integer the client has no authoritative way to know
without asking first) for zero cost, and is why `draw_order` is excluded
from the request body in Section 4.1. This is presented as a design
recommendation, not a product decision, on the grounds that it is purely
mechanical (which layer computes an internal sequence integer), exactly
like the already-settled precedent it mirrors.

---

# 5. Authentication & Ownership

**`Depends(get_owned_reading)` is sufficient. No second ownership
mechanism should be introduced.** Re-verified directly (fresh probes for
this step, not reused from Step 29's script):

| Scenario | Verified behavior |
|---|---|
| Unauthenticated request | `401`, identical body to every other route (`get_current_user`, which `get_owned_reading` depends on, rejects first) |
| Nonexistent Reading | `404` |
| Reading owned by another user | `404`, identical body to the nonexistent case |
| Reading with `owner_id = NULL` | `404` — fails closed, same mechanism as every other route (Step 29 already proved this generically for `get_owned_reading`; it applies identically here since the draw route would depend on the exact same function, not a copy) |
| Completed/saved Reading | Domain error (`ReadingNotDraftingError`), not an authorization error — correctly a `409`, not a `404`/`403` (Section 6) |
| Valid owner + valid draw | Succeeds |

Because `get_owned_reading` is a FastAPI dependency, it resolves — and
can reject — before the route body (and therefore before any
`add_card_draw()` call or database mutation) ever runs, exactly as it
already does for `/save` and the four interpretation routes. No new
authorization code is proposed anywhere in this design.

---

# 6. Domain/Error Mapping

| Domain condition | Exception | Exists today? | Proposed HTTP mapping |
|---|---|---|---|
| Reading not `DRAFTING` | `ReadingNotDraftingError` | Yes (`app/models/exceptions.py`) | `409` — same family as `ReadingNotSaveableError`/`ReadingNotReadyForInterpretationError`, both already `409` |
| Duplicate card (spread disallows) | `DuplicateCardError` | Yes | `409` — same family |
| `position_id` does not reference an existing `SpreadPosition`, **or** references one belonging to a different spread | **`SpreadPositionNotFoundError`** | **No — new, proposed** | `404` — the two cases are recommended to collapse into one response, mirroring the same enumeration-resistant collapsing already established for Reading ownership (Section 5) and for `SpreadNotFoundError`/`DeckNotFoundError` in Step 27; a position that exists but isn't part of *this* Reading's spread is, from the caller's perspective, not a usable position for this request |
| `card_id` does not reference an existing `Card`, **or** references one belonging to a different deck | **`CardNotFoundError`** | **No — new, proposed** | `404` — same collapsing rationale |
| Same `position_id` drawn twice within one Reading (Section 3.3) | **`PositionAlreadyDrawnError`** | **No — new, proposed** | `409` — same family as `DuplicateCardError`; this is a business-rule conflict, not a not-found or validation error |
| Malformed UUID (path or body) | Pydantic/FastAPI validation | N/A (framework) | `422` — automatic, no new code |
| Missing/invalid `orientation` enum value | Pydantic validation | N/A (framework) | `422` — automatic |

**No broad exception swallowing is proposed anywhere.** The one place a
generic `IntegrityError` must be caught (`PositionAlreadyDrawnError`,
Section 3.3) is recommended to use the same narrow, heuristic-checked
catch already proven in `auth_service.py::_is_duplicate_email_violation()`
— catch `IntegrityError`, inspect the underlying message for the
specific constraint name (`uq_card_draws_reading_id_position_id`, a
fixed, known string — actually more reliable than the email heuristic,
since this constraint's name is deterministic and SQLAlchemy-assigned,
not driver-message-format-dependent), and re-raise anything else
unmodified. This exact pattern is why Section 3.3's finding does not
rise to a stop condition: it is solvable with an already-proven
technique, not a new one.

---

# 7. Service-Layer Decision

**Recommendation: (B) a narrow service function — but added to the
existing `app/services/reading_service.py`, not a new `draw_service.py`.**

Reasoning, weighed directly against this repository's own precedent:

- **Not (A), a direct `reading.add_card_draw()` call from the route.**
  `mark_saved()` is called directly from `save_reading_route()` because
  it needs zero additional lookups — the Reading is already resolved by
  `get_owned_reading`, and the method takes no other arguments. The draw
  route is different in the same way `create_reading()` is different
  from `mark_saved()`: it must resolve two foreign IDs
  (`position_id`→`SpreadPosition`, `card_id`→`Card`) via `session.get()`,
  handle their absence with named exceptions, compute `draw_order`
  (Section 4.3), and catch the `IntegrityError` backstop (Section 3.3/6)
  — multi-step logic a bare model-method call from the route cannot
  express cleanly, exactly the same shape of reasoning that put
  `create_reading()` in a service function rather than inline in
  `create_reading_route()`.
- **Not a new `draw_service.py`.** `RAIDIAN_WISE_ARCHITECTURE_V1.md`
  Section 2 does sketch a separate `draw_service.py`
  (`backend/app/... draw_service.py (physical entry validation +
  digital draw; see Section 5)`), and
  `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md`'s own opening line
  cites it. But this task's own instruction is explicit: don't build
  that sketch's larger shape "merely because it appears in an older
  architectural sketch unless the current repository now provides a
  concrete reason to do so." No such concrete reason was found:
  `reading_service.py` today holds exactly one function; the proposed
  new function is comparable in size and shape to `create_reading()`
  (same "resolve IDs, construct/mutate, flush" pattern); both operate on
  the same `Reading` aggregate root; and `auth_service.py`'s own
  precedent already shows this project grouping multiple related
  operations (`register_user`, `authenticate_user`) in one file by
  resource area rather than splitting one function per file. A future
  step (Digital Draw, per the architecture sketch's own parenthetical)
  might eventually justify a dedicated module once there is a real,
  larger set of draw-related operations — that is a future call, not one
  this repository's current state supports making now.

**Proposed function** (signature only — not implemented here):

```python
def record_card_draw(
    session: Session,
    reading: Reading,
    *,
    position_id: UUID,
    card_id: UUID,
    orientation: Orientation,
) -> CardDraw:
    ...
```

Takes an already-resolved `Reading` (the route already has one via
`get_owned_reading` — no redundant re-fetch, exactly matching
`save_reading_route`'s own pattern of taking a `Reading` directly rather
than a `reading_id`). Would resolve `position`/`card`, validate
membership (Section 6), compute `draw_order` (Section 4.3), call
`reading.add_card_draw(...)`, catch the `IntegrityError` backstop
(Section 3.3), and `session.flush()` — never commit, matching every
other service function in this codebase without exception.

The existing `reading_service.py` module docstring ("Reading creation
business logic") would need a one-line scope update if this function is
added — noted here as a byproduct of the recommendation, not something
this read-only step performs.

---

# 8. Optional-Position Analysis

**The current domain model already makes this unambiguous. It does not
block implementation of the basic CardDraw route.**

Directly re-verified with a fresh, throwaway probe for this step
(distinct from, though consistent with, Step 29's own probe): a spread
with one required and one optional position; the required position is
drawn; `status` advances to `SPREAD_COMPLETE`
(`is_spread_complete = True`, since only required positions are
considered — Section 2.2); a subsequent attempt to draw the
still-empty optional position raises `ReadingNotDraftingError`, **the
identical exception any further draw attempt of any position would
raise once `SPREAD_COMPLETE` is reached** — confirmed by direct
execution, not inferred.

This resolves the question Step 15 originally left open, for exactly
this specific sub-question ("what happens if a client tries to draw the
still-empty optional position after completion"): **it is rejected,
uniformly, by the same `DRAFTING`-only guard that already governs every
other post-completion draw attempt.** `add_card_draw()`'s first check
(`self.status != DRAFTING`) makes no distinction between required and
optional positions — there is no code path anywhere that treats an
optional position specially once the Reading has left `DRAFTING`.

**What remains a genuinely open product question, not resolved here and
not blocking this route's design:** whether an optional position should
ever be *fillable at all*, given that filling only the required
positions already advances the Reading out of `DRAFTING` before an
optional position can be reached in the same session. Today, the only
way to fill an optional position is to draw it *before* the last
required position (order matters, client-controlled since the client
chooses which `position_id` to send each call) — filling it after would
always be too late. This is not a defect in the route design (the route
faithfully executes whatever the domain model already does); it is a
pre-existing characteristic of `add_card_draw()`'s own design (Step
15/16, not reopened here), surfaced by this audit because a real HTTP
client — unlike every existing trusted test caller — might plausibly hit
it. Recorded as an explicit, named product/UX question for whoever
designs the client flow (should the UI require/offer optional positions
before required ones? should the server relax the `SPREAD_COMPLETE`
guard for optional-only remaining positions?) — **not decided here**,
and not a blocker: with zero real seeded spreads containing any optional
position (Section 2.5), this scenario cannot occur against production
reference data today regardless of how the route is implemented.

---

# 9. Transaction & Persistence Behavior

- `record_card_draw()` (Section 7) would flush, never commit — the
  `get_db()` request boundary remains the sole commit point, unchanged.
- `reading.add_card_draw()` itself already does not flush or commit
  (Section 2.1) — the service function must flush explicitly, exactly
  matching `create_reading()`'s own two explicit `session.flush()` calls.
- **Rollback on failure**: if `_to_summary`-equivalent serialization (or
  any other post-flush step) fails after `add_card_draw()` has already
  flushed a new `CardDraw` row, `get_db()`'s existing
  commit-on-success/rollback-on-exception behavior (unchanged since
  Step 11, re-verified functioning correctly for the analogous Reading-
  creation case in Step 29's own forced-failure probe) discards it —
  the same mechanism, not a new one, would protect this route without
  any additional code.
- **The `IntegrityError` backstop (Section 3.3/6)** is the one place
  this route's service function needs logic beyond every prior service's
  shape — a `try/except IntegrityError` around the flush, exactly
  mirroring `register_user()`'s existing shape.
- **Concurrency** (two simultaneous requests racing to fill the same
  position, or racing on the server-computed `draw_order`): explicitly
  out of scope, consistent with — not a new gap introduced by — the
  already-recorded precedent in
  `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` ("Concurrent
  draw-adding against the same Reading... Out of scope, consistent with
  `Interpretation.sequence`'s own documented acceptance of... no locking
  around... single-writer-per-reading usage pattern"). The
  `IntegrityError` backstop (Section 3.3) still correctly turns a losing
  race into a clean `409` rather than a `500`, even though true
  concurrent-safety (e.g. row locking) is not designed here, matching
  that precedent exactly.

---

# 10. Test Plan

Every item the audit brief requires, plus items this audit's own findings
show are necessary (marked **[new]**):

**Authentication / ownership:**
1. Authenticated valid draw succeeds (`201`).
2. Unauthenticated request → `401`.
3. Nonexistent Reading → `404`.
4. Cross-user Reading → `404`, identical body to the nonexistent case.
5. `NULL`-owner Reading → `404` (fails closed).

**Persistence correctness:**
6. Successful draw is actually persisted (re-fetch and assert row
   exists with correct `reading_id`).
7. Position association is correct (`draw.position_id == position.id`).
8. Card association is correct (`draw.card_id == card.id`).
9. Upright draw persists `orientation="upright"`.
10. Reversed draw persists `orientation="reversed"`.
11. **[new]** Response `draw_order` is `1` for the first draw against a
    Reading and increments correctly for subsequent draws (Section 4.3).

**Domain-rule enforcement:**
12. Duplicate-card rejection → `409` (spread disallows duplicates).
13. **[new]** Duplicate-card allowed → `201` (spread explicitly allows
    duplicates) — the positive case, not just the rejection.
14. Non-`DRAFTING` Reading (`SPREAD_COMPLETE`/`INTERPRETED`/`SAVED`,
    parametrized across all three) → `409`.
15. Automatic `DRAFTING → SPREAD_COMPLETE` transition: the final
    required draw flips `status`, reflected in the response's
    `reading_status`.
16. Incomplete spread remains `DRAFTING` after a non-final draw.
17. Complete spread transitions exactly once — a second draw attempt
    after completion is rejected (`409`), not silently accepted or
    re-triggering the transition.
18. **[new]** `position_id` referencing a position that exists but
    belongs to a different spread → `404` (`SpreadPositionNotFoundError`).
19. **[new]** `card_id` referencing a card that exists but belongs to a
    different deck → `404` (`CardNotFoundError`).
20. **[new]** Nonexistent `position_id`/`card_id` (does not exist at
    all) → `404`, same body as the wrong-spread/wrong-deck case (18/19).
21. **[new]** Redrawing an already-filled position while the Reading is
    still `DRAFTING` (two required positions, one drawn, attempt to
    redraw it before the other) → `409`
    (`PositionAlreadyDrawnError`) — directly exercises the Section 3.3
    gap's resolution.

**Transaction integrity:**
22. Transaction rollback on a forced post-flush failure leaves no
    orphaned `CardDraw` row — mirrors Step 29's own creation-rollback
    probe, applied to this route.

**Input validation:**
23. Malformed UUID (`reading_id` path, or `position_id`/`card_id` body)
    → `422`.
24. Missing required field (`position_id`, `card_id`, or `orientation`)
    → `422`.
25. Invalid `orientation` value (not `"upright"`/`"reversed"`) → `422`.

**Optional-position behavior (Section 8):**
26. **[new]** A spread with a required and an optional position:
    filling only the required position advances to `SPREAD_COMPLETE`;
    a subsequent attempt to draw the (still-empty) optional position
    → `409` (`ReadingNotDraftingError`), not a different/special error.

This list intentionally does not include a concurrency/race test beyond
item 21 (a sequential simulation of the same failure mode), consistent
with Section 9's scope note.

---

# 11. Schema/Migration Assessment

**No migration is required.** Every column and constraint this route
needs already exists, unchanged since Step 16:
- `card_draws.reading_id`, `.position_id`, `.card_id`, `.orientation`,
  `.draw_order` — all present.
- `uq_card_draws_reading_id_position_id`,
  `uq_card_draws_reading_id_draw_order`,
  `ck_card_draws_draw_order_positive` — all present and already
  exercised by `tests/test_card_draw.py` (re-run as part of Section 13's
  full-suite check, still passing).

Confirmed by direct model re-read (Section 2.4) and by the full test
suite passing unchanged (Section 13) — no schema evidence anywhere
suggests a gap requiring a new column, constraint, or table.

---

# 12. Open Product/Design Questions (Not Decided Here)

1. **Single-draw vs. batch-draw request shape.** This document
   recommends single-draw-per-call (`POST /readings/{id}/draws` creates
   exactly one `CardDraw`) as the smaller, more REST-conventional
   surface, consistent with every other creation route in this API
   (`POST /readings`, `POST /auth/register` each create exactly one
   row). A batch variant (accepting an array, creating several
   `CardDraw` rows in one call/one transaction) was considered and is
   not recommended, but remains a legitimate alternative a future
   implementation step could choose instead — named here exactly as
   `READING_CREATION_OWNERSHIP_DESIGN.md` Section 297 already flagged
   it, not resolved by this document.
2. **Whether `CardDrawSummary` should embed `card_name`/`position_name`**
   for client display convenience, versus staying ID-only (Section 4.2's
   recommendation). Not decided here.
3. **Whether optional `SpreadPosition`s should ever be practically
   fillable**, given they can only be reached before the last required
   position is drawn (Section 8's second paragraph) — a UX/product
   question about spread design and client flow, not a defect in this
   route's design, and not blocking since no real seeded spread contains
   an optional position.
4. **Whether a `GET /readings/{reading_id}` route should be added**
   alongside or before the draw route — Section 4.2 works around its
   absence by embedding `reading_status` in the draw response, but a
   general single-Reading-fetch route would be a more broadly useful,
   separately-scoped addition this document does not propose building
   here.

---

# 13. Implementation Sequence

Following the exact Design → Implementation pairing this series has
already used for every prior lifecycle surface (Steps 25/26 → 27 for
Reading creation; Step 20/21 → 22 for authentication):

1. **This document** (Step 31) — design/audit, complete.
2. **A future Implementation step**, authorized separately, would:
   a. Add `SpreadPositionNotFoundError`, `CardNotFoundError`,
      `PositionAlreadyDrawnError` to `app/models/exceptions.py`.
   b. Add `CardDrawCreateRequest`/`CardDrawSummary` to
      `app/schemas/reading_api.py` (or a new sibling schema module, a
      minor naming call left to that step).
   c. Add `record_card_draw()` to `app/services/reading_service.py`
      (Section 7).
   d. Wire `POST /readings/{reading_id}/draws` in `app/api/reading.py`.
   e. Add the tests enumerated in Section 10.
   f. Run the focused and full test suites, exactly as every prior
      implementation step in this series has.
   g. Report file/behavior changes; do not commit without separate,
      explicit authorization — matching this entire series' standing
      constraint.
3. A resolution to Section 12's open questions (particularly #1) should
   happen before or during that implementation step, not silently
   default to this document's non-binding recommendation.

---

# 14. Stop Conditions

**None were triggered.** Specifically checked against every condition
this step's brief names:
- No security/ownership bypass — the design reuses `get_owned_reading`
  exactly as-is.
- No lifecycle contradiction — Section 8's optional-position question is
  fully resolved by existing code, not a contradiction.
- No database integrity problem — the existing constraints are correct
  and sufficient (Section 11); the one gap found (Section 3.3) is a
  missing *domain-level* pre-check, not a database defect, and is
  solvable entirely at the future service layer without any model or
  schema change.
- No production path creates an ownerless Reading — unaffected by this
  design (it operates on an already-existing, already-owned Reading).
- No route exposes another user's Reading — `get_owned_reading` reused
  unchanged.
- No uncaught client-reachable exception path was found that this design
  leaves unaddressed — every domain exception identified in Section 6
  has a proposed mapping; the one previously-unmapped gap (Section 3.3)
  is resolved by the proposed `IntegrityError` backstop, using an
  already-proven technique.
- No contradiction requiring a new product decision before *this
  route's* correctness can be established — Sections 8/12's open
  questions are genuine, but none of them blocks a correct, safe,
  ownership-respecting basic implementation from being built; they
  affect refinements (batch support, display-name embedding, optional-
  position UX) layered on top of it.

---

# 15. Final Readiness Assessment

**Ready for implementation**, contingent only on a future step choosing
among Section 12's named (not decided) options — none of which blocks a
correct minimal implementation, since this document's own
recommendations (single-draw, ID-only response, service function in
`reading_service.py`, server-computed `draw_order`) are sufficient to
build a safe, ownership-correct, lifecycle-correct route on their own.
No code, schema, migration, test, frontend, or existing documentation
file was modified by this step. `Documentation/CARDDRAW_API_DESIGN.md` is
the only new file.

---

# 16. Repository Verification

- Full test suite re-run for this step: **381 passed, 2 warnings** (the
  same two pre-existing `InsecureKeyLengthWarning`s, unchanged) —
  confirms this audit's own probes (run against throwaway, in-memory
  databases outside the test suite, all deleted/discarded after use)
  altered nothing.
- `git status --porcelain` at the end of this step: only the
  pre-existing, unchanged `README.md` modification and the untracked
  `Documentation/*.md` files already present after Step 30, plus this
  document itself as the sole new file. No application code, test,
  schema, or migration file differs from commit `ce1a7fb`.
