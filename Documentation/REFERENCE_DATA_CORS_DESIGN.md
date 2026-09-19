# Reference Data Serving & CORS — Design/Audit (Step 40)

Read-only design/audit, focused exclusively on the two blockers Step 39
identified. No application code, schema, migration, configuration, test,
or frontend file was modified in producing this report. No existing
`Documentation/*.md` file was edited. Nothing was committed or pushed.
Every claim below was independently re-verified against the current
repository — fresh source reads, a fresh live seeded-database query, and
a fresh full test run — rather than restated from Step 39's own report.

---

# 1. Executive Summary

**This design is sufficient to unblock implementation.** Both blockers
have a small, precisely-specified, minimal-scope design below, each
consistent with every existing architectural convention this project has
already established (the `_Model`/`extra="forbid"` schema pattern, the
thin-route-delegates-to-a-query pattern, the `RAIDIAN_`-prefixed
zero-config-friendly `Settings` pattern). Neither design requires a
schema change, a new dependency, or a departure from any approved
decision.

One genuinely new, concrete fact was found during re-verification that
materially shapes this design: **a `frontend/` directory already exists
in this repository**, fully committed, containing a default Vite + React
+ TypeScript scaffold with no API integration code yet and no overridden
dev-server port — meaning Vite's own default port (`5173`) is the actual
local-development origin, not an assumption. No production frontend
origin exists anywhere in the repository (no custom domain, no GitHub
Pages configuration, no deployment URL) — this design does not invent
one (Section 3).

Two questions are deliberately left open, per this step's own explicit
instruction not to resolve them: **whether reference data should be
public or require authentication**, and **the Product Spec's own
unresolved Q4 (deck-selection UI scope)**. Both are named precisely in
Section 10, with the technical design shaped to remain correct under
either eventual answer.

---

# 2. Current-State Verification

Re-confirmed directly, independent of Step 39's own claims:

- **CORS:** `app/main.py` re-read in full — no `CORSMiddleware` import,
  no `app.add_middleware(...)` call of any kind. Confirmed genuinely
  absent.
- **Reference-data endpoints:** a live OpenAPI schema dump
  (`app.openapi()['paths']`) shows exactly `/`, `/auth/register`,
  `/auth/login`, `/readings`, `/readings/{reading_id}/draws`,
  `/readings/{reading_id}/interpret`,
  `/readings/{reading_id}/interpretations`,
  `/readings/{reading_id}/interpretations/current`,
  `/readings/{reading_id}/narrative`, `/readings/{reading_id}/save` —
  confirmed genuinely absent for Spreads, SpreadPositions, Cards, or
  Decks.
- **Actual seeded dataset size** (queried live against a freshly seeded
  in-memory database, not assumed): **78 Cards, 3 Spreads (Celtic Cross:
  10 positions, Three Card: 3 positions, Single Card: 1 position), 1
  Deck.** This directly grounds Sections 3 and 7's design choices.
- **Model fields, re-read directly:**
  - `Spread`: `name`, `description`, `allow_duplicate_cards`; derived
    `position_count` property; `positions` relationship. **No
    active/inactive or enabled flag exists** — every seeded Spread is
    implicitly usable; there is no concept of a disabled Spread anywhere
    in the schema.
  - `SpreadPosition`: `spread_id`, `name`, `description`,
    `position_order`, `semantic_role`, `required`. **No coordinate or
    visual-layout field exists** — this model has no `x`/`y`, no
    `layout_hint`, nothing describing visual placement beyond ordinal
    position (`position_order`).
  - `Card`: `deck_id`, `name`, `arcana`, `suit`, `rank`, `image_ref`,
    `base_meaning_upright`, `base_meaning_reversed`, `keywords`
    (JSON list), `primary_themes`/`secondary_themes` (JSON lists).
  - `Deck`: `name`, `description`, `is_default`; `cards` relationship.
    No deck-ownership column exists (confirmed, consistent with Steps
    38/39's own finding that no model except `ReflectionSession` has any
    ownership column).
