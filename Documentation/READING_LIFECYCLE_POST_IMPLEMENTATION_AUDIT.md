# Reading Lifecycle & Ownership — Post-Implementation Audit (Step 29)

Read-only audit. No code, schema, migration, test, frontend, or other
documentation file was modified in producing this report. All findings
below were independently re-verified against the current repository state
— by direct code inspection, by running the existing test suite, and by
executing purpose-built integration checks (a standalone TestClient-driven
end-to-end script, and direct ORM probes) — rather than assumed from any
prior implementation report.

---

# 1. Scope and Baseline

- **Baseline commit:** `ce1a7fb` ("feat: implement authentication,
  ownership, and Reading save/history/creation").
- **Test suite result at time of this audit:** `381 passed, 2 warnings`
  (re-run fresh; the actual number, not assumed from Step 28's report —
  see Section 9 for detail). Warnings are the same two pre-existing
  `InsecureKeyLengthWarning`s from `test_security.py`'s deliberately
  undersized negative-path secrets.
- **Migration head:** single head `5dc3cb471b18`, 6 migration files.
- **Purpose:** determine whether the Step 22–27 authentication/ownership/
  Save/History/creation work actually closes the architectural gap Step 21
  identified (no production code could create a Reading, so ownership
  could not propagate to new data) and whether creation → draw → complete
  → interpret → save → history now forms a coherent, secure, end-to-end
  lifecycle.

---

# 2. Directly Verified Current Behavior

Verification method: a standalone script (`scratchpad/audit_e2e.py`, not
part of the repository) was run against a live `TestClient` and a real
in-memory SQLite database — registering two independent users, creating a
Reading via `POST /readings`, drawing cards directly via
`Reading.add_card_draw()` (the only production path — see Section 10),
interpreting, reinterpreting, saving, and querying history — asserting 39
independent conditions end to end. **All 39 passed.** In addition, three
targeted direct-ORM probes were run outside the test suite: (a) an
`is_spread_complete` check with a `SpreadPosition(required=False)`
position deliberately left undrawn, (b) a full `alembic upgrade head` /
`alembic downgrade base` round-trip against a throwaway database (deleted
afterward, no artifact left in the repository), and (c) a schema
inspection of the resulting `users`/`reflection_sessions` tables.

Selected results (full list available in the transcript; representative
subset below):

| Claim | Verified |
|---|---|
| `POST /readings` requires authentication | 401 without a token |
| Caller-supplied `owner_id` cannot influence ownership | rejected with 422 (`extra_forbidden`) before reaching the service layer |
| `ReflectionSession.owner_id` set to the authenticated caller | confirmed by direct row read, compared against the JWT `sub` claim |
| `Reading.reflection_session_id` populated | confirmed |
| New Reading starts `DRAFTING`, 0 CardDraws, 0 Interpretations | confirmed |
| Nonexistent `spread_id`/`deck_id` | 404, not 500 |
| Blank/whitespace question, malformed UUID (body and path) | 422, not 500 |
| Cross-user access (interpretation routes, save, narrative) | 404, identical to a nonexistent-Reading 404 |
| `NULL owner_id` Reading (constructed directly, bypassing the API) | 404 to every authenticated caller — fails closed |
| Interpreting a 0-draw `DRAFTING` Reading | 409, not 500 |
| All required positions drawn | auto-advances to `SPREAD_COMPLETE` |
| Draw attempted after `SPREAD_COMPLETE` | `ReadingNotDraftingError` raised |
| Reinterpretation, including after `SAVED` | new `Interpretation` row each time, `status` stays `SAVED`, 3 rows accumulate |
| History after save | Reading appears exactly once despite 3 interpretations; user B's history is empty; unauthenticated `GET /readings` is 401 |
| Narrative | 404 for a non-owner, 200 for the owner |
| Forced post-flush failure during creation (`_to_summary` monkeypatched to raise) | no orphaned `Reading` row afterward — rollback confirmed |
| `SpreadPosition(required=False)` left undrawn | `is_spread_complete` is `True`, `status` advances to `SPREAD_COMPLETE` once only the required position is filled — confirmed directly; **no existing test constructs this case** (Section 11) |
| `alembic upgrade head` → `downgrade base` | clean in both directions against a throwaway SQLite database; no artifact left behind |
| `users.email` index | unique (`ix_users_email`, `unique=1`) |
| `reflection_sessions.owner_id` FK | `ON DELETE CASCADE`, confirmed via `PRAGMA foreign_key_list` |
| `reflection_sessions.owner_id` index | present, non-unique (correct — many sessions per owner) |

---

# 3. End-to-End Lifecycle Trace

The full chain named in the audit brief —

```
authenticated User → owned ReflectionSession → Reading → CardDraws
  → SPREAD_COMPLETE → Interpretation history → SAVED → authenticated Reading History
```

was traced and **every step except one is reachable over HTTP and was
exercised as such** (creation, interpret, reinterpret, save, history, and
narrative all went through real routes in Section 2's script). The
exception: **there is still no HTTP route that records a CardDraw.**
`Reading.add_card_draw()` (the sole production-code path that creates a
`CardDraw`, confirmed by repository-wide search — Section 10) is called
from exactly one place: `tests/interpretation_helpers.py`, a test helper.
No file under `app/api/` references it. The audit script above had to call
it directly against an ORM session to advance the Reading past `DRAFTING`,
exactly as every existing test in this repository already does.

**This is not a newly discovered defect.** It is a pre-existing, explicitly
named, deliberately out-of-scope gap: `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md`
Section 2.6 ("No route exists anywhere that creates a Reading, records a
draw, or saves a Reading"), and `READING_CREATION_OWNERSHIP_DESIGN.md`
Sections 16/332 ("**The draw-recording API**... `Reading.add_card_draw()`
is already fully implemented and tested (Step 16), but no route calls it
anywhere, and designing that route is a distinct, separately-scoped piece
of future work"), both name it by design, before Step 27 was implemented.
Step 27's own scope (`READING_CREATION_API_DESIGN.md`) never claimed to
close it.

**Conclusion on Section 13's question:** the architectural gap Step 21
identified — *no production code could create a Reading, so ownership
could not propagate* — **is genuinely closed.** Creation, ownership
propagation, interpretation, save, and history now form a coherent,
correctly-secured, fully HTTP-reachable chain. The *separate* gap — no
HTTP route exists to record a card draw — was never claimed closed by
Steps 22–27 and remains exactly as documented before this step. The full
chain as literally listed in the audit brief is only completable end-to-end
via direct ORM access for the draw step; every other step is
HTTP-reachable and ownership-correct.

---

# 4. Ownership / Security Findings

- **No bypass found.** Exactly one production code path constructs a
  `Reading` (`app/services/reading_service.py::create_reading()`) and
  exactly one constructs a `ReflectionSession` (the same function). Both
  require a non-optional `User` parameter (`owner: User`, not
  `User | None`) — structurally impossible to reach without an
  authenticated caller (see Section 10).
- `get_owned_reading` (`app/api/dependencies.py`) is the single
  authorization boundary for every route that resolves an existing
  Reading (`/interpret`, `/interpretations/current`, `/interpretations`,
  `/narrative`, `/save` — 5 routes total, all confirmed via
  `APIRouter(prefix=...)` grep, Section 10). It runs as a FastAPI
  dependency, resolved before the route body executes — confirmed both by
  reading FastAPI's dependency-resolution order and, empirically, by the
  pre-existing `test_ownership.py::test_orchestration_is_not_invoked_*`
  tests plus this audit's own forced-failure probe.
- Nonexistent-Reading and owned-by-someone-else-Reading collapse to an
  identical `404` body — re-verified directly (Section 2), not merely
  re-read from the design doc.
- A `NULL owner_id` Reading (constructed by bypassing the API entirely,
  simulating pre-Step-22 legacy data) is inaccessible to every
  authenticated user — fails closed, re-verified directly.
- `POST /readings` rejects a client-supplied `owner_id` field outright
  (`extra_forbidden`, 422) before any service code runs — `ReadingCreateRequest`'s
  `extra="forbid"` config, inherited from its shared `_Model` base, is
  the enforcement mechanism.

**No security/ownership bypass was found. No stop condition was
triggered.**

---

# 5. Lifecycle Findings

- `is_spread_complete` uses required-position-set coverage
  (`required_position_ids.issubset(drawn_position_ids)`), not draw count —
  confirmed by direct code read and by the optional-position probe
  (Section 2): a spread with one required and one optional position
  reaches `SPREAD_COMPLETE` with only the required position filled.
- Every seeded, real spread (`Celtic Cross`, `Single Card`, `Three Card`)
  has **every** position marked `required: true` — confirmed by grepping
  `app/reference_data/spreads/*.yaml`. The `required=False` code path is
  real, correctly implemented, and directly verified in this audit, but is
  **not exercised by any actual reference data or by any test** — a
  coverage gap, not a behavior gap (Section 11).
- `DRAFTING` permits draws; `SPREAD_COMPLETE`/`INTERPRETED`/`SAVED` all
  reject further draws via `ReadingNotDraftingError` — confirmed directly.
- A failed draw (duplicate card, wrong spread/deck, wrong status) raises
  before `self.card_draws.append(draw)` or the status check runs, so it
  cannot accidentally advance status — confirmed by code read; the
  duplicate-card and cross-spread/deck rejection paths are already covered
  by `tests/test_card_draw.py`.
- Interpretation is gated by `reading.is_spread_complete`
  (`reading_orchestration.py::interpret_reading()`), explicitly **not**
  by `reading.status` — confirmed by code read (the check is a property
  evaluation, not a status comparison) and by this audit's own probe
  (interpreting succeeds immediately once the required position is
  filled, regardless of `status`'s exact value).
- Reinterpretation always creates a new `Interpretation` row and never
  reuses/overwrites one; `save_interpretation()`'s status transition is
  conditional (`DRAFTING/SPREAD_COMPLETE → INTERPRETED`, `SAVED` left
  untouched) — confirmed directly, including the specific
  reinterpret-after-`SAVED` case (3 interpretation rows accumulated,
  status remained `SAVED` throughout).
- This matches the approved Q4 decision (`PRODUCT_DECISIONS.md`): "current"
  interpretation is always highest-`sequence`, no pinning mechanism
  exists, and none was expected to.

---

# 6. Save / History Findings

- `mark_saved()`: `DRAFTING` raises `ReadingNotSaveableError`;
  `SPREAD_COMPLETE`/`INTERPRETED` succeed; `SAVED` is a no-op (idempotent,
  not an error) — all confirmed directly.
- Saving touches only `Reading.status`; it creates no `CardDraw`,
  `Interpretation`, or narrative row, and does not invoke narrative
  generation — confirmed by code read (`mark_saved()`'s body is a single
  status assignment) and reused from `test_api_reading.py`'s existing
  `test_save_does_not_*` tests, which were re-run as part of the full
  suite (Section 9).
- Cross-user save attempts fail via `get_owned_reading` (404) **before**
  `save_reading_route()`'s body — i.e. before `mark_saved()` is ever
  called — confirmed directly (Section 2: `user B saving user A's reading
  returns 404`).
- `GET /readings` requires authentication (401 unauthenticated, confirmed
  directly); filters on `status == SAVED` and `owner_id == current_user.id`
  in one query, joining only `ReflectionSession` — never `Interpretation`
  — so a Reading with 3 interpretations still appears exactly once
  (confirmed directly, not merely inferred from the query shape).
- Empty history returns `200 []`, not 404 — confirmed by the existing
  `test_empty_history_returns_200_with_empty_list` test (re-run,
  passing) and consistent with the route's own `list[ReadingSummary]`
  response model (an empty list serializes as `200 []` by construction).
- No orchestration/engine/narrative function is called anywhere in the
  History route (`app/api/reading.py::list_saved_readings_route()`) —
  confirmed by direct code read; it performs one `select(Reading).join(...)`
  and nothing else.

---

# 7. Narrative Findings

- `app/services/narrative/` (`assembler.py`, `sections.py`,
  `humanize.py`) remains a fully deterministic, template-based assembler
  — confirmed by direct code/grep: no AI-provider import, no Reflection
  Engine reference anywhere in that package.
- No Reflection Engine module exists anywhere in the repository (confirmed
  by `find`), and the four prompt files
  `NARRATIVE_LAYER_DESIGN.md`/Product Spec Section 3.3 name
  (`prompts/system/reflection_engine.md`, `prompts/system/safety.md`,
  `prompts/system/tone.md`, `prompts/interpretation.md`) remain 0 bytes —
  confirmed directly, unchanged since `PRODUCT_DECISIONS.md`'s own Q1
  finding.
- Narrative generation can occur only via `GET /readings/{id}/narrative`,
  which calls `get_narrative_for_reading()` → `get_current_interpretation()`
  (a read) → `assemble_narrative()` (pure, database-free) — confirmed by
  code read. No creation, draw, save, or history code path calls any
  narrative function — confirmed by grepping every caller of
  `assemble_narrative`/`get_narrative_for_reading` (exactly one call site
  each, both inside `reading_orchestration.py`/`app/api/interpretation.py`'s
  narrative route).
- Narrative retrieval respects ownership: it sits behind
  `get_owned_reading` exactly like every other interpretation-family
  route — confirmed directly (user B: 404; user A: 200).
- **Product Spec language still inaccurate, unchanged:** `RAIDIAN_WISE_PRODUCT_SPEC_V1.md`
  Sections 3.3/5(step 11)/12/20(Phase 4) still state, unconditionally,
  that Narrative Generation is AI-authored via the Reflection Engine, with
  no mention of the deterministic `[A]` MVP substitute actually shipped.
  This is **not a new finding** — `PRODUCT_DECISIONS.md` Q1 already
  identified and formally recommended a governance fix for exactly this
  (Section 8, item 1: "An ADR or a Product Spec revision recording Q1's
  staged narrative decision... the single most consequential item here").
  Re-verified directly: that governance action **still has not been
  performed** — the Product Spec text is unchanged, and no new ADR beyond
  ADR-0006 exists in `docs/DECISIONS.md`. This remains an open, tracked,
  pre-existing governance action, not something Steps 22–27 introduced or
  worsened.

Not redesigned here, per instruction.

---

# 8. API Consistency Findings

- Every Reading-touching route returns `ReadingSummary` or
  `InterpretationSummary`/`InterpretationHistoryEntry`/`NarrativeModel` —
  consistent, resource-appropriate response models; no route returns a
  raw ORM object or an ad hoc dict.
- HTTP status codes are consistent: `201` for creation (Reading and
  Interpretation), `200` for reads/save/idempotent-save, `401` for every
  authentication failure (identical body, `"Not authenticated"`), `404`
  for every not-found/not-owned case (identical body,
  `"Reading not found"`), `409` for `ReadingNotSaveableError`/
  `ReadingNotReadyForInterpretationError`, `422` for Pydantic validation
  failures.
- No response schema exposes an internal field: `UserResponse` excludes
  `hashed_password`; `ReadingSummary` excludes `reflection_session_id`,
  `spread_id`, `deck_id`, `draw_method`; no schema anywhere includes
  `owner_id`. Confirmed by direct read of every schema file in
  `app/schemas/`.
- No ownership leakage: nothing in any response body reveals whether a
  `reading_id` belongs to another user versus not existing at all (same
  404 body either way, Section 2).
- `ReadingSummary` reused verbatim across three call sites (creation
  response, save response, each history list entry) — no duplicated
  shape.
- **`ReadingSummary` sufficiency for creation:** `READING_CREATION_API_DESIGN.md`
  already named, as an explicit open question (not a defect), that a
  future draw-recording client would plausibly need `spread_id`/`deck_id`/
  `draw_method` from the creation response, which `ReadingSummary`
  omits — deliberately deferred to that future step rather than decided
  or invented here. Confirmed unchanged; not resolved by this audit
  either, per instruction not to make product decisions.

---

# 9. Database / Migration Integrity

- `alembic heads` → single head, `5dc3cb471b18`.
- Ordering (`alembic history`): `<base> → 3468c874958d → f5f0af118106 →
  2520310c3acf → 74ffb042dc2d → ce2f3bca2e5f → 5dc3cb471b18` — linear, no
  branch, no merge point.
- `users` table (inspected via `PRAGMA table_info`/`PRAGMA index_list`
  against a throwaway database): `id` (PK), `email` (unique index
  `ix_users_email`), `hashed_password`, `is_active` (`server_default`
  true), `created_at`/`updated_at`.
- `reflection_sessions.owner_id`: FK to `users.id`, `ON DELETE CASCADE`
  confirmed via `PRAGMA foreign_key_list`; non-unique index
  `ix_reflection_sessions_owner_id` present, correct (many sessions per
  owner).
- Reading's existing constraints (`reflection_session_id` unique+NOT NULL,
  `spread_id`/`deck_id` FK `RESTRICT`) are untouched by Steps 22–27 —
  confirmed by diff review (Step 28's own committed diff touches no
  column on `readings`).
- **No unnecessary migration was created by Steps 22–28** — exactly the
  two migrations Step 22 added (`ce2f3bca2e5f`, `5dc3cb471b18`); Step 27
  added zero, matching its own design (no schema change was required for
  `POST /readings`).
- **Upgrade/downgrade round-trip:** `alembic upgrade head` then
  `alembic downgrade base` was executed against a fresh, throwaway SQLite
  database (`scratchpad/audit_migration_check.db`, outside the
  repository). Both directions completed cleanly with no errors. The
  throwaway file was deleted immediately afterward; `find . -iname "*.db"`
  confirms no database artifact remains anywhere in the repository.

---

# 10. Repository-Wide Bypass-Path Findings

Direct repository-wide search (`grep`/`Grep`, not assumed from any prior
report):

- **`Reading(...)` construction:** exactly one call site —
  `app/services/reading_service.py:82`. (Test-only helpers
  `tests/factories.py::make_reading()` and
  `tests/interpretation_helpers.py::build_reading()` also construct one
  each, but neither is reachable from `app/`.)
- **`ReflectionSession(...)` construction:** exactly one production call
  site — `app/services/reading_service.py:78`. Same test-only exceptions
  as above.
- **`CardDraw(...)` construction:** exactly one call site —
  `app/models/reading.py:152`, inside `Reading.add_card_draw()`. No route
  calls this method (Section 3).
- **Every `Reading.status` assignment:** `app/models/reading.py:158`
  (`add_card_draw` → `SPREAD_COMPLETE`), `app/models/reading.py:191`
  (`mark_saved` → `SAVED`), `app/services/interpretation/persistence.py:60`
  (`save_interpretation` → `INTERPRETED`, conditionally). No other file
  assigns `Reading.status`.
- **Every direct `Reading` query:** `app/api/dependencies.py:74`
  (`session.get(Reading, reading_id)`, inside `get_owned_reading`) and
  `app/api/reading.py:149` (`select(Reading)...`, inside the History
  route). No other file queries `Reading` directly.
- **Every route accepting a `reading_id`:** the 5 routes enumerated in
  Section 4, all in `app/api/interpretation.py` (4 routes, all behind
  `get_owned_reading`) and `app/api/reading.py` (1 route, `/save`, also
  behind `get_owned_reading`). Confirmed by grepping every `reading_id:
  UUID` parameter declaration in `app/` — the only other occurrence is
  `app/schemas/interpretation_api.py`'s response field (not a route
  parameter) and `app/services/interpretation/context.py` (an internal
  helper parameter, not a route).
- **Every route file:** exactly 3 — `auth.py`, `interpretation.py`,
  `reading.py` — confirmed by directory listing.
- **Where ownership could be bypassed:** nowhere found. Every Reading
  construction requires a non-optional `User`; every Reading query that
  feeds a response goes through `get_owned_reading` or (for History) an
  explicit `owner_id == current_user.id` filter; no route or service
  function accepts a caller-suppliable owner/user identifier.
- **Where a Reading could be persisted without an owner:** nowhere in
  production code. `create_reading()`'s `owner: User` parameter is not
  optional — a Reading with `owner_id = NULL` can only arise today from
  test fixtures or pre-Step-22 data (both non-production, and the latter
  cannot exist in this codebase's history since no such data has ever
  been persisted here).

**Conclusion: the ownership/lifecycle invariants are genuinely
centralized, not merely convention.** No hidden bypass path was found.

---

# 11. Test Coverage Assessment

**Directly tested** (by the existing suite, independently re-run and
passing — Section 9): authentication (missing/expired/malformed/wrong-
algorithm token, inactive user), registration/login edge cases (bcrypt
boundary, duplicate email/race), ownership isolation across all 4
interpretation routes plus save, NULL-owner fail-closed (via `/save`),
Reading creation validation (blank/over-length question, malformed UUID,
nonexistent spread/deck, extraneous field rejection, post-flush rollback),
ownership propagation, initial status, empty-row creation, two-user
independence, default-deck resolution, History filtering/ordering/
idempotent-appearance, Save idempotency and side-effect-freedom,
reinterpretation history preservation, `is_spread_complete`
required-position-coverage semantics (with all-required real spreads).

**Covered only indirectly, or not at all:**
- **`SpreadPosition(required=False)` behavior is exercised by zero
  tests anywhere in the suite** — every real spread has all positions
  required, and no test constructs a custom spread with an optional
  position. This audit directly verified the actual behavior (Section 2)
  is correct, but the test suite itself provides no regression protection
  for it.
- **NULL-owner fail-closed is tested only via `/save`**
  (`test_save_of_an_unowned_reading_fails_closed`), not independently
  against the interpretation/narrative routes — acceptable, since all
  affected routes share the identical `get_owned_reading` dependency, but
  worth naming as indirect rather than direct coverage of those routes
  specifically.
- **No HTTP-level test exists for recording a card draw**, because no
  such route exists (Section 3) — not a coverage gap so much as a
  reflection of the route's absence.
- **No test exercises `alembic upgrade`/`downgrade` round-trip
  execution** — this audit performed that check manually (Section 9);
  it is not part of the automated suite.

**Redundant or misleading tests:** none identified. `test_ownership.py`
and `test_api_reading.py`'s own ownership tests overlap somewhat in what
they prove (both prove cross-user 404), but each targets a different
route family and neither weakens or bypasses the real ownership boundary
— both authenticate for real and hit the real dependency chain, with no
shortcuts or mocked-out authorization found anywhere in the test suite.

---

# 12. Product / Documentation Contradiction Audit

| Area | Classification | Note |
|---|---|---|
| JWT/HS256, explicit algorithm enforcement, `get_current_user`/`get_owned_reading` boundary | **Confirmed compliant** | Matches `AUTHENTICATION_OWNERSHIP_DESIGN.md`/`AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` exactly; re-verified directly (Sections 2, 4). |
| Ownership anchored on `ReflectionSession.owner_id`, nullable, CASCADE | **Confirmed compliant** | Matches `READING_HISTORY_OWNERSHIP_DESIGN.md` Section 2.5; re-verified (Section 9). |
| Save semantics (Q3), no pinning on reinterpret (Q4) | **Confirmed compliant** | Matches `PRODUCT_DECISIONS.md` Q3/Q4 and `SAVE_READING_DESIGN.md`; re-verified directly (Section 5/6). |
| Reading creation ownership propagation, Spread/Deck-must-exist, no owner field in request | **Confirmed compliant** | Matches `READING_CREATION_OWNERSHIP_DESIGN.md`/`READING_CREATION_API_DESIGN.md`; re-verified directly (Section 2). |
| Draw-recording HTTP API | **Intentional/deferred** | Named out of scope by `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` and `READING_CREATION_OWNERSHIP_DESIGN.md` before Step 27; still absent; not a defect (Section 3). |
| Narrative Generation via Reflection Engine (Product Spec Sections 3.3/5/12/20) vs. deterministic `[A]` actually shipped | **Documentation now stale** (pre-existing, already tracked) | `PRODUCT_DECISIONS.md` Q1 already identified this and recommended a governance action (ADR or Product Spec revision) that **still has not been performed** — re-verified directly, unchanged since Q1 was written. Not introduced or worsened by Steps 22–27. |
| `ReflectionSession.owner_id`'s own docstring (`app/models/reflection_session.py:29-33`) | **Documentation now stale (code comment, minor, newly surfaced by this audit)** | States "Nullable because no Reading/ReflectionSession-creation API exists yet... A future Reading-creation route must set it from the authenticated caller; not built here (Step 22 scope)." Step 27 built exactly that route. The column's nullability is still correct (an unsaved/legacy/test-constructed Reading can still have `owner_id = NULL`, and the audit confirms that case fails closed), but the docstring's framing — describing the creation route as future/nonexistent — is now inaccurate. Not a functional defect; a genuine, small documentation-currency gap in a code comment (not a `Documentation/*.md` file) that Step 27 did not update. |
| `ReadingSummary` sufficiency for a future draw-recording client | **Product decision still required** | Named, not decided, by `READING_CREATION_API_DESIGN.md`; unchanged (Section 8). |
| ADR-0004 (SQLite dev / PostgreSQL prod) | **Confirmed compliant** | `app/core/config.py` unchanged in this respect; no new database-specific assumption introduced (the duplicate-email heuristic in `auth_service.py` was already built and tested against both SQLite- and PostgreSQL-shaped error messages in Step 23). |
| ADR-0005 (AI exclusively via Reflection Engine) | **Confirmed compliant** | No component added in Steps 22–27 calls any AI provider or bypasses the (nonexistent) Reflection Engine; the deterministic narrative layer remains outside ADR-0005's scope entirely, as `NARRATIVE_LAYER_DESIGN.md` already established. |
| ADR-0003 (Platform Identity / modular architecture) | **Confirmed compliant** | Ownership anchored on `ReflectionSession` rather than `Reading`, preserving the "may in the future wrap other reflective activities" extensibility this ADR calls for — unchanged rationale, re-verified against current code. |

---

# 13. Genuine Defects

**None found.** No security/ownership bypass, no lifecycle contradiction,
no database integrity problem, no production path producing an ownerless
Reading, no route exposing another user's Reading, and no uncaught
client-reachable exception resulting in a 500 were found anywhere in the
39-point direct verification (Section 2) or the repository-wide search
(Section 10). No stop condition (Section 14 of the audit brief) was
triggered at any point in this audit.

---

# 14. Deferred / Product Decisions (Not Resolved Here)

- **Draw-recording HTTP API** — named, out of scope, unchanged since
  before Step 27; a future step's own design/implementation pair, not
  decided or built here.
- **Narrative Generation MVP governance action (Q1)** — `PRODUCT_DECISIONS.md`
  already recommends an ADR or Product Spec revision; still outstanding;
  not performed by this audit, consistent with this audit's own
  instruction not to silently resolve product decisions.
- **`ReadingSummary` vs. a richer `ReadingDetail` for a future draw-entry
  client** — named by `READING_CREATION_API_DESIGN.md`, still open.
- **Whether `ReflectionSession.owner_id`'s docstring should be corrected**
  — a documentation-currency question, not a product decision; flagged in
  Section 12 for a future (implementation, not audit) step to fix.

---

# 15. Recommended Next Steps

1. **Update the stale docstring** in `app/models/reflection_session.py`
   (Section 12) to reflect that `POST /readings` now sets `owner_id` —
   a small, low-risk documentation-only fix, not requiring a new design
   step.
2. **Design and implement the draw-recording API** (`POST
   /readings/{id}/draws` or equivalent) as the next substantive step in
   this series — this is the one remaining piece needed to make the full
   creation → draw → complete → interpret → save → history chain
   HTTP-reachable end to end, closing the last gap named (but not closed)
   by Step 27.
3. **Perform the Q1 governance action** `PRODUCT_DECISIONS.md` already
   recommends (an ADR or a `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` revision
   recording the deterministic `[A]` narrative layer as the formally
   accepted MVP substitute) — outside this project's current
   design/implementation step pattern, but flagged again here since it
   remains the single most consequential outstanding governance item
   this audit re-confirmed.
4. **Consider adding a test that constructs a `SpreadPosition(required=False)`**
   position against a real Reading, to give the already-correct
   completion-detection behavior (Section 2/5) durable regression
   coverage — not performed in this step per its read-only, no-new-tests
   instruction.

---

# 16. Final Audit Conclusion

The Step 22–28 authentication, ownership, Save/History, and Reading
creation implementation is **sound and matches its approved design
documents.** Every ownership and authorization claim audited was
independently re-verified against live code execution, not merely
re-read from a prior report, and every claim held. The architectural gap
Step 21 identified — no production path could create an owned Reading —
is **genuinely closed**: exactly one, non-bypassable, non-optional-owner
construction path exists for both `Reading` and `ReflectionSession`, and
every route touching an existing Reading is gated behind the same,
single, resource-enumeration-resistant authorization boundary. The
lifecycle invariants (`DRAFTING` → `SPREAD_COMPLETE` → `INTERPRETED` →
`SAVED`, required-position-based completion, append-only reinterpretation
history, idempotent save) are centralized in the model layer and hold
under direct, adversarial-style probing (forced rollback, NULL-owner
data, optional positions, malformed input) as well as the existing
381-test suite.

The one incomplete piece — no HTTP route yet records a card draw — is not
a defect introduced or concealed by this work; it was explicitly and
repeatedly named as out of scope before Step 27 began, and Step 27 never
claimed to close it. With that route built, the full creation-to-history
lifecycle described in this audit's brief would be completely
HTTP-reachable; today, every step except the draw itself already is.

**No stop condition was triggered. No code, schema, migration, test,
frontend, or other documentation file was modified. This file is the only
new file created by this step.**
