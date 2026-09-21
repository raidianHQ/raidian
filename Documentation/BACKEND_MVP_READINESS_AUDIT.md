# Backend MVP Readiness Audit (Step 39)

Read-only audit. No application code, schema, migration, test, frontend,
or documentation file was modified in producing this report. Nothing was
committed or pushed. Every claim below was independently re-verified
against the current repository — direct source reads, a live OpenAPI
schema dump, repository-wide searches, and a fresh full test run —
rather than restated from Steps 17–38's own reports, though their
conclusions are adopted wherever this audit's own re-verification
confirms them unchanged.

---

# 1. Executive Summary

**Conditionally ready.** The authenticated Reading lifecycle itself
(register → login → create → draw → complete → interpret → reinterpret
→ save → history) is fully implemented, fully HTTP-reachable, fully
ownership-correct, and fully covered by a passing 411-test suite. No
defect was found anywhere in that lifecycle.

**Two genuine, product-spec-grounded blockers were found, both outside
the lifecycle logic itself, in areas no prior Step 17–38 audit was
scoped to examine:**

1. **No CORS middleware exists anywhere in the application.** A browser
   frontend running on any origin other than the API's own would be
   rejected by the browser itself before a request even reaches this
   backend's authorization logic. This is not a frontend concern — no
   frontend-side code can substitute for a missing `Access-Control-Allow-Origin`
   response header.
2. **No HTTP endpoint exists anywhere to list Spreads, SpreadPositions,
   Cards, or Decks.** The Product Spec's own explicit MVP scope
   (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, quoted in Section 3) names two
   screens — "New Reading — Layout Selection" (browse/select a Spread)
   and "New Reading — Card Entry" (searchable card selector) — that
   cannot be built at all without a way to fetch this reference data
   over HTTP. It currently can only be read via direct ORM/database
   access, which a browser cannot perform.

Both are small, well-understood, additive backend changes (CORS
middleware is a standard FastAPI/Starlette feature; a reference-data
listing endpoint follows the exact same thin-route-over-existing-model
pattern already used four times in this codebase) — **neither requires
a redesign of anything already built**, and neither is proposed or
implemented in this audit step, per its own read-only boundary.

No other blocker was found. Every other question this audit was asked
to investigate — response schema sufficiency, lifecycle observability,
ownership/security, error handling, token/auth mechanics, migration
state — resolved to "no issue" or "already correctly deferred," detailed
in the sections below.

---

# 2. Complete MVP HTTP Workflow

Re-verified directly against a live OpenAPI schema dump
(`app.openapi()['paths']`) and fresh source reads of every route and
schema file — not assumed from any prior step.

| Stage | Endpoint | Auth | Ownership | Request | Response | Status | Frontend-ready? |
|---|---|---|---|---|---|---|---|
| Register | `POST /auth/register` | None | N/A | `{email, password}` | `{id, email, created_at}` | `201`/`409`/`422` | Yes — see Section A |
| Login | `POST /auth/login` | None | N/A | `{email, password}` | `{access_token, token_type}` | `200`/`401`/`422` | Yes — see Section B |
| Create Reading | `POST /readings` | Bearer token | Owner = `current_user` | `{spread_id, question, question_domain?, draw_method?, deck_id?}` | `ReadingSummary` | `201`/`401`/`404`/`422` | **Conditionally** — see Section D and Gap 2 |
| Draw Card | `POST /readings/{id}/draws` | Bearer token | `get_owned_reading` | `{position_id, card_id, orientation}` | `CardDrawSummary` | `201`/`401`/`404`/`409`/`422` | **Conditionally** — see Section D and Gap 2 |
| Interpret | `POST /readings/{id}/interpret` | Bearer token | `get_owned_reading` | none | `InterpretationSummary` | `201`/`401`/`404`/`409` | Yes — see Section E |
| Reinterpret | `POST /readings/{id}/interpret` (same route) | Bearer token | `get_owned_reading` | none | `InterpretationSummary` (new `sequence`) | `201`/`401`/`404`/`409` | Yes — see Section F |
| Save | `POST /readings/{id}/save` | Bearer token | `get_owned_reading` | none | `ReadingSummary` (`status: "saved"`) | `200`/`401`/`404`/`409` | Yes — see Section G |
| History | `GET /readings` | Bearer token | filtered to `current_user` | none | `list[ReadingSummary]` | `200`/`401` | Yes — see Section H |

Detailed per-stage findings follow.

## A. Registration

`POST /auth/register` — re-read `app/schemas/auth.py` and `app/api/auth.py`
fresh. Request: `email` (min 3, max 320 chars, shape-validated),
`password` (8–128 chars, ≤72 UTF-8 bytes for bcrypt). Duplicate email →
`409`, pre-check plus `IntegrityError` backstop (Step 23). Response:
`{id, email, created_at}` — never echoes `hashed_password`. **No
authentication state is established by registration** — `UserResponse`
contains no token. **The frontend must call `/auth/login` explicitly
afterward**; this is not a gap, it is the documented contract
(`AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` Section 5.1/5.2
describes them as two separate endpoints, and no document anywhere
claims registration also logs the user in).

## B. Login

