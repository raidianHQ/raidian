# Raidian Wise — Product Specification

# Document Information

Version: 1.0 (Draft for Review)
Status: Proposed — Not Yet Approved
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Defines the product vision, workflow, data model, interpretation architecture, and MVP scope for Raidian Wise, the tarot reading interpretation experience built within the Raidian platform.

Audience:
Project owner, contributors, software engineers, and AI development agents implementing Raidian Wise.

Authority:
This document proposes product architecture for approval. It does not override `docs/PROJECT_CHARTER.md`, `docs/PROJECT_VISION.md`, `docs/PRINCIPLES.md`, `docs/ARCHITECTURE.md`, `docs/NAMING_CONVENTIONS.md`, or `docs/DECISIONS.md`. Where this document proposes a term or pattern that conflicts with those governing documents, the conflict is called out explicitly in [Section 3](#3-relationship-to-existing-governance) rather than silently overridden. Once reviewed and approved, this document becomes the canonical spec for Raidian Wise, and any accepted terminology changes should be back-ported into `docs/NAMING_CONVENTIONS.md` and recorded in `docs/DECISIONS.md`.

---

# 1. Repository Context

Before this document was written, the existing repository was inspected. Findings:

- The repository is already named **Raidian** and is governed by a mature set of documents in `docs/` (`PROJECT_CHARTER.md`, `PROJECT_VISION.md`, `PRINCIPLES.md`, `ARCHITECTURE.md`, `NAMING_CONVENTIONS.md`, `ROADMAP.md`, `DECISIONS.md`, `AGENTS.md`). These describe Raidian as a broader **guided reflection platform** (symbolic systems, AI, journaling, optional Scripture) — tarot is explicitly one reflective experience within it, not the platform's sole identity (`docs/DECISIONS.md`, ADR-0003).
- Technology stack is already decided (ADR-0004) and partially scaffolded:
  - Backend: FastAPI + SQLAlchemy + Alembic + Pydantic. `backend/app/main.py` is a bare FastAPI app with a single root route; `backend/requirements.txt` and `backend/alembic.ini` are empty placeholders — no models, no migrations, no routers.
  - Frontend: React 19 + Vite + TypeScript + Tailwind CSS. `frontend/src/App.tsx` is the default Vite starter template — no application UI yet.
  - Database: SQLite (dev) / PostgreSQL (prod) — not yet configured.
  - Hosting: GitHub Pages (frontend) + Render (backend) — not yet configured.
- `prompts/` contains placeholder files for `interpretation.md`, `journal_summary.md`, `onboarding.md`, `reflection_questions.md`, `scripture_matching.md`, and a `prompts/system/` set (`reflection_engine.md`, `safety.md`, `tone.md`) — **all currently empty**. No interpretation logic, AI prompt design, or card data exists yet anywhere in the repository.
- ADR-0005 establishes that AI must be accessed **exclusively through a "Reflection Engine"** — no component may call an AI provider directly. This is directly relevant to the Interpretation Engine / Narrative Generation split described later in this document (see [Section 3.3](#33-reconciling-the-interpretation-engine-with-adr-0005)).
- No card, layout, or reading data model exists yet in code. There is nothing to migrate — this is a greenfield implementation inside an established governance shell.
- `README.md` has an uncommitted working change (not part of this task) that redescribes the project; it was left untouched.

**Conclusion:** there is no conflicting application code to reconcile. The only real reconciliation needed is at the **terminology and architecture-document level**, addressed below.

---

# 2. Product Vision

Raidian Wise is the tarot reading interpretation experience within the Raidian platform.

> **The user draws the cards. Raidian Wise records and interprets the reading.**

Raidian Wise does not select cards to fit a question, and it does not construct a predetermined narrative around a desired outcome. A user shuffles and draws from a physical deck (or, optionally, uses an unbiased digital draw) and Raidian Wise's job is strictly interpretive: given a fixed, already-drawn set of cards, positions, and a stated question, produce a structured, explainable, honest analysis — never a prophecy.

This vision is a direct extension of the existing platform vision (`docs/PROJECT_VISION.md`): reflection over prediction, humility over certainty, transparency over mystery, user agency over dependence. Raidian Wise adds one governing constraint specific to tarot mechanics: **separation of draw from interpretation**. The interpretation engine must never see or influence which cards were drawn, and the draw mechanism (physical or digital) must never see or be influenced by the question or the interpretation.

---

# 3. Relationship to Existing Governance

## 3.1 Product identity

Per ADR-0003, "Raidian" is the platform and tarot is its first reflective experience. This document treats **Raidian Wise as the name of that tarot experience** — the product surface a user interacts with — running on the underlying Raidian platform, services, and governance. This is an interpretation, not a decision the user has confirmed; see [Open Question Q1](#12-open-architectural-questions).

## 3.2 Terminology conflicts with NAMING_CONVENTIONS.md

The brief for this document uses several terms that collide with the platform's existing canonical terminology. Per the governance hierarchy (ADR-0006), `NAMING_CONVENTIONS.md` sits below `ARCHITECTURE.md` but is still binding until formally revised. These conflicts must be resolved before implementation — they are **not** resolved by this document unilaterally.

| Term in this brief | Existing canonical term (`NAMING_CONVENTIONS.md`) | Conflict | Recommendation |
|---|---|---|---|
| **Reading** = the entire recorded event: question, layout, cards, positions, orientation, draw method, interpretation | **Reading** = "a specific interaction involving one or more cards," one component *within* a broader **Reflection Session** (which also includes reflection questions, Scripture, journal entry) | Direct scope conflict — this brief's "Reading" is closer to the existing "Reflection Session" | Adopt this brief's usage (**Reading** = the full persisted record) for Raidian Wise, and update `NAMING_CONVENTIONS.md` to retire "Reflection Session" as a distinct wrapper entity, *or* explicitly nest Reading inside a future Reflection Session once journaling/reflection-question features exist. Needs owner decision — see Q2 below. |
| **Layout** = a reusable spread definition (e.g. Celtic Cross) | **Spread** = "a predefined arrangement of cards" (the exact same concept) | Naming-only conflict | Rename **Layout → Spread** throughout Raidian Wise to stay consistent, unless the owner prefers "Layout" for technical/API clarity (a legitimate reason — "spread" is also used colloquially for the physical array of drawn cards, which can be ambiguous in code). See Q3 below. |
| **Interpretation** | **Interpretation** = "the explanation of symbolic meaning... presented as possibilities rather than objective truth" | No conflict | Keep as-is. |
| **Interpretation Engine** / **Narrative Generation** (two distinct layers) | **Reflection Engine** = the single sanctioned gateway to AI (ADR-0005) | Not a naming conflict but an architectural one, resolved in [3.3](#33-reconciling-the-interpretation-engine-with-adr-0005) | — |
| **Reflection Question** (existing concept, not used in this brief) | Defined in `NAMING_CONVENTIONS.md`; the brief never mentions it | Omission, not conflict | Out of scope for Raidian Wise MVP; a natural post-MVP feature (prompt the user to journal about the "Uncertainty" or "Advice" section of their Interpretive Model). |

Until the owner rules on Q2/Q3, this document uses **Reading** and **Layout** as defined in the brief, with the conflict flagged at each definition.

## 3.3 Reconciling the Interpretation Engine with ADR-0005

ADR-0005 requires all AI access to go through a single "Reflection Engine." This brief requires a strict separation between a deterministic **Interpretation Engine** (produces the structured Interpretive Model) and a **Narrative Generation** layer (produces prose).

These are compatible, not competing, if scoped precisely:

- The **Interpretation Engine** is **not an AI system**. It is deterministic application logic (rule evaluation, scoring, theme matching) operating over structured data (cards, positions, question metadata). It must never call an AI provider. This satisfies the brief's requirement that card/theme analysis not be left to free-form LLM reasoning, and it means the Interpretation Engine sits entirely outside ADR-0005's scope.
- The **Narrative Generation** layer is the one component permitted to reach an AI provider, and it must do so exclusively through the existing **Reflection Engine** service (per ADR-0005), never directly. Its input is the finished Interpretive Model (not raw cards), and its system prompt (to live in `prompts/system/reflection_engine.md` and `prompts/interpretation.md`, both currently empty) must constrain it to *rephrase, not reconsider* the model — no new conclusions, no upgrading uncertainty to certainty.
- The **Scripture Engine** identifies themes and looks up Scripture references; it does not require AI at all for the MVP (see [Section 15](#15-scripture-for-reflection-architecture)) and therefore also sits outside the Reflection Engine boundary until/unless a future phase adds AI-assisted theme matching.

This gives a clean data-flow boundary that keeps ADR-0005 intact: **Interpretation Engine (deterministic) → Interpretive Model (structured, stored) → Narrative Generation (via Reflection Engine, AI) → prose (stored alongside, regenerable)**.

---

# 4. Core Philosophy

Carried forward from `docs/PROJECT_VISION.md` and `docs/PRINCIPLES.md`, with tarot-specific application:

- **The user draws; the application interprets.** Physical draw is the default and primary path. Digital Draw exists only for convenience and is architecturally quarantined from interpretation (see [Section 8](#8-physical-vs-digital-draw-model)).
- **Reflection over prediction.** No output may claim a guaranteed future. Banned constructions: "this will happen," "you are destined to," "the cards guarantee," "the universe has decided," "your guides are telling you."
- **Transparency over mystery.** Every conclusion in a reading must be traceable to specific cards, positions, and relationships (see [Section 13, Explainability](#13-explainability)).
- **Humility over certainty.** The system must be able to say a spread does not establish a clear outcome — see [Interpretive Model → Uncertainty](#107-uncertainty).
- **Scripture is reflection, not revelation.** Scripture responds to *themes*, never to *cards* directly, and is never presented as confirming a reading. See [Section 15](#15-scripture-for-reflection-architecture).
- **User retains responsibility.** The application does not replace personal judgment, prayer, or professional (medical/legal/financial) advice. See [Section 14, Disclaimer and Guardrails](#14-disclaimer-and-guardrails).

---

# 5. Core User Flow

1. User starts a new Reading.
2. User selects a Layout (spread).
3. User enters their question.
4. User optionally selects/confirms a question domain (e.g. general, relationship, career, decision).
5. User chooses a draw method:
   - **Physical Deck** — default.
   - **Digital Draw** — optional, clearly opt-in.
6. **Physical path:** user physically draws cards; for each Layout Position, selects the card via a searchable card selector and marks Upright/Reversed.
7. **Digital path:** the application performs an unbiased randomized draw against the selected deck, blind to the question and to the interpretation engine.
8. User reviews the completed spread (all positions filled, all cards visible, orientation shown) before proceeding.
9. User explicitly triggers **Interpret My Reading** — interpretation is never automatic on spread completion. This is a deliberate UX gate, not just a button: it reinforces that the app is interpreting a fixed, already-real event, not generating content as cards are picked.
10. The Interpretation Engine analyzes the Reading and produces a structured **Interpretive Model**.
11. The Narrative Generation layer converts the Interpretive Model into natural-language prose (via the Reflection Engine, per [Section 3.3](#33-reconciling-the-interpretation-engine-with-adr-0005)).
12. If Scripture for Reflection is enabled, relevant Scripture is generated/looked up from the Interpretive Model's themes and shown in a visually separate section.
13. User can save the Reading.
14. The saved record preserves: cards, positions, question, orientation, layout, deck, draw method, and interpretation engine version — permanently, independent of future re-interpretation (see [Section 17, Versioning](#17-versioning)).

---

# 6. Screen / Application Structure

MVP screen inventory (names illustrative, not final IA):

- **Home** — entry point; start new Reading, view recent readings, access settings.
- **New Reading — Layout Selection** — browse/select a Layout; shows position count and short description.
- **New Reading — Question** — free-text question entry + optional domain selector.
- **New Reading — Draw Method** — Physical (default) vs Digital toggle, with a short explanation of what each means and the non-influence guarantee for Digital.
- **New Reading — Card Entry** (Physical) — one interaction per Layout Position: searchable/filterable card selector (Major Arcana, Cups, Pentacles, Swords, Wands categories) + Upright/Reversed toggle; duplicate-card guard with override-to-correct.
- **New Reading — Digital Draw Result** (Digital only) — displays the randomly drawn spread; read-only, user confirms and proceeds (cannot cherry-pick individual cards, or the "draw" guarantee is meaningless).
- **Spread Review** — full visual layout of all positions, cards, and orientations before committing to interpretation; edit-in-place still available here.
- **Interpreting** — transient state while the Interpretation Engine + Narrative Generation run.
- **Reading Result** — narrative sections (Central Theme, Tension, What the Spread Shows, Trajectory, What May Be Unclear, Advice, Clarification, Overall Reflection), optional Scripture for Reflection block (visually separated), optional "How did Raidian Wise arrive at this?" explainability panel, Save action.
- **Reading History** — list of saved Readings, searchable/filterable.
- **Reading Detail** — a saved Reading's full record (evidence + interpretation as generated); MVP does not require re-interpretation, but the schema must not block it (see [Section 17](#17-versioning)).
- **Settings** — Scripture preference (Off / Include / Ask Each Reading), Bible translation preference, deck preference, disclaimer/about.
- **Disclaimer / About** — standing, always-accessible statement of what Raidian Wise is and is not (see [Section 14](#14-disclaimer-and-guardrails)).

---

# 7. Data Model

Conceptual entities only — no migrations are created in this phase.

## 7.1 Deck

Not explicitly requested as a top-level entity in the brief, but required implicitly (Card references `deck_id`, Digital Draw operates "from the selected deck," settings include deck preference). Proposed minimal entity:

- `id`
- `name` (e.g. "Rider-Waite-Smith")
- `description`
- `is_default`

## 7.2 Layout

A reusable spread definition — see [Section 3.2](#32-terminology-conflicts-with-naming_conventionsmd) for the Layout/Spread naming question. **Contains no actual cards.**

- `id`
- `name`
- `description`
- `position_count`
- `allow_duplicate_cards` (bool, default false — see [Section 8.2](#82-digital-optional))
- `positions` → ordered collection of Layout Position

## 7.3 Layout Position

- `id`
- `layout_id`
- `name`
- `description`
- `position_order`
- `semantic_role` (constrained enum, e.g. `significator`, `situation`, `recent_past`, `influencer_blocker`, `near_future`, `advice`, `advice_clarifier`)
- `required` (bool)

`semantic_role` is what the Interpretation Engine reasons over structurally (trajectory, blocker detection, advice/clarifier pairing) — it must be a constrained enum, not free text, or the analytical pipeline in [Section 9](#9-interpretation-architecture) has nothing reliable to key off.

## 7.4 Card

Deck-independent of any specific Reading.

- `id`
- `deck_id`
- `name`
- `arcana` (`major` / `minor`)
- `suit` (nullable for Major Arcana)
- `rank` (nullable for Major Arcana)
- `image_ref`
- `base_meaning_upright`
- `base_meaning_reversed`
- `keywords` (structured list)
- `primary_themes` (structured list — this is what theme-scoring and compound-theme logic key off)
- `secondary_themes` (structured list)

## 7.5 Reading

The full persisted record of one interpretation event — see [Section 3.2](#32-terminology-conflicts-with-naming_conventionsmd) for the "Reading" vs "Reflection Session" naming question.

- `id`
- `created_at`, `updated_at`
- `question` (text)
- `question_domain` (nullable enum/free text)
- `deck_id`
- `layout_id`
- `draw_method` (`physical` / `digital`)
- `status` (`drafting` / `spread_complete` / `interpreted` / `saved`)
- `interpretation_engine_version`
- `interpretive_model` (structured, stored — see [Section 10](#10-the-interpretive-model))
- `narrative` (generated prose, stored — regenerable independent of the Interpretive Model)
- `notes` (user's own, optional)
- `scripture_enabled` (bool, snapshot of the setting at time of reading)
- `scripture_translation` (nullable, snapshot at time of reading)

## 7.6 Card Draw

The historical record of what was actually placed in a position. Cards themselves stay deck-level and reusable; Card Draw is the per-Reading fact.

- `id`
- `reading_id`
- `position_id` (→ Layout Position)
- `card_id`
- `orientation` (`upright` / `reversed`)
- `draw_order`

`draw_method` is intentionally not duplicated here — MVP assumes one draw method per Reading, so it lives once on the Reading ([7.5](#75-reading)) rather than being repeated per Card Draw.

**Invariant:** Card is immutable reference data; Card Draw is the only place a Reading's actual cards live. Reinterpreting a Reading later must never touch Card Draw rows.

---

# 8. Physical vs. Digital Draw Model

## 8.1 Physical (default)

User draws physically, enters results via the card selector. No randomness lives in the application for this path — the app is a recorder, not a participant in the draw.

## 8.2 Digital (optional)

Requirements, restated as implementation constraints:

- Randomization source must be a standard unbiased CSPRNG-backed shuffle (e.g. Fisher–Yates over the deck's card list), not a naive repeated-random-choice loop susceptible to bias at scale.
- No duplicate cards within a single Reading unless the Layout explicitly permits duplicates (`allow_duplicate_cards`, [7.2](#72-layout)) — MVP layouts do not.
- The Digital Draw function must not accept the question, question_domain, or any interpretation output as input. This should be enforced architecturally, not just by convention: the digital-draw service function's signature should take only `deck_id` and `layout_id` (for position count), and nothing else — there is no parameter through which a question or bias *could* leak in, by construction.
- Draw method is recorded on the Reading (`draw_method` field, [7.5](#75-reading)) and is immutable once the spread is complete.

## 8.3 Convergence

Both paths terminate in the same Card Draw rows against the same Layout Positions. The Interpretation Engine ([Section 9](#9-interpretation-architecture)) has no branch for draw method — it only ever sees Card Draw + Layout + Reading metadata, identically regardless of how the cards arrived.

---

# 9. Interpretation Architecture

The Interpretation Engine is a deterministic analytical pipeline over structured data — not a single AI prompt. Per the brief, it evaluates:

1. **Card meanings** — base upright/reversed meaning per Card.
2. **Card theme strength** — how central a given theme is to a card (primary vs. secondary themes, [7.4](#74-card)).
3. **Question relevance** — how the stated question/domain weights which themes matter most for this Reading.
4. **Position relevance** — how a card's meaning is modulated by its Layout Position's `semantic_role`.
5. **Card relationships** — pairwise/groupwise relationships between drawn cards (e.g. same-suit clustering, Major Arcana density, numerological sequences).
6. **Compound themes** — named patterns formed by specific card/position combinations (full treatment in [Section 11](#11-compound-theme-architecture)).
7. **Structural relationships** — patterns tied to Layout structure itself (e.g. advice/clarifier pairing, situation/blocker adjacency).
8. **Trajectory** — the arc formed by moving through positions in `position_order` where `semantic_role` implies time or progression (past → influence → future).
9. **Contradictions** — competing signals that should be surfaced, not silently resolved.
10. **Uncertainty** — what the spread does not establish; a first-class, expected output, not a fallback.
11. **Interpretive evidence strength** — how well-supported the model's conclusions are by the actual cards drawn (not a prediction-confidence score).

These stages feed a single output object: the **Interpretive Model** ([Section 10](#10-the-interpretive-model)).

## 9.1 Pipeline shape

Conceptual data flow — see `RAIDIAN_WISE_ARCHITECTURE_V1.md` for the technical module layout.

```
Reading + Card Draws + Layout
        |
        v
 1. Resolve card meanings per position (meaning x orientation x position role)
        |
        v
 2. Score theme strength per card, weighted by question/domain relevance
        |
        v
 3. Evaluate card-to-card relationships (pairwise + groupwise)
        |
        v
 4. Evaluate structural relationships (position-role-driven, e.g. advice<->clarifier)
        |
        v
 5. Match compound-theme rules (core / conditional) against the above
        |
        v
 6. Derive trajectory from ordered positions with temporal/progressive roles
        |
        v
 7. Detect contradictions across steps 2-6
        |
        v
 8. Identify what remains unresolved (uncertainty)
        |
        v
 9. Score interpretive evidence strength (Strong / Moderate / Weak / Unresolved)
        |
        v
   Interpretive Model (structured, versioned, stored)
```

Every stage's output should be retained internally (even if not all surfaced to the user) so that [Explainability](#13-explainability) can point to *which stage and which cards* produced a given conclusion.

---

# 10. The Interpretive Model

Structured object produced by the Interpretation Engine, consumed by Narrative Generation. Fields:

## 10.1 Central Question
The user's actual question, carried through verbatim.

## 10.2 Central Issue
What the spread appears fundamentally concerned with — derived, not asked of the user.

## 10.3 Primary Tension
The strongest competing forces identified (e.g. Security ↔ Change, Clarity ↔ Uncertainty, Attachment ↔ Release). Must cite the supporting cards/positions (see [Section 13, Explainability](#13-explainability)).

## 10.4 Supporting Themes
Secondary themes reinforcing the Central Issue, each traceable to source cards.

## 10.5 Trajectory
The arc across ordered, time-relevant positions (e.g. Past → Influence → Near Future). Only populated when the Layout has positions with a temporal/progressive `semantic_role`; not every Layout implies a trajectory, and the model must be able to omit this section rather than force one.

## 10.6 Blocker / Resistance
What appears to interfere with resolution, drawn from positions/cards with an obstruction-oriented role or theme.

## 10.7 Uncertainty
What the spread does **not** establish. This is a required field, not optional — even a "Strong" evidence-strength reading should be able to name what it does *not* resolve. The engine must be willing to leave this substantial when evidence is thin, and the Narrative layer must not paper over it.

## 10.8 Advice
What the advice position (where present in the Layout) contributes, in the context of the rest of the reading — not just that position's meaning in isolation.

## 10.9 Clarification
How an advice-clarifier position (where present) modifies or explains the Advice.

## 10.10 Contradictions
Meaningful competing signals, listed explicitly rather than forced into a single resolved conclusion. Each contradiction should name the two (or more) conflicting sources.

## 10.11 Interpretive Evidence Strength
`Strong | Moderate | Weak | Unresolved`. Represents how well the drawn cards and their relationships support the derived conclusions — **explicitly not** a probability of a future outcome. This distinction must be stated in the UI wherever this value is shown.

---

# 11. Compound-Theme Architecture

The brief's example compounds (Security vs. Change, Security vs. Departure, Clarity vs. Uncertainty, Emotional Transition, Intuition Within Uncertainty, Clarity Leading to Change, Release Through Restructuring) are treated as a **starting seed set**, not a ceiling. The architecture must classify every compound rule into exactly one of three tiers, and that tier must be a stored attribute of the rule (not just a design-time note), because it governs how confidently the rule can fire and how it's surfaced in Explainability:

## 11.1 Core compounds
Patterns demonstrated to hold across multiple spreads/contexts. Eligible to be referenced directly in narrative prose with normal confidence.

## 11.2 Conditional compounds
Valid only when specific supporting conditions are present (particular cards, particular positions, particular question domain). Must record their trigger conditions explicitly; the engine must verify the condition before applying the compound, not just check for the presence of the named cards.

## 11.3 Emergent observations
Interesting patterns noticed during development or from real readings that have not yet been validated broadly. These must **not** silently graduate into Core compounds. Promotion from Emergent → Conditional → Core should be a deliberate, reviewed change (tracked the same way any interpretation-logic change is — see [Section 17, Versioning](#17-versioning)), specifically to avoid overfitting the engine to individual readings the team happens to remember.

This three-tier structure is itself an anti-overfitting mechanism: it forces every new compound rule to declare its own evidentiary status rather than being added with the same authority as a long-validated one.

---

# 12. Narrative Generation Architecture

Input: a finished Interpretive Model only — never raw Card Draws, never the question in isolation from the model's own Central Question field. This is enforced by the pipeline boundary in [Section 3.3](#33-reconciling-the-interpretation-engine-with-adr-0005): Narrative Generation calls the Reflection Engine (the platform's sole AI gateway per ADR-0005) with the Interpretive Model as its entire factual basis.

Hard constraints on this layer (system-prompt-enforced, in `prompts/system/reflection_engine.md` / `prompts/system/safety.md` / `prompts/interpretation.md` — all currently empty and need to be authored before this layer can function):

- Must not invent conclusions absent from the Interpretive Model.
- Must not introduce predictions the model doesn't support.
- Must not convert Uncertainty content into confident-sounding prose — uncertainty must read as uncertain.
- Must not claim divine revelation or that cards reveal God's will (this applies regardless of whether Scripture for Reflection is enabled).
- Must answer the user's actual question, not produce a generic card-by-card glossary.

Suggested section structure for the generated reading (directly per the brief):

**Your Reading** → Central Theme → The Tension → What the Spread Shows → Where Things Appear to Be Moving → What May Be Unclear → Advice → Clarification → Overall Reflection.

Each section maps 1:1 to an Interpretive Model field (Central Issue, Primary Tension, Supporting Themes/Contradictions, Trajectory, Uncertainty, Advice, Clarification — see [Section 10](#10-the-interpretive-model)), plus a closing reflection that should still avoid net-new claims. This 1:1 mapping is itself a safeguard — it gives the narrative layer nowhere to introduce content that doesn't already exist in the model.

---

# 13. Explainability

Post-MVP as a UI surface, but architecturally required from day one: the Interpretive Model's every derived field must retain references back to the specific Card Draws / positions that produced it (per the pipeline note in [Section 9.1](#91-pipeline-shape)). Example shape:

```
Primary Tension: "Security vs. Departure"
  Supported by:
    - 4 of Pentacles (Situation position)
    - 8 of Cups (Influencer position)
  Contributing themes: attachment, restlessness, material security, voluntary release
```

If this citation data isn't captured at generation time, it cannot be reconstructed later from the narrative prose alone — so the Interpretive Model's storage format ([Section 7.5](#75-reading), `interpretive_model` field) must include these references even before the "How did Raidian Wise arrive at this?" UI panel is built.

---

# 14. Disclaimer and Guardrails

A standing, always-accessible Disclaimer (not just a one-time onboarding modal) must state, in respectful and non-preachy language:

- Readings represent possible interpretations and scenarios, not guaranteed outcomes.
- Readings should not replace personal judgment, prayer, or one's relationship with God.
- Readings are not divine revelation, and no card represents a message directly from God.
- Readings should not replace appropriate professional advice (medical, legal, financial, or otherwise).

Language constraints (extending `NAMING_CONVENTIONS.md`'s existing "Avoid" list — destiny, fortune, guaranteed, certain, hidden knowledge, prophecy, psychic, magic, supernatural authority — with tarot-specific bans from the brief):
- "This will happen."
- "You are destined to..."
- "The cards guarantee..."
- "The universe has decided..."
- "Your guides are telling you..."

Both the Interpretation Engine's output vocabulary and the Narrative Generation system prompt must be built against this shared banned/preferred-language list — it should live in one place (proposed: `prompts/system/safety.md`) and be referenced by both, not duplicated.

The application should never use language suggesting destiny, supernatural certainty, divine selection, secret knowledge, or spiritual authority of the application itself. Raidian Wise should not feel cult-like.

---

# 15. Scripture for Reflection Architecture

Conceptually and architecturally separate from tarot interpretation, consistent with `docs/PROJECT_VISION.md`'s existing Scripture Integration section and the platform's Scripture Engine (`docs/ARCHITECTURE.md`).

```
Interpretive Model -> extracted themes (fear, patience, surrender, uncertainty, ...)
                              |
                              v
                    Theme -> Scripture Reference lookup
                              |
                              v
              User-selected translation (licensing-permitting)
                              |
                              v
                 "Scripture for Reflection" -- shown separately
```

Explicitly **not**: `Card -> God's message`. Scripture responds only to the theme layer, never to a card directly, and is never presented as validating a prediction.

## 15.1 Licensing constraint

Do not embed copyrighted Bible translation text in the MVP. Store **Scripture references and metadata** (book/chapter/verse, theme tags) rather than full passage text, until a translation's usage terms are confirmed. Many modern translations require a license or usage agreement even for short quotations at scale; public-domain translations such as KJV/WEB avoid this but may not match user preference. This is flagged as an open question — see Q5 in [Section 16](#16-open-architectural-questions).

## 15.2 User preference

Three states (per settings, [Section 6](#6-screen--application-structure)):
- Scripture Off
- Include Scripture
- Ask Me Each Reading

Plus a preferred-translation setting, gated by whichever translations are confirmed licensable for the MVP.

## 15.3 Theme taxonomy (seed set, from the brief)

fear/anxiety, wisdom, decisions, patience, waiting, relationships, forgiveness, grief, hope, money/stewardship, work, change, uncertainty, trust, surrender.

This taxonomy should be shared with — not independent of — the Interpretation Engine's own theme vocabulary ([Card.primary_themes / secondary_themes](#74-card)). Otherwise the two systems drift and theme names stop lining up between a reading's Supporting Themes and its Scripture matches.

---

# 16. Open Architectural Questions

These require owner decisions before or during implementation; this document does not resolve them unilaterally.

**Q1 — Product/platform naming.** Is "Raidian Wise" the public-facing name for the entire Raidian platform going forward, or specifically the tarot module within a broader "Raidian" platform (per ADR-0003)? This affects README, package naming, and whether `docs/PROJECT_VISION.md`/`PROJECT_CHARTER.md` need a title update or stay as-is with Raidian Wise as a named sub-product.

**Q2 — "Reading" vs. "Reflection Session."** Adopt this brief's flat "Reading" as the top-level persisted entity (recommended for MVP simplicity), or nest it under a broader Reflection Session wrapper per current `NAMING_CONVENTIONS.md` (more future-proof once journaling ships)? See [Section 3.2](#32-terminology-conflicts-with-naming_conventionsmd).

**Q3 — "Layout" vs. "Spread."** Rename to match existing convention, or keep "Layout" and update the convention doc instead? See [Section 3.2](#32-terminology-conflicts-with-naming_conventionsmd).

**Q4 — Deck entity scope for MVP.** Confirmed as needed ([Section 7.1](#71-deck)) but not specified in the brief — is a single hardcoded deck (e.g. Rider-Waite-Smith) sufficient for MVP with no deck-switching UI, or should the Deck table/selector exist in the UI from day one even with only one row?

**Q5 — Bible translation licensing.** Which translation(s), if any, are already cleared for use (a translation whose license the owner already holds, or a public-domain translation such as KJV/WEB/ASV)? This blocks whether MVP Scripture can show any translation text at all vs. references only.

**Q6 — Question domain taxonomy.** The brief mentions "question focus/domain" as user-selectable but doesn't enumerate values. Needs a starting list (e.g. General, Relationship, Career, Decision-Making, Personal Growth) before the selector can be built.

**Q7 — Duplicate-card policy default.** The brief says the app should "prevent accidental duplicate cards... while still allowing correction/editing" for physical readings. Recommended default: warn-and-allow-override (a real physical deck usually has one of each card, so a duplicate is almost always a data-entry mistake, but the user must be able to force it through if their deck genuinely differs). Confirm before implementation.

---

# 17. Versioning

Two things must remain distinct and independently evolvable:

**Original Reading Evidence** (immutable once the spread is complete):
question, layout, positions, cards, orientation, draw order, draw method, deck.

**Interpretation** (replaceable):
the Interpretive Model, the generated narrative, and the `interpretation_engine_version` that produced them.

Implication for the data model ([Section 7.5](#75-reading)): `interpretive_model` and `narrative` are logically a *result* of running engine version N against the immutable evidence fields, not part of the evidence itself. A future "Reinterpret with current engine" action should be able to overwrite/append a new `interpretive_model` + `narrative` + `interpretation_engine_version` without touching any Card Draw row. MVP does not need to build the reinterpretation UI, but the schema must not make it structurally impossible later (e.g. don't collapse evidence and interpretation into one denormalized blob).

---

# 18. MVP Scope

In:
- Home
- New Reading: Layout selection, Question entry (+ optional domain), Physical card entry via searchable selector, Upright/Reversed
- Spread Review
- Interpret My Reading (explicit trigger) → Interpretation Engine → Interpretive Model → Narrative Generation
- Save Reading
- Reading History + Reading Detail
- Basic Settings (Scripture preference, translation preference if applicable, deck info)
- Standing Disclaimer
- Optional Scripture for Reflection (references/metadata only, pending Q5)
- One initial deck (Rider-Waite-Smith or equivalent, pending Q4)
- A small number of established Layouts — recommend Single Card, Three Card (e.g. Situation/Action/Outcome), and one larger layout such as Celtic Cross to exercise trajectory/advice-clarifier logic; final list is an implementation-time decision, not blocking this spec.

Out (explicitly deferred, per the brief):
- Digital Draw
- Additional decks
- Additional/custom layouts, user-created layouts
- Visual card browsing beyond the searchable selector
- Richer Scripture study features
- Reading comparison
- Reinterpretation with newer engine versions (schema-ready, UI deferred)
- Export/print
- Advanced analytics
- Explainability UI panel (data captured from day one per [Section 13](#13-explainability); UI panel itself deferred)

---

# 19. Future Scope

Carried from the brief, grouped loosely by theme:

- **Draw:** Digital Draw mode, additional decks.
- **Layouts:** additional established layouts, user-created/custom layouts.
- **Card entry:** visual card browsing.
- **Interpretation:** reinterpretation using newer engine versions, deeper compound-theme library (grown deliberately per the Core/Conditional/Emergent process, not ad hoc), Explainability UI.
- **Scripture:** richer study features, translation library expansion pending licensing.
- **Platform-level** (per `docs/ROADMAP.md` M3/M5/M6, likely superset context for Raidian Wise rather than Raidian-Wise-specific): reading comparison, export/print, advanced analytics, journaling integration, growth tracking.

---

# 20. Recommended Implementation Phases

Phased to de-risk the parts most likely to need iteration (data model, Interpretation Engine rules) before investing in UI polish, and to keep every phase independently testable.

**Phase 0 — Decisions & Governance Sync.**
Resolve Q1–Q7 ([Section 16](#16-open-architectural-questions)). Update `docs/NAMING_CONVENTIONS.md` and record any resulting terminology changes as new entries in `docs/DECISIONS.md`, per governance hierarchy (ADR-0006). No application code.

**Phase 1 — Data Foundation.**
Database schema for Deck, Layout, Layout Position, Card, Reading, Card Draw (Alembic migrations). Seed data for one Deck and 2–3 Layouts. No interpretation logic yet — this phase is done when a Reading's evidence fields can be created, stored, and retrieved end-to-end via API, with a placeholder/stub interpretation.

**Phase 2 — Physical Reading Flow (UI + API).**
Layout selection, question entry, searchable card selector, Upright/Reversed, spread review, save/history. Interpretation still stubbed (e.g. returns the raw cards with no analysis) so the full user flow can be exercised and tested before the engine exists.

**Phase 3 — Interpretation Engine (deterministic).**
Build the pipeline ([Section 9.1](#91-pipeline-shape)) against seed Card theme data. Start with a small Core compound-theme set (a handful of the brief's seed examples, explicitly tagged Core only where genuinely validated — otherwise tagged Conditional/Emergent per [Section 11](#11-compound-theme-architecture)). Output the Interpretive Model as structured JSON; no narrative prose yet — verify the model's fields directly in tests/API responses.

**Phase 4 — Narrative Generation.**
Author `prompts/system/safety.md`, `prompts/system/tone.md`, `prompts/system/reflection_engine.md`, and `prompts/interpretation.md` (all currently empty). Wire Narrative Generation through the existing Reflection Engine boundary (ADR-0005). Validate against the banned-language list ([Section 14](#14-disclaimer-and-guardrails)) with adversarial test questions designed to try to elicit certainty/prophecy language.

**Phase 5 — Scripture for Reflection.**
Theme taxonomy alignment with Card themes ([Section 15.3](#153-theme-taxonomy-seed-set-from-the-brief)), reference-only Scripture data (pending Q5), settings UI (Off/Include/Ask Each Time + translation preference), visually separated display.

**Phase 6 — Disclaimer, Guardrails, Polish.**
Standing Disclaimer screen/component, final language audit across all generated and static UI copy against `NAMING_CONVENTIONS.md` + [Section 14](#14-disclaimer-and-guardrails), MVP hardening.

**Phase 7 (post-MVP) — Digital Draw.**
Only after the physical path and interpretation pipeline are stable, to keep the non-influence guarantee ([Section 8.2](#82-digital-optional)) easy to verify in isolation.

**Phase 8 (post-MVP) — Explainability UI, Reinterpretation, additional decks/layouts.**

---

## Related Documents

- `docs/PROJECT_CHARTER.md`, `docs/PROJECT_VISION.md`, `docs/PRINCIPLES.md` — governing philosophy this spec extends.
- `docs/NAMING_CONVENTIONS.md` — canonical terms; conflicts noted in [Section 3.2](#32-terminology-conflicts-with-naming_conventionsmd) pending resolution.
- `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` — platform architecture and ADRs this spec must remain consistent with (notably ADR-0003, ADR-0004, ADR-0005).
- `Documentation/RAIDIAN_WISE_ARCHITECTURE_V1.md` — technical architecture realizing this product spec.
