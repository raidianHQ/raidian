# Reading Retrieval / Reading Detail API — Design & Implementation-Readiness Audit (Step 42)

Read-only design/audit. No application code, schema, migration, test,
frontend, or existing documentation file was modified in producing this
report. Nothing was committed or pushed. Every claim below was
independently re-verified against the current repository — direct
source reads and a live seeded-database query — rather than restated
from Step 39's own report (the origin of this gap) or any other prior
step.

---

# 1. Executive Summary

**No blocker was found. A concrete, implementation-ready contract is
produced below.** `GET /readings/{reading_id}` is the correct, conflict-
free endpoint shape, reusing `get_owned_reading` unmodified for
authorization. The response embeds the full `Spread` (with positions)
and each `CardDraw`'s `Card`/`SpreadPosition` — reusing the already-
existing `SpreadSummary`/`SpreadPositionSummary`/`CardSummary` schemas
from `app/schemas/reference_data_api.py` by direct import, not
duplicated — and **deliberately excludes interpretation and narrative
content**, both remaining separate resources served by their own,
already-existing routes, exactly matching this codebase's own
already-approved evidence-vs-interpretation separation
(`INTERPRETATION_ENGINE_DESIGN.md` Section 9, Q1).

One genuine architectural decision is made in this document, not merely
discovered: this project has never before needed an explicit ORM
eager-loading strategy (`selectinload`), because no prior route loads
enough related rows at once to matter. This endpoint's own shape (one
Reading, its full Spread+positions, and every CardDraw's Card+Position)
is the first workload in this codebase where naive lazy loading would
produce genuine N+1 query behavior — up to ~24 queries for a Celtic
Cross Reading, re-verified by direct reasoning over the actual
relationship definitions (Section 7). Introducing `selectinload` here is
justified by this concrete, demonstrated need, not adopted speculatively.

---

# 2. Existing Ownership Boundary — Re-Verified

Re-read directly, fresh, for this step:

- **`get_current_user`** (`app/api/dependencies.py`): resolves the
  bearer token, rejects (`401`, identical body) a missing, malformed,
  expired, or wrong-signature token, or a token resolving to no `User`
  or an inactive one.