`POST /auth/login` — request `{email, password}`; response
`{access_token, token_type: "bearer"}`. Token is a signed JWT
(`sub`=user id, `iat`, `exp`), `HS256`, 24-hour expiry
(`jwt_access_token_expire_minutes`, `app/core/config.py`), no refresh
token (an explicit, already-approved decision, not a gap — Section 4).
Wrong credentials, nonexistent email, and inactive account all
collapse into one identical `401` (`InvalidCredentialsError`, no
account-existence leakage). **Browser usability:** the response is a
plain JSON body with no cookie, `Set-Cookie`, or redirect — the frontend
is expected to store the token itself (`localStorage`/memory, per
`AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` Section 13.2/14.1,
already named as a frontend-implementation-time choice, not decided
here) and attach `Authorization: Bearer <token>` to every subsequent
request.

## C. Reading Creation

`POST /readings` — re-read `app/services/reading_service.py::create_reading()`
and `app/schemas/reading_api.py::ReadingCreateRequest` fresh. Ownership
propagates from `Depends(get_current_user)` directly into
`ReflectionSession(owner=owner)` at construction — no client-suppliable
owner field exists (`extra="forbid"` rejects one as `422`). `spread_id`
required; nonexistent → `404`. `deck_id` optional, defaults to the
seeded default Deck; nonexistent → `404`. `question` required,
blank/whitespace-only rejected (`422`), max 4000 chars. `question_domain`
optional, max 60 chars, no enumerated/validated taxonomy (free text).
`draw_method` defaults to `PHYSICAL` (`DIGITAL` accepted by the enum but
implements no distinct server behavior — Section 10). Initial status is
always `DRAFTING`. **Response information:** `ReadingSummary` gives
`id`, `status`, `question`, `question_domain`, `created_at`,
`updated_at` — **it does not return `spread_id` or `deck_id`**, a
deliberate, already-named design choice (`READING_CREATION_API_DESIGN.md`
Section 8: "no current consumer... needs them"). This is directly
relevant to Gap 2 below: the frontend must retain the `spread_id` (and,
if non-default, `deck_id`) it originally chose in its own client-side
state to know which positions/cards are valid for the subsequent draw
stage — the server will not remind it.

## D. Card Drawing

`POST /readings/{id}/draws` — re-verified against `record_card_draw()`
and the route, fresh (unchanged since Step 32, docstring-corrected in
Step 36). Ownership via `get_owned_reading`. `position_id`/`card_id`
validated for existence and Spread/Deck membership (404, collapsed).
`orientation` required enum. `draw_order` server-computed, rejected if
client-supplied (`422`). Response `CardDrawSummary` includes
`reading_status`, letting the frontend learn immediately whether this
draw completed the spread — confirmed sufficient (Section 6). Completion
behavior, optional-position behavior, duplicate-card behavior, and
duplicate-position behavior are all unchanged and re-confirmed identical
to Steps 32–38's own findings (Section 7 restates the lifecycle
implications; Section 8 restates the error matrix). **Frontend-readiness
is marked "Conditional" here for exactly one reason: Gap 2** — the
frontend has everything the *lifecycle* needs from this endpoint, but no
way to discover *which* `position_id`/`card_id` values are valid to send
in the first place, absent a reference-data endpoint.

## E. Interpretation

`POST /readings/{id}/interpret` (`app/api/interpretation.py`,
re-read fresh, unchanged since Step 22's ownership retrofit). Auth via
`get_owned_reading`. Gated on `reading.is_spread_complete`
(evidence-based, not status-based) — `409` (`ReadingNotReadyForInterpretationError`)
if not yet complete. **Callable immediately after the final draw** —
confirmed directly: no additional action or delay is required between a
`201` draw response with `reading_status: "spread_complete"` and a
successful `POST .../interpret`. Response `InterpretationSummary`
embeds the full `InterpretiveModel` verbatim, including citations that
carry `card_name`/`position_name`/`position_semantic_role` — re-confirmed
by inspecting the schema (`app/schemas/interpretive_model.py`) and by
this project's own prior live response captures (Steps 29/33): the
Reading Result screen's display needs (which card, which position, which
theme) are fully satisfiable from this one response, no separate lookup
required.

## F. Reinterpretation

Same route as E — re-confirmed no separate endpoint exists or is implied
by any document. The frontend distinguishes first-interpretation from
reinterpretation entirely by **local knowledge of whether it has already
called this route for this Reading** — the response itself does not
self-label as "first" vs. "re-run," but does expose `sequence`
(monotonically increasing), which a frontend already holding a prior
response can compare directly. **Failure conditions** are identical to
first interpretation (`409` if the spread were somehow no longer
complete — structurally unreachable once complete, since nothing
un-fills a position). `GET /readings/{id}/interpretations` (history) and
`GET /readings/{id}/interpretations/current` (highest-`sequence` only)
remain available, unchanged, for a frontend that wants to show
interpretation history explicitly. No new API contract is implied or
needed here.

## G. Save

`POST /readings/{id}/save` — ownership via `get_owned_reading`.
Requires `SPREAD_COMPLETE` or `INTERPRETED`; `DRAFTING` → `409`.
Idempotent from `SAVED`. Response `ReadingSummary` with
`status: "saved"` — **sufficient**: the frontend's only actionable need
post-save (confirmation + the Reading's id/question for a "saved!" UI
state) is present.

