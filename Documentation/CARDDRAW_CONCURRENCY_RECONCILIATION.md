# CardDraw Concurrency Documentation Reconciliation & Remediation Decision (Step 35)

Read-only documentation and governance reconciliation. No application
code, schema, migration, test, frontend, or existing documentation file
was modified in producing this report. `PositionAlreadyDrawnError` was
not changed; the `draw_order` `IntegrityError` was not caught; no
retries or locking were added; no tests were added. Nothing was
committed or pushed.

---

# 1. Executive Summary

Step 34's central finding is re-confirmed, independently, in this step
(Section 2): a true concurrent same-position draw race collides on
**both** `uq_card_draws_reading_id_position_id` and
`uq_card_draws_reading_id_draw_order` simultaneously, SQLite reports the
`draw_order` constraint, and `_is_position_already_drawn_violation()`
therefore does not recognize it — re-verified again, fresh, against the
current, unmodified code, with the same deterministic result.

This step's own contribution is narrower and more targeted than Step
34's: it (a) traces every documentation location that makes a
concurrency-related claim about CardDraw and classifies each precisely
(Section 4), (b) writes the exact, narrowest corrected statement that
should eventually replace the overstated "authoritative backstop" claim,
without applying that correction yet (Section 5), (c) evaluates whether
any implementation change is currently justified by an existing
requirement, and (d) reaches one of the three required conclusions
(Section 9).

**Conclusion reached (Section 9): Option 1 — no implementation change is
currently justified.** No existing product, API, or architectural
requirement compels catching the `draw_order` race, adding retries, or
adding locking. The single-writer/no-locking acceptance already
established for `Interpretation.sequence` and inherited for CardDraw
remains internally consistent and sufficient. What **is** justified,
precisely and narrowly, is a documentation correction (not performed in
this step) to the specific overstated claim identified in Section 5 —
this is a correction to an inaccurate description of existing behavior,
not a new decision, and not an implementation change.

---

# 2. Step 34 Findings Re-Verification

Independently re-inspected for this step (not restated from Step 34's
own report):

- **`draw_order` uniqueness constraint:** `UniqueConstraint("reading_id",
  "draw_order", name="uq_card_draws_reading_id_draw_order")` —
  re-confirmed by reading `card_draw.py` directly and, separately, by
  enumerating `CardDraw.__table__.constraints` at runtime (not just
  static source).
- **`position_id` uniqueness constraint:**
  `UniqueConstraint("reading_id", "position_id",
  name="uq_card_draws_reading_id_position_id")` — same dual
  confirmation.
- **Where each is enforced:** database-level only, in both cases — no
  application code independently re-checks either uniqueness condition
  except `record_card_draw()`'s own in-memory pre-check, which covers
  only the position case (Section 5), not the draw_order case.
- **`record_card_draw()` pre-check behavior:** re-read directly —
  `if reading.status == ReadingStatus.DRAFTING and any(existing.position_id
  == position.id for existing in reading.card_draws): raise
  PositionAlreadyDrawnError(...)`, evaluated against whatever
  `reading.card_draws` already holds in the current session's identity
  map, before any new query. Unchanged since Step 32.
- **`_is_position_already_drawn_violation()` behavior:** re-read
  directly — `"position_id" in message.lower() and ("unique" in message
  or "duplicate" in message)`. Unchanged since Step 32.
- **`Reading.add_card_draw()` behavior:** re-read directly — unchanged
  since Step 16; performs the `DRAFTING` guard, spread/deck membership
  checks, the in-memory `DuplicateCardError` check, constructs the
  `CardDraw`, appends it to `self.card_draws`, and re-evaluates
  `is_spread_complete`. Never flushes or commits itself.
- **Transaction handling in `get_db()`:** re-read directly, unchanged
  since Step 11 — `yield db; db.commit()` inside `try`, `db.rollback();
  raise` inside `except Exception`. Applies uniformly to any exception
  reaching it, regardless of type.
- **The Interpretation concurrency precedent:** re-read directly from
  `app/models/interpretation.py` — `Interpretation.sequence`'s docstring
  states plainly that this project has "no locking around the sequence
  computation — acceptable for its current single-writer-per-reading
  usage pattern," and that `unique=True` exists specifically to turn "a
  hypothetical concurrent double-assignment... into a loud IntegrityError
  rather than a silent ordering ambiguity." Confirmed, again, that
  **nothing anywhere catches or translates this IntegrityError for
  `Interpretation.sequence`** — an unhandled `500` is the accepted,
  intended outcome for that field, not a gap.