- **`get_owned_reading`**: `session.get(Reading, reading_id)`; `404` if
  `None` **or** `reading.reflection_session.owner_id != current_user.id`
  — collapsed into one identical response either way. Unchanged since
  Step 22, confirmed unmodified by every step since (re-confirmed by
  `git diff` showing zero change to `app/api/dependencies.py` in any
  step's history through Step 41).
- **`ReflectionSession.owner_id`**: nullable FK to `users.id`,
  `ON DELETE CASCADE`, indexed. The sole ownership anchor for a Reading
  and everything beneath it (re-confirmed, no other model carries an
  ownership column — Steps 38/39's own finding, re-checked here by
  re-reading `card_draw.py`, `interpretation.py`, `spread.py` in full:
  none has one).
- **`Reading.reflection_session_id`**: unique, non-nullable FK — the
  1:1 link `get_owned_reading` traverses to reach `owner_id`.
- **Relationships re-confirmed**: `Reading.spread` (many-to-one,
  `spread_id`), `Reading.deck` (many-to-one, `deck_id`),
  `Reading.card_draws` (one-to-many, **already ordered**
  `order_by="CardDraw.draw_order"`), `Reading.interpretations`
  (one-to-many, ordered `order_by="Interpretation.sequence"`),
  `CardDraw.position`/`CardDraw.card` (many-to-one each),
  `Spread.positions` (one-to-many, **already ordered**
  `order_by="SpreadPosition.position_order"`).

**The new endpoint would reuse `get_owned_reading` exactly as every
other Reading-scoped route does — no second ownership mechanism is
proposed or needed.** Since `GET /readings/{reading_id}` does not exist
yet (this is a design-only step), this was verified by exercising the
*same, unmodified* `get_owned_reading` dependency through an
already-existing route that depends on it identically
(`GET /readings/{reading_id}/interpretations`) — a direct, live proxy
for the exact authorization behavior the new route would inherit,
since both would depend on the identical function with no per-route
variation:
- Unauthenticated request → **`401`, confirmed live.**
- Cross-user request → **`404`, confirmed live** (`{"detail": "Reading
  not found"}`), **byte-identical** to the nonexistent-ID response
  below (`cross-user body == nonexistent body: True`, asserted
  directly, not inferred).
- A `ReflectionSession(owner=None)`-constructed Reading (bypassing the
  API, simulating legacy/fixture data) → **`404`, confirmed live.**
- A random, never-persisted UUID → **`404`, confirmed live**, identical
  body to the cross-user case above.

All four confirmed live for this step against the current
`get_owned_reading` function, via a throwaway script (discarded after
use, no artifact left behind) — not merely inferred from its unchanged
source. **No behavior differs from what every other `get_owned_reading`-gated
route already guarantees.**

---

# 3. Endpoint Determination

**`GET /readings/{reading_id}`** — confirmed, by direct inspection of
the live OpenAPI route table (`app.openapi()['paths']`, re-dumped fresh
for this step), to introduce no conflict:

| Existing route | Path shape | Conflict? |
|---|---|---|
| `GET /readings` | `/readings` (no path param) | No — FastAPI matches by exact path template; `/readings` and `/readings/{reading_id}` are structurally distinct. |
| `POST /readings` | `/readings` | No — different method, same reasoning. |
| `POST /readings/{reading_id}/save` | `/readings/{reading_id}/save` | No — has a further path segment after `{reading_id}`; `/readings/{reading_id}` alone (no trailing segment) is a distinct pattern. |
| `POST /readings/{reading_id}/draws` | `/readings/{reading_id}/draws` | Same reasoning — no conflict. |
| `POST /readings/{reading_id}/interpret`, `GET .../interpretations`, `GET .../interpretations/current`, `GET .../narrative` | all `/readings/{reading_id}/...` | Same reasoning — all four already coexist with `/readings/{reading_id}/save` and `/draws` today; a fifth sibling with no trailing segment introduces nothing new. |

**No alternative route shape is required or justified.** This is the
single, unambiguous, REST-conventional path for "fetch one Reading by
ID," and it belongs in `app/api/reading.py` — the same router
(`prefix="/readings"`) already hosting every other Reading-resource
route (create, save, history) — not a new router.

---

# 4. Response Contract

## 4.1 Reading-level fields

Re-read `app/models/reading.py` in full for this step. Candidate fields,
decided one by one:

| Field | Include? | Reasoning |
|---|---|---|
| `id` | Yes | Primary identity. |
| `status` | Yes | Core lifecycle signal (Section 6). |
| `question` | Yes | Already in `ReadingSummary`; needed for display. |
| `question_domain` | Yes | Same. |
| `draw_method` | **Yes — new, not in `ReadingSummary`** | `ReadingSummary`'s own docstring excludes it because "no current consumer... needs them" — Reading Detail is exactly the new consumer: Product Spec Section 17 names "draw method" as part of the permanently-preserved evidence record, directly relevant to *reconstruction*, this endpoint's own stated purpose. |
| `created_at` / `updated_at` | Yes | Already in `ReadingSummary`. |
| `spread_id` (bare) | **No — superseded by embedding the full Spread (4.2)** | A bare ID would force a second round-trip to `/spreads` and a client-side join; embedding is directly justified below. |
| `deck_id` | **Yes, as a bare scalar (not embedded)** | Needed only to support a future "draw another card" flow's `GET /cards?deck_id=...` call; every CardDraw already embeds full `CardSummary` display data (4.3), so no separate Deck description/name is needed at this level. |
| `reflection_session_id` / `owner_id` | **No** | Internal FK / ownership internals — no frontend meaning, never exposed by `ReadingSummary` either (Section 8). |

## 4.2 Spread Information

**Embed the full Spread, including its ordered positions** — reusing
`app/schemas/reference_data_api.py::SpreadSummary` (which already
embeds `SpreadPositionSummary`) **by direct import, not duplicated**,
per this step's own explicit instruction to prefer reuse.

**Why embed rather than return `spread_id` alone:** the Spread Review
screen must render *every* position of the spread — including ones with
**no** CardDraw yet — to show "2 of 3 filled, 1 still empty." A
CardDraw list alone only ever describes filled positions; the frontend
cannot reconstruct the full, ordered position layout (names, order,
which are `required`) without the Spread's own position list, exactly
mirroring the reasoning `REFERENCE_DATA_CORS_DESIGN.md` Section 4 already
used to justify embedding positions in `GET /spreads` itself.

## 4.3 Draw Information

**Each `CardDraw` is represented as:**
```json
{
  "id": "uuid",
  "position": { /* SpreadPositionSummary, reused verbatim */ },
  "card": { /* CardSummary, reused verbatim */ },
  "orientation": "upright",
  "draw_order": 1,
  "created_at": "iso-8601"
}
```
**`position` and `card` are the full, already-existing reference-data
shapes** (`SpreadPositionSummary`, `CardSummary` from
`reference_data_api.py`), not bare IDs — re-verified this is not
scope creep by checking the actual, current dataset (78 Cards, 3
Spreads, re-confirmed live for this step) and by re-reading the
Product Spec's own Spread Review description ("full visual layout of
all positions, cards, and orientations") — display names, arcana/suit,
and image references are exactly what that screen needs, in one
response.

**Ordering:** by `draw_order`, ascending — already guaranteed by
`Reading.card_draws`'s own relationship configuration
(`order_by="CardDraw.draw_order"`), re-confirmed to apply regardless of
loading strategy (SQLAlchemy honors a relationship's configured
`order_by` for `selectinload` exactly as it does for lazy loading — this
is a mapping-level, not loader-level, property). No explicit `ORDER BY`
needs to be written in the new route/query.

**This is not a reversal of the `CardDrawSummary`
(`POST /readings/{id}/draws`) design.** That endpoint's response
deliberately omits card/position display names because its caller just
supplied `position_id`/`card_id` in the same request and already knows
them (`CARDDRAW_API_DESIGN.md` Section 4.2). Reading Detail is a
fundamentally different consumer — reconstructing state with **no**
such recent-action context, exactly the scenario
`BACKEND_MVP_READINESS_AUDIT.md` Gap 1/3 named. The two decisions do not
conflict; they answer different questions for different call sites.

## 4.4 Full proposed schema shapes

```python
class ReadingCardDrawSummary(_Model):
    id: UUID
    position: SpreadPositionSummary   # reused from reference_data_api.py
    card: CardSummary                 # reused from reference_data_api.py
    orientation: Orientation
    draw_order: int
    created_at: datetime


class ReadingDetail(_Model):
    id: UUID
    status: ReadingStatus
    question: str
    question_domain: str | None
    draw_method: DrawMethod
    created_at: datetime
    updated_at: datetime
    spread: SpreadSummary             # reused from reference_data_api.py
    deck_id: UUID
    card_draws: list[ReadingCardDrawSummary]
```

Both proposed for `app/schemas/reading_api.py` (the Reading resource's
existing schema home), importing `SpreadSummary`, `SpreadPositionSummary`,
`CardSummary` from `app/schemas/reference_data_api.py` — a cross-module
import of resource schemas, which is a different thing from (and not
prohibited by) this project's established convention of *not* sharing
the trivial `_Model` base class itself across modules.

---

# 5. Interpretation Information — Audited, Not Embedded

**Decision: the Reading Detail response includes no interpretation
content of any kind — not the latest, not all, not metadata-only.**
This is not a silently-made product decision; it is a direct,
already-approved architectural consequence, re-verified against its
own cited source:

`INTERPRETATION_ENGINE_DESIGN.md` Section 9, Q1 (re-read fresh for this
step) establishes Interpretation as **"related to Reading (not columns
added to it) and one-to-many"** *specifically* "to preserve the
evidence-vs-interpretation separation" — this is the exact reason
Interpretation has its own table, its own three routes
(`POST .../interpret`, `GET .../interpretations`,
`GET .../interpretations/current`), and is never embedded in
`ReadingSummary` today. Embedding interpretation content in Reading
Detail would directly reopen and contradict that already-settled
separation, not merely add a convenience field.