## H. Reading History

`GET /readings` — auth via `get_current_user`; filters
`owner_id == current_user.id AND status == SAVED`; orders
`updated_at DESC`; empty history returns `200 []`, not `404`. Response
is `list[ReadingSummary]`, each carrying `id`. **Whether the frontend
can use each returned `id` to retrieve everything it needs:**
**partially** — `id` is sufficient to call
`GET /readings/{id}/interpretations` (interpretation history) and
`GET /readings/{id}/narrative` (current narrative), both of which remain
`get_owned_reading`-gated and therefore correctly scoped to the same
user. **There is no way to re-fetch the Reading's own `CardDraw` rows
(which cards were drawn, in which positions/orientations) for a saved
Reading's detail view** — no endpoint returns them. This is Gap 1 in
Section 3 below.

---

# 3. HTTP Integration Gaps

| Gap | Evidence | Classification | Blocking? | Rationale |
|---|---|---|---|---|
| **No `GET /readings/{id}/draws` (or equivalent) to list a Reading's CardDraw rows** | Confirmed via live OpenAPI dump (Section 2) — no route returns `CardDraw` data at all, for any Reading, saved or not. | **MVP blocker for the "Spread Review" and "Reading Detail" screens specifically** (Product Spec Section 6: "Spread Review — full visual layout of all positions, cards, and orientations before committing to interpretation"; "Reading History — ... Reading Detail" in the screen inventory) | **Yes, for those two named screens** | The interpretation response's citations happen to carry card/position names for whichever cards a *rule actually cited* — but citations are not guaranteed to cover every drawn card (a card contributing to no matched rule has no citation anywhere), so the interpretation response is not a reliable substitute for "show me the full spread I drew." A frontend could work around this only by never navigating away from the in-memory state it built during the drawing flow itself — which fails the moment a user reloads the page or returns to a saved Reading later, exactly the "Reading Detail" screen's own purpose. |
| **No endpoint to list Spreads/SpreadPositions** | Confirmed via live OpenAPI dump — no route anywhere returns `Spread` or `SpreadPosition` data. | **MVP blocker** | **Yes** | Product Spec: "New Reading — Layout Selection — browse/select a Layout; shows position count and short description" is explicitly in the MVP "In:" scope list (Section 5 step 2 and the screen inventory, both quoted in Section 5 below). `POST /readings` requires a `spread_id` the frontend has no way to discover. |
| **No endpoint to list Cards (or Decks)** | Same evidence. | **MVP blocker** | **Yes** | Product Spec: "Card Entry (Physical) — ... searchable/filterable card selector (Major Arcana, Cups, Pentacles, Swords, Wands categories)" is explicitly in the MVP "In:" scope list. `POST /readings/{id}/draws` requires a `card_id` the frontend has no way to discover. |
| **No CORS middleware** | Confirmed via direct read of `app/main.py` — no `CORSMiddleware` import or `add_middleware` call anywhere. | **MVP blocker for any cross-origin browser client** | **Yes, for actual browser integration; no, for starting frontend architecture/scaffolding work** | Covered in full in Section 4. |
| **No `GET /readings/{id}` (single-Reading fetch)** | Confirmed via live OpenAPI dump. Already named and deliberately deferred by `CARDDRAW_API_DESIGN.md` Section 12 (Step 31). | **Frontend convenience, not currently blocking** | No | The Product Spec's own flow (Layout Selection → Question → Draw Method → Card Entry → Spread Review → Interpret → Result → Save) is describable as one continuous client-side session; nothing in the Product Spec requires surviving a full page reload mid-creation. `CardDrawSummary`'s `reading_status` field already covers the one piece of server-owned state (spread completion) the frontend would otherwise need this route to learn. A future step could still choose to add it — not required for MVP delivery of the documented flow. |
| **`DrawMethod.DIGITAL` has no corresponding "digital draw" endpoint or server-side random-draw behavior** | Confirmed via source read — `record_card_draw()` always requires a client-specified `position_id`/`card_id`; nothing performs a server-side random draw. | **Future enhancement, already self-documented as deferred** | No | `DrawMethod`'s own docstring (`app/models/enums.py`) states plainly: "Digital is reserved for future functionality... Physical is the default and only implemented path." This is a pre-existing, deliberate scope narrowing, not a new discovery — the Product Spec's own Phase 2 ("Physical Reading Flow") names the physical path as the actual near-term delivery target, with Digital Draw appearing only in the full MVP wish-list, not the phased build order. |
| **`ReadingSummary`/`CardDrawSummary` do not echo `spread_id`/`deck_id`/`position_id`-context back after creation** | Confirmed via schema read (Section 2C/2D). | **Not actually a gap** | No | The frontend already supplied these values (or knows the single default deck exists); this is a deliberate "smallest useful representation" choice consistent with `ReadingSummary`'s own documented precedent, not a missing capability — the frontend needs to retain its own client-side session state through the linear creation flow regardless, which the Product Spec's own screen sequence already implies. |

---

# 4. Browser Compatibility

## CORS

Directly confirmed by reading `app/main.py` in full: **no CORS
middleware is configured.** No `from fastapi.middleware.cors import
CORSMiddleware`, no `app.add_middleware(...)` call of any kind exists
anywhere in the application. FastAPI/Starlette ships `CORSMiddleware`
built in (no new dependency would be required to add it), but it is not
currently wired in.

