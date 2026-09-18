# Raidian Wise — Technical Architecture

# Document Information

Version: 1.0 (Draft for Review)
Status: Proposed — Not Yet Approved
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Describes the technical realization of `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` within the existing Raidian platform architecture. This document proposes module boundaries, service responsibilities, and data flow. It does not create database migrations, install dependencies, or implement code.

Audience:
Software engineers and AI development agents implementing Raidian Wise.

Authority:
This document extends `docs/ARCHITECTURE.md` and must remain consistent with it and with `docs/DECISIONS.md` (notably ADR-0004: Technology Stack, ADR-0005: Reflection Engine Architecture). It does not override either document.

---

# 1. Fit Within Existing Platform Architecture

`docs/ARCHITECTURE.md` defines the platform's high-level shape:

```
User -> React Frontend -> FastAPI API -> Application Services -> Reflection Engine -> Database + AI Provider
```

and five core services: Authentication, Reflection Engine, Scripture Engine, Journal Engine, Growth Engine.

Raidian Wise does not replace or duplicate this shape. It is a set of new services and routes that plug into it:

```
User
  |
  v
React Frontend (Raidian Wise screens)
  |
  v
FastAPI API (raidian_wise routes)
  |
  v
Application Services
  |-- Reading Service            (CRUD for Reading / Card Draw, orchestration)
  |-- Interpretation Engine      (deterministic; NEW, tarot-specific)
  |-- Narrative Generation       (calls Reflection Engine; NEW, tarot-specific)
  |-- Scripture Engine           (existing platform service; theme -> reference lookup)
  |
  v
Reflection Engine (existing platform AI gateway, ADR-0005)
  |
  v
Database (SQLite dev / PostgreSQL prod) + AI Provider
```

No component other than Narrative Generation may call the Reflection Engine, and no component may call an AI provider directly — this preserves ADR-0005 exactly as written; Raidian Wise adds one authorized caller, not a second gateway.

---

# 2. Backend Module Layout (Proposed)

Under `backend/app/`, following FastAPI conventions and the platform's stated design principles (thin API layer, business logic in services, `docs/ARCHITECTURE.md` → Design Principles):

```
backend/app/
  main.py                       (existing — mount routers here)
  api/
    routes_readings.py          (Reading lifecycle endpoints)
    routes_layouts.py           (Layout / Layout Position read endpoints)
    routes_cards.py             (Card search/browse endpoints)
    routes_settings.py          (Scripture preference, translation, deck settings)
  models/                       (SQLAlchemy models)
    deck.py
    layout.py
    layout_position.py
    card.py
    reading.py
    card_draw.py
  schemas/                      (Pydantic request/response schemas)
    reading.py
    layout.py
    card.py
    interpretive_model.py       (schema for the structured Interpretive Model)
  services/
    reading_service.py          (create/update Reading, transition status)
    draw_service.py             (physical entry validation + digital draw; see Section 5)
    interpretation/
      engine.py                 (pipeline orchestrator, Section 6)
      meanings.py                (stage 1-2: card meaning + theme strength)
      relevance.py               (stage 3-4: question + position relevance)
      relationships.py           (stage 5: card relationships)
      compounds.py                (stage 6: compound-theme matching + tiering)
      structure.py                (stage 7: structural relationships)
      trajectory.py               (stage 8: trajectory)
      contradictions.py           (stage 9: contradiction detection)
      evidence.py                 (stage 10-11: uncertainty + evidence strength)
    narrative_service.py         (calls Reflection Engine with the Interpretive Model)
    scripture_service.py         (existing/extended platform Scripture Engine integration)
  reflection_engine/              (existing platform AI gateway per ADR-0005; Raidian Wise
                                    adds a narrative_service caller, not a new gateway)
  db/
    session.py
  alembic/                       (migrations — not created in this phase)
```

This mirrors the product spec's pipeline stages ([`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 9.1](RAIDIAN_WISE_PRODUCT_SPEC_V1.md#91-pipeline-shape)) one module per stage, so each stage is independently unit-testable against fixed Card/Layout fixtures without needing a full Reading or any AI call.

---

# 3. Frontend Module Layout (Proposed)

Under `frontend/src/`, replacing the current Vite starter content (`App.tsx` is currently the default template and has no application code to preserve):

```
frontend/src/
  routes/  (or pages/, depending on router choice — react-router recommended, not yet installed)
    Home.tsx
    NewReading/
      LayoutSelect.tsx
      QuestionEntry.tsx
      DrawMethodSelect.tsx
      PhysicalCardEntry.tsx
      DigitalDrawResult.tsx
      SpreadReview.tsx
    ReadingResult.tsx
    ReadingHistory.tsx
    ReadingDetail.tsx
    Settings.tsx
    Disclaimer.tsx
  components/
    CardSelector/          (searchable selector: suit/arcana filter, thumbnail grid)
    SpreadLayout/           (visual position grid, orientation display)
    OrientationToggle.tsx
    InterpretiveModelView/  (narrative sections + optional explainability panel)
    ScriptureBlock.tsx      (visually distinct container — never rendered inline with narrative)
    DisclaimerBanner.tsx
  api/
    readings.ts
    layouts.ts
    cards.ts
    settings.ts
  types/
    reading.ts
    interpretiveModel.ts
```