- **All existing CardDraw concurrency documentation:** enumerated fully
  in Section 4.

**Independent re-reproduction:** the same-position race was reproduced
again, fresh, for this step, using two independent `Session` objects
against a new in-memory database (not reusing Step 34's own script
verbatim). Result, unchanged:
```
sqlite3.IntegrityError: UNIQUE constraint failed: card_draws.reading_id, card_draws.draw_order
```
`_is_position_already_drawn_violation()` called directly against the
resulting exception returns `False`. **One additional technical detail
not previously recorded:** enumerating `CardDraw.__table__.constraints`
at runtime shows SQLAlchemy's internal constraint ordering places
`uq_card_draws_reading_id_draw_order` *before*
`uq_card_draws_reading_id_position_id` in the table's constraint
collection — the reverse of their declaration order in
`__table_args__`. This offers a plausible concrete mechanism for why
SQLite's constraint-checking (and therefore error-reporting) order does
not follow source-declaration order: the actual DDL/index-creation
order, not the `__table_args__` tuple order, governs which constraint a
conflicting `INSERT` reports first. This is offered as an explanation,
not asserted as SQLite's documented behavior — the empirical result
(reproduced twice now, across two independent audit steps) is what this
document relies on, not the mechanism.

---

# 3. Current Concurrency Governance

The lineage is a single, unbroken chain, re-confirmed by this step's own
fresh repository search (not merely re-cited from Step 34):

1. `app/models/interpretation.py` (`Interpretation.sequence`) —
   originating precedent: no locking, single-writer-per-reading
   accepted, unhandled `IntegrityError` is the intended outcome.
2. `Documentation/READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md`
   Section 15/"Open Questions" — inherits the precedent verbatim for
   CardDraw, explicitly "without re-litigating it," before any
   draw-recording route existed.
3. `Documentation/CARDDRAW_API_DESIGN.md` Section 9 — restates the
   inherited acceptance, then adds the specific, now-shown-inaccurate
   claim that the `IntegrityError` backstop "still correctly turns a
   losing race into a clean 409 rather than a 500."
4. `app/models/exceptions.py` (`PositionAlreadyDrawnError`) and
   `app/services/reading_service.py` (`record_card_draw()`'s own
   docstring) — both, independently, describe the `IntegrityError` catch
   as "the authoritative backstop for a genuine concurrent-draw race,"
   unqualified.