**Consequence, precisely:** a browser-based frontend served from a
different origin than this API (which is the project's own permanent
architecture per ADR-0004 — React+Vite frontend on GitHub Pages, FastAPI
backend on Render, and even in local development a Vite dev server and
a `uvicorn` process run on different ports/origins by default) would
have every cross-origin request blocked by the browser itself before any
application code on either side runs, unless the server responds with
the appropriate `Access-Control-Allow-Origin` (and, for the
`Authorization` header this API requires, `Access-Control-Allow-Headers`)
response headers. **No frontend-side workaround exists for this** — it
is exclusively a server-response-header concern.

**Is this currently a blocker, or a deployment configuration task?**
**Both, precisely separated:** the specific allowed-origins *list* (dev
server URL, eventual GitHub Pages URL) is legitimately a per-environment
configuration detail — but the *middleware itself* is application code
that does not yet exist in any form, for any origin, including
`localhost`. Local development integration (the very first thing a
frontend implementation step would need to verify) would fail today
without it. This is why Section 1 classifies it as a blocker to *actual
browser integration* while not classifying it as a blocker to *starting*
frontend architecture/scaffolding work (component structure, routing,
build tooling, and API-client code can all be written and unit-tested
against a mocked API layer before any real cross-origin call is
attempted).

## Authentication from Browser

- **Expected header format:** `Authorization: Bearer <token>` —
  confirmed via `OAuth2PasswordBearer(tokenUrl="/auth/login",
  auto_error=False)` in `app/api/dependencies.py`, unchanged since Step
  22.
- **Token lifetime:** 24 hours (`jwt_access_token_expire_minutes`),
  confirmed in `app/core/config.py`. No refresh mechanism —
  `AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` Section 7.11
  already named "no refresh tokens" as a considered, explicit decision,
  re-confirmed unchanged.
- **Retention:** the frontend is expected to store the token itself
  (`localStorage` or in-memory) — no server-set cookie exists. This is
  named, not decided, as a frontend-implementation-time choice in the
  same document, unchanged.
- **Logout:** requires nothing server-side — confirmed no
  `/auth/logout` route exists anywhere (live OpenAPI dump, Section 2) —
  logout is client-side token discard only, consistent with the stated
  design (no server-side session/token-revocation state exists to clear).
- **Malformed/expired token behavior:** re-confirmed via
  `get_current_user`'s source — any decode failure (malformed, expired,
  wrong signature, wrong algorithm) collapses to an identical `401`, no
  distinguishing detail leaked.

## API Base URL / Configuration

The backend itself has no concept of "the frontend's origin" baked into
its request-handling logic anywhere (routes do not branch on `Origin` or
`Referer`) — this is purely a *frontend*-side configuration question
(where the frontend points its HTTP client), correctly classified as
**implementation work for the frontend, not a backend deficiency.** The
backend's own listening address/port is configured externally
(`uvicorn`/deployment config), unrelated to this audit's scope.

---

# 5. Reference Data Availability

The Product Spec's own MVP scope, re-read directly and quoted here in
full for precision (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, lines 100–133 and
502–512):

> "2. User selects a Layout (spread)... 6. Physical path: user
> physically draws cards; for each Layout Position, selects the card via
> a searchable card selector and marks Upright/Reversed."
>
> Screen inventory: "New Reading — Layout Selection — browse/select a
> Layout; shows position count and short description." / "New Reading —
> Card Entry (Physical) — one interaction per Layout Position:
> searchable/filterable card selector (Major Arcana, Cups, Pentacles,
> Swords, Wands categories) + Upright/Reversed toggle."
>
> MVP "In:" scope: "New Reading: Layout selection, Question entry (+
> optional domain), Physical card entry via searchable selector,
> Upright/Reversed."

**How the frontend can currently obtain each piece of required
reference data, checked one by one:**

- **Available Spreads:** **no HTTP path exists.** `app/seed/seed.py`
  populates the `spreads`/`spread_positions` tables at application
  startup/seed time; the only way to read them today is a direct
  database query (`session.scalars(select(Spread))`, exactly what every
  backend test in this repository does) — not reachable from a browser.
- **Spread Positions:** same — no HTTP path; reachable only via the
  `Spread.positions` ORM relationship, server-side only.
- **Available Cards:** same — no HTTP path; `app/seed/seed.py` and
  `app/reference_data/rider_waite_smith/deck.yaml` are the only sources,
  both server-side/build-time artifacts, not runtime-queryable by a
  browser.
- **Deck information:** same — no HTTP path; `Deck.is_default` is
  resolvable server-side (`reading_service.py` already does this to
  default `deck_id`), but a browser has no way to learn "what decks
  exist, and which is the default" directly.
- **Any other reference data the actual UI needs:** `SemanticRole`
  (structural role of a position, e.g. "situation," "recent past") and
  `Card.keywords`/`primary_themes`/`base_meaning_upright`/`base_meaning_reversed`
  are richer reference fields already modeled and seeded but, like the
  above, not exposed anywhere over HTTP.

