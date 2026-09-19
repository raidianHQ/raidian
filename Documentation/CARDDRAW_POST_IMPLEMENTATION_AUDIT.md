# CardDraw HTTP API — Post-Implementation Audit (Step 33)

Independent, read-only audit of the Step 32 CardDraw implementation. No
application code, test, schema, migration, dependency, frontend, or
existing documentation file was modified in producing this report.
Nothing was committed or pushed. Every claim below was independently
re-verified against the current repository — by direct code inspection
and by executing purpose-built, throwaway integration probes (a
standalone TestClient-driven end-to-end script covering 44 independent
assertions, plus targeted service-level concurrency/rollback probes, all
run against in-memory SQLite databases outside the test suite, discarded
after use) — rather than restated from Step 32's own self-report.

---

# 1. Executive Summary

**The implementation is clean and matches its approved design.** All 44
independent, freshly-written integration assertions passed; the full
test suite passes unchanged at 411; migration state is untouched; no
unrelated file was modified.

**One genuine, previously-undocumented risk was found and is reported
precisely below (Section 15): a true concurrent-request race on
server-computed `draw_order` produces an *unhandled 500* for the losing
request, not a clean domain error.** This is not a "confirmed defect"
against any approved design — concurrency handling was explicitly and
repeatedly named out of scope by `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md`
("no locking around... single-writer-per-reading usage pattern") before
this route was ever designed — but the *specific failure mode* (an
uncaught `IntegrityError` reaching FastAPI's default handler) was not
previously stated in those terms, and is worth recording as a named,
precise risk rather than leaving it implicit. No fix is proposed or
applied here.

No other confirmed defect, authorization bypass, incorrect status
transition, duplicate persistence, incorrect foreign-key association,
transaction leak, error-masking, incorrect HTTP status, response/schema
mismatch, or unintended change to prior Reading behavior was found.

---

# 2. Implementation Baseline

Directly re-read for this audit (not assumed from Step 32's report):
`backend/app/api/reading.py`, `backend/app/services/reading_service.py`,
`backend/app/schemas/reading_api.py`, `backend/app/models/exceptions.py`,
plus (unchanged since Step 29/31, re-confirmed present and untouched)
`backend/app/models/reading.py`, `backend/app/models/card_draw.py`,
`backend/app/models/spread_position.py`, `backend/app/models/card.py`,
`backend/app/api/dependencies.py`.

- `POST /readings/{reading_id}/draws` exists, `201`, gated by
  `Depends(get_owned_reading)` — confirmed via a live OpenAPI schema
  dump (`app.openapi()['paths']`), not just source reading.
- `record_card_draw()` (`app/services/reading_service.py`) resolves
  `position_id`/`card_id` via `session.get()`, validates spread/deck
  membership, gates its in-memory already-filled-position pre-check on
  `reading.status == ReadingStatus.DRAFTING`, computes
  `draw_order = max(existing) + 1`, delegates the actual mutation to
  `Reading.add_card_draw()` unchanged, and wraps the flush in a narrow
  `try/except IntegrityError` recognizing only the
  `uq_card_draws_reading_id_position_id` violation — confirmed by direct
  source read, matching exactly what Step 32 reported.
- `Reading.add_card_draw()`, `Reading.is_spread_complete`,
  `ReadingStatus`, `CardDraw`, `SpreadPosition.required` — all
  byte-for-byte unchanged since Steps 16/22/27 (confirmed via `git diff`
  showing zero changes to `app/models/reading.py`, `app/models/card_draw.py`,
  `app/models/spread_position.py`, `app/models/card.py`,
  `app/api/dependencies.py` anywhere in Step 32's or this audit's own
  session).
- Migration state: single head `5dc3cb471b18`, 6 files — unchanged
  (Section 13).

---

# 3. End-to-End Lifecycle Verification

A standalone script (`scratchpad/audit_carddraw_e2e.py`, outside the
repository, discarded after use) exercised the full chain against a live
`TestClient` and a real in-memory SQLite database:

```
register (2 users) → login → authenticated Reading creation
→ CardDraw #1 → CardDraw #2 → CardDraw #3 (completion)
→ interpret → reinterpret → save → reinterpret-after-save
→ history
```

**All 44 assertions passed**, including:
- Draw #1/#2 return `201`, `reading_status: "drafting"`, correct
  `draw_order` (1, 2).
- Draw #3 (final required position) returns `201`,
  `reading_status: "spread_complete"`, `draw_order: 3`; the DB row
  independently confirms `status = SPREAD_COMPLETE` and exactly 3
  `CardDraw` rows.
- Interpretation and reinterpretation both succeed after
  `SPREAD_COMPLETE`; sequence increments correctly.
- Save succeeds (`200`, `status: "saved"`); reinterpretation after save
  still succeeds and leaves `status` at `SAVED` (Q4 behavior, unchanged);
  still exactly 3 `CardDraw` rows (unaffected by any interpretation
  activity).
- History returns the Reading exactly once, `status: "saved"`.
- A draw attempt against the now-`SAVED` Reading returns `409`
  (`ReadingNotDraftingError`), and the `CardDraw` count remains 3 —
  **CardDraw insertion breaks no previously-established lifecycle
  behavior.**
- Cross-user draw attempt: `404`, body identical to a
  nonexistent-Reading `404`; zero `CardDraw` rows persisted from the
  rejected attempt.
- Unauthenticated draw attempt: `401`.
- The legitimate owner can still draw successfully on their own Reading
  immediately afterward (proving the rejected attempts left no state
  poisoning the owner's subsequent request).
- A `NULL`-owner Reading (constructed by bypassing the API entirely,
  simulating pre-Step-22 or fixture-only data) fails closed: `404` to an
  authenticated user attempting to draw against it.

---

# 4. CardDraw Persistence Verification

Directly queried the database (not just the HTTP response) after each
successful draw in Section 3's script: exactly one new `CardDraw` row
per request, correct `reading_id`, correct `position_id`, correct
`card_id`, correct `orientation`, `created_at` populated. The HTTP
response body's `position_id`/`card_id`/`orientation`/`draw_order`
fields were compared directly against the persisted row's own columns
and matched exactly in every case — **the response accurately
represents the persisted row.** No duplicate `CardDraw` row was ever
observed for a single successful request in any of this audit's probes.

---

# 5. Draw-Order Verification

- **First draw:** `draw_order == 1` — confirmed (Section 3).
- **Second draw:** `draw_order == 2` — confirmed (Section 3).
- **Multiple existing draws, computed correctly:** confirmed via a
  dedicated service-level probe (`record_card_draw()` called directly):
  after one successful draw (`order=1`), a failed duplicate-card attempt
  (which raises before any flush), then a genuinely successful second
  draw correctly received `order=2` — **not** `order=3`.
- **Failed draw does not consume an order:** directly confirmed by the
  same probe. Because `draw_order` is computed fresh on every call from
  `max(persisted rows) + 1` — never a stored, incrementing counter — a
  failed attempt has no side effect on any counter state; there is
  nothing to "consume." No gap was observed in any successful sequence
  across any probe in this audit.
- **Transaction rollback does not leave a phantom order:** confirmed in
  Section 3's forced-post-flush-failure probe — after a deliberately
  forced `RuntimeError` following a successful flush, the DB retained
  only the CardDraw rows from before the forced failure; the failed
  attempt's row was rolled back entirely, and no gap or phantom entry
  remained in the `draw_order` sequence.
- **Concurrency:** a genuine race **was** constructed and tested,
  independently of the HTTP layer (a true HTTP-level race cannot be
  produced deterministically in a synchronous test, since each request
  gets a freshly-queried session that correctly sees already-committed
  state — see Section 15 for why this matters). Two separate `Session`
  objects were used to simulate two truly concurrent requests, both
  loading the same Reading (0 existing draws) before either committed:
  - Session 1 drew position A, `draw_order = 1`, committed successfully.
  - Session 2 (already holding a stale, pre-race view of the Reading)
    drew position B, also computed `draw_order = 1`, and its flush
    raised a genuine `sqlite3.IntegrityError: UNIQUE constraint failed:
    card_draws.reading_id, card_draws.draw_order`.
  - This is **not** the `position_id` constraint (the two sessions drew
    different positions) — it is the sibling `draw_order` uniqueness
    constraint, which `record_card_draw()`'s `IntegrityError` backstop
    deliberately does not recognize (Section 6/15).

**A genuine race condition around server-side `draw_order` computation
does exist**, exactly as the pre-existing, already-approved design
documents already accepted ("no locking... single-writer-per-reading
usage pattern," `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md`). This
audit does not change that acceptance or propose locking. What this
audit adds, precisely, is the *consequence* of that race under the new
HTTP route — documented in Section 15, not fixed here.

---

# 6. Position/Card Validation Audit

All six cases independently re-verified (Section 3's script plus
dedicated probes), with the resulting HTTP status and underlying domain
exception confirmed for each:

| Case | Domain exception | HTTP status |
|---|---|---|
| Nonexistent `SpreadPosition` | `SpreadPositionNotFoundError` | `404` |
| Position belonging to another Spread | `SpreadPositionNotFoundError` (same collapsing) | `404` |
| Nonexistent `Card` | `CardNotFoundError` | `404` |
| Card belonging to another Deck | `CardNotFoundError` (same collapsing) | `404` |
| Already-filled position (still `DRAFTING`) | `PositionAlreadyDrawnError` | `409` |
| Duplicate Card (spread disallows) | `DuplicateCardError` | `409` |
| Valid position + valid Card | — | `201` |

**`PositionAlreadyDrawnError` vs. `DuplicateCardError` vs. the database
constraints, precisely:** `PositionAlreadyDrawnError` maps to
`card_draws`' `uq_card_draws_reading_id_position_id` constraint — the
*position* already has a card. `DuplicateCardError` is a pure in-memory
business rule (`Reading.add_card_draw()`'s own check against
`self.card_draws`, unchanged since Step 16) gated by
`Spread.allow_duplicate_cards` — the *same card* was already drawn
anywhere in this Reading, regardless of position — and has no
corresponding *database* constraint at all (confirmed by re-reading
`card_draw.py`'s `__table_args__`: only `position_id` and `draw_order`
are uniqueness-constrained; `card_id` is not). This means
`DuplicateCardError` is enforced *only* in application code, with no
database-level backstop — a pre-existing characteristic, unchanged by
Step 32, not a new gap this route introduces (the model-level guard
already existed since Step 16 and was never backed by a DB constraint;
Step 32 did not add or remove any constraint).

**Is the `IntegrityError` recognition heuristic
(`_is_position_already_drawn_violation`) sufficiently specific?**
Independently re-verified by direct inspection of both constraint
definitions in `card_draw.py`:
```python
UniqueConstraint("reading_id", "position_id", name="uq_card_draws_reading_id_position_id")
UniqueConstraint("reading_id", "draw_order", name="uq_card_draws_reading_id_draw_order")
CheckConstraint("draw_order >= 1", name="ck_card_draws_draw_order_positive")
```
The heuristic checks for the substring `"position_id"` plus
(`"unique"` or `"duplicate"`) in the lowercased exception message.
- **SQLite:** confirmed directly — the `position_id` constraint's
  message is `"UNIQUE constraint failed: card_draws.reading_id,
  card_draws.position_id"` (contains `"position_id"`); the sibling
  `draw_order` constraint's message is `"...card_draws.draw_order"`
  (does **not** contain `"position_id"`) — confirmed via the Section 5
  concurrency probe, which produced exactly this message and was
  correctly **not** misclassified (it propagated as a raw
  `IntegrityError`, proving the heuristic's negative case works
  correctly, not just its positive case).
- **PostgreSQL (reasoned, not executed — no Postgres instance available
  in this environment):** PostgreSQL's `IntegrityError` message embeds
  the constraint's own *name*, not raw column lists — e.g. `duplicate
  key value violates unique constraint "uq_card_draws_reading_id_position_id"`.
  Because this project's own constraint name literally contains the
  substring `"position_id"` (by construction, in the `name=` argument),
  and the sibling constraint's name literally contains `"draw_order"`
  instead, the same substring check remains correctly discriminating
  under PostgreSQL's message format too — this is the exact same
  reasoning already validated for `auth_service.py`'s analogous
  email-uniqueness heuristic (Step 23's own dedicated
  PostgreSQL-message-shape unit test). **No SQLite/PostgreSQL
  portability concern was found** for this specific heuristic.
- **No false-positive risk from other constraints on the same table**:
  the `CheckConstraint` (`ck_card_draws_draw_order_positive`) violation
  message contains neither `"unique"` nor `"duplicate"` in either
  dialect, and a foreign-key violation message contains neither
  substring either — both are correctly excluded by the heuristic's
  second condition regardless of the first. `record_card_draw()`'s
  `except IntegrityError` block only ever wraps the single flush of one
  new `CardDraw` insert, so no unrelated table's constraint can
  realistically reach this handler.

**Conclusion: the heuristic is neither too broad nor too narrow for its
actual, intended purpose** — it correctly recognizes exactly the one
constraint it names, on both supported database dialects, and correctly
declines to recognize its sibling constraint (as directly demonstrated
by the concurrency probe in Section 5, which produced a real, unaltered
`IntegrityError` rather than a misclassified `PositionAlreadyDrawnError`).

---

# 7. Lifecycle State Verification

Re-confirmed directly (Section 3, plus targeted probes):
- Partial draws (1 or 2 of 3 required positions filled) leave `status`
  at `DRAFTING`.
- The final required draw transitions `status` to `SPREAD_COMPLETE`
  exactly once — a subsequent draw attempt against an already-complete
  Reading is rejected (`409`, `ReadingNotDraftingError`), never
  re-triggers or duplicates the transition.
- Interpretation transitions `DRAFTING`/`SPREAD_COMPLETE` →
  `INTERPRETED` (unchanged, Step 11); reinterpretation remains allowed
  from `INTERPRETED` and from `SAVED` (status untouched when already
  `SAVED`) — both re-confirmed directly in Section 3's trace, unaffected
  by the new draw route's existence.
- Save remains idempotent — a second `/save` call against an
  already-`SAVED` Reading (not re-tested fresh in this step's own script
  but confirmed unaffected: the full suite's own
  `test_saving_an_already_saved_reading_is_idempotent` passed unchanged
  in Section 11's regression run).
- `CardDraw` rows remain immutable: no code path anywhere in
  `app/services/reading_service.py` or `app/api/reading.py` updates or
  deletes an existing `CardDraw` row — `record_card_draw()` only ever
  inserts, confirmed by direct source read; no `UPDATE`/`DELETE`
  statement against `CardDraw` exists anywhere in application code
  (re-confirmed via a repository-wide search for `CardDraw` usage
  outside test files — the only production references are the single
  construction site inside `Reading.add_card_draw()` and the read-only
  `session.get`/`select` calls already documented in Step 29's earlier
  repository-wide bypass-path audit, unchanged since).

**No lifecycle semantic was altered.**

---

# 8. Optional-Position Verification

Independently re-derived (not reused verbatim from Step 31/32's own
probes) with a fresh, throwaway spread (one required, one optional
position):

- **Confirms Step 31's conclusion:** once `SPREAD_COMPLETE` is reached
  (by filling only the required position), a subsequent attempt to draw
  the still-empty optional position raises `ReadingNotDraftingError` —
  the same, uniform guard that rejects any post-completion draw
  attempt, required or optional. No special-case optional-position logic
  exists anywhere, and none was found to be missing.
- **New for this step: behavior when the optional position is drawn
  *before* completion.** Directly tested: drawing the optional position
  first leaves `status` at `DRAFTING` (correct — the required position
  is still unfilled); drawing the required position second correctly
  transitions to `SPREAD_COMPLETE`, and both positions' `CardDraw` rows
  persist correctly. Optional positions are fully drawable at any point
  before the Reading leaves `DRAFTING` — there is no restriction on
  *when* (relative to other positions) an optional position may be
  filled, only on *after* the Reading has left `DRAFTING` (Section 7,
  same guard as everything else).

No new optional-position policy was invented; both behaviors above are
direct, unmodified consequences of `Reading.add_card_draw()`'s existing,
unchanged logic (the `DRAFTING`-only guard and the required-position-only
completion check).

---

# 9. Authentication & Ownership Verification

- `get_owned_reading` (`app/api/dependencies.py`, unmodified since Step
  22) remains the **sole** authorization boundary for this route —
  confirmed by source read (the route's only auth-related dependency)
  and by a dedicated spy probe: `app.api.reading.record_card_draw` was
  monkeypatched to record every invocation; both a cross-user request
  and an unauthenticated request were sent, and **zero** calls into the
  service function were recorded for either — authorization is fully
  resolved (and can fully reject) before any service/domain code runs.
- User A creates a Reading; User B's draw attempt against it returns
  `404`, byte-identical to the body returned for a nonexistent Reading
  (Section 3) — collapsing is preserved, unchanged from every other
  Reading-scoped route.
- User A can draw successfully on their own Reading immediately after
  User B's and an unauthenticated attempt were both rejected — no
  session/state leakage between requests.
- `CardDrawCreateRequest` declares exactly three fields
  (`position_id`, `card_id`, `orientation`); its shared `_Model` base's
  `extra="forbid"` rejects a client-supplied `owner_id` (or any other
  unrecognized field) as `422` before the route body ever executes —
  confirmed directly (Section 3). **No CardDraw route accepts an
  owner/user identifier from the client, directly or indirectly.**

---

# 10. API Contract Verification

All items independently re-verified (Section 3's script), each against
its own dedicated request:

| Check | Result |
|---|---|
| Malformed Reading UUID (path) | `422` |
| Malformed `position_id` | `422` |
| Malformed `card_id` | `422` |
| Missing required fields (empty body) | `422`, names all three missing fields |
| Unknown field (general) | `422` (`extra_forbidden`) |
| `owner_id` supplied | `422` (`extra_forbidden`) |
| `draw_order` supplied | `422` (`extra_forbidden`) |
| Valid orientation (`upright`, `reversed`) | accepted, persists correctly |
| Invalid orientation (`"sideways"`) | `422` (`enum` validation error) |
| Successful draw status code | `201` |
| Response `reading_status` accuracy | Confirmed correct at every stage: `"drafting"` after a non-completing draw, `"spread_complete"` after the completing draw — matches the DB row's own `status` in every case checked |

No contract expansion was found or introduced by this audit.

---

# 11. Transaction/Rollback Verification

- **No partial CardDraw survives a failed request:** confirmed via a
  forced post-flush failure (monkeypatching `_to_draw_summary` to raise
  after `record_card_draw()` had already flushed) — the DB retained only
  the CardDraw rows that existed before the forced failure; the new row
  was fully discarded.
- **No Reading status mutation survives a failed transaction:** the same
  probe confirmed `reading.status` remained at its pre-request value
  (`DRAFTING`) after the forced failure and rollback — even though
  `add_card_draw()` may have mutated `reading.status` in memory before
  the flush, the rollback (via `get_db()`'s existing
  `except Exception: db.rollback()`) discards that in-memory mutation
  along with the row.
- **Unrelated `IntegrityError`s are not swallowed:** directly proven,
  not merely asserted — the Section 5 concurrency probe produced a
  genuine, unrelated (`draw_order`, not `position_id`) `IntegrityError`,
  and it propagated out of `record_card_draw()` completely unmodified
  (verified by exact exception type and message), never reinterpreted
  as `PositionAlreadyDrawnError`.
- **The service does not commit:** confirmed by source read —
  `record_card_draw()` calls `session.flush()` exactly once, no
  `session.commit()` anywhere in `reading_service.py`.
- **`get_db()` remains the sole, authoritative commit point:** unchanged
  since Step 11, re-confirmed by the rollback probe's own success (the
  forced failure could only have been correctly discarded if `get_db()`'s
  existing commit-on-success/rollback-on-exception boundary were still
  the only place a commit occurs).

---

# 12. Regression Test Results

Run fresh for this audit (not reused from Step 32's own numbers):
- Focused (`test_api_reading.py` + `test_card_draw.py` +
  `test_reading_lifecycle.py`): **94 passed, 0 failed.**
- Full suite: **411 passed, 0 failed, 2 warnings** — the same two
  pre-existing `InsecureKeyLengthWarning`s from `test_security.py`'s
  deliberately undersized negative-path secrets, unchanged in cause and
  count since Step 22.
- **No existing test was deleted or weakened** — confirmed by `git diff`
  on `backend/tests/test_api_reading.py` (the only test file Step 32
  touched): every diff hunk is a pure addition (new fixtures, new test
  functions) appended after the pre-existing Reading Creation section;
  zero lines were removed from any pre-existing test.

---

# 13. Migration/Repository State

- `alembic heads`: single head, `5dc3cb471b18` — unchanged.
- Migration file count: 6 — unchanged; **no migration was introduced by
  Step 32.**
- No temporary database artifact remains anywhere in the repository
  (`find . -iname "*.db"` returns nothing outside `.git`).
- No unexpected schema change exists — confirmed by `git diff` showing
  zero modification to any file under `backend/alembic/` or to any
  model file's column/constraint definitions.

**`git status --porcelain` at the time of this audit** (before this
report's own file was created):
```
 M README.md
 M backend/app/api/reading.py
 M backend/app/models/exceptions.py
 M backend/app/schemas/reading_api.py
 M backend/app/services/reading_service.py
 M backend/tests/test_api_reading.py
?? Documentation/AUTHENTICATION_OWNERSHIP_DESIGN.md
?? Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
?? Documentation/CARDDRAW_API_DESIGN.md
?? Documentation/POST_IMPLEMENTATION_DOCUMENTATION_RECONCILIATION.md
?? Documentation/PRODUCT_DECISIONS.md
?? Documentation/READING_CREATION_API_DESIGN.md
?? Documentation/READING_CREATION_OWNERSHIP_DESIGN.md
?? Documentation/READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md
?? Documentation/READING_HISTORY_OWNERSHIP_DESIGN.md
?? Documentation/READING_LIFECYCLE_POST_IMPLEMENTATION_AUDIT.md
?? Documentation/SAVE_READING_DESIGN.md
```
Exactly Step 32's own end state — unchanged, since nothing has been
committed since. This audit adds exactly one new file,
`Documentation/CARDDRAW_POST_IMPLEMENTATION_AUDIT.md`.

---

# 14. Cross-Document Consistency

| Document | Claim checked | Result |
|---|---|---|
| `CARDDRAW_API_DESIGN.md` | Endpoint shape, request/response contract, service-layer placement (`reading_service.py`, not a new `draw_service.py`), error mappings | **Confirmed compliant** — implementation matches the design exactly, field for field, mapping for mapping. |
| `CARDDRAW_API_DESIGN.md` Section 3.3 ("redrawing an already-filled position **while still `DRAFTING`** is caught only by...") | Whether Step 32's DRAFTING-gated pre-check was a deviation from the design | **Confirmed compliant, not a deviation** — the design document's own phrasing already says "while still DRAFTING," meaning the implementation's gating is a faithful realization of what the design already specified, not a new decision made during implementation. |
| `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` | `is_spread_complete` required-position-coverage rule; no-locking/single-writer concurrency acceptance | **Confirmed compliant** — both re-verified directly (Sections 5, 8 above); the concurrency acceptance is unchanged, and this audit's Section 15 finding is additive detail, not a contradiction of that acceptance. |
| `READING_CREATION_API_DESIGN.md` / `READING_CREATION_OWNERSHIP_DESIGN.md` | Reading creation unaffected by the new route | **Confirmed compliant** — `create_reading()` and its route are byte-unchanged (Section 2); all prior Reading-creation tests pass unchanged (Section 12). |
| `SAVE_READING_DESIGN.md` | Save semantics, idempotency, no CardDraw side effects | **Confirmed compliant** — re-verified directly (Sections 3, 7); `mark_saved()` untouched. |
| `READING_HISTORY_OWNERSHIP_DESIGN.md` | History reflects correct final status, one row per Reading | **Confirmed compliant** — re-verified directly (Section 3). |
| `AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` | `get_owned_reading` remains the single authorization boundary | **Confirmed compliant** — re-verified directly (Section 9), including a fresh spy-based proof that the service is never invoked when authorization fails. |
| `POST_IMPLEMENTATION_DOCUMENTATION_RECONCILIATION.md` | The stale `app/models/reflection_session.py` docstring flagged in Step 30 | **Still present, unfixed** — re-confirmed directly; Step 32 correctly did not touch this file (out of its own scope), so this remains exactly the same, already-known, already-classified documentation issue from Step 30 — not a new finding, not worsened. |

No genuine contradiction was found between the current implementation
and any of the eight documents reviewed. No historical design document
was treated as contradicted merely for describing a pre-implementation
state — each claim above was checked against what that document actually
asserts about the *implemented* (not merely designed) system, and every
such assertion held.

---

# 15. Findings & Risk Classification

1. **Concurrent-request race on `draw_order` produces an unhandled 500
   for the losing request.** — **Potential risk** (not a confirmed
   defect against any approved design: concurrency was explicitly
   accepted as out of scope before this route existed). Precisely: two
   truly simultaneous requests recording draws against the same Reading
   can both compute the same `next_draw_order`; the first to flush
   succeeds, and the second's flush raises a genuine
   `uq_card_draws_reading_id_draw_order` `IntegrityError` that
   `record_card_draw_route()` has no handler for (its `except` clauses
   only cover the five named domain exceptions) — this propagates as an
   uncaught exception, which FastAPI surfaces as an unhandled `500`
   rather than a clean, retryable `409`. Verified directly and
   deterministically (Section 5) using two independent `Session` objects
   simulating genuine concurrency; not reproducible through the ordinary
   single-threaded HTTP test path, which is precisely why it had not
   surfaced before. Not fixed here, per this step's own constraints.
2. **`DuplicateCardError` has no database-level backstop** (only
   `position_id` and `draw_order` are uniqueness-constrained at the DB
   layer; `card_id` is not) — **Intentional behavior, pre-existing,
   unchanged by Step 32.** The in-memory guard in
   `Reading.add_card_draw()` has enforced this since Step 16, without a
   DB constraint, and Step 32 introduced no new duplicate-card path that
   would need one. Noted for completeness, not flagged as a defect.
3. **`app/models/reflection_session.py`'s stale ownership docstring**
   (Step 30's finding) — **Documentation issue, pre-existing, unchanged.**
   Correctly out of Step 32's own scope; still open.
4. **Everything else audited (Sections 3–13)** — **No issue.**

No authorization bypass, no incorrect status transition, no duplicate
persistence, no incorrect foreign-key association, no transaction
leakage, no error-masking (beyond the concurrency case above, which is a
gap in coverage rather than active masking), no incorrect HTTP status
code, no response/schema mismatch, no hidden bad assumption around
seeded data, and no unintended change to any previously-implemented
Reading behavior was found anywhere in this audit.

---

# 16. Required Follow-Up

Neither of the two open items below requires action before proceeding —
both are named for a human/product decision, not blockers:

1. **Whether the draw-order concurrency risk (Finding 1) warrants a
   fix** (e.g., a database-level retry-on-conflict, a row lock on the
   Reading during the read-compute-write sequence, or simply accepting
   an occasional `500` under real concurrent load as consistent with the
   already-approved single-writer assumption) is a product/architecture
   decision this audit does not make. If accepted as-is, no action is
   needed; if not, it would be a small, targeted fix to
   `record_card_draw_route()`'s exception handling (or to
   `record_card_draw()`'s transaction shape) for a future step to design
   and implement — not performed here.
2. **The stale `reflection_session.py` docstring** (Finding 3) remains
   available for a trivial, low-risk correction whenever a future step
   touches that file, per Step 30's own recommendation — still not
   urgent, still not performed here.

---

# 17. Final Assessment

**The implementation is clean and ready to proceed to the next design
step.** Every lifecycle, ownership, persistence, and API-contract claim
this audit tested — independently, not by restating Step 32's own
report — held under direct execution. The one genuine risk found
(Finding 1) is a documented, scoped gap in an area the project's own
governing design documents already, knowingly, left unhandled; it does
not represent a regression, a contradiction of an approved decision, or
a blocker to further work.

**Test result:** 411 passed, 0 failed, 2 warnings (unchanged from Step
32).
**Migration head:** `5dc3cb471b18` (single head, 6 files, unchanged).
**Git status:** exactly Step 32's 5 modified files plus 10 untracked
`Documentation/*.md` files (including this report as the 11th); the
pre-existing `README.md` diff unchanged; nothing committed or pushed.
**Files created by this step:** `Documentation/CARDDRAW_POST_IMPLEMENTATION_AUDIT.md`
(exactly one).
**Files changed by this step:** none.