5. `app/services/reading_service.py`
   (`_is_position_already_drawn_violation()`'s own docstring) — more
   cautious than (4): describes the sibling `draw_order` constraint as
   something the `max()+1` computation "should make practically
   unreachable," rather than asserting the backstop is authoritative.
   This is the one place in the current codebase that already hedges,
   correctly in spirit though not quite precisely (Section 5 explains
   why "practically unreachable" is itself not quite the right framing
   either).
6. `Documentation/CARDDRAW_POST_IMPLEMENTATION_AUDIT.md` Section 15 —
   first documented discovery of the different-position race's HTTP
   consequence (an unhandled `500`), classified there as a "potential
   risk," not a "confirmed defect," against the accepted single-writer
   precedent.
7. `Documentation/CARDDRAW_CONCURRENCY_DESIGN.md` — the most recent,
   most accurate record: identifies the same-position race's dual
   collision, reproduces it deterministically, and states precisely that
   the "authoritative backstop" claim does not hold for either race
   shape.

This step's own governing conclusion (Section 9) treats item 7 as
already correct and does not need to re-derive it — item 7 is this
document's own direct predecessor and its findings are adopted, not
merely cited.

---

# 4. Documentation Lineage Audit

Every current documentation source referencing the terms this step names,
classified individually:

| Source | Statement | Classification |
|---|---|---|
| `app/models/interpretation.py` — `Interpretation.sequence` docstring | "no locking... single-writer-per-reading usage pattern... loud IntegrityError rather than a silent ordering ambiguity" | **Still accurate** — nothing about this field or its handling has changed, and no catch/translate mechanism was ever claimed for it, so there is no overstatement to correct. |
| `Documentation/READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` — "Concurrent draw-adding against the same Reading. Out of scope..." | Inherits the precedent, makes no claim about any backstop's effectiveness (none existed yet at that point) | **Still accurate / historical** — correctly describes the state as of Step 15, before any draw route existed; makes no claim this audit needs to correct. |
| `Documentation/CARDDRAW_API_DESIGN.md` Section 9 — "The IntegrityError backstop... still correctly turns a losing race into a clean 409 rather than a 500" | Affirmative correctness claim about the backstop's effectiveness under concurrency | **Technically misleading** — an affirmative, testable claim that this audit (and Step 34) shows to be false for both race shapes, not merely a description of scope. Per this project's own convention, `Documentation/*.md` design records are not retroactively edited (Section 9 below explains why this document does not propose editing it) — but it is the one design-document statement in this lineage that is actually wrong, not merely dated. |
| `app/models/exceptions.py` — `PositionAlreadyDrawnError` docstring — "the authoritative backstop for a genuine concurrent-draw race" | Affirmative, unqualified correctness claim, in a **currently live code comment**, not a point-in-time design record | **Outdated / technically misleading**, and the highest-priority item to eventually correct, because — unlike a `Documentation/*.md` design record — this is a docstring a developer reads today, attached to the exact class this audit shows does not reliably fire under the scenario it describes. |
| `app/services/reading_service.py` — `record_card_draw()`'s own docstring — same "authoritative backstop" phrase | Same claim, same code-comment status | **Outdated / technically misleading**, same reasoning as above. |
| `app/services/reading_service.py` — `_is_position_already_drawn_violation()`'s own docstring — "should make practically unreachable" | A hedged claim, still in the same code-comment category | **Technically misleading, though less overstated** — "practically unreachable" is closer to correct in spirit (it does not claim the backstop is authoritative) but is still imprecise: the sibling constraint is not "unreachable," it is in fact the constraint SQLite reports *first* in exactly the scenario the surrounding code exists to handle. The word "unreachable" undersells a case this audit shows is the *typical*, not the rare, outcome of a genuine same-position race. |
| `Documentation/CARDDRAW_POST_IMPLEMENTATION_AUDIT.md` Section 15 | Documents the different-position race and its `500` consequence, classified as a "potential risk" | **Still accurate** as of its own writing (it had not yet discovered the same-position dual-collision case, which Step 34 found afterward) — **historical/point-in-time**, not misleading, since it does not claim more than what it verified at the time. |
| `Documentation/CARDDRAW_CONCURRENCY_DESIGN.md` | Full corrected account of both race shapes, the dual-collision mechanism, and the inaccurate claim | **Still accurate** — this document's own direct predecessor; nothing in this step's re-verification (Section 2) contradicts it. |

**No document in this lineage is a *contradiction* of an approved
decision** — every item above is either accurate, historical, or an
overstated *implementation-effectiveness* claim layered on top of an
otherwise still-valid architectural acceptance. The acceptance itself
(single-writer, no locking, loud failure is tolerable) is not in
question anywhere in this table.

---

# 5. PositionAlreadyDrawnError Reconciliation

The narrowest technically accurate statement, distinguishing the three
cases this step's brief names precisely (written here as the exact
replacement language a future documentation-only step should apply —
**not applied in this step**):

**Sequential same-position draw** (two attempts against the same
position, within the same request-handling session, one after another —
the overwhelmingly common real-world case, e.g. a client mistakenly
double-submitting, or a UI bug re-sending the same position): **the
in-memory pre-check in `record_card_draw()` reliably catches this and
raises `PositionAlreadyDrawnError` before any database insert is
attempted.** This part of the existing claim is correct and is not
weakened by this reconciliation.

**Concurrent same-position draw** (two genuinely simultaneous requests,
each in its own session, each having loaded the Reading before either
committed): **both requests can pass the in-memory pre-check** (each
sees zero conflicting draws, since neither has yet observed the other's
uncommitted work). **Both then attempt an insert that violates both the
`position_id` and `draw_order` uniqueness constraints simultaneously.**
SQLite's constraint-violation reporting, in every reproduction run
across this step and Step 34, reports the `draw_order` constraint, which
`_is_position_already_drawn_violation()` does not recognize. **Therefore:
`PositionAlreadyDrawnError` is not the guaranteed, or even the
empirically observed, result of a genuine concurrent same-position
race** — the guaranteed result today is an unhandled `IntegrityError`
propagating as a `500`, for the *same* reason as the different-position
case below, not a distinct one.

**Concurrent different-position draw** (two genuinely simultaneous
requests targeting two different positions of the same Reading): **only
`draw_order` collides** (position_id does not, since the positions
differ). The result is the same unhandled `IntegrityError`/`500`, for
the single reason that no code path recognizes a `draw_order`-only
collision at all.