**Assessment, per this section's own required classification:** none of
this reference data can reasonably be obtained "another way" by a
browser client (it is not static, boilerplate, or embeddable — it is the
project's actual seeded content: 78 real card definitions with meanings/
themes and several real spread/position layouts, already living in the
database and reference-data YAML files, subject to change if reseeded).
**A reference-data endpoint (or endpoints) is genuinely required** — not
invented here, but identified as necessary by direct comparison against
the Product Spec's own explicit, already-approved MVP screen list. This
audit does not design that endpoint's shape, request/response contract,
or scope (single combined endpoint vs. one per resource type, full
card-meaning payload vs. minimal, etc.) — consistent with this step's
own read-only, no-new-API boundary; that design work belongs to a future
step, exactly mirroring how `CARDDRAW_API_DESIGN.md` was produced before
`record_card_draw()` was ever implemented.

---

# 6. Response Schema Sufficiency

Reviewed every browser-facing response schema directly
(`app/schemas/reading_api.py`, `app/schemas/auth.py`,
`app/schemas/interpretation_api.py`, `app/schemas/interpretive_model.py`,
`app/schemas/narrative_model.py`):

- **`ReadingSummary`:** sufficient for its three actual call sites
  (creation confirmation, save confirmation, history list entry) — no
  field is undocumented-ORM-dependent; every field is a plain,
  documented, already-typed value. Insufficient *on its own* for a
  "Spread Review"/"Reading Detail" screen, but this is exactly Gap 1
  (Section 3), not a defect in the schema's own designed scope.
- **`CardDrawSummary`:** sufficient for the immediate post-draw UI
  update (confirmation + `reading_status`); does not embed card/position
  display names (Section 10 — deliberately deferred, not silently
  assumed).
- **Authentication responses** (`UserResponse`, `TokenResponse`):
  sufficient — no password material ever returned; token is a plain,
  browser-storable string.
- **Interpretation responses** (`InterpretationSummary`): sufficient and
  notably rich — the embedded `InterpretiveModel`'s citations carry
  `card_name`/`position_name`/`position_semantic_role` directly, so the
  Reading Result screen's display does not depend on any separate
  reference-data lookup for the cards a citation actually names.
- **Narrative responses** (`NarrativeModel`): sufficient — every
  section's `statements[].text` is already human-readable prose, ready
  to render directly; no undocumented field dependency found.
- **History responses:** sufficient for the list view itself (Section
  2H); insufficient, same as `ReadingSummary` above, for a detail view
  needing the actual drawn cards — Gap 1.

**No response schema requires the frontend to depend on an undocumented
ORM/model field.** Every gap found in this audit is an *absent
endpoint*, not an *insufficient schema* on an endpoint that already
exists.

---

# 7. Lifecycle Synchronization

Traced directly against current source, re-confirming Steps 29/33's own
findings still hold and adding the response-visibility angle this step's
brief specifically asks for:

- **`DRAFTING` → card draws → `SPREAD_COMPLETE`:** externally observable
  — every successful draw's response includes `reading_status`, which
  flips to `"spread_complete"` on exactly the draw that completes the
  spread (re-confirmed, Section 2D). No frontend-side inference (e.g.,
  "count how many positions I've filled") is required, though a frontend
  *could* additionally track this client-side if useful for progressive
  UI (e.g., a "2 of 3 drawn" indicator) — optional, not required.
- **`SPREAD_COMPLETE` → interpretation → `INTERPRETED`:** the
  interpretation response does not itself echo the Reading's new
  `status` field (`InterpretationSummary` has no `reading_status` field,
  unlike `CardDrawSummary`) — **a minor asymmetry, not a synchronization
  problem**, because interpretation's precondition (`is_spread_complete`)
  and its `201` response together already tell the frontend everything
  it needs: interpretation only ever succeeds when the Reading is at
  least `SPREAD_COMPLETE`, and a successful interpretation call is itself
  proof the Reading is now `INTERPRETED` (or remains `SAVED`, per Q4) —
  the frontend does not need to separately fetch `status` to know this,
  since the very fact of a `201` response is the confirmation. Flagged
  here as an observed asymmetry with `CardDrawSummary`'s own design, not
  as a defect.
- **`INTERPRETED` → save → `SAVED`:** externally observable — the save
  response's `status` field directly confirms `"saved"`.
- **No frontend-only inference is required anywhere the backend already
  owns the state** — re-confirmed across every transition; the one
  asymmetry noted above does not require inference, only relies on a
  `201` status code as the confirming signal instead of an explicit
  field, which is a legitimate (if slightly inconsistent) API design,
  not a gap.

**No genuine synchronization problem was found.**

---

# 8. Error Handling

Frontend-relevant error matrix, re-verified against live source for
every route (`app/api/auth.py`, `app/api/reading.py`,
`app/api/interpretation.py`) and `app/api/dependencies.py`:

| Status | When | Frontend-distinguishable? |
|---|---|---|
| `401` | Missing/expired/malformed/wrong-signature token; inactive account; wrong login credentials | Yes — identical body (`"Not authenticated"` or `"Incorrect email or password"` per route) always means "re-authenticate," never leaks which specific condition applied |
| `404` | Reading/position/card doesn't exist, or exists but isn't the caller's/doesn't belong to the right spread/deck | Yes, per-route distinguishable via the `detail` message (`"Reading not found"`, `"Spread position not found"`, `"Card not found"`), though ownership-vs-nonexistence is *deliberately* not distinguishable within the "Reading not found" case (Section 9) |
| `409` | `ReadingNotSaveableError`, `ReadingNotReadyForInterpretationError`, `ReadingNotDraftingError`, `DuplicateCardError`, `PositionAlreadyDrawnError`, `EmailAlreadyRegisteredError` | Yes — each carries a distinct, human-readable `detail` string suitable for direct display or for driving specific UI branches (e.g., "this position is already filled, pick another") |
| `422` | Pydantic/FastAPI validation failures (malformed UUID, missing/unknown field, blank question, invalid enum value) | Yes — FastAPI's structured `detail` array names the offending field and reason, sufficient for field-level form validation UI |
| `500` (unhandled) | **Known, accepted, not eliminated:** a genuine concurrent `draw_order` race (same-position or different-position) — Steps 33–36's own conclusion, preserved unchanged here | **Not cleanly distinguishable from any other unexpected server error** — this is the one place the frontend cannot build a specific "someone else just drew, please retry" UI branch, because the backend does not currently produce a distinct signal for it. This is not re-litigated as a new blocker; it is restated, unchanged, from the already-accepted Step 35 conclusion (Option A: documented and accepted, not fixed). |

**Preserved exactly, per this step's own explicit instruction:** the
single-writer/no-locking limitation remains accepted; no idempotency
guarantee exists; no retry guarantee exists; a concurrent race is *not*
guaranteed to produce `PositionAlreadyDrawnError` specifically (it may
surface as an unhandled `500` instead, for either race shape) — this
audit re-confirms, rather than revisits, that conclusion.

---

# 9. Ownership/Security Verification

Re-proven directly for this step (not assumed from Step 33/38's own
prior proofs), by source re-inspection of every route file and
`app/api/dependencies.py`:

- **Unauthenticated requests fail:** every workflow route except
  `/auth/register` and `/auth/login` depends, directly or transitively,
  on `get_current_user` — confirmed by checking every route's
  `Depends(...)` signature in `app/api/reading.py` and
  `app/api/interpretation.py`.
- **Cross-user access fails:** `get_owned_reading` collapses "not yours"
  and "doesn't exist" into an identical `404` — unchanged since Step 22,
  re-confirmed present on every route that resolves an existing Reading
  (`/draws`, `/save`, `/interpret`, `/interpretations`,
  `/interpretations/current`, `/narrative`).
- **`NULL`-owner Readings fail closed:** same mechanism, same guarantee
  — `reading.reflection_session.owner_id != current_user.id` is `True`
  for any authenticated user when `owner_id` is `NULL`, since no user's
  `id` ever equals `NULL`.
- **Ownership established at Reading creation:** `create_reading()`
  requires a non-optional `owner: User` — structurally impossible to
  construct an owned-later or ownerless-then-claimed Reading through the
  API.
- **CardDraw does not duplicate ownership:** `CardDraw` has no
  ownership-related column of any kind (re-confirmed, full column list
  read directly from `app/models/card_draw.py`); ownership is resolved
  exclusively by following `reading_id` → `reflection_session_id` →
  `owner_id`.
- **History returns only the current user's saved Readings:**
  `list_saved_readings_route()`'s query filters
  `ReflectionSession.owner_id == current_user.id` directly in the SQL,
  not merely by post-filtering in Python — re-confirmed by source read.

**No new authorization mechanism was found necessary, proposed, or
added.**

---

# 10. Product/API Decision Status

| Question | Classification | Blocking frontend implementation? |
|---|---|---|
| Batch vs. single CardDraw per request | Deliberately deferred (`CARDDRAW_API_DESIGN.md` §12) | **No** — a frontend can call the single-draw endpoint once per position exactly as the Product Spec's own "one interaction per Layout Position" flow already describes; batching would be an optimization, not a requirement. |
| CardDraw display-name embedding | Deliberately deferred (same document) | **No** — Gap 2's reference-data endpoint, once it exists, gives the frontend card/position names independently; `CardDrawSummary` not embedding them is not itself blocking as long as that lookup exists somewhere. |
| Whether `GET /readings/{id}` should exist | Deliberately deferred (same document); reassessed in Section 3 of this audit | **No** — see Gap table reasoning; not required for the documented linear flow. |
| Idempotency/retry semantics | Explicitly documented as absent (`CARDDRAW_CONCURRENCY_RECONCILIATION.md` §7) | **No** — no product requirement demands it; the frontend can treat a `500` as a generic "something went wrong, please try again" case without a specific contract. |
| `DrawMethod.DIGITAL` / Digital Draw | Deliberately deferred, self-documented in the enum itself | **No** — Physical is the documented default and the actual near-term delivery target (Product Spec Phase 2). |
| Reference-data endpoint existence (Spreads/Positions/Cards/Decks) | **Not previously named by any Step 17–38 document — newly identified by this audit** | **Yes** — see Section 5/Gap table; this is the one item in this table that is genuinely blocking, and it was not a previously-deferred decision so much as a scope area no prior step's own boundary happened to cover (every prior CardDraw/Reading step audited the *lifecycle*, not the *reference-data-serving* surface). |
| CORS configuration | **Not previously named by any Step 17–38 document — newly identified by this audit** | **Yes**, for actual browser integration — see Section 4. |