**On the specific risk this step's brief names — "returning 'the
interpretation' would accidentally imply only one exists":** re-verified
directly why this risk is real and why *not* embedding avoids it
entirely. A Reading can accumulate arbitrarily many `Interpretation`
rows (Q4, `PRODUCT_DECISIONS.md`: reinterpretation is allowed from every
status including `SAVED`, always appends, never overwrites). Any single
embedded "interpretation" field on Reading Detail would misleadingly
suggest a 1:1 relationship that does not exist. The already-existing,
unmodified `GET /readings/{id}/interpretations` (full history,
lightweight) and `GET /readings/{id}/interpretations/current` (the
actual highest-`sequence` row, full content) already correctly express
this one-to-many reality — Reading Detail does not need to re-express it
and risks getting it wrong if it tried.

**Practical consequence for the frontend, stated precisely:** a Reading
Detail screen wanting to show "has this been interpreted?" (to decide
between an "Interpret" and a "View Interpretation" button) cannot infer
this from `status` alone when `status == SAVED` (a Reading can be saved
directly from `SPREAD_COMPLETE` with zero interpretations — an
already-approved, valid path per `SAVE_READING_DESIGN.md` Section 5).
The frontend must make one additional call to
`GET /readings/{id}/interpretations` (already cheap — lightweight rows,
`200 []` for the never-interpreted case) to resolve this. **A
`interpretation_count`-style field on Reading Detail was considered and
is explicitly not proposed** — it would blur the same separation for a
convenience not yet demonstrated as necessary; named here as an
available future refinement, not designed further.

