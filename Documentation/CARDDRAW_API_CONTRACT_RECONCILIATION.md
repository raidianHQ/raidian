# CardDraw API — Post-Implementation Documentation & Contract Reconciliation (Step 38)

Read-only audit. No application code, test, schema, migration, or
frontend file was modified in producing this report. No existing
`Documentation/*.md` file was edited. Nothing was committed or pushed.
Every claim below was independently re-verified against the current
repository (fresh reads, fresh greps, a fresh full test run) rather than
restated from Steps 31–37's own reports, though their conclusions are
adopted where this audit's own re-verification confirms them unchanged.

---

# 1. Executive Summary

**The CardDraw HTTP implementation and its surrounding documentation are
now internally consistent, with exactly one known, already-classified
exception that requires no further action.** That exception is
`Documentation/CARDDRAW_API_DESIGN.md`'s own overstated claim that the
`IntegrityError` backstop "still correctly turns a losing race into a
clean `409`" — re-confirmed present, verbatim, unmodified, at that
document's lines 511–515. This is not a new finding: Steps 34 and 35
already identified it, deliberately declined to edit the historical
document (per this project's own established convention), and instead
corrected the three *live code* docstrings that made the equivalent
claim (Step 36) and superseded the design document's claim with two
newer, accurate records (`CARDDRAW_CONCURRENCY_DESIGN.md`,
`CARDDRAW_CONCURRENCY_RECONCILIATION.md`). This audit confirms that
resolution is complete and stable — the live code no longer makes the
overstated claim anywhere, and the historical document correctly remains
unedited, exactly as intended.

No new contradiction, no new stale claim, no implementation defect, and
no undocumented behavior drift was found anywhere in the 15 files and
document set this step was asked to re-verify. Four product/API
questions remain genuinely open (batch-vs-single draw, display-name
embedding, a `GET /readings/{id}` route, idempotency/retry) — all
already correctly named as undecided by prior steps, none silently
resolved by this audit or by the shipped implementation choosing one
behavior over another.

**No runtime-behavior-changing recommendation is made.** The one
documentation action available (correcting `CARDDRAW_API_DESIGN.md`'s
claim) is not recommended as urgent, since its factual correction
already lives in two later, authoritative documents and in the
corrected code comments themselves — re-stated here as available, not as
newly required.

---

# 2. Current Shipped API Contract

Re-verified directly against `backend/app/api/reading.py` and
`backend/app/schemas/reading_api.py` (both re-read fresh for this step):

**`POST /readings/{reading_id}/draws`**
- **Authentication:** `Depends(get_owned_reading)`, which itself depends
  on `Depends(get_current_user)` — unauthenticated → `401`.
- **Ownership:** `get_owned_reading` resolves `reading_id` and rejects
  (`404`) if the Reading does not exist or its
  `reflection_session.owner_id != current_user.id`, including `NULL`.
  No second ownership mechanism exists anywhere in this route.
- **Request fields:** exactly `position_id: UUID`, `card_id: UUID`,
  `orientation: Orientation` (`"upright"` | `"reversed"`) — all
  required, no defaults. `CardDrawCreateRequest` inherits `_Model`'s
  `extra="forbid"`, so any unrecognized field (including a
  client-supplied `owner_id` or `draw_order`) is rejected as `422`
  before the route body runs.
- **`draw_order` server computation:** `record_card_draw()` computes
  `max((d.draw_order for d in reading.card_draws), default=0) + 1` —
  never accepted from the request body.
- **Response shape:** `CardDrawSummary` — `id`, `position_id`,
  `card_id`, `orientation`, `draw_order`, `created_at`,
  `reading_status`.
- **HTTP status codes:** `201` success; `401` unauthenticated; `404`
  Reading not found / not owned / `SpreadPositionNotFoundError` /
  `CardNotFoundError`; `409` `PositionAlreadyDrawnError` /
  `DuplicateCardError` / `ReadingNotDraftingError`; `422` validation.
- **Error mappings**, re-confirmed one-for-one against the route's own
  `except` clauses (source read, not inferred): `SpreadPositionNotFoundError`
  → 404, `CardNotFoundError` → 404, `PositionAlreadyDrawnError` → 409,
  `DuplicateCardError` → 409, `ReadingNotDraftingError` → 409. No other
  exception type is caught by this route — any other exception
  (including an unrecognized `IntegrityError`) propagates to `get_db()`
  and surfaces as an unhandled `500`, unchanged since Step 32.
- **Lifecycle/status behavior:** the pre-check
  (`reading.status == ReadingStatus.DRAFTING and any(existing.position_id
  == position.id for existing in reading.card_draws)`) is gated on
  `DRAFTING` specifically so a non-`DRAFTING` Reading's draw attempt
  falls through to `Reading.add_card_draw()`'s own `DRAFTING` guard,
  producing `ReadingNotDraftingError` rather than being masked by
  `PositionAlreadyDrawnError` — re-confirmed unchanged in
  `reading_service.py`.
- **Spread/deck membership validation:** `position.spread_id !=
  reading.spread_id` and `card.deck_id != reading.deck_id` both collapse
  into `SpreadPositionNotFoundError`/`CardNotFoundError` respectively
  (404), matching the same not-found/not-yours collapsing already used
  by `get_owned_reading`.
- **Duplicate-card behavior:** delegated entirely to
  `Reading.add_card_draw()`'s own, unchanged-since-Step-16 in-memory
  check against `Spread.allow_duplicate_cards` — raises
  `DuplicateCardError`.
- **Duplicate-position behavior:** the in-memory pre-check (sequential
  case) or the `IntegrityError` backstop (concurrent case, not
  guaranteed — Section 4) — raises `PositionAlreadyDrawnError` when
  recognized.
- **Optional-position behavior:** no special-case code exists anywhere;
  `is_spread_complete` (unchanged, `app/models/reading.py`) counts only
  required positions, and the `DRAFTING`-only guard applies uniformly
  regardless of a position's `required` flag.

**All of the above is verified, unchanged, and matches
`CARDDRAW_API_DESIGN.md`'s own contract exactly** (Section 3 below).

---

# 3. Documentation Consistency Matrix

| Document | Claim | Status |
|---|---|---|
| `CARDDRAW_API_DESIGN.md` — endpoint shape, request/response contract, error mappings, service-layer placement | Matches shipped implementation | **No issue** — re-verified field-for-field, mapping-for-mapping against current source (Section 2). |
| `CARDDRAW_API_DESIGN.md` §9 — "IntegrityError backstop... still correctly turns a losing race into a clean 409" | Contradicts current, tested behavior | **Historical/point-in-time, already superseded** — re-confirmed present verbatim; correctly left unedited per this project's convention; superseded by `CARDDRAW_CONCURRENCY_DESIGN.md`/`CARDDRAW_CONCURRENCY_RECONCILIATION.md`. Not re-flagged as an open action (Section 9). |
| `CARDDRAW_POST_IMPLEMENTATION_AUDIT.md` §15 — different-position race produces unhandled `500`, classified "potential risk" | Accurate as of its own writing | **Historical/point-in-time, not misleading** — it discovered only the different-position case; the same-position dual-collision case was found afterward (Step 34) and does not contradict this document, only extends it. |
| `CARDDRAW_CONCURRENCY_DESIGN.md` — full dual-collision finding, options A–E, no selection | Current, most complete technical record | **No issue** — re-confirmed accurate by this step's own re-verification (Section 4). |
| `CARDDRAW_CONCURRENCY_RECONCILIATION.md` — narrowed `PositionAlreadyDrawnError` claim, Option A conclusion, documentation-lineage table | Current, authoritative reconciliation | **No issue** — re-confirmed accurate; its Section 11 recommendation (correct the three live docstrings) was carried out in Step 36, and its own text was correctly never itself edited afterward (it is itself now a point-in-time record of the reconciliation, which is appropriate). |
| `app/models/exceptions.py` — `PositionAlreadyDrawnError` docstring | Post-Step-36 text | **No issue** — re-read fresh; correctly states the pre-check reliably catches the sequential case, the DB constraint is the authoritative *data-integrity* invariant, and the exception itself is not guaranteed under a genuine race. No trace of the old "authoritative backstop for a genuine concurrent-draw race" phrase remains (confirmed by direct grep, zero matches). |
| `app/services/reading_service.py` — `_is_position_already_drawn_violation()` and `record_card_draw()` docstrings | Post-Step-36 text | **No issue** — same re-confirmation; no trace of "practically unreachable" or the old backstop phrase remains. |
| `app/models/reflection_session.py` — `owner_id` docstring | Post-Step-37 text | **No issue** — re-read fresh; correctly states ownership originates at Reading creation via `current_user`, is reached through the 1:1 `reflection_session_id` relationship, and nullability is explained by its current, accurate reason (fixture-constructed rows, `get_owned_reading`'s fail-closed handling). No trace of "no Reading/ReflectionSession-creation API exists yet" remains (confirmed by direct grep, zero matches). |
| `Documentation/PRODUCT_DECISIONS.md`, `docs/ROADMAP.md` | Any CardDraw-specific concurrency, batch, or idempotency claim | **No issue — no such claim exists.** A repository-wide search (Section 6) found neither document mentions CardDraw, batch draws, or idempotency anywhere; nothing in them contradicts or needs reconciling with the CardDraw work. |

---

# 4. Concurrency Contract Reconciliation

Re-verified directly, item by item, against this step's own fresh
re-reads (not merely re-cited from Step 34/35):

- **Data-integrity guarantee vs. HTTP error semantics:** correctly
  distinguished across all four CardDraw design documents and both
  corrected code docstrings. No document anywhere claims the
  `position_id` uniqueness invariant itself is at risk; every document
  that discusses the race is explicit that the *database row* is always
  correct and that only the *client-facing error* is currently poor for
  a genuine race.
- **The accepted single-writer/no-locking limitation:** consistently
  traced to its origin (`Interpretation.sequence`) across
  `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md`,
  `CARDDRAW_API_DESIGN.md`, `CARDDRAW_CONCURRENCY_DESIGN.md`, and
  `CARDDRAW_CONCURRENCY_RECONCILIATION.md` — re-confirmed present and
  unchanged in all four.
- **Same-position race can violate both constraints:** stated correctly
  and specifically only in `CARDDRAW_CONCURRENCY_DESIGN.md` and
  `CARDDRAW_CONCURRENCY_RECONCILIATION.md` (the two documents produced
  after this fact was discovered) — correctly absent from the two
  earlier documents, which predate the discovery and are not thereby
  made inconsistent (they simply do not address a scenario not yet
  found when they were written).
- **SQLite's observed constraint-selection behavior:** stated precisely
  and consistently in both later documents — "SQLite has been observed
  to report the `draw_order` constraint instead" — correctly hedged as
  an empirical observation (reproduced multiple times across two
  independent audit steps), not asserted as documented SQLite behavior.
- **`PositionAlreadyDrawnError` is not guaranteed under a genuine race:**
  now stated identically, in compatible language, in all three locations
  that discuss it post-Step-36: the exception's own docstring, the
  heuristic function's own docstring, and
  `CARDDRAW_CONCURRENCY_RECONCILIATION.md` — re-confirmed by direct
  comparison of the current text against that document's own Section 5
  "narrowest technically accurate statement."
- **No idempotency or retry guarantee exists:** re-confirmed by a fresh
  repository-wide search (`idempoten`, `retry`, `at-least-once`, `at
  most once`, `exactly once`) across `Documentation/*.md` and
  `docs/*.md` — the only match anywhere is `CARDDRAW_API_DESIGN.md`'s
  own test-plan item about the *domain* lifecycle ("Complete spread
  transitions exactly once"), unrelated to HTTP retry/idempotency
  semantics — identical result to Step 35's own search, confirming no
  drift.

**No document currently makes the now-known-invalid "guarantees a clean
409" claim except the one, already-classified, deliberately-unedited
historical record identified in Section 3.** No other document — old or
new — repeats or extends that inaccuracy.

---

# 5. Ownership/Lifecycle Reconciliation

Re-confirmed directly against current source (not assumed from Step 33's
own audit):

- **Ownership originates at Reading creation:** `create_reading()`
  (`reading_service.py`) takes a required (non-optional) `owner: User`
  parameter and constructs `ReflectionSession(owner=owner)` — re-read
  fresh, unchanged since Step 27.
- **`ReflectionSession.owner_id` is the sole ownership anchor:**
  re-confirmed — no other model anywhere in `app/models/` has an
  `owner_id` or equivalent column (re-checked `reading.py`,
  `card_draw.py`, `spread_position.py`, `card.py` directly; none
  declares any ownership-related column).
  `CardDraw` has no duplicated owner field — confirmed directly from
  `card_draw.py`'s full column list (`reading_id`, `position_id`,
  `card_id`, `orientation`, `draw_order` only).
- **`get_owned_reading` remains the authorization boundary:** the sole
  `Depends(...)` used for ownership across every Reading-scoped route,
  including the CardDraw route — re-confirmed by source read of
  `app/api/reading.py` and `app/api/dependencies.py`, both unchanged in
  this respect since Step 22.
- **CardDraw creation cannot bypass ownership:** `record_card_draw_route()`
  resolves `reading` exclusively via `Depends(get_owned_reading)`, and
  `record_card_draw()` itself performs no independent ownership check
  and accepts no owner-identifying parameter — a client-supplied
  `owner_id` in the request body is rejected at the schema layer
  (`extra="forbid"`) before any service code runs.
- **`DRAFTING → SPREAD_COMPLETE → INTERPRETED → SAVED` remains intact:**
  unchanged — `Reading.add_card_draw()`, `save_interpretation()`, and
  `mark_saved()` are the only three places `Reading.status` is ever
  assigned anywhere in `app/`, re-confirmed by a fresh repository-wide
  search for `.status = ReadingStatus` and `self.status =`.
- **Drawing after completion remains rejected:** `add_card_draw()`'s
  `DRAFTING`-only guard, unchanged since Step 16, still fires for any
  non-`DRAFTING` Reading regardless of which position is targeted.
- **Saving remains independent of drawing implementation details:**
  `mark_saved()` (unchanged since Step 18) reads and writes only
  `Reading.status`; it has no awareness of `CardDraw`, `draw_order`, or
  any concurrency mechanism — re-confirmed by source read.

**No lifecycle or ownership invariant has drifted since Step 33's own
audit confirmed the same set of facts.**

---

# 6. Product/API Decision Status

Re-checked against `PRODUCT_DECISIONS.md`, `docs/ROADMAP.md`, and every
`Documentation/*.md` file named in this step's brief, classified per
this step's own four-way scheme (explicitly decided / implementation
detail / deliberately deferred / undocumented assumption):

| Question | Classification | Basis |
|---|---|---|
| Batch vs. single-card draw per request | **Deliberately deferred** | `CARDDRAW_API_DESIGN.md` §12 explicitly names this as a considered-but-undecided alternative, not silently resolved by the single-draw implementation shipped — the document itself frames the single-draw choice as this document's own *recommendation*, not a ratified product decision. |
| Whether to embed card/position display names in `CardDrawSummary` | **Deliberately deferred** | Same document, same section — explicitly named as a deferred enhancement question, and `CardDrawSummary`'s current ID-only shape is presented as a design choice consistent with `ReadingSummary`'s own precedent, not as a closed product decision. |
| Whether `GET /readings/{reading_id}` should exist | **Deliberately deferred** | Named explicitly in `CARDDRAW_API_DESIGN.md` §12 as a separately-scoped, unproposed addition; `reading_status` was added to `CardDrawSummary` specifically to work around its absence, not to substitute a decision that it shouldn't exist. |
| Idempotency/retry semantics for `POST /readings/{reading_id}/draws` | **Undocumented assumption turned into an explicit non-guarantee by `CARDDRAW_CONCURRENCY_RECONCILIATION.md`** | No document ever asserted this route was idempotent or retryable; Step 35's own audit made this absence explicit and precise (Section 7 of that document) rather than leaving it merely unstated. As of this audit, it is accurate to call it **explicitly documented as absent**, not merely undocumented. |
| Remaining Product Spec/API contract ambiguity | **None found beyond the above four** | `RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, re-checked for any CardDraw-specific requirement language, contains none — the Product Spec speaks only to the general Reading/Draw lifecycle (Section 17's immutability language, already satisfied), not to any HTTP-level contract detail this audit's four questions above don't already cover. |

**No product decision was resolved by this audit.** Each item above is
reported exactly as it already stood after Step 31; the shipped
implementation's specific choices (single-draw, ID-only response, no
`GET` route, no retry) are correctly documented as *implementation
choices consistent with an explicitly deferred question*, not as the
product decision itself.

---

# 7. Test Coverage Reconciliation

Cross-checked the 30 CardDraw tests in `tests/test_api_reading.py`
(enumerated fresh for this step, not assumed from Step 32's own count)
against Section 2's contract:

**Explicitly, directly tested:** authentication (`401`), ownership
(cross-user and `NULL`-owner `404`), all three request fields' presence/
type validation (`422` for malformed/missing/unknown/client-supplied
`draw_order`/`owner_id`), both orientation values, server-computed
`draw_order` (first and subsequent), duplicate-card rejection,
sequential same-position rejection, non-`DRAFTING` rejection, the
`DRAFTING`→`SPREAD_COMPLETE` transition (including "exactly once"),
nonexistent/foreign-spread position, nonexistent/foreign-deck card,
transaction rollback on forced failure, the unrelated-`IntegrityError`
non-swallowing case (service-level), and `reading_status` presence and
correctness in the response.

**Only indirectly tested:** the interaction between CardDraw recording
and the rest of the lifecycle (interpret/save/history) is not exercised
by any test *inside* `test_api_reading.py`'s CardDraw section itself —
it is covered by the pre-existing `_complete_reading()`/
`build_reading()` helpers used throughout the file's Save/History
sections, which construct completed Readings via direct model calls
(`add_card_draw()`), not via the HTTP route. The full HTTP-level chain
(create → draw → draw → draw → interpret → save → history) is exercised
only by this audit's own and Steps 29/33's own throwaway scripts, never
codified as a permanent test.

**Meaningful contract behaviors with no test coverage:**
- The optional-position scenario (Section 8 of `CARDDRAW_POST_IMPLEMENTATION_AUDIT.md`)
  — still true, unchanged since Step 33; no real seeded spread contains
  an optional position, so this remains a coverage gap without also
  being a production risk.
- A true concurrent race of either shape (same-position or
  different-position) — deliberately not codified as a permanent test,
  per `CARDDRAW_CONCURRENCY_RECONCILIATION.md` §10's own explicit
  conclusion that this is optional under the chosen Option A (accept and
  document), not required.

**Tests that could be mistaken for encoding a product guarantee as an
implementation detail:** none found. Every test in the CardDraw section
asserts either a concrete status code plus a concrete persisted-state
check, or a concrete response-field value — none asserts a
concurrency-specific guarantee (e.g., no test asserts "a concurrent
request always returns 409"), consistent with no such guarantee existing
to encode.

**No test was added, modified, or deleted in this step.**

---

# 8. Findings, Classified

| # | Finding | Classification |
|---|---|---|
| 1 | `CARDDRAW_API_DESIGN.md` §9's "turns into a clean 409" claim | **Historical/point-in-time** — correctly superseded, correctly left unedited, no action needed. |
| 2 | Optional-position scenario has no test | **Documentation correction needed? No — already correctly documented as an accepted, non-urgent gap** (`CARDDRAW_POST_IMPLEMENTATION_AUDIT.md` §11, unchanged conclusion); not re-classified as more urgent by this audit. |
| 3 | No HTTP-level end-to-end test of the full CardDraw→History chain | **No issue** — the chain's individual segments are each fully tested at the HTTP level (creation, save, history) and CardDraw itself is fully tested at the HTTP level; only their *end-to-end composition* lacks a single permanent test, which is a coverage-completeness observation, not a contract gap, since nothing in the composition is untested individually. |
| 4 | Four product/API questions remain open (Section 6) | **Product/governance decision needed, if ever pursued — not urgent, already correctly named, not newly discovered.** |
| 5 | Everything else audited (Sections 2–5, 7) | **No issue.** |

**No implementation defect was found.**

---

# 9. Exact Recommended Corrections, If Any

**None are required.** The one documentation item this audit's own
matrix names (Finding 1) is already fully addressed by the existing
governance chain (superseding documents plus corrected code comments) —
re-editing the historical `CARDDRAW_API_DESIGN.md` record would
contradict this project's own established convention (preserve
design/audit documents as point-in-time records) without adding any
missing information, since the correction already exists, twice over, in
later documents.

If a future step nonetheless wants to leave a pointer, the smallest
available action (not recommended as necessary, only named as available,
per this audit's own no-runtime-change constraint and the fact that this
is itself a documentation file, not runtime code) would be a one-line
note in a future document indexing which CardDraw documents are
current — not a change to `CARDDRAW_API_DESIGN.md` itself.

---

# 10. Stop-Condition Assessment

**No stop condition was triggered.** No implementation defect, no
authorization bypass, no lifecycle inconsistency, no contradiction of an
approved decision, and no silently-resolved product decision was found
anywhere in this audit. The single documentation item tracked (Finding
1) was already known, already classified, and already correctly handled
by prior steps — re-confirming it is not the same as discovering it.

---

# 11. Final Repository/Test-State Verification

- **Full test suite:** run fresh for this step — **411 passed, 0
  failed, 2 warnings** (the same two pre-existing
  `InsecureKeyLengthWarning`s from `test_security.py`, unchanged).
- **`git diff --check`:** clean, no whitespace errors (exit code 0).
- **Migration heads:** single head, `5dc3cb471b18`; 6 migration files —
  unchanged.
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
  Exactly Step 37's own end state — no unexpected modified or untracked
  file exists anywhere in the repository. Nothing changed outside this
  audit's own new file,
  `Documentation/CARDDRAW_API_CONTRACT_RECONCILIATION.md`.
- **Nothing committed or pushed.**