**No product decision is resolved by this audit.** The two newly
identified items are reported as backend-implementation gaps (Section
13), not as product decisions requiring a human choice — nothing about
*what* reference data to expose or *which* origins to allow is
ambiguous or contested; both are mechanical completions of already-clear
requirements (the Product Spec already names the screens; ADR-0004
already names the two-origin deployment architecture).

---

# 11. Test Coverage

- **Direct API-level tests exist for:** registration, login, Reading
  creation, CardDraw recording (30 tests), save, history, and all four
  interpretation/narrative routes, plus a dedicated ownership test file
  (`test_ownership.py`) proving the 401/404/collapsing behavior across
  every route — all re-confirmed present and passing (Section 12).
- **Integration coverage:** the full HTTP chain
  (create→draw→draw→draw→interpret→reinterpret→save→history) is not
  codified as a single permanent test anywhere in the suite — it has
  only ever been exercised by this project's own throwaway audit scripts
  (Steps 29, 33, 38's own predecessor audits), consistent with
  `CARDDRAW_API_CONTRACT_RECONCILIATION.md` §7's own, unchanged finding.
- **Covered only through lower-level tests:** `Reading.add_card_draw()`'s
  own model-level behavior (`test_card_draw.py`,
  `test_reading_lifecycle.py`) is exercised directly via ORM calls, not
  HTTP — appropriate, since these are unit tests of the domain method
  the HTTP layer itself delegates to, not a substitute for HTTP-level
  coverage (which exists separately in `test_api_reading.py`).
- **Critical browser-facing contracts with no meaningful test
  coverage:** **the two gaps this audit found (reference data, CORS)
  have zero test coverage anywhere in the suite, for the simple reason
  that no such endpoint or middleware exists to test.** This is not a
  test-coverage defect — there is nothing to cover yet.
- **Tests encoding implementation details as product guarantees:** none
  newly found; `CARDDRAW_API_CONTRACT_RECONCILIATION.md` §7 already
  checked this specifically for the CardDraw test set and found none —
  re-confirmed unchanged by this audit's own fresh review of the same
  test file.

**No test was added, modified, or deleted in this step.** Full suite:
**411 passed, 0 failed, 2 warnings** (Section 13).

---

# 12. Migration/Database Readiness

- **Alembic head:** single head, `5dc3cb471b18` — re-confirmed via
  `alembic heads`.
- **Migration chain:** 6 files, linear, no branch — re-confirmed via
  file count and (unchanged since Step 33's own explicit
  upgrade/downgrade round-trip test) no evidence of drift since.
- **Schema consistency:** re-confirmed no pending model change lacks a
  corresponding migration — `git status` shows no modification to any
  model file's column/constraint definitions beyond the docstring-only
  edits already accounted for in Steps 36–37.
- **Ownership FK:** `reflection_sessions.owner_id` → `users.id`,
  `ON DELETE CASCADE`, indexed — unchanged, re-confirmed present in the
  migration and matching the live model.
- **Relevant uniqueness constraints:** `users.email` (unique),
  `card_draws (reading_id, position_id)` (unique),
  `card_draws (reading_id, draw_order)` (unique),
  `readings.reflection_session_id` (unique) — all re-confirmed present
  and unchanged.
- **No pending migration is required by the current MVP backend** —
  every gap this audit identified (Section 3) is an *additive HTTP
  surface* concern (new routes reading already-existing, already-seeded
  tables) or a *middleware* concern (CORS), neither of which requires
  any schema change.

---

# 13. Findings Classification

| # | Finding | Classification |
|---|---|---|
| 1 | No HTTP endpoint for Spread/SpreadPosition/Card/Deck reference data | **Backend implementation blocker** — required by the Product Spec's own named MVP screens; not previously scoped by any prior step. |
| 2 | No CORS middleware | **Backend implementation blocker** — required for any cross-origin browser client, which is this project's permanent architecture (ADR-0004), not merely a dev convenience. |
| 3 | No `GET /readings/{id}/draws` (or equivalent) to recover a Reading's drawn cards | **Backend implementation blocker for the "Spread Review"/"Reading Detail" screens specifically** — narrower in scope than #1/#2 (only blocks re-fetching already-drawn state, not the initial draw flow itself), but genuinely required by the named screens per Section 3's own reasoning. |
| 4 | No `GET /readings/{id}` | **Frontend implementation task / not currently blocking** — the linear creation flow does not require it; already correctly named as deferred. |
| 5 | `DrawMethod.DIGITAL` unimplemented | **Deliberately deferred, already self-documented** — not a new finding. |
| 6 | `InterpretationSummary` lacks a `reading_status` field (asymmetry with `CardDrawSummary`) | **No issue** — the `201` status code itself already conveys the needed confirmation; noted, not classified as a defect. |
| 7 | Concurrent `draw_order` race can surface as an unhandled `500` | **No issue — already documented and accepted (Steps 33–36)**, explicitly preserved unchanged by this audit's own instruction. |
| 8 | `CARDDRAW_API_DESIGN.md`'s superseded concurrency claim | **Historical/point-in-time** — unchanged status from Step 38. |
| 9 | Everything else audited (Sections 2, 6, 7, 9, 11, 12) | **No issue.** |

**No documentation correction and no product/governance decision is
required by this audit's own findings** — findings 1–3 are
implementation gaps with a clear, already-approved requirement behind
them (the Product Spec and ADR-0004, both pre-existing, both already
governance-approved), not open questions needing a human product choice.

---

# 14. Stop-Condition Assessment

**Two findings require resolution before full browser-based frontend
integration can be verified end-to-end: Finding 1 (reference data) and
Finding 2 (CORS).** Finding 3 (CardDraw re-fetch) blocks two specific,
named screens but not the initial Reading-creation-through-save flow.

**None of these is a defect in anything already built** — the entire
authenticated Reading/CardDraw/Interpretation/Save/History lifecycle
this project has spent Steps 17–38 designing, implementing, and
auditing is correct, complete, and ready exactly as built. The stop
condition here is narrower and more specific than "the backend is not
ready": it is "two small, well-defined, additive pieces of backend
surface do not exist yet, and the Product Spec's own named MVP screens
depend on them."

---

# 15. Final Recommendation

**Do not begin browser-integrated frontend implementation against the
live API until Findings 1 and 2 are addressed** — not because the
existing lifecycle is unsound, but because a browser literally cannot
call this API cross-origin (Finding 2) and cannot discover the data
needed to construct valid Reading-creation and CardDraw requests
(Finding 1) no matter how correct the lifecycle endpoints themselves
are.

**Frontend architecture and scaffolding work (routing, component
structure, build tooling, state-management design, API-client code
written against the already-stable, already-documented contract in
Sections 2 and Documentation/CARDDRAW_API_DESIGN.md /
READING_CREATION_API_DESIGN.md / SAVE_READING_DESIGN.md /
READING_HISTORY_OWNERSHIP_DESIGN.md) can reasonably begin now**, since
none of it depends on Findings 1–3 being resolved first — it depends on
the *shape* of the already-stable, already-audited contract, which this
step reconfirms is not going to change.

**Recommended next step:** a Design/Audit pass (mirroring this entire
series' own established Design → Implementation pairing) for exactly
two, narrowly-scoped additions:
1. A reference-data HTTP surface (Finding 1) — its exact shape (one
   endpoint vs. several, full vs. minimal card payload, whether
   `SpreadPosition`/`Card` reference fields like `base_meaning_upright`
   belong in an MVP payload or a later one) is a genuine design question
   this audit does not resolve.
2. CORS middleware configuration (Finding 2) — its exact allowed-origin
   list is an environment/deployment detail, not a design question, but
   still deserves the same explicit, documented treatment this project
   gives every other backend surface change.

Finding 3 (CardDraw re-fetch) can be folded into either that same step
or deferred slightly further, at the next step's own discretion, since
it blocks only two specific screens rather than the entire creation
flow.

**Per this step's own final boundary: unless a future audit discovers a
genuine backend defect or a requirement the existing approved MVP
contract cannot satisfy, no further general backend audit is proposed.**
The two blockers this audit found are implementation gaps with a clear
path forward, not open design questions requiring repeated
re-examination.

---

# 16. Final Repository/Test State

- **Test count:** 411 passed, 0 failed.
- **Warnings:** 2 — the same pre-existing `InsecureKeyLengthWarning`s
  from `test_security.py`, unchanged in cause and count since Step 22.
- **Migration head:** single head, `5dc3cb471b18`; 6 migration files.
- **`git diff --check`:** clean, no whitespace errors (exit code 0).
- **`git status --porcelain`** at the end of this step:
  ```
   M README.md
   M backend/app/api/reading.py
   M backend/app/models/exceptions.py
   M backend/app/models/reflection_session.py
   M backend/app/schemas/reading_api.py
   M backend/app/services/reading_service.py
   M backend/tests/test_api_reading.py
  ?? Documentation/AUTHENTICATION_OWNERSHIP_DESIGN.md
  ?? Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
  ?? Documentation/BACKEND_MVP_READINESS_AUDIT.md
  ?? Documentation/CARDDRAW_API_CONTRACT_RECONCILIATION.md
  ?? Documentation/CARDDRAW_API_DESIGN.md
  ?? Documentation/CARDDRAW_CONCURRENCY_DESIGN.md
  ?? Documentation/CARDDRAW_CONCURRENCY_RECONCILIATION.md
  ?? Documentation/CARDDRAW_POST_IMPLEMENTATION_AUDIT.md
  ?? Documentation/POST_IMPLEMENTATION_DOCUMENTATION_RECONCILIATION.md
  ?? Documentation/PRODUCT_DECISIONS.md
  ?? Documentation/READING_CREATION_API_DESIGN.md
  ?? Documentation/READING_CREATION_OWNERSHIP_DESIGN.md
  ?? Documentation/READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md
  ?? Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md
  ?? Documentation/READING_LIFECYCLE_POST_IMPLEMENTATION_AUDIT.md
  ?? Documentation/SAVE_READING_DESIGN.md
  ```
  Exactly Step 38's own end state, with
  `Documentation/BACKEND_MVP_READINESS_AUDIT.md` added as the only new
  file. `README.md`'s pre-existing diff is unchanged.
- **Files changed by this step:** none. Only one new file created.
- **Nothing committed or pushed.**