**What must not be implied, per this step's own instruction:** the
`position_id` uniqueness constraint **remains a completely real,
unconditionally enforced database invariant** in every case above — no
race, of any shape, has ever been shown (in this step or Step 34) to
allow two `CardDraw` rows for the same `(reading_id, position_id)` pair
to actually persist. What this reconciliation narrows is only the claim
about which *exception type* an application-layer caller observes when
that invariant does its job — not whether the invariant itself holds.

---

# 6. Accepted Failure Semantics

Restated precisely, distinguishing what *is* accepted from what merely
*results* from what is accepted:

- **Accepted, by three-generation governance precedent (Section 3):** no
  locking around `draw_order` (or, before it, `Interpretation.sequence`)
  computation; a genuine race may surface as a database-level error
  reaching the application layer.
- **A direct, mechanical consequence of that acceptance, not a
  separately accepted decision:** today, that database-level error is
  *unhandled* for both CardDraw race shapes, surfacing as an HTTP `500`
  rather than any clean response — this specific consequence was never
  itself stated or approved as *desirable*, only as the unsurprising
  result of not building a backstop that (Section 5) does not currently
  work as intended for the concurrent case.
- **Not accepted, and not claimed by any document to be accepted:** data
  corruption, lifecycle inconsistency, or silent loss of the
  position-uniqueness invariant. None of these occurs (Section 8).

---

# 7. API/Product Contract Analysis

A repository-wide search (`Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md`,
`Documentation/RAIDIAN_WISE_ARCHITECTURE_V1.md`,
`Documentation/CARDDRAW_API_DESIGN.md`, and every `docs/*.md` file) for
"idempoten," "retry," "at-least-once," "at most once," and
"exactly once" found **no match anywhere** for any concurrency,
idempotency, or retry guarantee. The only "exactly once" match in the
entire repository (`CARDDRAW_API_DESIGN.md`'s test-plan item "Complete
spread transitions exactly once") is about the *domain lifecycle*
invariant (a Reading cannot be completed twice) — unrelated to HTTP
retry or request-idempotency semantics.

**What the current API contract actually promises, precisely:**
- **Database correctness for successful requests** — yes, unconditionally
  (Section 8).
- **Concurrent requests are supported** — not promised anywhere; the
  route accepts concurrent requests the same way any FastAPI route does
  by default (the framework itself is concurrency-capable), but nothing
  documents a guarantee about *correct arbitration* between two racing
  requests beyond "the database's own constraints will not be violated."
- **Serialized draw creation** — not promised; no document claims
  requests are processed in a globally serialized order.
- **A particular HTTP response for a concurrency failure** — not
  promised. `CARDDRAW_API_DESIGN.md`'s own `409` claim for this case
  (Section 4) is exactly the claim this reconciliation shows to be
  inaccurate as a description of *current behavior* — and, distinctly,
  it was never itself a *ratified product/API guarantee* either, only an
  implementation-design document's own (incorrect) expectation of what
  its own proposed code would do.
- **Automatic retry** — not promised, not implemented, not mentioned
  anywhere.
- **Idempotency** — not promised. `POST /readings/{reading_id}/draws` is
  a plain resource-creation endpoint with no idempotency key or
  equivalent mechanism anywhere in its contract.

**If a controlled `409` were added for the `draw_order` race (Option B,
Step 34), this would be a *new* API behavior, not a restoration of an
existing guarantee** — nothing currently documented promises it, so
adding it would need to be recognized, by whoever authorizes it, as
introducing a new, small piece of API contract (a documented `409` case
for concurrent-draw conflicts), not merely "fixing" something the
contract already claimed. This distinction directly informs Section 9.

---

# 8. Lifecycle Integrity Analysis

Reconfirmed directly against Step 34's own findings (Sections 5 and 7 of
that document), cross-checked against this step's own fresh
re-verification (Section 2) rather than assumed:

- **`DRAFTING`:** unaffected — a losing request's attempted mutation
  (including any in-memory-only status change) is never persisted.
- **`SPREAD_COMPLETE`:** unaffected, including the specific case named
  by this step's brief — **a losing transaction that would otherwise
  have completed the spread is fully rolled back, in its entirety,
  before any of its effects (the new `CardDraw` row, or the `status`
  mutation `Reading.add_card_draw()` made in memory) reach the
  database.** Step 34's own Section 7 scenario (two concurrent draws to
  the two remaining required positions of a 1-of-3-filled Reading)
  directly demonstrated this: the Reading correctly remained `DRAFTING`
  with exactly the winner's position filled, never transiently or
  incorrectly marked complete.