- **Reference-data seed code:** `app/seed/seed.py` — `seed_spread()`/
  `seed_all_spreads()` (idempotent, looked up by unique `name`),
  `seed_deck()` (singular, hardcoded to exactly one `RWS_DECK_DIR`,
  `is_default: true`) — re-confirmed unchanged since Steps 27/29/32's own
  repeated verification of this same fact.
- **Existing schema/API conventions, re-confirmed for reuse:** the
  `_Model` base (`ConfigDict(frozen=True, extra="forbid")`, duplicated
  per schema module rather than shared — an established, deliberate
  convention per `app/schemas/reading_api.py`'s own docstring), UUID
  typing throughout, thin routes that delegate to a single query or
  service call, `responses={...}` blocks documenting every status code
  a route can return.
- **Authentication/ownership dependencies:** `get_current_user`,
  `get_owned_reading` — re-read fresh, unchanged since Step 22.
- **Configuration architecture:** `app/core/config.py`'s `Settings`
  class — re-confirmed the existing pattern: a simple, flatly-typed
  field with a permissive, zero-config-friendly default (`database_url`,
  `jwt_secret_key`), documented inline as requiring override in a real
  deployment, sourced from an `RAIDIAN_`-prefixed environment variable
  or `.env` file.
- **`frontend/` directory (new finding for this step):** fully committed
  to git (`git ls-files frontend/` lists 19 tracked files;
  `git status -- frontend/` shows no local modifications). Contains a
  default `npm create vite@latest` React+TypeScript scaffold —
  `package.json` (`react`, `react-dom`, `tailwindcss`; `vite`, `eslint`,
  `typescript` as dev dependencies), `vite.config.ts` (plugins: `react()`
  only — no `server.port` override, no proxy configuration, no API base
  URL anywhere). No `.env`/`.env.example` file exists in `frontend/`. No
  API-client code, no `fetch`/`axios` usage, no environment-variable
  reference to a backend URL anywhere in `src/`.
- **ADR-0004** (re-read from `docs/DECISIONS.md`, already quoted in
  Step 4/39's own audits, re-confirmed unchanged): React + Vite +
  TypeScript + Tailwind CSS frontend, FastAPI backend, GitHub Pages +
  Render hosting — two independently deployed origins, confirmed as the
  binding architectural decision this design must serve.
- **`docs/ROADMAP.md` / `Documentation/PRODUCT_DECISIONS.md`:**
  re-searched for any CORS or reference-data-endpoint mention — none
  found, consistent with Step 39's own finding that this scope area was
  never previously covered by any Step 17–39 document.
- **Product Spec Q4 (Deck scope), re-confirmed present and unresolved:**
  `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` line 476: "Deck entity scope for
  MVP. Confirmed as needed... but not specified in the brief — is a
  single hardcoded deck... sufficient for MVP with no deck-switching UI,
  or should the Deck table/selector exist in the UI from day one even
  with only one row?" — line 512: "One initial deck (Rider-Waite-Smith
  or equivalent, pending Q4)." Re-confirmed this question is never
  resolved anywhere in `PRODUCT_DECISIONS.md` (that document's own,
  differently-numbered "Q4" is an unrelated, already-settled question
  about interpretation-pinning, not this one).

**All Step 39 findings are re-confirmed accurate.** No new contradiction
of any prior conclusion was found; two new, additive facts (the existing
`frontend/` scaffold and its exact dev-server default) were found and
are incorporated into this design.

---

# 3. CORS Design

**Where CORS middleware belongs:** `app/main.py`, registered via
`app.add_middleware(CORSMiddleware, ...)`, immediately after `app`'s
construction and before any router is included — the standard, only
correct location for Starlette/FastAPI middleware registration. No new
dependency is required: `CORSMiddleware` ships as part of Starlette,
already an installed transitive dependency of FastAPI (confirmed via
`requirements.txt`, which pins `fastapi` directly).

**Local development origin:** `http://localhost:5173` — not an
assumption; this is Vite's own documented default dev-server port,
confirmed unoverridden by this repository's actual, committed
`frontend/vite.config.ts` (Section 2). `http://127.0.0.1:5173` should
also be permitted, since browsers treat `localhost` and `127.0.0.1` as
distinct origins and either may be used depending on how a developer
starts the dev server or opens the browser.

**Production/deployed frontend origin:** **not currently knowable, and
not invented here**, per this step's own explicit instruction. No
GitHub Pages URL, custom domain, or deployment configuration exists
anywhere in this repository today (confirmed, Section 2). The design
below expresses this as a **configuration requirement**: the allowed
production origin(s) must be supplied via environment configuration at
deploy time, following the exact same pattern this project already uses
for `jwt_secret_key` (a documented, override-required setting with a
safe, non-production default) — not resolved as a hardcoded value now.

**Origins from configuration — yes:** a new `Settings` field,
consistent with the existing pattern:
```python
cors_allowed_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
"""Comma-separated list of origins permitted to make cross-origin
requests to this API (Access-Control-Allow-Origin). Defaults to the
local Vite dev server only, matching frontend/vite.config.ts's own
unoverridden default port -- any real deployment MUST override this via
RAIDIAN_CORS_ALLOWED_ORIGINS to include the deployed frontend's actual
origin, mirroring jwt_secret_key's own override-required convention."""
```
parsed into a `list[str]` (split on `,`, stripped) at the point
`CORSMiddleware` is configured in `main.py` — no new parsing dependency
needed, a one-line `.split(",")` is sufficient for this shape.

**Credentials:** **not required.** This project's authentication is
Authorization-header-based JWT (`Bearer <token>`), never a cookie —
confirmed via `app/api/dependencies.py`'s `OAuth2PasswordBearer` usage
and re-confirmed no route anywhere sets or reads a cookie. Starlette's
`allow_credentials` flag governs cookie/browser-credential inclusion in
cross-origin requests (`fetch(..., {credentials: 'include'})`) — since
this API never relies on that mechanism, `allow_credentials=False` is
correct and should remain the setting, which also avoids the CORS
specification's own prohibition on combining `allow_credentials=True`
with a wildcard origin (a combination this design does not use either
way, but worth noting as a non-issue precisely because credentials mode
is not needed here).

**Authorization headers supported correctly:** yes, by explicit
inclusion — `Authorization` must appear in `allow_headers` for the
browser to permit this project's actual auth mechanism to cross an
origin boundary; it is not a CORS-safelisted header and would otherwise
be stripped/blocked.

**Allowed methods:** `GET`, `POST` only — re-confirmed via the live
route dump (Section 2) that no route anywhere in this API uses `PUT`,
`PATCH`, or `DELETE`. Restricting to exactly the methods in use is more
precise than a wildcard and requires no future change unless a route
using a new method is added (at which point updating this list is a
one-line change alongside that route's own addition).

**Allowed headers:** `Authorization` (the bearer token) and
`Content-Type` (required specifically because every `POST` route in
this API accepts a JSON body — `application/json` is not a
CORS-safelisted content type, so `Content-Type` must be explicitly
allowed or every JSON `POST` would fail preflight).

**Wildcard origins:** **inappropriate, and not proposed.** Even without
credentials mode, an unrestricted `allow_origins=["*"]` would let any
website's client-side JavaScript read this API's responses (reference
data, but also authentication error messages, and — for any user who
has a valid token accessible to that JS, e.g. via a separate
vulnerability — authenticated Reading data) and would let any origin
probe `/auth/login`/`/auth/register` freely. An explicit, configured
allowlist is the correct design regardless of the credentials question.

**Preflight requests:** handled automatically by `CORSMiddleware` for
any `OPTIONS` request matching a configured origin/method/header
combination — no per-route code is needed or should be added; this is
exactly what the middleware exists to do, and every route already
returns only `GET`/`POST`, both fully covered by the `allow_methods`
list above.

**Full proposed shape** (not implemented in this step):
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins.split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
```

---

# 4. Reference Data API Design

All four proposed schemas below would follow the existing `_Model`
(`frozen=True, extra="forbid"`) convention, in a new module
(`app/schemas/reference_data_api.py`, proposed name only — not created
here) mirroring `reading_api.py`'s own per-resource independence
convention. All four proposed routes would follow the existing
thin-route pattern, in a new module (`app/api/reference_data.py`,
proposed name only) — no existing route file is proposed to be extended,
since none of the existing three route files (`auth.py`,
`interpretation.py`, `reading.py`) is the right home for resource types
that are not Reading-scoped.

## Spreads

**Endpoint:** `GET /spreads`. **Method:** `GET` (pure read, no
side effect — the only HTTP method this operation could ever need).

**Response shape (proposed):** a list of:
```json
{
  "id": "uuid",
  "name": "Three Card",
  "description": "...",
  "position_count": 3,
  "allow_duplicate_cards": false,
  "positions": [
    {"id": "uuid", "name": "Recent Past", "description": "...", "position_order": 1, "semantic_role": "recent_past", "required": true},
    ...
  ]
}
```
**Positions are embedded directly in the Spread response**, not a
separate endpoint — re-verified this is the more minimal design given
Section 2's confirmed dataset size (3 Spreads, at most 10 positions
each; the entire payload for all Spreads combined is a few kilobytes).
A separate list-then-detail (`GET /spreads` lightweight,
`GET /spreads/{id}` with positions) two-endpoint split was considered
and rejected specifically because it adds a second endpoint and a
second round trip for a dataset too small to justify the split — the
Layout Selection screen can simply ignore the `positions` field it
doesn't need yet, and the Card Entry screen (reached moments later, for
the same Spread) already has it without a second fetch.

**`position_count`:** included directly — the model already exposes
this as a derived property (`Spread.position_count`), and the Product
Spec explicitly names it as needed for the Layout Selection screen
("shows position count and short description").

**`allow_duplicate_cards`:** included — not merely "possibly useful
later," but directly required by the Product Spec's own named Card
Entry behavior ("duplicate-card guard with override-to-correct"): the
frontend needs to know, per Spread, whether a duplicate-card submission
should even be attempted/offered as an override, or is structurally
impossible for that Spread (every currently-seeded Spread has this
`false`, per Section 2 — but the field is not a spread-selection-UI
detail, it is exactly the value the existing, already-shipped backend
error (`DuplicateCardError`, `409`) is conditioned on).

**Inactive/invalid spreads:** none exist — the schema has no such
concept (Section 2); every row returned by this endpoint is
unconditionally usable.

**Ordering:** by `name`, ascending — no dedicated ordering field exists
on `Spread` (Section 2), and imposing `ORDER BY name` requires no schema
change; a stable, simple, deterministic order is all that is needed for
3 rows.

**Only seeded/usable spreads:** trivially true — no API path exists (or
is proposed) to create a Spread, so every row in the table is,
definitionally, seeded reference data.

## Spread Positions

Covered by the embedded `positions` array above — **no separate
endpoint is proposed.** Response fields (`id`, `name`, `description`,
`position_order`, `semantic_role`, `required`) map directly,
one-for-one, to the model's own columns — no internal ORM detail (e.g.
`spread_id`, redundant once nested under its own Spread) is exposed.
**Coordinates/visual-layout metadata:** confirmed absent from the model
(Section 2) — this design does not invent any (per this step's own
"do not invent card metadata" instruction, extended here to layout
metadata by the same reasoning); a frontend building a visual spread
layout would need its own static, per-Spread-name layout definitions
(e.g., a small hardcoded mapping of "Celtic Cross" position names to
screen coordinates) — a frontend-side concern, not something this
backend design can or should manufacture from data that does not exist.

## Cards

**Endpoint:** `GET /cards`. **Method:** `GET`.

**Query parameter:** `deck_id: UUID | None = None` — optional, mirroring
`POST /readings`'s own `deck_id` parameter exactly: when omitted,
resolves to the seeded default Deck (`Deck.is_default.is_(True))`,
identical logic to `reading_service.py::create_reading()`'s own
already-proven resolution). This sidesteps needing the frontend to
already know a `deck_id` at all for the current, single-deck MVP, while
remaining structurally correct if a second Deck is ever added later.

**Response shape (proposed):** a flat list of:
```json
{
  "id": "uuid",
  "name": "The Fool",
  "arcana": "major",
  "suit": null,
  "rank": "0",
  "image_ref": "...",
  "keywords": ["...", "..."]
}
```
`base_meaning_upright`/`base_meaning_reversed`/`primary_themes`/
`secondary_themes` are **not proposed for inclusion** in this listing
response — the Card Entry screen (a *selector*, per the Product Spec's
own description) needs enough to search/filter/display a card ("The
Fool," Major Arcana, an image), not its full interpretive meaning text,
which belongs to the Reading Result screen (already fully served by the
interpretation response's own citations, Step 39 Section 2E) — this
mirrors `ReadingSummary`'s own "smallest useful representation"
precedent exactly, not an arbitrary trim.

**Search/filter behavior:** **client-side, not server-side** — directly
grounded in Section 2's confirmed dataset size (78 rows total, fixed,
known, changing only at deploy/reseed time, never at runtime). A single
full-list fetch, cached for the session, searched/filtered entirely in
the browser (`arcana`/`suit`/`name` are all present in the response for
exactly this purpose), is sufficient and simpler than building
server-side search/pagination for a dataset this small and this stable.
**Pagination:** **not needed**, same reasoning — 78 rows is not a
pagination-scale dataset by any reasonable definition, and the Product
Spec's own "searchable/filterable" language describes a client-side
interaction pattern (type-to-filter), not a paged listing.

**Ordering:** by `arcana`, then `suit` (nulls — i.e. Major Arcana —
first), then `rank`/`name` — a stable, human-sensible default order
(Major Arcana 0–21, then each Minor Arcana suit in sequence) requiring
no schema change, computed entirely in the query's `ORDER BY` clause.

**Whether card names are sufficient:** not alone — `arcana`/`suit` are
needed for the Product Spec's own explicitly-named filter categories
("Major Arcana, Cups, Pentacles, Swords, Wands categories"), already
included above.

## Decks

**Endpoint:** `GET /decks`. **Method:** `GET`.

**Justification, precisely:** not for deck-*selection* UI (Q4, Section
10, left open) — for the Product Spec's own, separately-named, already
in-scope MVP screen item: "Basic Settings (Scripture preference,
translation preference if applicable, **deck info**...)"
(`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` line 509, part of the explicit "In:"
MVP list at lines 502–512). A minimal Decks listing is required for
*that* screen regardless of whether deck-switching is ever built.

**Response shape (proposed):** a list of:
```json
{"id": "uuid", "name": "Rider-Waite-Smith", "description": "...", "is_default": true}
```

**Whether the frontend needs all decks or only selectable decks:** all
— there is currently no concept of a non-selectable Deck (no
active/enabled flag on the model, same as Spread), and with exactly one
Deck seeded, the distinction is moot today regardless.

**Default deck representation:** `is_default: true/false`, a direct,
unmodified pass-through of the existing column — **proposed for
inclusion**, since it is the same value `create_reading()` already uses
server-side to resolve an omitted `deck_id`, and surfacing it lets the
Settings screen correctly label "Rider-Waite-Smith (default)" without
any client-side guesswork.

**Deck ownership:** none exists (Section 2) — this endpoint requires no
ownership filtering of any kind.

**Whether deck selection is actually part of the current MVP UI:**
**not resolved here — this is exactly Product Spec Q4**, preserved as
open in Section 10. This endpoint's design is deliberately neutral to
that question: it serves the Settings "deck info" need either way, and
would equally well serve a future deck-selector UI if Q4 is ever
resolved in that direction, without requiring any change to this
endpoint's own shape.

---

# 5. Authentication & Access Model

**Ownership-scoping is confidently ruled out** — none of `Spread`,
`SpreadPosition`, `Card`, or `Deck` carries any ownership column
(re-confirmed, Section 2), and no product requirement anywhere implies
one user's view of this data should differ from another's. Applying
`get_owned_reading`-style scoping here would be a mechanically
unjustified copy of a pattern that exists specifically to protect
*user-generated* data (Readings and everything beneath them), not
shared, seeded, global content.

**The remaining choice — public (no auth) vs. authenticated (any valid
token, no ownership check) — is not resolved by this design, per this
step's own explicit instruction (Section 10).** Both are technically
straightforward and equally consistent with this project's existing
conventions:
- **Public** would mean these four new routes take no `Depends(...)` at
  all — the simplest implementation, and defensible on the grounds that
  reference data carries no sensitivity (card meanings, spread
  structures) and every *other* public precedent in this API
  (`/auth/register`, `/auth/login`) already establishes that not every
  route requires a resolved user.
- **Authenticated** would mean these routes depend on
  `Depends(get_current_user)` only (never `get_owned_reading`, which has
  no meaning here) — defensible on the grounds of uniformity with every
  other resource-touching route in this API, even though no ownership
  check would ever actually run.

This document does not select between them. The API contract table
(Section 6) marks this explicitly as `TBD (public or authenticated —
not ownership-scoped)` rather than guessing.

---

# 6. API Contract Table

| Endpoint | Method | Auth | Params | Request Body | Response | Success | Errors | Ordering | Search/Filter | IDs |
|---|---|---|---|---|---|---|---|---|---|---|
| `/spreads` | `GET` | **TBD (public or authenticated — Section 5/10)** | none | none | `list[SpreadSummary]` (with embedded `positions`) | `200` | `401` only if authenticated variant is chosen | `name` asc | None (client-side, if any) | UUID |
| `/cards` | `GET` | **TBD (public or authenticated)** | `deck_id: UUID \| None` (query) | none | `list[CardSummary]` | `200` | `404` if a non-default `deck_id` is supplied and does not exist; `401` only if authenticated | `arcana`, `suit`, `rank`/`name` | Client-side only (dataset size, Section 4) | UUID |
| `/decks` | `GET` | **TBD (public or authenticated)** | none | none | `list[DeckSummary]` | `200` | `401` only if authenticated | insertion order (trivial, 1 row today) | None | UUID |

**All three are intended as a stable frontend contract** — once
implemented, their response shapes should be treated with the same
stability discipline this project already applies to `ReadingSummary`/
`CardDrawSummary` (additive changes only, no silent field removal),
since a frontend's Reading-creation and Card-Entry flows would depend on
them directly.

**No `GET /spreads/{id}` or `GET /decks/{id}` single-resource routes are
proposed** — with all three lists small enough to fetch in full
(Section 2/4), a single-resource-detail route would add API surface
with no consumer need it doesn't already satisfy.

---

# 7. Security Analysis

- **Accidental credential exposure:** none — none of the four proposed
  response shapes contains any authentication material, and none
  requires the client to send anything beyond (at most) an existing
  bearer token.
- **Overly broad origins:** addressed directly in Section 3 — explicit
  allowlist, no wildcard, methods and headers narrowed to exactly what
  this API uses.
- **Unnecessary authenticated access:** not applicable to CORS; for
  reference data, this is exactly Section 5's open question — this
  design does not force unnecessary authentication, but also does not
  rule it out, since "authenticated but not ownership-scoped" is not
  itself insecure, merely a stricter-than-necessary default if chosen.
- **Excessive data exposure:** checked directly — the proposed Card
  response deliberately excludes interpretive-meaning fields
  (`base_meaning_upright`/`reversed`, theme lists) not needed for a
  selector UI (Section 4); nothing proposed exposes more than the named
  screen requires.
- **User-owned data leakage:** structurally impossible — none of the
  four proposed queries joins or filters on `ReflectionSession`,
  `Reading`, `CardDraw`, or `Interpretation` in any way; they read only
  `Spread`, `SpreadPosition`, `Card`, `Deck`.
- **Enumeration risks:** minimal and not novel — Spread/Card/Deck IDs
  are already present in every existing `POST /readings` and
  `POST /readings/{id}/draws` request payload's error paths today
  (`SpreadNotFoundError`/`CardNotFoundError`/`DeckNotFoundError` already
  reveal, via a `404`, whether a *guessed* ID exists — this is
  pre-existing behavior, not introduced by this design) — listing
  endpoints do not meaningfully worsen this, since the data is
  non-sensitive reference content, not a signal about any user's
  private state.
- **Unnecessary internal fields:** checked directly against every
  proposed response shape (Section 4) — none includes a raw foreign key
  that duplicates its own nesting context (e.g., `SpreadPosition`'s own
  `spread_id` is omitted from the embedded shape, since it is redundant
  once nested under its parent Spread), matching `ReadingSummary`'s own
  established "no redundant FK" precedent.

**No security concern found that this design does not already address
or correctly leave open (Section 5) rather than over-engineer.**

---

# 8. Caching/Data Freshness Considerations

- **Does reference data change at runtime?** No — confirmed directly,
  again, for this step: no route anywhere in this API (existing or
  proposed) ever writes to `Spread`, `SpreadPosition`, `Card`, or
  `Deck`. `CardDraw` rows reference them but never mutate them.
- **Changes only through deployment/seeding:** yes — `app/seed/seed.py`
  is the sole write path, run at application startup/deploy time, not
  request time.
- **Cache-control:** **not needed for MVP correctness**, though a
  conservative `Cache-Control: public, max-age=<some value>` response
  header would be a reasonable, low-risk future addition once these
  routes exist — not designed here, since nothing in the current MVP
  requires it and adding it later is a header-only change with no
  contract impact.
- **Can the frontend safely fetch once per session?** Yes — given the
  data changes only at deploy time (Section 2/8), a single fetch per
  page load (or even per app session, held in memory/a simple client
  store) is entirely sufficient; no polling, no cache-invalidation
  mechanism, no ETag/conditional-GET design is warranted by anything in
  the actual current architecture.
- **Pagination/search need, restated from Section 4:** none — 78 Cards
  and 3 Spreads are both far below any reasonable threshold where
  server-side pagination or search would out perform a single fetch plus
  client-side filtering.

**No caching architecture is proposed.** A plain `200` JSON response, no
special headers, is sufficient.

---

# 9. Test Plan for Implementation

Not written in this step. Documented for the future implementation step
to add:

**CORS:**
- A request with the allowed local-dev origin (`http://localhost:5173`)
  in its `Origin` header receives the correct
  `Access-Control-Allow-Origin` response header.
- A request with a disallowed origin does not receive that header (and,
  per Starlette's own behavior, the browser — not the test — would be
  what actually blocks it; the test should assert the header's absence/
  mismatch, not attempt to simulate browser enforcement).
- An `OPTIONS` preflight request for a `POST` route with
  `Access-Control-Request-Headers: Authorization, Content-Type` receives
  a `200`/`204` with the matching `Access-Control-Allow-Headers` and
  `Access-Control-Allow-Methods` values.
- A request carrying an `Authorization` header cross-origin still
  succeeds against an existing authenticated route (proving the header
  allowlist doesn't accidentally block the mechanism CORS exists
  alongside).

**Reference data (once Section 5's open question is resolved):**
- `GET /spreads` returns all 3 seeded Spreads (or the then-current
  count), each with the expected fields and a correctly-populated,
  correctly-ordered `positions` array.
- `GET /spreads` ordering is alphabetical by `name`.
- Each returned Spread's `position_count` matches its own
  `len(positions)`.
- `GET /cards` with no `deck_id` returns all 78 cards from the default
  deck.
- `GET /cards?deck_id=<valid-id>` returns that deck's cards; a
  nonexistent `deck_id` returns `404`.
- `GET /cards` ordering matches the proposed `arcana`/`suit`/`rank`
  scheme.
- `GET /decks` returns the single seeded Deck with `is_default: true`.
- If the authenticated variant is chosen (Section 5): unauthenticated
  requests to each route return `401`; if the public variant is chosen:
  unauthenticated requests succeed identically to authenticated ones.
- Response schema field-set assertions (`set(body.keys()) == {...}`)
  for each of the three response shapes, mirroring this project's own
  existing convention (e.g. `test_history_entries_do_not_embed_interpretation_content`'s
  own exact-keys assertion style).
- No route anywhere accidentally exposes `base_meaning_upright`/
  `reversed`, `primary_themes`/`secondary_themes`, or any `Reading`/
  `CardDraw`/`Interpretation`-related field.

---

# 10. Product/Governance Decisions Still Open

| Question | Status |
|---|---|
| **Whether reference data should be publicly accessible or require authentication** | **Open — not resolved by this design (Section 5).** Both are technically sound; no product/security requirement forces either. |
| **Product Spec Q4 — Deck scope/default, whether the frontend should expose deck selection** | **Open, unresolved anywhere in the repository — re-confirmed present, unchanged, at `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` line 476.** This design's `GET /decks` endpoint is deliberately neutral to this question (Section 4). |
| **Unresolved layout/display requirements** (visual coordinates for rendering a spread) | **Open, and not a backend question at all** — no such data exists in the schema, and nothing in any governing document proposes adding it; a frontend-side, per-Spread-name static layout mapping is the only currently-implied approach, named but not designed here. |
| **Whether `GET /readings/{reading_id}` belongs in MVP** | **Preserved exactly as Step 39 left it — not reopened, not resolved, and explicitly not designed in this step per its own Section 6 instruction.** |
| **The exact production frontend origin for CORS** | **Open — not a product decision, a deployment-configuration task (Section 3)**; expressed as a required environment override, not guessed. |

**No product decision is resolved by this design.** Every item above is
reported exactly as open, with the technical design shaped to remain
correct regardless of how each is eventually answered.

---

# 11. Scope Boundary

**Explicitly not designed or implemented in this step:**
- `GET /readings/{reading_id}` (Reading Detail) — Step 39's Gap 3/4;
  intentionally not reopened here (Section 6 of this step's own
  instructions).
- Batch CardDraw recording — unchanged, still deferred
  (`CARDDRAW_API_DESIGN.md` §12).
- Idempotency/retry semantics for any route — unchanged, still absent
  and not proposed (`CARDDRAW_CONCURRENCY_RECONCILIATION.md` §7).
- `CardDrawSummary` display-name embedding — unchanged, still deferred;
  this design's `GET /cards` response independently satisfies the same
  underlying need (a frontend can now look up a drawn card's display
  name client-side from the reference-data fetch, without needing the
  draw response itself to embed it) without reopening or resolving that
  named question.
- Any endpoint, field, or behavior not directly required by the New
  Reading / Layout Selection / Card Entry / Settings-deck-info screens
  named in the Product Spec and cited in Sections 3–4 above.
- Any change to the existing Reading/CardDraw/Interpretation/Save/
  History lifecycle, its schemas, its error mappings, or its ownership
  model — none of this design touches any of it.
- The CardDraw concurrency question (Steps 33–36) — unchanged, remains
  accepted and documented, not reopened.
- Actual CORS implementation, actual reference-data route/schema/service
  implementation, actual tests — all deferred to a future,
  separately-authorized implementation step, exactly mirroring this
  project's own established Design → Implementation pairing.

---

# 12. Stop-Condition Assessment

**No stop condition was triggered. Implementation can proceed from this
design**, once a future step resolves Section 5's one remaining open
technical question (public vs. authenticated reference-data access) —
which is not itself a blocker to *starting* implementation, since the
implementation step could reasonably default to one choice while
flagging it for confirmation, exactly as this project's own prior
Design/Audit steps have occasionally done for comparably small,
non-architectural choices.

No genuine backend defect, no contradiction of an approved decision, and
no invented requirement was found or introduced anywhere in this design.

---

# 13. Recommended Implementation Sequence

Mirroring this project's own established Design → Implementation
pairing (most recently: Steps 31→32 for CardDraw):

1. **CORS middleware** — the smaller of the two changes; add
   `CORSMiddleware` to `app/main.py` plus the new `cors_allowed_origins`
   `Settings` field, exactly as specified in Section 3. No schema, no
   new route, no new schema module — the lowest-risk, fastest-to-verify
   piece.
2. **Reference-data schemas and routes** — `app/schemas/reference_data_api.py`
   (three response shapes, Section 4), `app/api/reference_data.py`
   (three routes, Section 6), registered in `app/main.py` alongside the
   existing three routers. Resolve Section 5's open question first (or
   flag it for a one-line confirmation before writing the `Depends(...)`
   clause), then implement exactly the contract in Sections 4/6.
3. **Tests** — per Section 9's plan.
4. **Full regression run** — confirm the existing 411 tests remain
   unaffected and the new tests pass, exactly matching this project's
   own standing verification discipline for every prior implementation
   step.

After this sequence completes, per Step 39's own final recommendation,
frontend implementation against the live API should be unblocked for
the full documented MVP workflow.
