# Raidian Wise — Interpretation Engine Design (Step 1: Contract)

# Document Information

Version: 1.1 (Draft for Review — open questions resolved)
Status: Proposed — Not Yet Approved
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Defines Step 1 of the deterministic Interpretation Engine: its input/output contract, allowed information sources, and the resolved design-level decisions for the six questions that contract raised (Section 9). This is a design contract, not an implementation — no engine code, schema change, or migration is created by this document.

Audience:
Software engineers and AI development agents implementing the Interpretation Engine (Step 2 onward).

Authority:
This document concretizes `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` (Sections 9–13: Interpretation Architecture, The Interpretive Model, Compound-Theme Architecture, Narrative Generation Architecture, Explainability) and `RAIDIAN_WISE_ARCHITECTURE_V1.md` (Sections 5–7) against the *actual, current* implementation, rather than the conceptual sketch those documents proposed before any code existed. Where this document narrows or refines those sketches, it says so explicitly; it does not override them. It does not override `docs/ARCHITECTURE.md`'s ADR-0005 boundary (AI access exclusively through the Reflection Engine).

---

# 0. Scope

This document defines **Step 1 only**: the engine's input contract, allowed information sources, output contract, determinism requirements, and responsibility boundaries. It does **not**:

- Implement the engine, any pipeline stage, or any compound-theme rule.
- Create or modify any database model, migration, or reference-data file.
- Design the internal algorithm for any individual stage (theme scoring, trajectory derivation, etc.) — that is Step 2+.

Per instruction, no existing functionality was changed to produce this document.

---

# 1. Repository Inspection Summary

Findings from inspecting the current codebase (`backend/app/models/`, `backend/app/seed/`, `backend/app/reference_data/`, `backend/tests/`) as of commit `8c766af`, before writing this design. This section exists so Sections 2–9 can cite it instead of asserting facts inline.

## 1.1 What exists (confirmed, implemented, tested)

- **Models**: `Deck`, `Card`, `CardCorrespondence`, `Spread`, `SpreadPosition`, `ReflectionSession`, `Reading`, `CardDraw` (`backend/app/models/`). All SQLAlchemy 2.0-style, UUID primary keys, `created_at`/`updated_at` on every table.
- **Reference data**: 78 RWS cards (`backend/app/reference_data/rider_waite_smith/*.yaml`) with original-wording meanings, keywords, and themes; 78 correspondence records (`correspondences.yaml`); a **closed, enforced** 107-tag theme vocabulary (`theme_vocabulary.yaml`); 3 spreads (Single Card, Three Card, Celtic Cross) with positions.
- **Loading**: `app/seed/loader.py` (parse + validate YAML, no DB) and `app/seed/seed.py` (idempotent upsert into the DB) — see `RAIDIAN_WISE_REFERENCE_DATA_V1.md` for the full pipeline.
- **No `services/`, `schemas/`, or `api/` directories exist yet.** Nothing beyond models, DB session plumbing, and the reference-data loader/seed pipeline has been implemented. `backend/app/main.py` is still the bare FastAPI stub from initial scaffolding.
- **`prompts/*.md` files (repo root) are all empty** — no Narrative Generation prompt content exists.
- **Tests**: `backend/tests/` — one file per model/concern, `conftest.py` provides an in-memory SQLite `db_session` fixture with foreign keys enforced, `factories.py` provides minimal object builders. 102 tests, all passing as of this commit.

## 1.2 What is proposed but NOT implemented

These appear in `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` / `RAIDIAN_WISE_ARCHITECTURE_V1.md` as sketches, written before any schema existed. They are **not** in the current database:

- `Reading` has **no** `interpretation_engine_version`, `interpretive_model`, or `narrative` column. `ReadingStatus` has **no** `interpreted` value (only `drafting`, `spread_complete`, `saved` — see `app/models/enums.py`). **There is currently nowhere in the schema to store the Interpretation Engine's output.**
- `Reading` has **no** `notes`, `scripture_enabled`, or `scripture_translation` column.
- No `InterpretiveModel` Pydantic schema, no `services/interpretation/` package, no `CompoundThemeRule` registry — these are sketched in `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 6 as illustrative Python, not implemented.
- No Reflection Engine, Narrative Generation service, or Scripture Engine integration exists in this repository.

This gap (no output storage) is the single biggest fact this design must account for — resolved in [Section 9, Q1](#9-resolved-design-decisions).

## 1.3 Documentation drift noticed (not fixed here)

`RAIDIAN_WISE_ARCHITECTURE_V1.md` Sections 2 and 4 still sketch `layout.py` / `layout_position.py` / `layout_id`, predating the approved Spread/SpreadPosition naming (`docs/NAMING_CONVENTIONS.md`, confirmed in the actual models). This document uses the current, correct names throughout. Fixing the architecture doc's stale naming is out of scope here (not part of this task, and not a correctness issue for the engine design itself).

---

# 2. Engine Inputs

Grounded in the actual model fields (Section 1.1). "Confirmed" means the field exists today and is populated by existing, tested code paths (`Reading.add_card_draw`, the seed pipeline). "Proposed" means it does not exist yet.

## 2.1 Reading / question context — `Reading`

| Field | Type | Status |
|---|---|---|
| `question` | `str`, non-empty (validated) | Confirmed |
| `question_domain` | `str \| None` | Confirmed field; **no fixed taxonomy exists** — `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 16 Q6 was never resolved. The engine must treat this as free text or `None`, not a closed enum, until Q6 is resolved — see [Section 9, Q3](#9-resolved-design-decisions) (question-domain weighting deferred, not implemented in Step 2). |
| `draw_method` | `physical \| digital` | Confirmed. **Must not branch engine logic** — see [Section 3.2](#32-must-not-use) and `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 5 ("Interpretation Engine code never branches on draw method"). Available only for provenance/display. |
| `status` | `drafting \| spread_complete \| saved` | Confirmed. The engine is invoked *because* a Reading reaches a ready state (product spec: user explicitly triggers "Interpret My Reading" — Section 5, step 9) — it is a trigger condition, not an analytical input. No `interpreted` status exists yet to transition *to* (Section 1.2). |
| `notes` | — | **Does not exist on `Reading`.** Not an available input. |

## 2.2 Spread definition — `Spread` + `SpreadPosition`

| Field | Type | Status |
|---|---|---|
| `Spread.name`, `.description` | `str` | Confirmed |
| `Spread.allow_duplicate_cards` | `bool` | Confirmed. Relevant context (a spread permitting duplicates changes what "the same card in two positions" means), not something the engine enforces (that's `Reading.add_card_draw`'s job, already implemented). |
| `Spread.positions` | ordered `list[SpreadPosition]`, by `position_order` | Confirmed |
| `SpreadPosition.name`, `.description` | `str` | Confirmed |
| `SpreadPosition.position_order` | `int`, 1-based, contiguous | Confirmed, DB-enforced (unique + check constraint) |
| `SpreadPosition.semantic_role` | `SemanticRole` enum: `significator, situation, recent_past, influence_blocker, near_future, advice, advice_clarifier, general` | Confirmed. **This is the primary structural signal** the engine reasons over (trajectory, advice/clarifier pairing, blocker detection) — see `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 9, stages 4/7/8. |
| `SpreadPosition.required` | `bool` | Confirmed |

`position_order` (the Spread's own defined sequence) is the field that carries structural/interpretive meaning for trajectory and adjacency logic — **not** `CardDraw.draw_order` (Section 2.4), which is a data-entry/physical-draw sequence with no interpretive significance of its own. Conflating the two would be a real implementation bug; Step 2 should key all positional reasoning off `SpreadPosition.position_order` and `semantic_role`.

## 2.3 Card selections — `Card` (via `CardDraw.card`)

| Field | Type | Status |
|---|---|---|
| `name`, `arcana`, `suit`, `rank` | — | Confirmed |
| `base_meaning_upright`, `base_meaning_reversed` | `str` | Confirmed. Prose text — available for **citation/quotation in output**, not for the engine to parse or run NLP over. Deterministic logic operates on the structured fields below, not by interpreting this prose. |
| `keywords` | `list[str]` | Confirmed |
| `primary_themes`, `secondary_themes` | `list[str]`, drawn from the closed 107-tag vocabulary | Confirmed. **The primary structured signal for theme-based analysis** (scoring, compound-theme matching). |

## 2.4 Card positions, orientation, draw order — `CardDraw`

| Field | Type | Status |
|---|---|---|
| `card_id` → `Card`, `position_id` → `SpreadPosition` | — | Confirmed. This is how "which card is in which position" is known — there is no other path. |
| `orientation` | `Orientation` enum: `upright \| reversed` | **Confirmed, currently supported.** Determines which of `base_meaning_upright`/`base_meaning_reversed` (and, in a future stage, which thematic weighting) applies. |
| `draw_order` | `int`, 1-based, unique per reading | Confirmed. Provenance/display only (Section 2.2) — not structural. |

A Reading's full card set is `reading.card_draws`, already ordered by `draw_order` at the relationship level (`Reading.card_draws` — `order_by="CardDraw.draw_order"`); Step 2 should re-derive spread-structural order from each draw's `position.position_order` rather than assuming `draw_order` matches it.

## 2.5 Other confirmed-available context

- `Reading.deck` → `Deck.name` / `.description` — minor context, mainly for citation (which deck's cards were used). Not expected to drive analytical logic while only one deck (Rider-Waite-Smith) exists.
- `Reading.reflection_session` — the wrapping `ReflectionSession` row carries no fields beyond identity/timestamps (Section 1.1). No additional context available through it.

## 2.6 Summary: the engine's total input surface

```
Reading (question, question_domain, draw_method*, status-as-trigger)
  + Spread (allow_duplicate_cards, description)
      + SpreadPosition[] (position_order, semantic_role, required)
  + CardDraw[] (orientation, draw_order*)
      + Card (arcana, suit, rank, keywords, primary_themes, secondary_themes, meaning text for citation)
          + CardCorrespondence (see Section 3 — allowed, with caveats)

  * draw_method and draw_order: available, but must not drive analytical branching (Sections 2.1, 2.2).
```

---

# 3. Allowed Information Sources

## 3.1 May use

| Source | Use |
|---|---|
| `Card.primary_themes` / `.secondary_themes` | Primary basis for theme scoring and compound-theme matching. Always validated against `theme_vocabulary.yaml` at seed time (`app/seed/loader.py`), so the engine can assume every tag it encounters is canonical — no further normalization needed. |
| `Card.keywords` | Supplementary structured signal; short phrases, not prose. |
| `Card.base_meaning_upright` / `.base_meaning_reversed` | Citation/display text only (Section 2.3) — quote it, don't parse it. |
| `theme_vocabulary.yaml` (via `app.seed.loader.load_theme_vocabulary()`) | The closed set of valid theme tags. Useful for the engine to validate its own intermediate output against, the same way content validation does. |
| `CardCorrespondence` fields | May be used as **descriptive/supplementary context** (e.g. citing a card's element or astrological note) — **with the caveat in 3.3 below.** |
| `Spread` / `SpreadPosition` (all fields, Section 2.2) | Structural backbone for position-relevance, trajectory, and structural-relationship logic. |
| `Reading.question`, `.question_domain` | `question` is carried through verbatim into the Interpretive Model's Central Question (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 10.1) and may weight theme relevance (pipeline stage 2–3) when `question_domain` is present; must degrade gracefully when it's `None` (Section 2.1). |
| `CardDraw.orientation` | Determines upright/reversed meaning selection and (in later stages) thematic weighting. |
| Compound-theme rule definitions (Step 2+, not yet created) | Once they exist, as versioned **data** (a rule registry), per `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 6.1 — tiered `core`/`conditional`/`emergent` per `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 11. |

## 3.2 Must NOT use

| Excluded source | Why |
|---|---|
| Any AI/LLM call, or output from one | The Interpretation Engine sits **entirely outside** the ADR-0005 AI boundary (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 3.3: "must never call an AI provider"). This is the single hardest constraint in this whole design. |
| Scripture data / theme-to-verse mappings | A separate, later layer (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 15); no Scripture schema exists yet regardless. |
| Any data outside the database / reference-data files | No external web lookups, no live astrological ephemeris or transit calculations. `CardCorrespondence` is static, pre-loaded reference data — never a live computation. |
| `Reading.draw_method` as a branching condition | Physical and Digital paths converge on identical `CardDraw` rows; the engine must not know or care which path produced them (Section 2.1; `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 5). |
| Free-text user commentary / notes | No such field exists on `Reading` today (Section 2.1), and even if one is added later, it should feed Narrative Generation at most, not the deterministic engine — parsing arbitrary free text would break determinism and reproducibility. |
| Other Readings, aggregate/statistical data across Readings | Each Reading is interpreted independently from its own evidence plus static reference data. No cross-reading learning, ranking, or popularity-based weighting at this stage. |
| Randomness / non-deterministic values of any kind | No `random`, no wall-clock time, no environment-dependent values inside the engine (Section 5). Digital Draw's randomness, if used, already happened and is fixed in `CardDraw` before the engine runs. |
| Correspondence data as a basis for rules requiring internal astrological consistency | `RAIDIAN_WISE_REFERENCE_DATA_AUDIT_V1.md` Section 7.3 found the Major Arcana's sign/planet pairings don't consistently follow a single rulership logic (documented, not a bug — see that audit). A rule like "this card's sign is ruled by that planet, therefore X" would silently misfire on several Major Arcana cards. Correspondence data may be cited descriptively; it must not be load-bearing for deterministic conclusions — confirmed as a standing constraint, not just a default, in [Section 9, Q5](#9-resolved-design-decisions). |

---

# 4. Engine Outputs

## 4.1 Shape

The engine produces one **Interpretive Model** per interpretation run, concretizing `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 10 into a typed, machine-readable structure. This is a **proposed schema** (no `schemas/` package exists yet — Section 1.2); field names below are what Step 2 should implement, not a preview of already-written code.

```
InterpretiveModel
  schema_version: str                    # this output schema's own version (Section 5)
  engine_version: str                    # the interpretation logic's version (Section 5)
  reference_data_version: str            # a computed content hash of the reference data actually
                                          #   readable at run time -- see Section 9, Q2 (resolved)
  generated_at: datetime                 # when this run occurred (metadata only -- not an input, never affects content)

  central_question: str                  # Reading.question, verbatim (Product Spec 10.1)
  central_issue: Explained[str]          # Product Spec 10.2
  primary_tension: Explained[Tension] | None   # Product Spec 10.3
  supporting_themes: list[Explained[str]]      # Product Spec 10.4
  trajectory: Explained[Trajectory] | None     # Product Spec 10.5 -- omitted (null), not forced, when
                                                #   the Spread has no temporal/progressive semantic_role
  blocker: Explained[str] | None               # Product Spec 10.6
  uncertainty: list[str]                       # Product Spec 10.7 -- REQUIRED, may be non-empty even
                                                #   on a "Strong" evidence_strength result
  advice: Explained[str] | None                # Product Spec 10.8 -- only when Spread has an
                                                #   `advice` position
  clarification: Explained[str] | None         # Product Spec 10.9 -- only when Spread has an
                                                #   `advice_clarifier` position
  contradictions: list[Contradiction]          # Product Spec 10.10
  evidence_strength: "strong" | "moderate" | "weak" | "unresolved"   # Product Spec 10.11
```

Supporting shapes:

```
Explained[T]:
  value: T
  citations: list[Citation]        # never empty for a non-null Explained field -- an
                                    # unsupported conclusion is a bug, not a valid output

Citation:
  source_type: "card_draw" | "compound_rule" | "structural_rule"
  card_draw_id: UUID | None         # set when source_type == "card_draw"
  card_name: str | None             # denormalized for human-readable Explainability display
  position_name: str | None
  position_semantic_role: str | None
  contributing_theme: str | None    # which theme tag from that card justified inclusion
  rule_id: str | None               # set when source_type is a rule (Section 3.1); stable
                                     #   identifier into the compound-theme / structural-rule registry
  rule_tier: "core" | "conditional" | "emergent" | None

Tension:
  pole_a: str
  pole_b: str
  label: str                        # e.g. "Security vs. Change"

Trajectory:
  arc: list[TrajectoryStep]

TrajectoryStep:
  position_name: str
  semantic_role: str
  card_name: str
  orientation: "upright" | "reversed"

Contradiction:
  description: str
  sources: list[Citation]           # 2 or more -- a single-source "contradiction" is a bug
```

## 4.2 Provenance is structural, not reconstructible after the fact

Every non-null `Explained[T]` field carries its own `citations` inline, rather than a separate global lookup map keyed by field name. This is a deliberate refinement of `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 6's sketch (which used a single trailing `citations` dict) — inline citations keep each field self-contained and type-safe, and match Section 6's own stated reasoning ("citations should be forwarded, not reconstructed after the fact") more directly. Step 2 should build every intermediate pipeline stage to carry its citations forward into whatever field it ultimately contributes to, exactly as `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 6 already specifies.

## 4.3 Where this gets stored

**Resolved — see [Section 9, Q1](#9-resolved-design-decisions).** A new `Interpretation` table, related to `Reading` (not columns added to it), one row per engine run. Not yet implemented (Section 1.2 still holds until Step 2 runs a migration) — this subsection now states the decision, not just the requirement. The **evidence vs. interpretation separation** already established (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 17, Versioning) holds by construction: storing an `InterpretiveModel` never writes to `CardDraw`, `Card`, `Spread`, or any other evidence table — only to this new, purely additive table.

---

# 5. Determinism Requirements

"Deterministic" means precisely this: **given the same `Reading` + its `CardDraw` rows (the evidence, per Section 2) and the same reference-data snapshot (Card, CardCorrespondence, Spread, SpreadPosition, theme_vocabulary content), the engine produces a structurally identical `InterpretiveModel` every time it runs** — same field values, same citation sets, same ordering of list fields. Not "similar," not "equivalent in meaning" — identical.

This requires, concretely:

- **No randomness.** No `random`, no `uuid4()` for anything that affects output content (a `Citation`'s own row IDs are fine since they're inputs, not engine-generated), no reliance on hash-based iteration order. Python's `set` iteration order for strings is affected by per-process hash randomization (`PYTHONHASHSEED`) — any output derived from a `set` (e.g. a union of theme tags across drawn cards) **must** be explicitly sorted (e.g. alphabetically, or by a fixed rule-registry order) before being placed in output. This is a concrete, easy-to-miss bug source Step 2 must guard against, not a hypothetical one.
- **No wall-clock or environment dependence** inside the analytical logic itself. `generated_at` (Section 4.1) is metadata *about* a run, never an input to *what* the run concludes.
- **No I/O beyond the initial data load** (`RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 6: "pure functions over structured input, no side effects"). No network calls, no reading other Readings.
- **Versioned inputs.** `engine_version` must change whenever interpretation *logic* changes (a new compound-theme rule, a reweighted scoring formula) — this is the versioning `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 17 already requires for reinterpretation. `reference_data_version` must change whenever the *content* the engine reads from changes (a card's themes edited, a new compound rule tier promotion). Both must be captured on every output (Section 4.1) so a stored `InterpretiveModel` can always be attributed to the exact logic + content that produced it, and so a later "reinterpret with current engine" action can tell whether anything actually changed.
- **Reproducibility is testable.** Given a fixed `Reading` fixture (as `tests/factories.py` already builds), calling the engine twice must produce equal `InterpretiveModel` objects. This should become a standard test pattern in Step 2, the same way `test_seed.py` already tests seed idempotency for the data layer.

---

# 6. Separation of Responsibilities

Three layers, matching `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 3.3 and `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 1, restated precisely against what exists today:

## 6.1 Data / reference layer — exists today

`app/models/` + `app/reference_data/` + `app/seed/`. Owns **what things are** (Card, CardCorrespondence, Spread, SpreadPosition, theme vocabulary) and **what was drawn** (Reading, CardDraw). Contains zero interpretation logic — confirmed by inspection (Section 1.1). The Interpretation Engine is a *consumer* of this layer, never a modifier of it (Section 4.3).

## 6.2 Deterministic Interpretation Engine — proposed, this document's subject

Reads Reading + CardDraw + Spread + SpreadPosition + Card + CardCorrespondence + theme_vocabulary (Sections 2–3). Produces one `InterpretiveModel` (Section 4). Pure, deterministic (Section 5), no AI, no side effects beyond its own eventual output. Must not call, import, or know about a Narrative Generation service or the Reflection Engine — the dependency arrow points one way only (data layer → engine → future narrative layer), never back.

## 6.3 Future Narrative Generation layer — explicitly out of scope, not designed here

Per `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 12: consumes **only** the finished `InterpretiveModel` (Section 4) — never raw `CardDraw`, `Card`, or `CardCorrespondence` directly, and never the question in isolation from `InterpretiveModel.central_question`. It is the sole caller of the Reflection Engine (ADR-0005). It must not re-derive or override anything the Interpretive Model concluded — only rephrase it into prose. This document does not design this layer; it is named here only to make the boundary explicit, since Step 2 implementers need to know where the Interpretation Engine's responsibility *ends*.

---

# 7. Design Constraints

Restated from the task, plus what inspection confirmed about each:

- **Preserve the existing data foundation.** No model, migration, or reference-data file is touched by this document. Confirmed clean — `git status` shows only this new file plus the pre-existing, unrelated `README.md` edit.
- **Do not redesign existing schemas unless absolutely necessary.** None of the 8 existing models need redesigning for this contract. Step 2 will likely need an **additive** migration (new columns/table for storing `InterpretiveModel` output, a new `ReadingStatus.interpreted` value) — additive is not redesign, and exactly what the existing `ReadingStatus` docstring already anticipated ("new values can be appended in a future migration without reshaping this table," `app/models/enums.py`).
- **No AI/LLM-generated interpretation logic.** Enforced structurally in Section 3.2 and Section 6.2 — the engine sits outside the ADR-0005 boundary entirely.
- **No engine implementation in this step.** Confirmed: this document contains no engine code, no schema, no migration.

---

# 8. Existing Conventions the Engine Should Follow

Identified from `backend/tests/` and `backend/app/` so Step 2 doesn't invent new patterns where established ones already exist:

- **Model style**: SQLAlchemy 2.0 `Mapped`/`mapped_column`, `UUIDPrimaryKeyMixin` + `TimestampMixin` (`app/db/base.py`), portable enums via `str_enum_type()` (stores `.value`, not `.name` — a real bug this project already hit and fixed once, `app/db/base.py`'s docstring explains why).
- **Validation style**: collect *every* problem before raising, not just the first (`ReferenceDataError`, `app/seed/loader.py`) — the engine's own future input-validation (e.g. "this Reading's Spread has no positions") should follow the same pattern rather than failing fast on the first issue found.
- **Separation of parsing/validation from persistence**: `loader.py` (pure, no DB) vs. `seed.py` (DB writes) is a pattern directly analogous to what Section 6.2 asks of the engine — pure analytical logic, no side effects, with persistence handled by a separate caller. Step 2 should mirror this split (e.g. an `engine.py` that returns an `InterpretiveModel` object, with a separate, thin persistence step that saves it).
- **Test conventions**: `pytest`, one file per concern, `conftest.py`'s in-memory SQLite `db_session` fixture (foreign keys explicitly enabled — SQLite doesn't do this by default), `factories.py`'s minimal explicit builders (not a generic factory framework). Reference-data-only tests that don't need a database use module-scoped fixtures loading real YAML content directly (`test_reference_data_loader.py`'s pattern) — the engine's own rule-registry tests should follow this same no-database-needed style, since compound-theme rules are decided (Section 9, Q4) to be a code registry, not DB rows.
- **Documentation conventions**: every `Documentation/*.md` file carries a Document Information header (Version/Status/Owner/Last Updated/Purpose/Audience/Authority) and a closing "Related Documents" section — followed by this document.
- **Naming**: `Reading`/`Spread`/`SpreadPosition` (never "Layout" — `docs/NAMING_CONVENTIONS.md`), theme tags in lowercase `snake_case`, enum values lowercase strings matching their Python enum's `.value`.

---

# 9. Resolved Design Decisions

The six questions raised in the prior draft, resolved at the design level against the existing repository, Product Spec, and Architecture documentation. None of these decisions have been implemented — no model, migration, or code exists for any of them yet. Each is marked with what remains deferred to Step 2 (or later).

## Q1 — Where does the `InterpretiveModel` get stored?

**Decision:** A new, related `Interpretation` table (`interpretations`), **not** columns added to `Reading`. One row per engine run — `reading_id` (FK), `engine_version`, `reference_data_version` (Q2), `interpretive_model` (JSON, the structure in Section 4.1), `created_at`/`updated_at` (the standard `TimestampMixin`, for consistency with every other model — Section 8). "The current interpretation" is simply the row with the latest `created_at` for that `reading_id`; no `is_current` flag. `ReadingStatus` gains an `interpreted` value, sequenced `drafting → spread_complete → interpreted → saved`.

**Rationale:**
- A related table, not new columns on `Reading`, follows the precedent this project already established with `CardCorrespondence` — its own docstring gives the exact reasoning that applies here too: a distinct concern gets its own table "so [it] could be added later without reshaping" the row it's about. `Reading` is evidence (Section 6.1); an `Interpretation` is a *result derived from* that evidence, which is precisely the distinction `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 17 asks to be preserved.
- One-to-many (not one-to-one) is required by that same Section 17: "an old reading should be capable of being reinterpreted... without altering the original reading evidence." A single overwritable JSON column on `Reading` would lose every prior interpretation the moment a newer engine version re-ran; a related table keeps the full history for free, as a consequence of its shape rather than extra logic.
- No `is_current` flag: `MAX(created_at) WHERE reading_id = ...` is one query, always correct by construction, and adds no column that could drift out of sync with reality (e.g. two rows both flagged current after a bug). This project has consistently favored derived values over stored, driftable ones (`Spread.position_count` is the clearest existing precedent — a Python `@property`, not a stored column, "so it can never drift").

**Impact on existing architecture:** Zero changes to any existing table. One new table (additive migration) plus one additive `ReadingStatus` enum value. The enum extension was explicitly anticipated by the existing code's own docstring (`app/models/enums.py`: "new values can be appended in a future migration without reshaping this table") — this is not a redesign.

**Correction found during Step 2 implementation:** this draft originally assumed adding `interpreted` would require an Alembic migration recreating a CHECK constraint on `readings.status`, since `str_enum_type` (`app/db/base.py`) is documented as "SQLite CHECK-constraint-backed." Inspecting the actual migrated schema showed this constraint was never actually emitted (`Enum(..., native_enum=False)` defaults `create_constraint` to `False` unless set explicitly, which `str_enum_type` doesn't do) — `status` is a plain `VARCHAR(20) NOT NULL` in every environment today, confirmed by inspecting the live SQLite schema. Adding `interpreted` therefore required **no DDL change at all**, only the Python enum edit; the generated migration (`2520310c3acf`) contains only `CREATE TABLE interpretations`. This is a pre-existing, harmless gap between that docstring's claim and actual behavior (enum values are validated at the application layer via SQLAlchemy's type system, not enforced by the database) — noted here for accuracy; fixing the docstring or adding a real constraint is out of scope for this task (would be an unrelated schema change).

**Implementation timing:** Deferred to Step 2 (the migration, the `Interpretation` model, the `ReadingStatus.INTERPRETED` value). Nothing implemented now.

---

## Q2 — How should reference-data versioning be identified?

**Decision:** `reference_data_version` is a **computed content hash**, not a stored field on any reference-data table. At interpretation time, the engine hashes a canonical serialization of every reference-data row it is permitted to read (Section 3.1): all `Card`, `CardCorrespondence`, `Spread`, `SpreadPosition` rows, plus `theme_vocabulary.yaml`'s content. The hash is computed fresh on each run and stored only on the resulting `Interpretation` row (Q1) — reference-data tables themselves gain no new column.

**Rationale:**
- Rejected "git commit SHA of the reference-data directory": it identifies what the *YAML files* said at some commit, not what the *database* currently contains. Nothing today records which commit `seed.py` was last run from, and the two can legitimately diverge (an older checkout re-seeded later, a manual DB edit — however unlikely, the schema doesn't prevent it). A git SHA would be an unverified claim; a content hash is self-verifying by construction, which is exactly what Section 5's determinism requirement needs ("two runs actually used the same reference-data snapshot" becomes directly checkable, not asserted).
- Computing it at run time (rather than maintaining a stored "current version" value updated by the seed process) needs no new seed-time bookkeeping, no risk of the stored value going stale, and follows the same "derive, don't store-and-risk-drift" preference as Q1's `is_current` decision.
- Scope is the *entire* reference dataset, not just the specific Reading's drawn cards. A narrower, per-reading hash would be more precise about exactly what influenced one interpretation, but a single global version is simpler to implement (one pure function, called once per run), simpler to compare across readings ("were these two interpreted against the same reference data?" becomes a plain string equality check), and matches how this kind of versioning is conventionally done (a ruleset version, not a per-invocation slice of it).

**Impact on existing architecture:** None. No schema change to `Card`, `CardCorrespondence`, `Spread`, `SpreadPosition`, or the theme vocabulary file. This is a pure function Step 2 adds inside the engine, reading data that already exists.

**Cross-reference to Q4:** this hash covers reference *data* only. Compound-theme rule changes are covered by `engine_version` instead (they're code, per Q4's resolution) — a rule change is a deploy, not a content edit, so it should not be conflated with `reference_data_version`.

**Implementation timing:** Deferred to Step 2 (the hashing function itself). The decision of *what* to hash and *why* is made now.

---

## Q3 — Is `question_domain` in scope for Step 2?

**Decision:** `question_domain` is accepted and carried through as context (it already exists on `Reading`, unchanged), but Step 2 does **not** implement question-domain-weighted theme scoring. Pipeline stage 3 ("question relevance," `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 9) ships as a no-op for v1: every theme is treated as equally relevant to the question regardless of `question_domain`'s value, including when it's `None`.

**Rationale:**
- `question_domain` has no fixed taxonomy — this was Q6 in the *original* product spec's own open-questions list (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 16) and was never resolved. Inventing a taxonomy now, inside an architecture-resolution task, would be exactly the kind of scope creep the reference-data phases already deliberately avoided (compare: card-content authorship was treated as its own dedicated phase, not folded into an unrelated task).
- A half-built weighting heuristic (e.g. naive keyword matching between `question_domain` and theme names) would be worse than no weighting at all: it would silently make the engine's output depend on an unreviewed, undocumented heuristic, which cuts directly against Section 5's determinism-*and-trustworthiness* intent — determinism alone isn't the goal, *understood* determinism is.
- Nothing is lost by deferring: `question_domain` is already nullable and already carried through to `central_question`'s context. Turning on weighting later, once a taxonomy exists, requires no schema change — only new logic inside the existing pipeline stage 3 placeholder.

**Impact on existing architecture:** None. No schema change — `Reading.question_domain` is untouched, already nullable, already handled.

**Implementation timing:** Nothing to implement now or in Step 2 for this stage specifically (it ships as an explicit pass-through/no-op). Real work is deferred until the product-level question-domain taxonomy (product spec Section 16, Q6) is separately resolved — that resolution is a content/product decision, out of this document's scope.

---

## Q4 — How should compound-theme rules be represented?

**Decision:** Confirmed as a **Python code registry**, not a database table, for v1 — this affirms `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 6.1's own recommendation rather than overturning it. Each rule is a `CompoundThemeRule` object (already sketched there: `id`, `name`, `tier`, `trigger`, `description`, `contributing_theme_tags`), collected in a single registry module. Rule `id`s are permanent, stable slugs (e.g. `"security_vs_change"`) — once assigned, an `id` is never reused for a different rule; a rule whose fundamental meaning changes retires its old `id` and mints a new one, the same discipline as any other public identifier.

**Rationale:**
- A rule's `trigger` is fundamentally *logic* (`Callable[[MatchContext], bool]` in the existing sketch), not data — representing it in a database row would require inventing a constrained predicate DSL (e.g. a JSON structure like `{"all_of": [...]}`) that something then has to safely interpret. That's real engineering investment with no present justification: the product spec's own seed set is about seven named compounds (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 11), nowhere near the scale where a DB table's proposed threshold — "if the rule set grows large enough to need runtime editing" — is met.
- Code-as-rules turns out to directly satisfy a requirement the product spec already states rather than merely being the cheaper option: Section 11.3 requires promotion from `emergent` → `conditional` → `core` to be "a deliberate, reviewed change." A code change reviewed via a normal commit/PR *is* that deliberate review, with no extra tooling needed to enforce it.
- Keeps the registry testable the way `theme_vocabulary.yaml` content is tested today (`test_reference_data_loader.py`'s pattern) — no database required to unit-test a rule's trigger logic against fixture data.

**Impact on existing architecture:** None to existing tables. Adds new code only (`app/services/interpretation/compound_rules.py` or similar, per the layout `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 2 already sketches) — no `services/` directory exists yet (Section 1.1), so this is new, not a change to anything present.

**Implementation timing:** Deferred to Step 2 (the registry itself and the seed set of rules). The representation choice (code, not DB) is decided now, matching `Citation.rule_id`'s shape already fixed in Section 4.1.

---

## Q5 — Should correspondence data ever be load-bearing?

**Decision:** No. `CardCorrespondence` remains **citation/display-only** — never a scoring or trigger input for compound-theme matching, evidence-strength scoring, or any other deterministic conclusion, for the foreseeable future (not just "for now" pending a quick fix). Section 3.2's original position is confirmed, not just left standing by default.

**Rationale (the evidence considered, per the task's explicit instruction to only make it load-bearing if evidence supports doing so):**
- The audit (`RAIDIAN_WISE_REFERENCE_DATA_AUDIT_V1.md` Section 7.3) found the Major Arcana's sign/planet pairings don't consistently follow a single rulership logic — confirmed still true, nothing in this repository has changed that since the audit.
- The Minor Arcana's correspondence data **is** internally consistent (the Golden Dawn decanic system, verified in the same audit) — this is genuine evidence *for* a possible narrow exception. It was weighed and rejected anyway: the Minor Arcana's `element` (fire/water/air/earth) is already fully and reliably derivable from `Card.suit` alone (wands are fire by definition of being wands) — using it doesn't actually require touching `CardCorrespondence` at all, so it was never really "correspondence data" being load-bearing in the first place, just suit identity. Beyond `element`, the rest of the Minor Arcana's correspondence content (specific decans, planetary sub-rulers) adds a *second*, differently-sourced layer of meaning on top of `Card.primary_themes`/`secondary_themes`, which already fully carries this project's own original-wording interpretive content (Section 1.1, `RAIDIAN_WISE_REFERENCE_DATA_V1.md` Section 1) — there is no evidence that the deterministic engine needs a second theme signal to do its job.
- An asymmetric rule — "load-bearing for Minor Arcana, descriptive-only for Major Arcana" — would itself be a source of confusion for anyone writing or reviewing a future compound-theme rule (Q4), and confusion in what's load-bearing is exactly what determinism (Section 5) and Explainability (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 13) exist to prevent.

**Impact on existing architecture:** None. `CardCorrespondence` continues to exist exactly as built, available for citation in narrative/Explainability contexts (Section 3.1), with no new usage and no schema change.

**Implementation timing:** Nothing to implement — this is a constraint on what Step 2 must *not* do, not a feature to build. Revisiting this decision is explicitly future work, and only on the condition stated in the original draft: a separate content pass that reconciles the Major Arcana's correspondence attributions into one consistent system. No such pass is planned or scoped here.

---

## Q6 — Citation/provenance granularity

**Decision:** **Final-field-level citations only** are persisted. Each `Explained[T]` field in the stored `InterpretiveModel` (Section 4.1) carries the citations that support *that field's* conclusion. Intermediate pipeline-stage computations (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 9.1's nine stages) are not separately persisted or independently inspectable after a run completes — they exist only in memory during that run, flowing their citations forward into whichever final field they contribute to (Section 4.2, already decided).

**Rationale:**
- The product spec's own Explainability example (Section 13) only ever asks "what supports *this* conclusion" (e.g. *"Primary Tension: Security vs. Departure — Supported by: 4 of Pentacles (Situation), 8 of Cups (Influencer)"*) — a final-field citation list answers that completely. Nothing in the stated Explainability UX asks "show me everything stage 5 computed, including what didn't make it into the final model."
- Persisting every intermediate stage's output would mean designing and storing a second, larger structure alongside the `InterpretiveModel` with no stated consumer for it yet — exactly the kind of unnecessary schema/complexity the task constraints (and this project's general practice — see `Spread.position_count` again) argue against building ahead of need.
- The *discipline* of carrying citations forward through intermediate stages (Section 4.2) is unaffected by this decision and remains required — that's an internal code-structure requirement, not a persistence one. If a future need emerges for deeper stage-by-stage inspection (e.g. a developer-facing debug view), it can be added later as an optional field without reshaping anything decided here, since nothing about today's decision forecloses it.

**Impact on existing architecture:** None — confirms and narrows what Section 4.1 already specified; no schema change.

**Implementation timing:** Deferred to Step 2 (building the pipeline so citations flow forward correctly). The granularity decision itself — final-field only, no intermediate-stage persistence — is made now.

---

# 10. Summary of What Remains Deferred

Every decision above is a design resolution, not an implementation. Nothing in this update touched a model, migration, or reference-data file — confirmed by the diff (Section "Files Changed" in the accompanying report). Concretely still to do, all in Step 2 or later:

- The `Interpretation` model + migration + `ReadingStatus.INTERPRETED` (Q1).
- The reference-data content-hashing function (Q2).
- The actual Interpretation Engine pipeline and its nine stages, including a literal no-op for stage 3 pending the product-level question-domain taxonomy (Q3).
- The `CompoundThemeRule` registry and its seed set of rules (Q4).
- Nothing to build for Q5 — it is a standing constraint, not a feature.
- The pipeline's internal citation-forwarding implementation, producing final-field-only persisted citations (Q6).
- The product-level question-domain taxonomy itself (Q3's real dependency) — explicitly out of this document's scope, same as it was out of scope for the original product spec.
- Any reconciliation of Major Arcana correspondence data (Q5's stated condition for revisiting) — not planned, not scoped.

---

## Related Documents

- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Sections 9–13, the conceptual design this document concretizes.
- `RAIDIAN_WISE_ARCHITECTURE_V1.md` — Sections 5–7, the technical sketch this document grounds against the real implementation.
- `RAIDIAN_WISE_REFERENCE_DATA_V1.md`, `RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md`, `RAIDIAN_WISE_THEME_VOCABULARY_V1.md` — the reference-data layer this engine consumes.
- `RAIDIAN_WISE_REFERENCE_DATA_AUDIT_V1.md` — Section 7, the interpretation-readiness findings this document's Section 3.2 (Q5) responds to.
- `docs/DECISIONS.md` — ADR-0005, the AI-access boundary this design stays outside of.