The `ScriptureBlock` being its own component (not a prop/section inside the narrative renderer) is a deliberate reinforcement of the product spec's separation requirement — it should be structurally impossible for Scripture text to end up interleaved with interpretation prose in the DOM.

---

# 4. Data Model — Schema Sketch

Conceptual only; matches `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 7. No Alembic migration is created in this phase.

```
deck
  id (pk)
  name
  description
  is_default

layout
  id (pk)
  name
  description
  position_count
  allow_duplicate_cards

layout_position
  id (pk)
  layout_id (fk -> layout.id)
  name
  description
  position_order
  semantic_role   (enum)
  required

card
  id (pk)
  deck_id (fk -> deck.id)
  name
  arcana          (enum: major, minor)
  suit            (nullable)
  rank            (nullable)
  image_ref
  base_meaning_upright
  base_meaning_reversed
  keywords        (json array)
  primary_themes  (json array)
  secondary_themes (json array)

reading
  id (pk)
  created_at
  updated_at
  question
  question_domain (nullable)
  deck_id (fk -> deck.id)
  layout_id (fk -> layout.id)
  draw_method     (enum: physical, digital)
  status          (enum: drafting, spread_complete, interpreted, saved)
  interpretation_engine_version
  interpretive_model (json)
  narrative        (text)
  notes            (nullable text)
  scripture_enabled
  scripture_translation (nullable)

card_draw
  id (pk)
  reading_id (fk -> reading.id)
  position_id (fk -> layout_position.id)
  card_id (fk -> card.id)
  orientation    (enum: upright, reversed)
  draw_order