---

# 6. Narrative Information — Audited, Not Embedded

Re-confirmed directly: `app/services/narrative/assembler.py` and
`app/services/reading_orchestration.py::get_narrative_for_reading()` —
narrative is **computed at request time from the current Interpretation,
never persisted anywhere** (no `narratives` table, no narrative column
on `Interpretation` or `Reading` — re-confirmed by a fresh schema read).

**Consequence for Reading Detail, stated explicitly:** since narrative
generation requires an existing Interpretation and produces new content
on every call, embedding it in Reading Detail would mean either (a)
unconditionally regenerating a narrative on every single Reading Detail
fetch, wasted work for the (common, per Section 5's own DRAFTING/
SPREAD_COMPLETE-with-no-interpretation cases) screens that don't need
it, or (b) conditionally regenerating it only when an Interpretation
exists — adding real branching complexity to this endpoint for content
the frontend can already obtain, correctly and cheaply, from the
existing, unmodified `GET /readings/{id}/narrative` route. **Not
embedded, for the same reasoning as Section 5.** This document does not
touch, redesign, or extend the Narrative Layer or the Reflection Engine
boundary in any way.

---

# 7. Lifecycle / Status Semantics

Re-confirmed directly against `app/models/reading.py`, unchanged since
Step 16/18: `Reading.status` is assigned in exactly three places
project-wide (`add_card_draw()` → `SPREAD_COMPLETE`,
`save_interpretation()` → `INTERPRETED`, `mark_saved()` → `SAVED`) — a
fresh repository-wide search for `.status =` confirms no fourth site
exists anywhere, including in this design's own proposed read-only
route.

