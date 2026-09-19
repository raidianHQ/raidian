# CardDraw Concurrency & Draw-Order Remediation — Design/Audit (Step 34)

Read-only design/audit. No application code, schema, migration, test,
frontend, or existing documentation file was modified in producing this
report. Nothing was committed or pushed. No option below is selected or
implemented — this document establishes what is true, what is already
decided by prior governance, and what remains genuinely open.

---

# 1. Executive Summary

Step 33 found that a true concurrent race on server-computed `draw_order`
produces an unhandled `500` for the losing request. This step
independently re-verified that finding and, in doing so, **found it is
narrower in one respect and more serious in another than Step 33's own
framing suggested:**

- **Narrower:** the race is not a data-integrity problem at all. Every
  scenario tested (Section 3, Section 7) confirms the loser's entire
  transaction — including any in-memory `Reading.status` mutation — is
  atomically discarded on rollback. No corruption, no partial write, no
  phantom completion, and no lost required-position coverage was
  produced by any race tested. This is purely an **HTTP error-semantics**
  gap, not a **data-integrity** gap (Section 5 draws this distinction
  precisely).
- **More serious:** this audit discovered that `PositionAlreadyDrawnError`'s
  own `IntegrityError` backstop — documented, in this exact codebase, as
  "the authoritative backstop for a genuine concurrent-draw race" — **does
  not reliably work for the exact race it was built to catch.** When two
  concurrent requests target the *same* position from the same pre-race
  state, they necessarily also collide on `draw_order` (both compute the
  same `max(existing) + 1`), and SQLite deterministically reports the
  `draw_order` constraint violation instead of the `position_id` one when
  a single INSERT violates both simultaneously — confirmed reproducibly,
  three times, in this audit (Section 3.2). The existing heuristic
  therefore misses this case and lets a raw `IntegrityError` propagate,
  exactly as it does for the already-known, different-position case. This
  is a genuine mismatch between an affirmative design claim
  (`CARDDRAW_API_DESIGN.md`: "the IntegrityError backstop... still
  correctly turns a losing race into a clean 409... even though true
  concurrent-safety... is not designed here") and the actual, tested
  behavior — not merely a point-in-time snapshot, but a specific
  correctness claim this audit shows does not hold.

**The underlying tolerance for this class of race is an explicitly
accepted, three-generation-deep documented limitation in this exact
codebase**, inherited verbatim from `Interpretation.sequence`'s own
"no locking... single-writer-per-reading... loud IntegrityError rather
than a silent ordering ambiguity" precedent (Step 9), carried forward
unchanged through `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md`
(Step 15) and `CARDDRAW_API_DESIGN.md` (Step 31). **This document does
not silently revise that acceptance.** What it does establish: (a) the
specific, previously-uncorrected claim that the backstop "turns a losing
race into a clean 409" should be treated as inaccurate going forward
(Section 9/11), and (b) five remediation options, compared without a
selection, for whichever product/governance decision addresses it next.

---

# 2. Current Implementation Re-Verification

Re-read directly for this step (not assumed from Step 33):

- `backend/app/services/reading_service.py::record_card_draw()` — the
  in-memory already-filled-position pre-check is gated on
  `reading.status == ReadingStatus.DRAFTING`; `draw_order` is computed as
  `max((d.draw_order for d in reading.card_draws), default=0) + 1`
  **immediately before** calling `Reading.add_card_draw()`, from
  whatever `reading.card_draws` already holds in the current session's
  identity map (no fresh query is issued at this point — confirmed by
  source read: it iterates the already-loaded Python collection, not a
  new `SELECT`). The flush is wrapped in
  `try/except IntegrityError`, calling
  `_is_position_already_drawn_violation(exc)`.
- `backend/app/models/card_draw.py` — confirmed unchanged since Step 16:
  ```python
  UniqueConstraint("reading_id", "position_id", name="uq_card_draws_reading_id_position_id")
  UniqueConstraint("reading_id", "draw_order", name="uq_card_draws_reading_id_draw_order")
  CheckConstraint("draw_order >= 1", name="ck_card_draws_draw_order_positive")
  ```
- `_is_position_already_drawn_violation()` (`reading_service.py`) checks
  the lowercased exception message for the substring `"position_id"` plus
  (`"unique"` or `"duplicate"`) — unchanged since Step 32.

**Two concurrent requests can deterministically compute the same
`draw_order`:** yes, confirmed directly (Section 3). Any two sessions
that both load the same `Reading` and access `reading.card_draws` before
either has committed a new draw will independently compute an identical
`max(...) + 1`, because each session's view of `reading.card_draws`
reflects only what was committed *before* that session's own load — this
is standard read-committed-or-looser isolation behavior, not a bug
specific to this code.

**Exact exception produced by SQLite:** `sqlite3.IntegrityError`, wrapped
by SQLAlchemy as `sqlalchemy.exc.IntegrityError`. Message text depends on
which constraint fires (Section 3).

**Does the current service/API layer catch or transform it?** Only for
the one specific case the heuristic matches — and, per Section 3.2's
finding, that case is narrower in practice than its own documentation
claims. Every other `IntegrityError` (including, this audit shows, the
same-position race) propagates unchanged through `record_card_draw()`,
uncaught by `record_card_draw_route()` (whose `except` clauses list only
`SpreadPositionNotFoundError`, `CardNotFoundError`,
`PositionAlreadyDrawnError`, `DuplicateCardError`,
`ReadingNotDraftingError` — none of which is a raw `IntegrityError`), and
reaches `get_db()`'s generic `except Exception: db.rollback(); raise`,
which rolls back correctly (Section 6) and re-raises, which FastAPI
surfaces as an unhandled `500`.

**Would PostgreSQL behave materially differently?** Reasoned, not
executed (no PostgreSQL instance available in this environment) —
addressed precisely in Section 9, including the specific new uncertainty
this audit's Section 3.2 finding introduces.

**Does the existing transaction boundary (`get_db()`) change the
result?** No — `get_db()` is unchanged since Step 11 and behaves
identically regardless of which constraint fired; it rolls back and
re-raises whatever exception reaches it. The transaction boundary is not
the source of the problem and requires no change under any option that
keeps the current commit-once-at-the-request-boundary architecture
(Section 6).

---

# 3. Reproduction of the Concurrency Failure

Two independent, deterministic reproductions were run for this audit
(both using two separate `Session` objects against a shared in-memory
SQLite database — the same technique Step 33 used, extended here).

## 3.1 Different-position race (Step 33's original scenario, re-confirmed)

Two sessions load the same `Reading` (0 existing draws), both compute
`draw_order = 1`, and draw *different* positions. The first to flush
commits cleanly (`draw_order = 1`). The second's flush raises:
```
sqlite3.IntegrityError: UNIQUE constraint failed: card_draws.reading_id, card_draws.draw_order
```
`_is_position_already_drawn_violation()` correctly returns `False` (the
message contains no `"position_id"` substring), so the raw
`IntegrityError` is re-raised — unchanged from Step 33's finding,
independently reproduced again here.

## 3.2 Same-position race — new finding

Two sessions load the same `Reading` (0 existing draws), both compute
`draw_order = 1`, and both draw the *same* position. The resulting
`CardDraw` row would violate **both** `uq_card_draws_reading_id_position_id`
**and** `uq_card_draws_reading_id_draw_order` simultaneously. Reproduced
three consecutive times, deterministically:
```
sqlite3.IntegrityError: UNIQUE constraint failed: card_draws.reading_id, card_draws.draw_order
```
**SQLite reports the `draw_order` constraint, not `position_id`, every
time** — despite `position_id` being declared first in
`__table_args__`. `_is_position_already_drawn_violation()` therefore
returns `False` for this case too, and the raw `IntegrityError`
propagates exactly as in Section 3.1.

**This is the scenario `PositionAlreadyDrawnError`'s own docstring names
explicitly** ("the authoritative backstop for a genuine concurrent-draw
race the pre-check cannot see") — and it does not behave as documented.
The pre-check (in-memory, same-session) already handles every
*sequential* already-filled-position case correctly and was never at
risk; it is specifically the cross-session, genuinely concurrent case
the backstop exists for, and that is exactly the case this audit shows
it misses.

## 3.3 Session state after either failure

Confirmed directly (not previously tested in Step 33): after the failed
flush, the session is immediately unusable for *any* further ORM
operation — including reading an already-loaded, in-memory attribute of
an object with no pending query. Attempting `reading.status` on the
losing session's already-loaded `Reading` object raised:
```
PendingRollbackError: This Session's transaction has been rolled back
due to a previous exception during flush. To begin a new transaction
with this Session, first issue Session.rollback().
```
This is addressed precisely in Section 6.

---

# 4. Existing Concurrency Assumptions

A repository-wide search (`grep -rn -i "concurren|single-writer|race|locking"`
across `backend/app/` and every `Documentation/*.md`/`docs/*.md` file)
found a single, consistent, three-generation lineage — not three
independent claims:

1. **Origin** (`app/models/interpretation.py`, `Interpretation.sequence`,
   pre-dating this entire Reading/ownership series): *"this project has
   no locking around the sequence computation — acceptable for its
   current single-writer-per-reading usage pattern... `unique=True` turns
   a hypothetical concurrent double-assignment... into a loud
   IntegrityError rather than a silent ordering ambiguity."* **Critically:
   nothing anywhere catches or translates this IntegrityError for
   `Interpretation.sequence`** — an unhandled `500` under a genuine race
   on this field is the explicitly intended, accepted outcome, not a gap
   needing a backstop at all.
2. **Inheritance** (`READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md`,
   Step 15, written before any draw-recording route existed): *"Concurrent
   draw-adding against the same Reading. Out of scope, consistent with
   `Interpretation.sequence`'s own documented acceptance of 'no locking
   around... single-writer-per-reading usage pattern'... the same
   assumption is inherited here without re-litigating it."*
3. **Restatement with an added claim** (`CARDDRAW_API_DESIGN.md`, Step
   31): repeats the same inherited acceptance, then adds: *"The
   IntegrityError backstop... still correctly turns a losing race into a
   clean 409 rather than a 500, even though true concurrent-safety (e.g.
   row locking) is not designed here."* **This is the one place the
   lineage adds a claim beyond "the race is accepted" — an affirmative
   claim about the backstop's effectiveness — and Section 3 shows that
   claim does not hold, for either race shape.**

Also directly relevant: `auth_service.py::register_user()`'s duplicate-
email `IntegrityError` backstop (Step 23) is the one place in this
codebase an `IntegrityError`-as-concurrency-backstop pattern was built
**and verified to work** — that backstop's target constraint
(`users.email`, a single-column-pair uniqueness with no sibling
constraint on the same table competing for the same violated row) has no
analogue to Section 3.2's dual-violation ambiguity, which is specific to
`card_draws` having two independent uniqueness constraints that a single
racing INSERT can violate simultaneously.

**Classification of the Step 33/34 race, precisely:**
- **The race's existence, and the acceptability of an unhandled
  exception resulting from it, is an accepted, explicitly documented
  limitation** — three governance generations deep, unbroken, never
  silently assumed.
- **The specific claim that an existing backstop already turns this into
  a clean `409` is an undocumented-until-now inaccuracy** — not a
  contradiction of the accepted limitation itself, but a factual error in
  one document's description of the current mitigation's effectiveness.
  This document corrects the record (Section 9/14) without revising the
  underlying single-writer acceptance.

---

# 5. Data Integrity Invariants

Distinguished precisely, per this step's own instruction:

**Data integrity (verified intact under every race tested, Sections 3
and 7):**
- `draw_order` unique within a Reading — **never violated**; the
  database constraint is the actual enforcement mechanism and it holds
  under every race tested. No two `CardDraw` rows for the same Reading
  ever end up with the same `draw_order`, race or no race.
- Successful draws receive deterministic sequential ordering — confirmed
  (Section 7): draws that actually commit are always numbered
  gap-free, `1, 2, 3, ...`, regardless of how many *other*, non-winning
  attempts raced against them.
- Two simultaneous valid draws never corrupt the Reading — confirmed:
  exactly one of any two racing draws to the same position ever persists;
  for two racing draws to *different* positions, at most one loses to the
  `draw_order` collision (both could in principle succeed only if they
  did not race, i.e. computed different `draw_order` values, which
  requires them not to be truly concurrent).
- A failed concurrent request never leaves a partially-created
  `CardDraw` — confirmed (Section 3, Section 7): the loser's row is
  never committed; `get_db()`'s rollback removes it from the session
  entirely.
- `Reading.status` remains lifecycle-correct — confirmed (Section 7):
  the loser's in-memory `status` mutation (if `add_card_draw()` happened
  to advance it before the failed flush) is discarded along with
  everything else in that transaction. No test produced a Reading whose
  persisted `status` was inconsistent with its persisted `CardDraw` rows.
- Position uniqueness remains enforced — confirmed: the database
  constraint holds regardless of which error message SQLite chose to
  report first; the *row itself* is never persisted for either violated
  constraint.
- `Reading.add_card_draw()` required no change and none is proposed —
  every invariant above is enforced by that method and the database
  schema exactly as they already exist; nothing in this audit found a
  design conflict requiring it to change.

**HTTP error semantics (the actual gap, confirmed broken in two shapes,
Section 3):**
- A losing request should receive a clean, actionable HTTP response
  (ideally a `409`-class "someone else changed this Reading, please
  retry") — **this does not currently happen for either race shape**
  (different-position, Section 3.1; same-position, Section 3.2). Both
  currently surface as an unhandled `500`.

**The core conclusion of this section: nothing about data integrity is
at risk here. The entire gap is that the losing client is told the wrong
thing about what happened**, even though what actually happened (their
draw was correctly and completely not persisted) was itself correct.

---

# 6. Transaction and Rollback Analysis

- **Does the session become failed/pending rollback?** Yes, immediately
  upon the failed flush — confirmed directly (Section 3.3), including
  for attribute access requiring no new query.
- **Does `get_db()` correctly roll it back?** Yes, unconditionally —
  `except Exception: db.rollback(); raise` catches *any* exception type,
  not a specific one, so it correctly rolls back regardless of which
  constraint fired or whether the service's own heuristic recognized it.
  This was true before this audit and required no change to verify.
- **Does any Reading/ReflectionSession/CardDraw state remain partially
  committed?** No — confirmed in every probe (Sections 3, 7): the
  in-memory mutations `Reading.add_card_draw()` made before the failed
  flush (appending the new `CardDraw` to `reading.card_draws`,
  potentially advancing `reading.status`) are never persisted, since the
  flush that would have written them is exactly what failed.
- **Does the existing service convention of never calling `rollback()`
  remain correct?** **Yes, for the current code — but this is not free
  for every possible remediation option**, and this nuance is new,
  surfaced directly by Section 3.3's finding: because the session becomes
  fully unusable (even for in-memory attribute reads) the instant the
  flush fails, **any future code path that wants to catch this
  `IntegrityError` and do anything with the session or any of its
  tracked objects before the exception reaches `get_db()` must call
  `session.rollback()` itself first**, or it will raise a *new*,
  unrelated `PendingRollbackError` instead of whatever clean response it
  intended to produce. The current code is safe today by construction —
  `PositionAlreadyDrawnError`'s existing `except IntegrityError` branch
  only builds an f-string using `reading.id` and `position_id`
  (`position_id` is a plain UUID parameter, not an ORM attribute) — but
  whether `reading.id` itself is safe to read from a poisoned session
  the way it currently does (without an explicit `rollback()` first) is
  worth flagging precisely: it has not caused an observed failure in any
  probe in this audit, but Section 3.3 demonstrates that *some* attribute
  reads (`reading.status`) do fail this way, and this document does not
  have enough evidence to certify that *no* attribute read ever would.
  **This is named as a verification gap for whichever option touches this
  code path next (Section 8), not fixed or further investigated here.**

---

# 7. Lifecycle Interaction Analysis

Four scenarios, each independently constructed and run for this step
(not reused verbatim from Step 33, which did not test lifecycle
interaction specifically):

1. **Required-position race, neither individually completing:** a
   Reading with 1 of 3 required positions already filled; two concurrent
   sessions race to fill the two *different* remaining required
   positions. The winner commits (2 of 3 filled, `status` remains
   `DRAFTING`); the loser's attempt (which, had it not raced, would have
   been the reading's actual completing draw) is fully rolled back.
   **Final state: `status = DRAFTING`, exactly 2 `CardDraw` rows,
   correctly matching only the two positions that actually persisted.**
   No phantom completion, no missed-but-silently-assumed completion — the
   Reading simply, correctly, is not yet complete, and the losing client
   must retry to actually complete it (receiving a `500` telling them
   nothing useful today — the HTTP-semantics gap, not a data problem).
2. **Same-position race (duplicate-position race):** covered in Section
   3.2 — confirmed the winning draw persists exactly once, `status`
   reflects reality, and the loser leaves no trace.
3. **Optional-position race:** not separately re-run as its own
   scenario, reasoned directly from the mechanism instead: nothing in
   `record_card_draw()`'s `draw_order` computation, the `IntegrityError`
   backstop, or `Reading.add_card_draw()`'s own `is_spread_complete`
   recomputation branches on `SpreadPosition.required` at any point
   before the flush — the `required` flag only affects which positions
   `is_spread_complete`'s own required-position-coverage check counts,
   which is evaluated identically whether the race is over a required or
   optional position. The mechanism producing Section 5's data-integrity
   guarantees (atomic rollback of the entire in-memory mutation set on a
   failed flush) applies uniformly regardless of which specific position
   or flag combination triggered it — there is no code path where an
   optional position's involvement changes the rollback behavior.
4. **Same-Reading concurrent draws to different positions, neither
   racing on the same target:** this is scenario 1 in miniature (and
   also Section 3.1) — already directly confirmed.

**Conclusion: `Reading.status` cannot become inconsistent under any race
shape tested or reasoned through.** The existing transaction boundary
(one flush per request, one commit-or-rollback per request, at
`get_db()`) is sufficient on its own to preserve every lifecycle
invariant even with zero locking — the *only* consequence of the
accepted single-writer assumption being violated is that the losing
request's own work is lost and reported poorly, never that the winning
request's work (or the Reading's overall state) is corrupted.

---

# 8. Remediation Options A–E

No option is selected. Each is assessed against the same criteria; none
is recommended over another except where an existing governing document
already settles part of the question (noted explicitly where that
occurs).

## Option A — Accept the race, document it explicitly

Document (in code comments and/or a `Documentation/*.md` file) that a
true concurrent draw race can surface as an unhandled `500`, exactly
mirroring `Interpretation.sequence`'s own already-accepted precedent
(Section 4). No implementation change.
- **Correctness:** No change — already correct (Section 5).
- **SQLite / PostgreSQL:** No dialect-specific concern; the accepted
  outcome (an unhandled exception) is dialect-agnostic by construction.
- **Transaction interaction:** None — `get_db()`'s existing behavior
  already produces this outcome correctly today.
- **Migration impact:** None.
- **API behavior:** Unchanged — a losing client still receives a `500`.
- **Testability:** Straightforward — this audit's own reproductions
  (Section 3) already demonstrate the accepted behavior deterministically;
  a permanent regression test could assert "a genuine race produces *an*
  error" without needing to assert a specific clean status code.
- **Implementation complexity:** None.
- **Compatibility with existing architecture:** Perfect — this *is* the
  existing architecture's own stated philosophy, applied consistently.
- **New product decision required:** No — this option requires only
  correcting `CARDDRAW_API_DESIGN.md`'s inaccurate "turns into a clean
  409" claim (Section 9/14) to match the already-accepted philosophy,
  not a new decision.

## Option B — Catch and translate the `draw_order` IntegrityError

Add a second heuristic (or broaden the existing one) to also recognize
the `draw_order` constraint violation, translating it to a new or
existing domain exception (e.g. a `ConcurrentDrawConflictError`, or
reusing `PositionAlreadyDrawnError`'s `409` family) at the service layer,
following the exact pattern already proven for
`_is_position_already_drawn_violation()`.
- **Correctness:** Would not change data integrity (already correct);
  would change only what the losing client is told.
- **SQLite:** Straightforward — the `draw_order` constraint's message
  format is confirmed (Section 3) and just as recognizable via substring
  matching as the `position_id` one.
- **PostgreSQL:** Same reasoning as the existing heuristic (Section 9) —
  the constraint's own name contains a distinguishing substring, so the
  same technique should port, *contingent on* resolving Section 3.2's
  ambiguity (see below).
- **Transaction interaction:** Must account for Section 3.3/6's finding
  — whatever catches this exception must not touch the session or any
  tracked object in a way that requires a fresh read before either
  re-raising a clean domain exception (which itself does not touch the
  session, following the existing `PositionAlreadyDrawnError` route
  handler's own safe pattern) or explicitly calling `session.rollback()`
  first if it needs to.
- **Migration impact:** None.
- **API behavior:** A losing client would receive a clean `409` instead
  of a `500` — but **would not know unambiguously whether they lost a
  position-uniqueness race or a pure ordering race**, since (per Section
  3.2) the *same-position* case now also collides on `draw_order` first
  — meaning a single, broadened heuristic would need to decide whether
  to report it as `PositionAlreadyDrawnError` or a new, distinct
  "ordering conflict, please retry" error, since SQLite's message alone
  cannot currently distinguish "you raced on the same position" from
  "you raced on a different position but the same order slot" once
  `draw_order` is reported first in both cases. **This is a design
  question this option surfaces, not one this document resolves** —
  whichever future implementation step picks this option must decide
  whether that distinction matters to the client (arguably it does not:
  in both cases, the correct client action is "reload the Reading and
  retry").
- **Retry behavior:** Not proposed as part of this option — determining
  *where* a retry belongs (client, service, or not at all) is named as
  its own question below (Option B does not itself retry; it only
  produces a clean, retryable error).
- **Testability:** The same two-session technique this audit already
  used (Sections 3, 5) is directly reusable as a permanent test.
- **Implementation complexity:** Low — one additional heuristic function
  and one additional `except`/`raise` mapping, following an
  already-proven pattern exactly.
- **Compatibility with existing architecture:** High — extends, rather
  than replaces, the existing pre-check-plus-backstop convention.
- **New product decision required:** Arguably not a *product* decision
  (the resulting error is still just "please retry"), but does require
  an *implementation* decision (the error-shape question above) a design
  step would need to settle.

## Option C — Database/transaction locking

Acquire a row-level lock (e.g. `SELECT ... FOR UPDATE` on the `Reading`
row, or on a dedicated ordering counter) before computing `draw_order`,
serializing concurrent writers against the same Reading.
- **Correctness:** Would eliminate the race entirely at its source
  (prevents the *second* concurrent writer from proceeding until the
  first commits, rather than letting both attempt and one fail).
- **SQLite:** `SELECT ... FOR UPDATE` is accepted syntactically but
  SQLite does not implement row-level locking the way PostgreSQL does —
  SQLite's actual concurrency model is file/database-level (its
  `BEGIN IMMEDIATE`/`BEGIN EXCLUSIVE` transaction modes, or simply its
  default single-writer file lock) — meaning a row-lock-based design
  would behave *differently* in dev/test (SQLite) than in production
  (PostgreSQL, per ADR-0004), which is precisely the kind of
  dialect-divergent behavior this project's own conventions (the
  SQLite/PostgreSQL-portable `IntegrityError`-message heuristics already
  built for both `auth_service.py` and `reading_service.py`) have so far
  deliberately avoided.
- **PostgreSQL:** Would work as intended (`SELECT ... FOR UPDATE` is a
  standard, well-supported PostgreSQL locking primitive).
- **Transaction interaction:** Would require holding a lock for the
  duration of the read-compute-write sequence within a single request's
  transaction — a real, if small, latency/throughput cost under genuine
  concurrent load, and a departure from this project's otherwise
  lock-free convention everywhere else (Section 4).
- **Migration impact:** None required structurally, though a dedicated
  locking column/mechanism could be one (Option D territory).
- **API behavior:** A losing request would *wait* rather than fail —
  changes the observable behavior more fundamentally than Option B (a
  client-perceived latency increase under contention, instead of a fast
  clean error).
- **Testability:** Harder to test deterministically than B — would
  require genuine multi-threaded or multi-process test infrastructure to
  prove lock acquisition/ordering, which this project's test suite does
  not currently have any precedent for (every existing test, including
  this audit's own probes, uses sequential, single-threaded session
  interleaving to *simulate* concurrency, not genuine parallelism).
- **Implementation complexity:** Higher than B — touches the
  transaction/session-acquisition pattern, not just error mapping.
- **Compatibility with existing architecture:** Lower — would be the
  first place in this codebase using explicit row locking; every other
  concurrency-sensitive field (`Interpretation.sequence`, now
  `CardDraw.draw_order`) has so far deliberately chosen the
  unique-constraint-plus-loud-error pattern instead (Section 4).
- **New product decision required:** Arguably yes — choosing to pay a
  latency/complexity cost to *prevent* the race (rather than to report it
  cleanly) is a different tradeoff than Options A/B, and departs from an
  established, twice-repeated architectural pattern in this exact
  codebase without those prior decisions having been revisited.

## Option D — Atomic database-side draw-order allocation

Replace `MAX(draw_order) + 1` (computed in Python from an in-memory
collection) with a database-side atomic allocation — e.g., a
per-Reading sequence, or an `INSERT ... SELECT COALESCE(MAX(draw_order),0)+1
...` single-statement pattern that lets the database itself serialize the
computation.
- **Correctness:** Could close the race at its source, similar in spirit
  to Option C but without an explicit lock.
- **SQLite:** SQLite supports `INSERT ... SELECT` patterns, but true
  atomicity against concurrent writers still depends on SQLite's own
  transaction/locking model (the same caveat as Option C) — a
  single-statement `INSERT...SELECT` is not automatically race-free
  across two separate connections without an appropriate isolation
  level or explicit locking underneath it.
- **PostgreSQL:** Native sequences (`SERIAL`/`GENERATED... AS IDENTITY`)
  or advisory locks could implement this cleanly, but a *per-Reading*
  (not global) sequence is not a built-in primitive — would likely need
  either a synthetic per-Reading counter table/column or an
  `INSERT...SELECT...FOR UPDATE` pattern, which reintroduces Option C's
  own locking question.
- **Transaction interaction:** Comparable to Option C.
- **Migration impact:** **Likely yes** — a per-Reading atomic counter
  typically needs either a new column (e.g. a `next_draw_order` counter
  on `Reading`, updated atomically) or a dedicated allocation mechanism,
  which this option's own framing (per this step's instructions) must
  flag rather than assume away: this is very likely schema-impacting,
  unlike A or B.
- **API behavior:** Same as A/B if paired with a clean error, or same
  as C if paired with a wait-based approach — depends on which
  sub-approach is chosen, which this document does not choose.
- **Testability:** Similar to C — genuine concurrency is hard to prove
  deterministically in this project's current single-threaded test
  style.
- **Implementation complexity:** Higher than B, comparable to or higher
  than C, and uniquely carries migration risk the other options do not.
- **Compatibility with existing architecture:** Lower — introduces a new
  kind of server-side counter/allocation mechanism this project has not
  used anywhere else (Interpretation.sequence's own global counter is
  computed the same Python-side `MAX()+1` way, with the same accepted
  race — so this option would also represent a first-of-its-kind
  departure for *that* pattern too, not just for CardDraw).
- **New product decision required:** Yes, clearly — this is the option
  most likely to require both a schema change and a broader
  architectural precedent-setting decision (whether to abandon the
  Python-side `MAX()+1` pattern project-wide, not just for CardDraw).

## Option E — Alternative ordering semantics

Ask whether `draw_order` actually needs to represent strict, globally
serialized creation order under concurrency, or merely *a* valid,
gap-free, unique ordering of whichever draws actually persisted — i.e.,
whether the invariant that matters is "unique and dense," not
"reflects real-world simultaneity precisely."
- **What the governing documents already say:** `RAIDIAN_WISE_PRODUCT_SPEC_V1.md`
  Section 17 lists "draw order" among the immutable evidence fields
  preserved on a saved Reading, but says nothing about its behavior
  under concurrent recording — it describes the field's *product*
  meaning (the order cards were actually drawn), not an API concurrency
  contract. `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` and
  `CARDDRAW_API_DESIGN.md` both already establish that `draw_order` is
  server-computed specifically to prevent client-supplied gaps/duplicates
  (Section 4.3 of the latter) — implying the *intended* semantic is
  "unique and dense," which Section 5 confirms is exactly what already
  holds today, race or no race. **No governing document requires
  `draw_order` to preserve strict real-time simultaneity ordering under
  concurrent requests** — a genuine race, by definition, has no single
  correct "real" order between the two racing requests to begin with
  (they were, from the system's perspective, simultaneous).
- **Conclusion:** the current semantics (server-computed, unique, dense,
  gap-free among whatever actually commits) already satisfy every
  documented requirement, including under a race. This option does not
  require a semantic *change* — it is closer to a restatement/confirmation
  that today's behavior is already correct by the only definition any
  governing document supplies. **Not a product decision at all**, since
  nothing is actually being changed; naming it here satisfies this
  step's own instruction to check whether the documents already answer
  the question (they do, in the negative — no stronger ordering guarantee
  is required).
- All other assessment columns (SQLite/PostgreSQL/transaction/migration/
  API/testability/complexity/architecture) are **not applicable** — this
  option changes nothing about the implementation, only clarifies that no
  implementation change is compelled by the ordering semantic itself.

---

# 9. SQLite vs. PostgreSQL Analysis

- **The existing, working part of the heuristic** (`_is_position_already_drawn_violation`,
  as it applies to a *pure*, non-`draw_order`-colliding position-uniqueness
  violation) remains portable — its reasoning (matching the constraint's
  own name, which is dialect-stable by construction) was already
  independently re-verified in Step 33 and is unchanged here.
- **The new uncertainty this audit introduces (Section 3.2):** whether
  PostgreSQL, like SQLite, reports the `draw_order` constraint ahead of
  the `position_id` constraint when a single INSERT violates both
  simultaneously is **not known and not testable in this environment**
  (no PostgreSQL instance available). This matters specifically for any
  future Option B-shaped remediation: if PostgreSQL reports the *opposite*
  constraint first (`position_id` before `draw_order`), then the exact
  same race, run against SQLite (dev/test) versus PostgreSQL
  (production, per ADR-0004), could produce **different domain
  exceptions and different HTTP status codes for what is, from a client's
  perspective, the identical situation** — a portability risk this audit
  can name precisely but not resolve without a PostgreSQL environment to
  test against. **This is flagged as an open verification gap**, not
  assumed in either direction.
- **Options C/D's dialect divergence** is analyzed directly within each
  option (Section 8) — SQLite's weaker row-locking model versus
  PostgreSQL's native support is the dominant portability concern for
  those two options, independent of the message-ordering question above.
- **Option A/E** carry no portability risk, since neither depends on
  interpreting a database error message at all.

---

# 10. Test Coverage Gap Analysis

**What Step 32/33's existing tests currently prove:**
- `test_unrelated_integrity_error_is_not_swallowed`
  (`tests/test_api_reading.py`, Step 32) proves the heuristic correctly
  declines to misclassify a `draw_order`-only collision (different
  positions) as `PositionAlreadyDrawnError` — i.e., it proves the
  heuristic's *negative* case is correct.
- `test_redrawing_an_already_filled_position_is_rejected_with_409`
  (Step 32) proves the *sequential*, same-session already-filled-position
  case is caught by the in-memory pre-check — it does **not** exercise
  the cross-session `IntegrityError` backstop at all (the pre-check
  short-circuits before ever reaching the flush), a distinction this
  audit's Section 3.2 finding makes newly significant: **no existing
  test exercises the true concurrent same-position race**, so no existing
  test could have caught the Section 3.2 finding, and none currently
  regresses it either way.
- Step 33's own audit script (not a permanent test) demonstrated the
  different-position race live but was discarded after use, per its own
  read-only scope.

**What is not currently proven by any test in the suite:**
- A true concurrent (multi-session) race of any shape — same-position or
  different-position.
- The specific HTTP status code a losing client receives under either
  race shape (currently undefined/untested — an unhandled `500` is what
  happens, but nothing pins this as expected behavior in a way that
  would catch a future regression in either direction).
- Whether the eventual winner of a race is always correctly and fully
  persisted (this audit's own probes confirm it, Section 3/7, but this
  is not codified as a permanent regression test).

**Tests that would be required for each option, if selected (not written
here):**
- **Option A:** one or two permanent tests asserting that a genuine race
  (constructed the same way this audit did) produces *some* error and
  leaves the database in a correct, non-corrupted state — codifying
  Section 5's data-integrity findings as regression coverage, without
  asserting a specific "clean" status code (since none is promised under
  this option).
- **Option B:** the above, plus an assertion that the losing request's
  response is the new clean, controlled status code (not `500`); a
  dedicated test for whichever error-shape decision Option B's own open
  question (Section 8) resolves; continued coverage of the existing
  `test_unrelated_integrity_error_is_not_swallowed`-style negative case,
  extended to confirm nothing *else* is now over-broadly caught.
- **Option C/D:** all of the above, plus genuine multi-threaded or
  multi-process test infrastructure this project does not currently
  have any precedent for — a meaningfully larger testing investment than
  B, and worth naming as its own cost when comparing options.
- **All options:** regression coverage proving ordinary, non-racing
  sequential draws are entirely unaffected — already provided by the
  full existing suite (411 tests, Section "Regression" below), which
  passed unchanged throughout this audit.

No test was added, modified, or deleted in this step.

---

# 11. Product/Governance Decision Boundary

**Does fixing this require a new product decision?** It depends on which
option:
- **Option A** requires no new product decision — it is a direct,
  unmodified continuation of an already-three-times-affirmed
  architectural choice (Section 4). The only action it implies is a
  documentation correction (Section 14), not a product decision.
- **Option E** requires no decision at all — it changes nothing; the
  governing documents already answer the ordering-semantics question in
  the negative (no stronger guarantee is required than what already
  holds).
- **Option B** requires an implementation-level decision (how to shape
  the resulting error for the newly-discovered dual-collision ambiguity,
  Section 8) but arguably not a *product* decision, since the
  user-facing outcome in every case remains "please retry."
- **Options C and D** each represent a genuine departure from this
  project's established, twice-repeated single-writer/no-locking
  precedent (Section 4) — choosing either would be **substituting a new
  concurrency *guarantee* for the project's existing concurrency
  *acceptance***, which this document explicitly does not do on anyone's
  behalf. Per this step's own instruction not to silently convert the
  "single-writer/no-locking" assumption into a guarantee, **selecting C
  or D is named here as requiring an explicit product/architecture
  decision this document does not make and does not recommend making.**

**Is the existing documentation sufficient to resolve this alone?** For
Options A and E: yes — the existing three-generation precedent and the
Product Spec's own silence on real-time ordering (Section 8) are already
sufficient to justify either without new governance. For Options B, C,
and D: no — B needs a small implementation-shape decision (not
product-level); C and D need an actual product/architecture decision
this document identifies but does not make, consistent with this
project's own repeatedly-demonstrated practice of naming such decisions
precisely rather than resolving them inside a design/audit step.

---

# 12. Recommended Next Step

Not a selection among Options A–E (none is chosen, per this step's own
constraint) — but two concrete, low-risk, no-new-decision actions this
document's own findings make available immediately, independent of
whichever option a future governance step eventually picks:

1. **Correct `CARDDRAW_API_DESIGN.md`'s specific, now-shown-inaccurate
   claim** that the existing `IntegrityError` backstop "still correctly
   turns a losing race into a clean 409" — not by editing that
   historical document (this project's own established convention
   preserves design documents as point-in-time records, per
   `POST_IMPLEMENTATION_DOCUMENTATION_RECONCILIATION.md`'s own Section 3
   reasoning), but by recording, in whatever step next touches this
   code, that the claim is superseded by this document's Section 3.2
   finding — exactly the same treatment Step 30 already gave the stale
   `reflection_session.py` docstring.
2. **If and when a future implementation step is authorized to act on
   this document:** Option A (documentation-only) is the only option
   requiring zero new product/architecture decision and zero new test
   infrastructure investment; Option B is the smallest option that
   changes observable behavior, and its own remaining question (the
   error-shape ambiguity, Section 8) is a scoped, boundable design
   question rather than an open-ended one. Options C and D are named as
   available but require a governance decision this document explicitly
   does not make.

---

# 13. Implementation Readiness / Stop Conditions

**No stop condition was triggered.** No security/ownership bypass, no
data-integrity defect, no database-integrity problem, and no
contradiction of an approved lifecycle or ownership decision was found —
Section 5/7 directly confirm data integrity holds under every race shape
tested. The one confirmed defect this audit found (Section 3.2:
`PositionAlreadyDrawnError`'s backstop does not work as its own
documentation claims for the concurrent same-position case) is precisely
scoped, does not affect data integrity, and does not block any other
work.

**Implementation readiness, per option:**
- **Option A:** implementation-ready immediately — it is a documentation
  action only.
- **Option E:** nothing to implement.
- **Option B:** implementation-ready *after* a future design step
  resolves the error-shape question named in Section 8 — not fully
  contract-ready in this document, since that question was deliberately
  left open rather than answered unilaterally.
- **Options C/D:** not implementation-ready — both require a
  product/architecture decision this document identifies but does not
  make (Section 11), and Option D specifically may require schema/
  migration work that has not been designed.

**This document does not authorize implementation of any option.** A
future step would need to be explicitly authorized, naming which option
(or combination) to pursue, before any code, test, schema, or migration
change is made.

---

# Regression Verification

Run fresh, at the end of this audit, to confirm the audit itself
introduced no change: **411 passed, 0 failed, 2 warnings** (the same two
pre-existing `InsecureKeyLengthWarning`s from `test_security.py`,
unchanged). `alembic heads`: single head, `5dc3cb471b18`, unchanged.

**`git status --porcelain` at the end of this step:**
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
?? Documentation/CARDDRAW_CONCURRENCY_DESIGN.md
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
Exactly Step 33's own end state, with `Documentation/CARDDRAW_CONCURRENCY_DESIGN.md`
added as the only new file. Nothing committed or pushed.