```

Indexing notes for implementation: `card_draw(reading_id)` and `card_draw(position_id)` should be indexed since every interpretation run and every Reading Detail view loads a Reading's full set of draws; `card(deck_id, arcana, suit)` supports the searchable card selector's filters.

---

# 5. Draw Service

Single service, two entry points, sharing one exit path — this is where the product spec's physical/digital convergence requirement ([`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 8.3](RAIDIAN_WISE_PRODUCT_SPEC_V1.md#83-convergence)) is enforced in code:

```python
# Illustrative signatures, not final code
def record_physical_draw(reading_id, position_id, card_id, orientation) -> CardDraw: ...

def perform_digital_draw(deck_id: UUID, layout_id: UUID) -> list[CardDraw]:
    # Signature intentionally excludes question, question_domain, and any
    # interpretation output. There is no parameter through which either
    # could influence the shuffle.
    ...
```

`perform_digital_draw`'s narrow signature is the enforcement mechanism for the brief's non-influence requirement — not a comment or a code review convention, but a function boundary that makes the violation impossible to write by accident. Both entry points write to the same `card_draw` table shape, so `Interpretation Engine` code never branches on draw method.

---

# 6. Interpretation Engine — Internal Architecture

Pure functions over structured input, no side effects, no I/O beyond the initial data load — this is what makes it safe to keep entirely outside the ADR-0005 AI boundary ([`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 3.3](RAIDIAN_WISE_PRODUCT_SPEC_V1.md#33-reconciling-the-interpretation-engine-with-adr-0005)).

```python
def interpret(reading: Reading, card_draws: list[CardDraw], layout: Layout) -> InterpretiveModel:
    meanings = resolve_meanings(card_draws)                     # stage 1
    theme_scores = score_themes(meanings, reading.question_domain)  # stage 2-3
    position_weighted = apply_position_relevance(theme_scores, layout)  # stage 4
    relationships = evaluate_relationships(card_draws)           # stage 5
    structural = evaluate_structure(card_draws, layout)          # stage 7
    compounds = match_compounds(position_weighted, relationships, structural)  # stage 6
    trajectory = derive_trajectory(card_draws, layout)           # stage 8
    contradictions = detect_contradictions(position_weighted, relationships, compounds)  # stage 9
    uncertainty = identify_uncertainty(position_weighted, compounds, contradictions)  # stage 10
    evidence_strength = score_evidence_strength(compounds, contradictions, uncertainty)  # stage 11

    return InterpretiveModel(
        central_question=reading.question,
        central_issue=..., primary_tension=..., supporting_themes=...,
        trajectory=trajectory, blocker=..., uncertainty=uncertainty,
        advice=..., clarification=..., contradictions=contradictions,
        evidence_strength=evidence_strength,
        citations=...,  # per-field references back to card_draw ids, for Explainability
    )
```

Each intermediate value should carry its own source citations (which `card_draw` rows / `layout_position` roles it derived from) forward into the final `InterpretiveModel.citations` map, rather than citations being reconstructed after the fact — reconstruction after the fact is unreliable once compound-theme matching has combined multiple signals.

## 6.1 Compound-theme rule storage

Rules are data, not inline conditionals scattered through `compounds.py`, so tier (`core` / `conditional` / `emergent` — [`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 11](RAIDIAN_WISE_PRODUCT_SPEC_V1.md#11-compound-theme-architecture)) and trigger conditions stay inspectable and reviewable independent of code changes:

```python
@dataclass
class CompoundThemeRule:
    id: str
    name: str                  # e.g. "Security vs. Departure"
    tier: Literal["core", "conditional", "emergent"]
    trigger: Callable[[MatchContext], bool]
    description: str
    contributing_theme_tags: list[str]
```

Storing these as versioned data (a Python registry to start; a database table if the rule set grows large enough to need runtime editing) keeps promotion from `emergent` → `conditional` → `core` a reviewable diff, consistent with the product spec's anti-overfitting intent.

---

# 7. Narrative Generation Service

```python
def generate_narrative(model: InterpretiveModel, tone_profile: str = "default") -> str:
    prompt = render_prompt(model)   # from prompts/interpretation.md template
    return reflection_engine.complete(
        system_prompt=load("prompts/system/reflection_engine.md"),
        safety_rules=load("prompts/system/safety.md"),
        tone=load("prompts/system/tone.md"),
        user_prompt=prompt,
    )
```

`narrative_service` is the **only** module permitted to import from `reflection_engine/` per ADR-0005. This should be enforced with a lint rule or import-boundary check (e.g. an import-linter contract, or a simple test that greps for `reflection_engine` imports outside the allowed module) rather than relying on convention alone, since this boundary is one of the platform's stated architectural guarantees.

---

# 8. Scripture Engine Integration

Raidian Wise does not build a new Scripture Engine — it is one of the platform's existing five core services (`docs/ARCHITECTURE.md`). Raidian Wise's contribution is:

- Theme tags on `InterpretiveModel` output ([`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 15.3](RAIDIAN_WISE_PRODUCT_SPEC_V1.md#153-theme-taxonomy-seed-set-from-the-brief)) that the Scripture Engine can consume as its lookup key.
- A `scripture_reference` table (or equivalent) storing `theme_tag -> (book, chapter, verse, translation)` metadata only — no embedded passage text pending the licensing decision (Q5).

The call shape:

```
InterpretiveModel.contributing_theme_tags -> scripture_service.find_references(tags, translation) -> ScriptureReference[]
```

This call does not go through the Reflection Engine for the MVP (no AI involved in a metadata lookup) — see `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 3.3 for why this is consistent with ADR-0005 rather than a violation of it.

---

# 9. API Sketch

Illustrative REST shape (final route naming should resolve the Reading/Layout terminology questions in the product spec, Section 16, before being finalized):

```
POST   /readings                       create a new Reading (draft)
PATCH  /readings/{id}                  update question/domain/layout/draw_method
POST   /readings/{id}/draws            record a physical Card Draw
POST   /readings/{id}/digital-draw     perform + record a full digital draw
GET    /readings/{id}                  fetch a Reading (evidence + interpretation if present)
POST   /readings/{id}/interpret        run Interpretation Engine + Narrative Generation
POST   /readings/{id}/save             mark status = saved
GET    /readings                       list/search Reading history

GET    /layouts                        list Layouts
GET    /layouts/{id}                   Layout + positions

GET    /cards                          search/filter Cards (deck, arcana, suit, name)

GET    /settings                       current Scripture/translation/deck preferences
PATCH  /settings                       update preferences
```

Per `docs/NAMING_CONVENTIONS.md` (plural nouns for API routes), this already follows the existing convention.

---

# 10. Non-Functional Notes

- **Testability:** every Interpretation Engine stage ([Section 6](#6-interpretation-engine--internal-architecture)) should be unit-testable against fixed Card/Layout fixtures with no database or network dependency. Narrative Generation should be tested against a fixed set of Interpretive Models with the Reflection Engine mocked, specifically including adversarial cases designed to check the banned-language constraints hold under prompt variation.
- **Privacy:** Readings are personal reflective data (`docs/PRINCIPLES.md` — Privacy By Design). No Reading data should be sent anywhere beyond the Reflection Engine call itself (i.e., no third-party analytics on question text or interpretations).
- **Determinism boundary:** the Interpretation Engine's output should be reproducible given the same Reading + engine version — this is what makes Explainability and future reinterpretation trustworthy. Narrative Generation is inherently non-deterministic (AI-generated prose) and is not expected to be reproducible; only the Interpretive Model is a versioned, stable artifact.

---

## Related Documents

- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — product architecture this document implements.
- `docs/ARCHITECTURE.md` — platform-level architecture this document extends.
- `docs/DECISIONS.md` — ADR-0004 (Technology Stack), ADR-0005 (Reflection Engine Architecture) in particular.
- `docs/NAMING_CONVENTIONS.md` — naming standards for database, Python, React, and API routes.
