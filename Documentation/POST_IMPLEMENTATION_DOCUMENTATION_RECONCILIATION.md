# Post-Implementation Documentation & Product Decision Reconciliation (Step 30)

Read-only reconciliation pass. No application code, test, schema,
migration, dependency, or frontend file was modified in producing this
report, and no existing `Documentation/*.md` file was edited. Nothing was
committed or pushed. This document distinguishes **confirmed facts**
(re-verified directly against the current repository), **documented
inconsistencies** (a claim somewhere that no longer matches current code),
and **recommendations** (left for a human/product decision, never made
here).

---

# 1. Executive Summary

- **One genuinely stale statement was found and requires updating**: a
  docstring in `app/models/reflection_session.py` describes Reading
  creation as not-yet-built. It is now factually wrong — `POST /readings`
  has existed since Step 27. This is a code comment (living documentation
  read alongside current code), not a point-in-time design record, so it
  is the one place this audit recommends an actual text change.
- **No other stale claims were found in production code.** A
  repository-wide search for the same class of claim (no route/API
  exists, ownership cannot be established, "not built here") turned up
  exactly this one location.
- **Every `Documentation/*.md` design/audit document that says "no Reading
  creation route exists" remains historically accurate** — each was
  written and approved *before* Step 27, describing the repository as it
  stood at that time, consistent with this project's established,
  repeatedly-reaffirmed convention that these documents are point-in-time
  decision records, never retroactively edited after their own step's
  implementation lands. They are not contradictions; they are dated
  snapshots, correctly labeled as such by their own step numbers.
- **Q1 (narrative MVP) remains open, exactly as `PRODUCT_DECISIONS.md`
  already found it.** The Product Spec's plain text and the shipped
  deterministic narrative layer are not in conflict about the *intended
  end state* (both want AI-authored narrative via the Reflection Engine
  eventually) — the gap is that the Product Spec's MVP text has not been
  formally amended to record the deterministic layer as the approved
  interim substitute. That governance action is still outstanding, is not
  performed here, and this document does not recommend which way it
  should be resolved.
- **The CardDraw HTTP gap is reconfirmed, unchanged, and still explicitly
  out of scope** under every approved design document that named it.
  Nothing about Steps 22–29 altered that scoping.