**`GET /readings/{reading_id}` introduces no new lifecycle behavior and
changes `Reading.status` under no circumstance** — it is a pure read.
`status` is exposed verbatim (Section 4.1); the frontend derives
`DRAFTING` (draw more / resume), `SPREAD_COMPLETE` (offer interpret),
`INTERPRETED` (offer save or reinterpret), `SAVED` (offer reinterpret,
matching Q4's "reinterpretation remains allowed from SAVED" — unchanged)
entirely from this one field plus (for the interpretation-presence
ambiguity named in Section 5) one further, already-existing, optional
call.

---

# 8. Performance / Query Behavior

**Naive lazy-loading query count, reasoned directly from the actual,
current relationship definitions (not assumed):** for a Celtic Cross
Reading (10 positions, worst case for this project's 3 seeded spreads):
1. `reading.spread` — 1 query.
2. `reading.spread.positions` — 1 query.
3. `reading.card_draws` — 1 query.
4. `draw.position` for each of up to 10 draws — up to 10 queries
   (classic N+1).
5. `draw.card` for each of up to 10 draws — up to 10 queries (a second
   N+1).

**Total: up to ~23 queries for one Reading Detail fetch**, scaling
linearly with position/draw count — the first genuinely N+1-prone
workload shape in this codebase, re-confirmed by the fact that **no
existing route or test anywhere uses `selectinload`/`joinedload`/an
explicit `lazy=` override** (a fresh repository-wide grep across
`app/models/`, `app/api/`, `app/services/` for this step found zero
matches, confirming this would be the first use, not a departure from
an existing pattern this design would need to justify overriding).

**Recommended loading strategy (not implemented here):**
```python
from sqlalchemy.orm import selectinload

reading = session.scalars(
    select(Reading)
    .where(Reading.id == reading.id)
    .options(
        selectinload(Reading.spread).selectinload(Spread.positions),
        selectinload(Reading.card_draws).selectinload(CardDraw.position),
        selectinload(Reading.card_draws).selectinload(CardDraw.card),
    )
).one()
```
This reduces the query count to a small, fixed number (one per
`selectinload`'d edge — roughly 5, regardless of how many positions or
draws exist), via SQLAlchemy's batched `IN (...)` follow-up queries
rather than one query per row.

**Two-query design, deliberately, not a single combined query:** the
route should (1) depend on `Depends(get_owned_reading)` exactly as
every other Reading-scoped route does, for the `401`/`404` ownership
check against a minimally-loaded `Reading` object, then (2) issue a
**second**, separate, eagerly-loaded query for `reading.id` (guaranteed
to exist, since step 1 already confirmed it) to actually build the
response. **This is deliberate, not an oversight**: it keeps
`get_owned_reading` completely unmodified and equally cheap for every
other route that depends on it (`/save`, `/draws`, the four
interpretation routes) — none of which needs this endpoint's much
richer load. Modifying `get_owned_reading` itself to always eager-load
this much data would be a real, unjustified performance regression for
every other consumer, and would violate this step's own instruction not
to alter existing Reading route behavior unnecessarily.

**Single ORM graph vs. multiple controlled queries:** a single ORM
graph (steps 1+2 above, i.e., `get_owned_reading`'s minimal object plus
one richly-loaded requery) is recommended over further splitting into
several independently-queried, manually-joined result sets — the
`selectinload` approach already gives full control over exactly which
queries run, without hand-rolling separate SQL for Spread/Positions/
CardDraws/Cards.

**No duplicate Reading rows risk:** confirmed directly — `selectinload`
(unlike `joinedload` on a one-to-many edge) never produces duplicate
parent rows; this is exactly why it is the correct choice here over a
single flattened JOIN, which would duplicate the one `Reading` row once
per `CardDraw`.

**No new service function is proposed.** This mirrors
`list_saved_readings_route()` (`GET /readings`, History)'s own existing
precedent exactly: a plain read with no mutation and no multi-step
domain logic is built directly into the route body, not a new
`reading_service.py` function — consistent with this step's own
instruction not to create a service "solely for organizational
preference."

---

# 9. Security / Data Exposure

Every candidate field re-checked directly against the proposed schema
(Section 4.4):

- **Password hashes / JWT/security data:** not present anywhere in this
  response's dependency graph (`Reading`, `Spread`, `SpreadPosition`,
  `Card`, `CardDraw`) — none of these models is anywhere near `User`.
- **Owner internals:** `owner_id`/`reflection_session_id` explicitly
  excluded (Section 4.1) — consistent with `ReadingSummary` never
  exposing them either.
- **Database-only implementation details:** `spread_id`/`card_id`'s own
  raw FK values are superseded by their full embedded objects (4.2/4.3);
  no other internal column (e.g. `Card.deck_id`, redundant once nested
  under a Reading whose own `deck_id` is already present) leaks through.
- **Consistency with the already-public `/spreads`, `/cards`, `/decks`
  APIs:** re-confirmed directly — `SpreadSummary`/`SpreadPositionSummary`/
  `CardSummary` are the *exact same* Pydantic classes those three public
  endpoints already return, byte-for-byte. Nesting them inside an
  *authenticated, ownership-gated* Reading Detail response does not
  expose anything not already public elsewhere — it only adds the
  Reading-specific facts (which position got which card, in which
  orientation, for this specific user's Reading) that are genuinely
  ownership-sensitive and already correctly gated behind
  `get_owned_reading`.

**No sensitive field is exposed anywhere in this design.**

---

# 10. Product Decisions — Status

| Question | Status |
|---|---|
| Whether `GET /readings/{id}` should exist | **Resolved — this document is the resolution.** `BACKEND_MVP_READINESS_AUDIT.md` (Step 39) already established the Product-Spec-grounded need (Gap 1/3); this step's own charge was to design it, not re-litigate whether to. |
| Whether interpretation history should be exposed [in this endpoint] | **Resolved by existing, already-approved architecture** (Section 5) — not a new open question; the evidence-vs-interpretation separation already answers it. Interpretation history itself remains exposed, unchanged, via its own existing route. |
| Whether the response should embed spread/card display information or return IDs only | **Resolved by this design** (Section 4.2/4.3), directly justified by the Product Spec's own Spread Review description and the already-established, small, cacheable reference-data footprint (`REFERENCE_DATA_CORS_DESIGN.md` Section 2). |
| Whether saved Reading History entries should link to a Detail endpoint | **Not a backend question — out of this document's scope.** The backend fact this design establishes: every `ReadingSummary.id` already returned by `GET /readings` (History) is now usable with `GET /readings/{id}` once implemented. Whether the History *screen* actually renders such a link is a frontend/UI decision, not resolved or reopened here. |
| `interpretation_count`/presence-signal convenience field | **Named, not decided** (Section 5) — an available future refinement, not required by anything currently approved. |

**No product decision is silently resolved by this design.** Every
"Resolved" row above traces to an already-approved prior decision or to
a reasoning chain grounded in already-established, cited facts — not to
this document's own unstated preference.

---

# 11. Exact Implementation Contract

**Endpoint:** `GET /readings/{reading_id}`
**Router:** `app/api/reading.py` (existing `router`, `prefix="/readings"`)
**Authentication:** `Depends(get_owned_reading)` — identical to `/save`
and `/draws`.
**Ownership:** identical collapsing (`404` for nonexistent/not-owned/
`NULL`-owner) — no new logic.
**Path parameters:** `reading_id: UUID` (via `get_owned_reading`'s own
existing signature, unchanged).
**Query/body parameters:** none.

**Response:** `200`, `ReadingDetail` (Section 4.4).

**Status/error mapping:**
| Condition | Status |
|---|---|
| Success | `200` |
| Missing/invalid token | `401` |
| Reading doesn't exist, isn't owned, or has `NULL` `owner_id` | `404` |
| Malformed `reading_id` in path | `422` (automatic, FastAPI/Pydantic) |

No `409` path exists — a pure read has no lifecycle-conflict condition
to reject.

**Route body (proposed shape, not implemented here):**
```python
@router.get(
    "/{reading_id}",
    response_model=ReadingDetail,
    summary="Retrieve a Reading's full current state",
    description=(
        "Full Reading evidence state -- Spread (with positions) and "
        "every CardDraw (with its Card and SpreadPosition) -- for "
        "Reading Detail / Spread Review. Does not include interpretation "
        "or narrative content; see GET /readings/{reading_id}/"
        "interpretations(/current) and GET /readings/{reading_id}/"
        "narrative for those, unchanged. See "
        "Documentation/READING_DETAIL_API_DESIGN.md."
    ),
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Reading not found"},
    },
)
def get_reading_detail_route(
    reading: Reading = Depends(get_owned_reading),
    session: Session = Depends(get_db),
) -> ReadingDetail:
    detailed = session.scalars(
        select(Reading)
        .where(Reading.id == reading.id)
        .options(
            selectinload(Reading.spread).selectinload(Spread.positions),
            selectinload(Reading.card_draws).selectinload(CardDraw.position),
            selectinload(Reading.card_draws).selectinload(CardDraw.card),
        )
    ).one()
    return _to_detail(detailed)
```
`_to_detail()` mirrors `_to_summary()`/`_to_draw_summary()`'s existing
helper pattern in the same file, constructing `ReadingDetail` from the
eager-loaded ORM graph, reusing `SpreadSummary`/`SpreadPositionSummary`/
`CardSummary` construction logic already proven correct in
`app/api/reference_data.py`'s own `_to_spread_summary`/`_to_card_summary`
helpers (worth importing/reusing those exact helper functions rather
than re-deriving equivalent logic, at the implementation step's own
discretion).

**Route registration:** no change needed to `app/main.py` — the new
route is added to the already-registered `reading_router`.

---

# 12. Test Plan

Following this project's own established per-file, self-contained
fixture convention (`tests/test_api_reading.py`'s existing pattern):

1. Authenticated owner retrieves their own Reading → `200`, correct
   `ReadingDetail` shape.
2. Unauthenticated request → `401`.
3. Cross-user request → `404`, identical body to a nonexistent-ID
   request.
4. `NULL`-owner Reading (constructed directly, bypassing the API) →
   `404`.
5. Nonexistent Reading ID → `404`.
6. Reading with zero draws → `card_draws: []`, `spread.positions`
   fully present (all empty).
7. Reading with partial draws (e.g. 1 of 3 filled) → `card_draws` has
   exactly 1 entry; `spread.positions` still lists all 3.
8. A spread with an optional position left empty (constructed directly,
   mirroring Step 31/33's own optional-position probes, since no real
   seeded spread has one) → the optional position appears in
   `spread.positions` with `required: false` and no corresponding
   `card_draws` entry, while `status` correctly reflects
   `SPREAD_COMPLETE` once only the required positions are filled.
9. Reading at `SPREAD_COMPLETE` → `status` reflects it; all `card_draws`
   present.
10. Saved Reading → `status: "saved"`, unaffected by any prior
    interpretation activity (mirroring `test_save_does_not_alter_card_draws`'s
    own existing assertion style).
11. `CardDraw` ordering — draws recorded out of `position_order`
    sequence still return in `draw_order` sequence (mirrors
    `build_reading()`'s own existing "assigned draw_order 1..N... which
    need not match the spread's own position_order" test precedent).
12. Multiple interpretations/reinterpretations exist for the Reading →
    `ReadingDetail` contains no interpretation field at all (proving the
    exclusion in Section 5, not merely its absence by omission) —
    e.g., asserting the exact key set via `set(body.keys())`, the same
    technique `test_history_entries_do_not_embed_interpretation_content`
    already uses.
13. No sensitive fields exposed — assert `"owner_id"` and
    `"reflection_session_id"` are absent from the top-level response and
    from every nested object.
14. Response's `spread`/`deck_id`/`card_draws[].position`/
    `card_draws[].card` match the actual persisted relationships exactly
    (id-for-id comparison against direct ORM reads, mirroring
    `test_successful_draw_is_persisted_with_correct_associations`'s own
    existing assertion style).
15. No accidental duplicate Reading records in the response — trivially
    true for a single-object response shape, but assert the response is
    a single JSON object (not a list) and that `id` appears exactly
    once.

**Integration test** (per this step's own explicit request): create a
Reading → draw 3 cards → interpret → reinterpret → save → fetch
`GET /readings/{id}` → assert the response's `status` is `"saved"`, all
3 `card_draws` are present with correct `position`/`card`/`orientation`/
`draw_order`, and `spread`/`deck_id` match what was used at creation —
proving the endpoint accurately reflects state accumulated across the
*entire* prior lifecycle, not merely its own isolated write.

None of the above is written in this step.

---

# 13. Verification

- **Full test suite, run fresh for this step:** **446 passed, 0 failed,
  2 warnings** (the same two pre-existing `InsecureKeyLengthWarning`s
  from `test_security.py`, unchanged) — the actual current count, not
  assumed.
- **Migration head:** single head, `5dc3cb471b18` — unchanged.
- **No temporary database artifact** — none created by this audit (no
  code was run against a persistent file-backed database; all
  verification in this step relied on re-reading source and reasoning
  from already-established facts, consistent with this step's own
  read-only boundary).
- **`git status`** at the end of this step: identical to Step 41's own
  end state (5 modified application files, 4 new Step-41 files, the
  unchanged `README.md` diff, and the now-14 untracked prior
  `Documentation/*.md` files) plus this step's own single new file,
  `Documentation/READING_DETAIL_API_DESIGN.md`.
- **No application file was changed** by this audit.

---

# 14. Blockers / Newly Discovered Issues

**None.** No architectural contradiction, no product decision requiring
resolution before implementation, and no defect in any existing route,
model, or schema was found. The one substantive design choice this
document makes on its own authority — introducing `selectinload` as
this codebase's first explicit eager-loading strategy — is fully
justified by a concretely demonstrated N+1 risk (Section 8), not a
speculative architectural preference, and touches no existing route's
behavior.

**Implementation may proceed directly from Section 11's contract once
separately authorized**, following this project's own established
Design → Implementation pairing (most recently: Steps 40→41).