- **`INTERPRETED`:** unaffected — no code path connects `record_card_draw()`
  or its failure modes to interpretation state; a Reading cannot even
  reach `INTERPRETED` without first being `SPREAD_COMPLETE`, which
  itself is unaffected as above.
- **`SAVED`:** unaffected — `mark_saved()` is untouched by this entire
  code path; a race during drawing has no mechanism to reach a Reading
  that has already left `DRAFTING`, since `add_card_draw()`'s own
  `DRAFTING`-only guard (unchanged, Section 2) rejects any draw attempt,
  racing or not, against a non-`DRAFTING` Reading before the race
  question is even reached.
- **Reinterpretation:** unaffected — entirely downstream of
  `SPREAD_COMPLETE`, which is unaffected.
- **History:** unaffected — depends only on `status == SAVED`, itself
  unaffected.
- **Ownership:** unaffected — `get_owned_reading` is not touched by any
  part of this analysis; every race scenario in this document and Step
  34 assumes a single, already-authorized owner racing against
  themselves (e.g., two browser tabs, or a client retry-without-backoff)
  or, at most, two concurrent requests already past the ownership
  check — ownership resolution itself has no concurrency interaction
  with `draw_order` at all.

**No lifecycle invariant can be violated by any race shape identified in
this document or its predecessor.** The conclusion is unchanged from
Step 34 and is not weakened or strengthened by this step's narrower
documentation focus — it is restated here because this step's own brief
specifically asks for reconfirmation, not because any new risk was
found.

---

# 9. Remediation Decision Boundary

Walking the four options exactly as this step's brief frames them,
without selecting one merely because it is technically possible:

**A. Documentation-only reconciliation.** Retains the current
architecture; requires no code change; directly continues the
three-generation precedent (Section 3); corrects exactly the
Section 4/5 inaccuracies and nothing else. **This is the option this
document's own findings actively support** — nothing in Sections 2, 7,
or 8 identifies a requirement this option fails to satisfy.

**B. Controlled HTTP error remediation.** Per Section 7, this would
constitute a **new** API guarantee, not a bugfix restoring an existing
one — no current requirement compels it. Step 34 already identified
(and this document does not re-litigate) that choosing this option also
surfaces its own unresolved design question: whether the same-position
and different-position race should map to the same or different domain
exceptions, given that SQLite's message alone no longer reliably
distinguishes them (Section 5). **Not selected here** — available for a
future, separately authorized implementation step, per Section 11.

**C. Retry semantics.** This step's brief explicitly asks to consider
the danger of retrying a request whose intent may already be satisfied
by the competing transaction. Applied precisely to CardDraw: if a
client's draw attempt loses a same-position race, the position in
question **is already filled — by someone else's card, not the losing
client's.** A blind automatic retry of "record this exact draw" would
either (a) fail again identically (if retried verbatim against the same
now-filled position) or (b) require the retry logic to *decide* what the
client actually wanted (try a different position? report the conflict to
the human?) — a product-level question about user intent that no
existing document answers and that this document does not answer either.
For the different-position race, a retry is more plausibly safe (the
client's *own* intended position was never contested — only the
`draw_order` slot was), but nothing in the current API contract (Section
7) distinguishes these two cases for a generic retry mechanism to key
off of. **No existing product/API requirement supports automatic
retries, and per this step's own explicit instruction, none is
recommended here.**

**D. Locking/atomic allocation.** Step 34's conclusion is carried forward
unchanged: both sub-options represent an architectural departure from
the twice-repeated single-writer/no-locking precedent (Section 3), and
Option D specifically carries likely migration/schema risk Step 34 already
detailed. **The governance decision this would require is: whether to
convert the project's existing concurrency *acceptance* into a
concurrency *guarantee*, project-wide (since the same pattern also
governs `Interpretation.sequence`) or narrowly for CardCard alone** —
this document does not make that decision, consistent with Step 34's own
boundary and this step's explicit instruction not to invent one.

**Conclusion: Option A is what this document's own re-verification
supports; Options B/C/D remain available, unselected, each with its own
named prerequisite (an implementation-shape decision for B, an unmet
product-intent question for C, an unresolved architecture-wide
governance decision for D).**

---

# 10. Test Implications

No test is added in this step. Documented here, for whichever option a
future step pursues:

**If Option A (documentation-only) is chosen:**
- No new test is strictly required, since no behavior changes.
- Optionally, a permanent regression test could assert that a
  constructed race (using the same two-session technique this step and
  Step 34 both used) produces *some* error and leaves the database in a
  provably correct state (unique `draw_order`, unique `position_id`, no
  orphaned rows) — codifying Section 8's findings as regression coverage
  without asserting any particular "clean" status code, since none is
  promised under this option. Not required, but available.

**If Option B (controlled `409`) is later chosen:**
- A test proving the `draw_order`-only race now returns the new
  controlled status code instead of `500`.
- A test proving the same-position race also returns a controlled
  status code (exact domain exception depends on that option's own
  unresolved design question, Section 9).
- A test proving the existing `test_unrelated_integrity_error_is_not_swallowed`-style
  negative case still holds — i.e., that broadening the heuristic did
  not start misclassifying some *third*, genuinely unrelated
  `IntegrityError`.
- Regression coverage proving ordinary, non-racing sequential draws are
  entirely unaffected (already provided by the existing 411-test suite).

**If Option C (retry) were ever chosen** (not recommended, Section 9):
- A test proving a retry after losing a *different-position* race
  succeeds and produces the client's originally-intended draw.
- A test proving a retry after losing a *same-position* race does **not**
  silently succeed by drawing a different position the client never
  asked for, and does not silently duplicate the winner's own draw.
- These tests cannot be written meaningfully until the product-intent
  question in Section 9 (what should happen to the client's *original*
  request when their position was already taken by someone else) is
  answered — a decision this document does not make.

**If Option D (locking/atomic allocation) were ever chosen** (not
recommended, Section 9):
- Genuine multi-threaded or multi-process test infrastructure this
  project does not currently have any precedent for — a materially
  larger testing investment than any other option, as Step 34 already
  noted.

No test for any guarantee this project has not chosen to provide (retry,
serialized ordering, a specific concurrency SLA) is proposed.

---

# 11. Recommended Next Step

Per Section 9's explicit conclusion:

**1. No implementation change is currently justified; document the
accepted limitation and correct the overstated backstop claim.**

Concretely, and only as a description of what a future, separately
authorized step could do (not performed here):
- Correct the two live-code docstrings identified as "outdated /
  technically misleading" in Section 4
  (`app/models/exceptions.py::PositionAlreadyDrawnError` and
  `app/services/reading_service.py::record_card_draw()`) to state the
  narrowed, accurate claim from Section 5 — that the in-memory pre-check
  reliably catches the sequential case, while the database backstop's
  effectiveness for a genuine concurrent race is not guaranteed to
  produce `PositionAlreadyDrawnError` specifically (it may surface as an
  unhandled error instead), without at any point implying the underlying
  `position_id` uniqueness invariant itself is unreliable.
- Leave `Documentation/CARDDRAW_API_DESIGN.md`'s own overstated claim as
  a point-in-time design record, per this project's own established
  convention (confirmed again in Section 4) — its inaccuracy is already
  correctly superseded by `CARDDRAW_CONCURRENCY_DESIGN.md` and this
  document, without needing retroactive editing.
- This correction, if and when performed, is a small, low-risk,
  comment-only change — comparable in shape and size to the
  `reflection_session.py` docstring correction Step 30 already
  identified and this step's own instructions explicitly decline to
  perform yet.

---

# 12. Implementation Readiness / Stop Conditions

**No stop condition was triggered.** No security/ownership bypass, no
data-integrity defect, no database-integrity problem, and no
contradiction of an approved lifecycle, ownership, or architectural
decision was found — Section 8 directly reconfirms lifecycle integrity
holds under every race shape identified across this document and its
predecessor.

**This document does not authorize any implementation change.** Section
11's documentation correction remains available for a future,
explicitly authorized step (mirroring how Step 30's `reflection_session.py`
finding remains available, unperformed, since Step 30). Options B, C,
and D (Section 9) each remain named, unselected, and gated on their own
respective prerequisite — none is implementation-ready as written here.

---

# Regression Verification

Run fresh, at the end of this step, to confirm the audit itself
introduced no change: **411 passed, 0 failed, 2 warnings** (the same two
pre-existing `InsecureKeyLengthWarning`s from `test_security.py`,
unchanged).

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
Exactly Step 34's own end state, with
`Documentation/CARDDRAW_CONCURRENCY_RECONCILIATION.md` added as the only
new file. `README.md`'s pre-existing diff is unchanged. Nothing
committed or pushed.