- **Repository is clean.** Same commit as Step 28/29 (`ce1a7fb`), same
  single migration head, `381` tests passing, only the pre-existing
  `README.md` modification and the now-nine untracked `Documentation/*.md`
  files (eight prior + Step 29's audit).

---

# 2. Current Implementation Baseline

- **Branch:** `main`.
- **HEAD commit:** `ce1a7fb` — "feat: implement authentication, ownership,
  and Reading save/history/creation" — unchanged since Step 28; Step 29
  added no commit (it only created an untracked documentation file).
- **Test suite:** re-run fresh for this step — `381 passed, 2 warnings`
  (the same two pre-existing `InsecureKeyLengthWarning`s from
  `test_security.py`'s deliberately undersized negative-path secrets).
- **Migration head:** single head `5dc3cb471b18`; 6 migration files.
- **Routes:** 3 route files (`auth.py`, `interpretation.py`, `reading.py`),
  8 routes total — unchanged since Step 27.

---

# 3. Stale Documentation Findings (Item A)

## 3.1 The one confirmed stale statement

**File/location:** `backend/app/models/reflection_session.py`, lines
29–33 (the `ReflectionSession` class docstring, `owner_id` paragraph).

**Current statement (verbatim):**
> "Nullable because no Reading/ReflectionSession-creation API exists yet
> (Documentation/AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md
> Section 4.4) -- there is currently no code path that could supply a
> value at insert time. A future Reading-creation route must set it from
> the authenticated caller; not built here (Step 22 scope)."

**What the implementation now actually does:** `POST /readings`
(`app/api/reading.py::create_reading_route`, wired to
`app/services/reading_service.py::create_reading()`, Step 27) is exactly
that "future Reading-creation route." It requires an authenticated caller
(`Depends(get_current_user)`) and sets `ReflectionSession(owner=owner)`
at construction — precisely the mechanism the docstring describes as not
yet existing.

**Is the statement stale?** Yes, in part:
- "no Reading/ReflectionSession-creation API exists yet" — **stale**,
  now false.
- "there is currently no code path that could supply a value at insert
  time" — **stale**, now false; `create_reading()` always supplies one.
- "A future Reading-creation route must set it from the authenticated
  caller" — **stale in tense** (describes a future event that has
  already happened), though the *requirement* it states is exactly what
  the now-existing route does.
- "not built here (Step 22 scope)" — **still true and worth keeping**:
  it correctly scopes what Step 22 itself did *not* build, which remains
  an accurate historical fact about that step regardless of what a later
  step did.

The column's actual behavior (`nullable=True`) is **not** stale — it is
still correct and still necessary: a `ReflectionSession` can still be
constructed with `owner=None` today (test fixtures do this deliberately,
and Step 29's audit constructed one directly to verify the NULL-owner
fail-closed behavior), so `NOT NULL` still cannot be safely enforced
schema-wide. Only the prose explaining *why* it's nullable is out of
date — the reasoning it originally gave ("no code path could supply a
value") no longer holds, even though nullability itself remains correct
for an unrelated, still-true reason (non-API-created rows can still
exist).

**Minimal documentation change that would be appropriate** (not applied
here): replace the "no ... API exists yet" framing with something to the
effect of: *"Nullable because a `ReflectionSession` can still be
constructed without an owner (e.g. by test fixtures) even though
`POST /readings` (Step 27, `app/services/reading_service.py::create_reading()`)
always supplies one for API-created Readings — `get_owned_reading`
(`app/api/dependencies.py`) treats a NULL-owner Reading as inaccessible
to every authenticated caller rather than relying on a NOT NULL
constraint to prevent one from existing."* This is a one-paragraph,
same-file, comment-only edit with no schema or behavior change implied.

## 3.2 Repository-wide search for other instances of the same claim

A pattern search across `backend/app/` and `backend/tests/` for the same
class of claim (variations of "no Reading/ReflectionSession-creation API
exists," "no route exists that creates a Reading," "no code path that
could supply an owner," "not built here") found **no other occurrence in
production code**. One adjacent, non-stale hit was found and is not a
finding: `app/api/auth.py`'s module docstring ("No ownership/
Reading-authorization logic belongs here") — this is a still-true
statement about where ownership logic *does* live (`app/api/dependencies.py`),
not a claim that ownership logic doesn't exist anywhere.

## 3.3 Documentation/*.md files: historically accurate, not contradictions

Every `Documentation/*.md` file reviewed (the eight named in this step's
instructions) that states "no Reading-creation route exists" —
`AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` Sections 4.4/4.5,
`READING_CREATION_OWNERSHIP_DESIGN.md` Sections 31/55/112 and others,
`READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 2.6 — was
written and approved *before* Step 27 existed, as part of the audit or
design process that led to Step 27 being built. Each is explicit about
its own point-in-time nature (e.g. `AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md`
Section 4.4: "Once the (not-yet-existing) Reading/ReflectionSession-creation
path is built... `NOT NULL` becomes both safe and correct to enforce from
that point forward" — a conditional statement about a future event, not a
claim about the eternal present).

**These are not classified as stale or as contradictions.** This
matches the standing, repeatedly-reaffirmed convention of this entire
project series: design and audit documents are historical decision
records, preserved exactly as approved, never retroactively edited to
match later implementation state. Retroactively "fixing" them would
destroy their value as a record of what was known/decided at each step
and is explicitly outside this step's (and every prior step's) authorized
scope ("preserve all previously-created design documents exactly as-is").
A reader who understands these documents as dated (each carries a "Step
N" designation and a list of prior documents it was checked against) is
not misled by them; a reader of `app/models/reflection_session.py`'s
docstring today, with no step number attached, reasonably would be —
which is the actual distinction driving Section 3.1's finding.

## 3.4 Other documentation contradictions introduced by Steps 22–28

Beyond the one item above, no other documentation/implementation
contradiction was found. Specifically checked and found consistent:
- `app/api/interpretation.py`'s module docstring (retrofitted in Step 22)
  accurately describes the current `get_owned_reading`-gated behavior —
  no stale "no authentication exists" language remains (the pre-Step-22
  version of this docstring, visible in Step 28's committed diff, did say
  exactly that; it was correctly updated as part of Step 22 itself).
- `app/api/reading.py`'s module docstring (Step 24, extended Step 27)
  accurately attributes each route to its origin step and design
  document.
- `app/services/reading_service.py`'s docstring accurately describes its
  own scope and non-responsibilities (no stale claims found).
- No schema (`app/schemas/reading_api.py`, `app/schemas/auth.py`) docstring
  makes a claim contradicted by current behavior.

---

# 4. Product/Governance Q1 Reconciliation (Item B)

This section restates, precisely and without adding a new opinion, what
`PRODUCT_DECISIONS.md`'s own Q1 already established, re-verified directly
against the current repository rather than assumed from that document's
text.

**What the Product Spec currently says** (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md`,
re-read directly, Sections 3.3, 5 step 11, 12, 20 Phase 4 — confirmed
unchanged since `PRODUCT_DECISIONS.md` was written): Narrative Generation
is described, unconditionally and without any MVP/phased carve-out, as
AI-authored prose produced by calling the Reflection Engine (the
platform's sole sanctioned AI gateway per ADR-0005) with the finished
Interpretive Model as its factual basis. Section 20 Phase 4's build plan
for Narrative Generation consists entirely of authoring Reflection-Engine
prompt files and wiring through ADR-0005 — no deterministic-only phase is
described anywhere in that document.

**What the implementation currently does** (re-confirmed directly, Step
29 Section 7 and re-checked here): `app/services/narrative/` is a
complete, fully deterministic, template-based prose assembler. It
contains no AI-provider call and no Reflection Engine reference anywhere.
No Reflection Engine module exists anywhere in this repository (confirmed
by search). The four prompt files the Product Spec names
(`prompts/system/reflection_engine.md`, `prompts/system/safety.md`,
`prompts/system/tone.md`, `prompts/interpretation.md`) remain 0 bytes each
— re-confirmed directly for this step.

**Is this an actual contradiction, or a sequencing issue?** `PRODUCT_DECISIONS.md`
Q1 already answers this precisely, and re-reading it against the current
repository does not change the answer: it is **a sequencing/dependency
issue, not a disagreement about intended direction**. Both documents want
the same eventual thing (AI-authored narrative, exclusively via the
Reflection Engine, per ADR-0005) — the Product Spec simply describes that
end state as available for MVP, when in fact its enabling platform
dependency (the Reflection Engine, listed in `docs/ROADMAP.md` as a
cross-cutting M1 milestone alongside Authentication, not a
Raidian-Wise-specific piece of work) does not exist anywhere in the
codebase yet, for any component. `PRODUCT_DECISIONS.md` explicitly notes
that building a one-off AI call just for Raidian Wise's narrative would
itself violate ADR-0005's "exclusively through the Reflection Engine"
mandate — so "just build what the spec says" is not actually an available
option today, independent of preference. This is why `PRODUCT_DECISIONS.md`
frames it as the Product Spec being "inaccurate to what will actually ship
as MVP unless formally amended," not as a design error in either
document.

**What decision/ADR/spec clarification is still required:** exactly what
`PRODUCT_DECISIONS.md` Section 8 already names, re-confirmed as still
outstanding: a formal governance action — either a new ADR (in
`docs/DECISIONS.md`) or a `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` revision (or
both) — recording that the deterministic Narrative Layer (`[A]`,
`NARRATIVE_LAYER_DESIGN.md`) is the accepted MVP substitute for the
originally-specified AI/Reflection-Engine narrative (`[A']`), with `[A']`
remaining the long-term required target rather than abandoned. **This
document does not perform that action and does not recommend which of
the two (or which combination) is the right mechanism** — that choice, and
whether to accept Option 3 from `PRODUCT_DECISIONS.md`'s own three
considered options at all, remains a human/product decision.

**Which existing document should own that decision:** per the governance
hierarchy `docs/DECISIONS.md` ADR-0006 establishes (Charter → Vision →
Principles → Architecture → Decisions → Agents → Roadmap → Naming
Conventions), `PRODUCT_DECISIONS.md` itself is explicit that it "has no
authority to enact" this — it is a recommendation document, not a
decision-of-record. The two documents actually positioned to hold this
decision are **`docs/DECISIONS.md`** (a new ADR, the natural home for a
platform-level architectural staging decision, sitting at the
"Decisions" tier of the governance hierarchy) and/or
**`RAIDIAN_WISE_PRODUCT_SPEC_V1.md`** itself (a direct revision of
Sections 3.3/5/12/20's MVP language). Note: `RAIDIAN_WISE_PRODUCT_SPEC_V1.md`
does not appear by name in ADR-0006's own eight-tier list, which is
itself worth flagging as a minor governance-structure gap (not
resolved here) — the Product Spec's own authority level relative to
that hierarchy is not explicitly stated anywhere this audit found.

**What implementation work, if any, is blocked by this:** **none,
currently.** `PRODUCT_DECISIONS.md` states this directly ("Implementation
impact: None required by this document itself... no code change follows
from Q1 alone"), and re-verification confirms it still holds: the
deterministic narrative layer is fully built, tested, and shipping today
regardless of whether the governance action happens. The only thing
genuinely blocked is the Product Spec text's *accuracy* about what MVP
delivers — not any code. Separately, and not contingent on this
governance action at all, the future `[A']` (AI-assisted) design work
remains blocked on the Reflection Engine existing as a platform capability
— an independent, larger, cross-cutting dependency that this document's
resolution would not remove either way.

---

# 5. Remaining CardDraw HTTP Gap (Item C)

**Status, reconfirmed directly for this step:** unchanged since Step 29's
audit. `Reading.add_card_draw()` (`app/models/reading.py:108`) remains
the sole production-code path that creates a `CardDraw`. No file under
`app/api/` references it — reconfirmed by a fresh search. It is called
from exactly one place in the entire repository:
`tests/interpretation_helpers.py::build_reading()`, a test helper.

**Is this still explicitly out of scope under the existing approved
designs?** Yes, unchanged, re-confirmed by re-reading the specific
sections that name it:
- `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 2.6: "No API
  route exists anywhere that creates a Reading, records a draw, or saves
  a Reading" (written before Step 24 or 27 existed) and Section 15/348:
  the draw-recording route is named as future work, explicitly not
  designed by that document.
- `READING_CREATION_OWNERSHIP_DESIGN.md` Section 16/332: "**The
  draw-recording API** (`POST /readings/{id}/draws` or equivalent) —
  `Reading.add_card_draw()` is already fully implemented and tested (Step
  16), but no route calls it anywhere, and designing that route is a
  distinct, separately-scoped piece of future work this document
  deliberately does not fold into 'Reading creation.'"
- `READING_CREATION_API_DESIGN.md` line 180: reaffirms the same boundary
  when explaining why `ReadingSummary` (not a richer representation) was
  chosen for the creation response — "its only plausible consumer — a
  future card-entry/draw-recording client — is itself explicitly out of
  scope and undesigned."

Step 27 built Reading creation and explicitly did not fold the
draw-recording route into that work, consistent with all three documents
above. Nothing in Steps 22–29 altered, narrowed, or widened this scoping
in any way.

**Which future design/implementation step should address it:** following
the exact pattern already established by this series for every other
lifecycle surface — a **Design/Audit step** (mirroring Steps 19, 25, 26)
that turns `Reading.add_card_draw()`'s existing, already-tested model-level
contract into a concrete `POST /readings/{id}/draws`-shaped (or
equivalent) API contract, addressing at minimum: request/response shape,
whether a single draw or a batch of draws is accepted per call, how
`draw_order` is supplied or inferred, ownership enforcement (reusing
`get_owned_reading`, per every design document's own repeated instruction
that the route "must call `Reading.add_card_draw()`... and must not
re-implement the `SPREAD_COMPLETE` check, the immutability guard, or the
completion definition itself" —
`READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 10), and error
mapping for `ReadingNotDraftingError`/`DuplicateCardError`/invalid
position or card references — followed by a corresponding
**Implementation step**, exactly mirroring the Step 26 → Step 27
relationship this project already used for Reading creation itself. This
document does not perform that design work and does not implement the
route, per this step's own instruction.

---

# 6. Cross-Document Consistency Audit

Beyond items A and B, the following were checked directly against current
code and found **consistent, no new contradiction found**:

| Document | Claim checked | Current implementation | Result |
|---|---|---|---|
| `AUTHENTICATION_OWNERSHIP_DESIGN.md` | JWT/HS256, `get_current_user`/`get_owned_reading` boundary, 404-not-403 collapsing | `app/api/dependencies.py`, unchanged since Step 22 | Consistent |
| `AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` | User model shape, registration/login contract, bcrypt/PyJWT choice | `app/models/user.py`, `app/api/auth.py`, `app/core/security.py` | Consistent |
| `READING_HISTORY_OWNERSHIP_DESIGN.md` | Ownership anchored on `ReflectionSession.owner_id`, History never joins `Interpretation` | `app/api/reading.py::list_saved_readings_route` | Consistent |
| `SAVE_READING_DESIGN.md` | `mark_saved()` semantics, idempotency, no Interpretation/Narrative side effects | `app/models/reading.py::mark_saved()` | Consistent |
| `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` | `is_spread_complete` uses required-position coverage, not draw count | `app/models/reading.py::is_spread_complete` | Consistent (re-verified directly with an optional-position probe in Step 29) |
| `READING_CREATION_OWNERSHIP_DESIGN.md` / `READING_CREATION_API_DESIGN.md` | Creation contract, default Deck resolution, no owner field in request | `app/services/reading_service.py`, `app/schemas/reading_api.py` | Consistent |
| `PRODUCT_DECISIONS.md` Q2/Q3/Q4/Q5/Q6 | `SPREAD_COMPLETE` assignment mechanism, `SAVED` meaning, no interpretation-pinning, single-endpoint interpret-then-fetch, full transition rule set | Reviewed against `app/models/reading.py`, `app/services/interpretation/persistence.py` | Consistent |
| `READING_LIFECYCLE_POST_IMPLEMENTATION_AUDIT.md` (Step 29, this project's own prior output) | Every finding it reports | Spot-checked several against current code for this step (migration head, test count, route/construction-site counts) | Consistent — no drift found between Step 29 and now, as expected given zero commits since |

No document was found asserting something the current implementation
contradicts, other than the single stale code-comment identified in
Section 3.1.

---

# 7. Required Documentation Updates

Exactly one, matching Section 3.1: the `owner_id` paragraph of
`app/models/reflection_session.py`'s class docstring should be edited (a
comment-only change, no behavior change) to stop describing Reading
creation as not-yet-built and instead explain nullability in terms of its
current, still-true rationale (fixture-constructed and any other
non-API-originated `ReflectionSession` rows can still lack an owner, and
`get_owned_reading` — not a `NOT NULL` constraint — is what makes that
safe). **Not applied in this step**, per its read-only, no-code-changes
instruction; left for a future, explicitly authorized implementation
touch (even a trivial one).

No `Documentation/*.md` file requires an update under this project's own
established convention (Section 3.3) — they are point-in-time records,
correctly dated, not living documentation.

---

# 8. Open Product Decisions

1. **Q1 (narrative MVP governance action)** — restated precisely in
   Section 4. Not resolved here. Owner: a human/product decision-maker,
   recorded via `docs/DECISIONS.md` and/or `RAIDIAN_WISE_PRODUCT_SPEC_V1.md`.
2. **`ReadingSummary` vs. a richer `ReadingDetail` for a future
   draw-recording/card-entry client** — named, unchanged, by
   `READING_CREATION_API_DESIGN.md` (Section 5 of this document's own
   Step 29 predecessor); still open, still not decided here.
3. **The Product Spec's own place in the ADR-0006 governance hierarchy**
   — noted in Section 4 as a minor, newly observed structural gap (the
   eight-tier list does not name it explicitly); not a blocker to
   anything currently built, and not resolved here.

---

# 9. Implementation Blockers / Non-Blockers

**Blocked on nothing found in this audit:**
- Every currently-shipped feature (authentication, ownership, Reading
  creation, interpretation, save, history, the deterministic narrative
  layer) functions correctly today and is blocked by none of the open
  items above.

**Genuinely blocked, independent of this step's findings:**
- The `[A']` AI-assisted narrative pass remains blocked on the Reflection
  Engine existing as a platform capability (a cross-cutting M1 milestone,
  not Raidian-Wise-specific) — unchanged, and not something a Q1
  governance action alone would unblock.
- The draw-recording HTTP route is not "blocked" so much as simply
  **not yet designed** — Section 5's recommended next step (a Design/Audit
  pass) is the only prerequisite, not a decision or external dependency.

**Not blocked, but incomplete:**
- The stale docstring (Section 3.1) does not block anything; it is a
  documentation-accuracy issue only.

---

# 10. Repository / Test Verification (Item D)

- **Branch:** `main`.
- **Commit:** `ce1a7fb` — identical to Step 28 and Step 29; no commit was
  made in Step 29 or in this step.
- **Working-tree modifications:** `README.md` only — the same
  pre-existing, byte-identical, 94-insertion diff verified at every prior
  step in this series.
- **Untracked documentation:** nine files — the eight named in this
  step's instructions plus `READING_LIFECYCLE_POST_IMPLEMENTATION_AUDIT.md`
  (created by Step 29). This document
  (`POST_IMPLEMENTATION_DOCUMENTATION_RECONCILIATION.md`) is the tenth,
  added by this step.
- **Migration head:** single head, `5dc3cb471b18`; 6 migration files —
  unchanged.
- **Full test count:** `381 passed, 2 warnings`, re-run fresh for this
  step (not assumed from Step 28/29's own reports).
- **Unexpected changes since Step 28:** none found. `git diff --stat`
  against tracked files shows only `README.md`'s unchanged 94-insertion
  diff; no application file, test, schema, migration, or dependency file
  differs from the state committed in `ce1a7fb`.

---

# 11. Recommended Next Step

Two independent, non-conflicting paths are available, neither decided or
prioritized over the other by this document:

1. **A small, low-risk implementation touch**: correct the stale
   `app/models/reflection_session.py` docstring per Section 3.1/7 — a
   single-paragraph, comment-only change with no schema, behavior, or
   test impact, needing at most a brief, explicitly authorized
   implementation step (or could be folded into whatever step touches
   that file next).
2. **A new Design/Audit step for the draw-recording API** (Section 5) —
   the next substantive piece of lifecycle work this series has already
   flagged, twice, as the one remaining gap between the current
   implementation and a fully HTTP-reachable creation-to-history
   lifecycle.

Separately, and on a different track entirely: **the Q1 governance
action** (Section 4/8) remains available for a human/product
decision-maker to take up whenever they choose — it is not gated on
either of the two paths above, and nothing in this project's own
technical roadmap is currently blocked by it remaining open.

**No code, schema, migration, test, frontend, or other documentation file
was modified. This file and its immediate predecessor
(`READING_LIFECYCLE_POST_IMPLEMENTATION_AUDIT.md`, Step 29) are the only
new files present that were not already untracked before Step 29. Nothing
was committed or pushed.**
