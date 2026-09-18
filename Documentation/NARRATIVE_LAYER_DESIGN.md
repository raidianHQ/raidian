# Raidian Wise — Narrative Layer Design (Step 6)

# Document Information

Version: 1.0 (Draft for Review — Not Yet Approved)
Status: Proposed — Design Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Defines the future layer that converts a deterministic `InterpretiveModel` (baseline `329a6e4` — designed in `INTERPRETATION_ENGINE_DESIGN.md`, rule-specified in `INTERPRETATION_RULES_DESIGN.md`, implemented in Step 2/4, and empirically validated across 10 cases in `INTERPRETATION_ENGINE_VALIDATION.md`) into human-readable Raidian Wise interpretation text. This document establishes the **deterministic narrative contract** — the input/output shape, the field-to-section mapping, and the determinism guarantees — independently of any AI. It does not design an LLM prompt, and it does not implement any code.

Audience:
Software engineers and AI development agents who will implement the narrative assembly layer (a future step, not this one) and, later and separately, any optional AI-assisted wording pass.

Authority:
Concretizes `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 12 (Narrative Generation Architecture) and Section 13 (Explainability) and `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 7 (Narrative Generation Service) against the actual, current `InterpretiveModel` schema (`app/schemas/interpretive_model.py`) and the empirical findings in `INTERPRETATION_ENGINE_VALIDATION.md`, the same way `INTERPRETATION_ENGINE_DESIGN.md` concretized Sections 9–13 against the pre-implementation codebase. Does not override `docs/DECISIONS.md` ADR-0005 (AI exclusively through the Reflection Engine) — it sits entirely upstream of where that boundary applies.

---

# 0. Scope

This document defines **Step 6 only**: the deterministic narrative contract. It does **not**:

- Implement any narrative assembly code, schema, or migration.
- Design an LLM system prompt, user prompt template, or any content for `prompts/interpretation.md` / `prompts/system/*.md` (confirmed still empty, 0 bytes each — unchanged since `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 1's original inspection).
- Modify `InterpretiveModel`, any engine module, any reference-data file, or any existing test.
- Build or modify any frontend component (`frontend/src/App.tsx` remains the bare Vite starter — confirmed by inspection; no Raidian Wise screens exist yet) or backend API route (`backend/app/api/` does not exist yet — confirmed by inspection).

---

# 1. Repository Inspection Summary

Findings from inspecting the current codebase as of `329a6e4`, before writing this design:

- **`InterpretiveModel`** (`app/schemas/interpretive_model.py`) is fully implemented, tested (164 tests), and empirically validated (`INTERPRETATION_ENGINE_VALIDATION.md`). Its 14 top-level fields, and the `Citation`/`Explained[T]`/`Tension`/`Trajectory`/`Contradiction` shapes that compose them, are exactly as specified in `INTERPRETATION_ENGINE_DESIGN.md` Section 4.1 — nothing has drifted.
- **No narrative code exists anywhere in the repository.** No `services/narrative/` package, no `NarrativeDocument`-equivalent schema, no template files. `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 7 sketches an illustrative `generate_narrative(model, tone_profile) -> str` function that calls the Reflection Engine directly — this is a sketch predating any implementation, not existing code, and (per this task's explicit instruction) is not what this document designs yet.
- **No API layer exists.** `backend/app/api/` does not exist; `backend/app/main.py` remains the bare FastAPI stub (confirmed by the original Product Spec's own Section 1 inspection, re-confirmed here — nothing has changed this). There is no HTTP endpoint today that could serve a narrative even if one were generated.
- **No frontend application exists.** `frontend/src/App.tsx` is still the default Vite/React template. There are no Raidian Wise screens, so "presentation/UI" in this document is necessarily a forward-looking interface contract, not a description of an existing consumer.
- **`prompts/interpretation.md` and `prompts/system/{reflection_engine,safety,tone}.md` are all 0 bytes** — confirmed by direct inspection. No prompt content of any kind exists to design against or reuse.
- **Reference data has no theme-tag display-label field.** `theme_vocabulary.yaml` stores only the closed-vocabulary `snake_case` tag strings (e.g. `new_beginnings`, `self_evaluation`) — there is no separate authored "human-readable label" column anywhere. This matters directly for narrative text (Section 7 below) and is addressed as a deliberate, mechanical (not content-authoring) decision rather than deferred.

## 1.1 The governing constraint already exists, and is stronger than a generic "downstream-only" rule

`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 12 already states the narrative input contract precisely, prior to this document:

> Input: a finished Interpretive Model only — never raw Card Draws, never the question in isolation from the model's own Central Question field.

And Section 12's suggested section structure is already named and already mapped 1:1 to specific `InterpretiveModel` fields:

> **Your Reading** → Central Theme → The Tension → What the Spread Shows → Where Things Appear to Be Moving → What May Be Unclear → Advice → Clarification → Overall Reflection.
> Each section maps 1:1 to an Interpretive Model field (Central Issue, Primary Tension, Supporting Themes/Contradictions, Trajectory, Uncertainty, Advice, Clarification), plus a closing reflection that should still avoid net-new claims.

This document does not invent a new section structure — it **adopts this one**, resolves the two fields it left ambiguous (`blocker`, `evidence_strength` — neither is explicitly named in that list), and turns it into a testable rule specification the same way `INTERPRETATION_RULES_DESIGN.md` did for the engine's own stages (Section 6 below).

---

# 2. Core Architectural Rule (Restated and Enforced)

```
Reading → Deterministic Interpretation Engine → InterpretiveModel → Narrative Layer
```

The Narrative Layer is **downstream-only**. Concretely, this document establishes three specific, checkable consequences, not just a general principle:

1. **Single input.** The Narrative Layer's deterministic stage (Section 3) takes exactly one input: an `InterpretiveModel` instance. It does not query `Card`, `CardDraw`, `CardCorrespondence`, `Spread`, `SpreadPosition`, or `Reading` directly — even though every one of those tables is easily reachable from the same database session, and even though `Citation.card_draw_id` would make it *technically* possible to re-fetch a card's full meaning-text prose. This is a deliberate prohibition (Section 4), not an oversight: re-fetching would silently reintroduce exactly the "raw Card Draws" access Product Spec Section 12 already forbids.
2. **No new facts.** Every word of factual content (which theme, which card, which position, which rule) in the narrative output must trace back to a specific `InterpretiveModel` field value or `Citation`. The deterministic layer may add *connective* language ("This reading centers on...", "It is also shaped by...") but never a new *claim*.
3. **No re-derivation.** The Narrative Layer must never re-rank themes, re-decide a compound match, re-order a trajectory, or recompute `evidence_strength` — every such decision was already made once, by the engine, and citing it again here would risk the two layers disagreeing over time (e.g. if the engine's tiebreak logic changes but a narrative-layer copy of similar logic doesn't).

---

# 3. Three Layers Within "The Narrative Layer"

The phrase "Narrative Layer" in the task, the Product Spec, and the Architecture doc actually names **three distinct concerns** that have been conflated in the pre-existing sketches (`RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 7's `generate_narrative()` bundles all three into one illustrative function). Separating them is this document's central structural decision:

```
InterpretiveModel
      |
      v
[A] Deterministic Narrative Assembly   <-- THIS DOCUMENT'S SUBJECT. Pure, template-based,
      |                                    no AI, fully reproducible. Produces a
      |                                    NarrativeDocument (Section 5).
      v
[B] Presentation / UI Rendering        <-- Out of scope here (no frontend exists yet). Consumes
      |                                    a NarrativeDocument and decides visual layout,
      |                                    styling, collapsing of Explainability panels, etc.
      v
  (shown to user)

[A'] Optional future AI-assisted wording  <-- NOT DESIGNED HERE (explicit instruction: no LLM
      (a possible alternate/additional        prompt yet). If ever built, sits between [A] and
       path from [A]'s output, gated by        [B], consumes ONLY [A]'s NarrativeDocument output
       ADR-0005, Section 8 below)               (never the InterpretiveModel or raw evidence
                                                 directly), and must be strictly optional.
```

**Why this split matters:** `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 10 already states "Narrative Generation is inherently non-deterministic (AI-generated prose) and is not expected to be reproducible; only the Interpretive Model is a versioned, stable artifact." Taken literally, that sentence would mean Raidian Wise has **no** reproducible, versioned, testable narrative artifact at all — only a deterministic structured model on one side and unpredictable AI prose on the other, with nothing in between to unit-test, cache, or fall back to if the AI call fails or is disabled. This document's [A]/[A']/[B] split closes that gap: [A] is exactly as deterministic and versioned as the `InterpretiveModel` it reads, testable the same way, and usable as a complete, if plainer, narrative on its own — with [A'] as a strictly optional enhancement layered on top, never a replacement dependency.

---

# 4. Narrative Input Contract

**Input:** exactly one `InterpretiveModel` instance (Section 2, point 1). No other parameter is accepted by the deterministic assembly stage [A] except a `narrative_template_version` selector implied by the assembler's own code version (Section 9) — there is no `tone_profile` parameter, no user preference input, no locale parameter at this stage (all out of scope, Section 12 below discusses why).

**Explicitly not part of the input:**
- `Reading`, `CardDraw`, `Card`, `CardCorrespondence`, `Spread`, `SpreadPosition` rows — forbidden by Section 2.
- The user's `question` in isolation — only reachable via `InterpretiveModel.central_question`, already-carried-through verbatim (Product Spec Section 12, restated).
- Anything from a prior `Interpretation` row other than the one `InterpretiveModel` being rendered — no cross-interpretation comparison, no "this reading changed since last time" logic (that would be a distinct, unscoped feature).

**Validity precondition:** the input must be a structurally valid `InterpretiveModel` (i.e., it already passed Pydantic validation when the engine produced it — `Explained.citations` non-empty, etc.). The deterministic assembler performs no additional validation of engine output; it trusts the engine's own schema guarantees (Section 4.1 of `INTERPRETATION_ENGINE_DESIGN.md`) rather than re-checking them, the same trust relationship `persistence.py` already has with `engine.interpret()`'s output today.

---

# 5. Narrative Output Structure

A new artifact, `NarrativeDocument`, sketched here at the same "illustrative signature, not final code" level `RAIDIAN_WISE_ARCHITECTURE_V1.md` already uses for pre-implementation designs:

```
NarrativeDocument
  schema_version: str                    # this document shape's own version
  narrative_template_version: str        # the deterministic assembler's own logic version
                                          #   (independent of engine_version -- Section 9)
  source_schema_version: str             # copied from InterpretiveModel.schema_version
  source_engine_version: str             # copied from InterpretiveModel.engine_version
  source_reference_data_version: str     # copied from InterpretiveModel.reference_data_version
  generated_at: datetime                 # metadata only -- never an input, mirrors
                                          #   InterpretiveModel.generated_at's own role

  sections: tuple[NarrativeSection, ...]  # fixed, ordered -- Section 6's mapping table
```

```
NarrativeSection
  id: str                      # stable slug, e.g. "central_theme", "the_tension"
  title: str                   # fixed display heading, e.g. "Central Theme"
  source_field: str | None     # which InterpretiveModel field this section renders;
                                #   None only for "Your Reading" (intro) and "Overall
                                #   Reflection" (closing), which synthesize multiple
                                #   fields per Rule N1/N9 (Section 6)
  present: bool                 # False when omitted because its source field was null
                                #   (Product Spec 10.5/10.8/10.9's "must be able to omit")
  statements: tuple[NarrativeStatement, ...]   # see below
```

```
NarrativeStatement
  text: str                          # one deterministically-assembled sentence/phrase
  citations: tuple[Citation, ...]    # copied verbatim from the source InterpretiveModel
                                      #   entry -- never recomputed (Section 8)
```

A section with a scalar source field (`central_issue`, `primary_tension`, `blocker`, `advice`, `clarification`) has exactly one `NarrativeStatement`. A section with a list-shaped source field (`supporting_themes`, `uncertainty`, `trajectory.value.arc`, `contradictions`) has one `NarrativeStatement` per entry, in the source list's own order (never re-sorted — Section 2, point 3).

---

# 6. Field-to-Section Mapping (Testable Rule Specification)

Following the same rule-specification discipline `INTERPRETATION_RULES_DESIGN.md` Section 2 established, each section is defined with a fixed trigger, inputs, output, and provenance rule.

## Rule N1 — "Your Reading" (intro)
**Source field:** none directly; synthesizes `central_question` and `evidence_strength`.
**Trigger:** always present.
**Output:** one statement quoting `central_question` verbatim, plus one statement naming `evidence_strength` alongside its fixed, mandatory disclaimer (Rule N8).
**Citations:** none — this section states metadata, not a cited conclusion (`central_question` is definitionally uncited, exactly as `InterpretiveModel` itself carries it with no `Citation`).

## Rule N2 — "Central Theme"
**Source field:** `central_issue` (`Explained[str]`, never null — Section 4.1's contract guarantees this).
**Trigger:** always present.
**Output:** one statement naming the humanized theme label (Section 7's mechanical transform) as the reading's central concern.
**Citations:** `central_issue.citations`, copied verbatim.

## Rule N3 — "The Tension"
**Source field:** `primary_tension` (`Explained[Tension] | None`).
**Trigger:** present only when `primary_tension is not None`.
**Output:** one statement naming `Tension.label` (already a human-readable string, e.g. `"Clarity vs. Uncertainty"` — no humanization needed, Section 7) and its two poles.
**Citations:** `primary_tension.citations`, copied verbatim (already includes the compound-rule citation per `INTERPRETATION_RULES_DESIGN.md` Rule C2).
**When absent:** Section omitted entirely (`present = False`) — see Section 10 for why this is not the same treatment as `uncertainty`'s emptiness.

## Rule N4 — "What Stands in the Way" *(a refinement of Product Spec Section 12's list — see below)*
**Source field:** `blocker` (`Explained[str] | None`).
**Trigger:** present only when `blocker is not None`.
**Output:** one statement naming the humanized theme label associated with the blocker draw.
**Citations:** `blocker.citations`, copied verbatim.
**Design note:** Product Spec Section 12's illustrative section list does not name a `Blocker` section separately from "The Tension" — but Section 10.6 defines `Blocker / Resistance` as its own, distinct field from `Primary Tension` (10.3), and the engine keeps them structurally independent (`INTERPRETATION_RULES_DESIGN.md` Rules A4 vs. C2 are unrelated code paths, and `blocker` can be present while `primary_tension` is null, or vice versa — confirmed possible by the schema, since neither's presence implies the other's). Conflating them into one section would either drop `blocker` silently when `primary_tension` is null, or force an artificial link between two facts the engine never claimed were related. This document resolves the ambiguity by giving `blocker` its own section, positioned directly after "The Tension" — a refinement of the illustrative list, not a deviation from Section 10's authoritative field-by-field contract.

## Rule N5 — "What the Spread Shows"
**Source fields:** `supporting_themes` (`tuple[Explained[str], ...]`) and `contradictions` (`tuple[Contradiction, ...]`), grouped per Product Spec Section 12's own pairing ("Supporting Themes/Contradictions").
**Trigger:** present whenever `supporting_themes` is non-empty OR `contradictions` is non-empty (today, `contradictions` is always empty — `INTERPRETATION_ENGINE_VALIDATION.md` Section 7 — so in every currently-producible reading this section's presence is driven by `supporting_themes` alone).
**Output:** one statement per `supporting_themes` entry (humanized label) and one per `contradictions` entry (its `description`, already human-readable prose per the engine's own contract — Section 4.1 of `INTERPRETATION_ENGINE_DESIGN.md`).
**Citations:** each statement carries its own source entry's citations, copied verbatim — never merged into one undifferentiated section-level citation list, so a future Explainability view can still answer "which specific theme does this citation support" (Product Spec Section 13's own example format).
**Currently-empty-list handling:** since `contradictions` is always `()` today (`INTERPRETATION_ENGINE_VALIDATION.md`, confirmed across all 10 validation cases), this section will render only its `supporting_themes` statements in practice until Section 9 of `INTERPRETATION_RULES_DESIGN.md`'s deferred contradiction work is ever approved. The assembler must not render a placeholder sentence implying contradictions were checked and found absent — that would be an unsupported claim (no rule currently evaluates "no contradictions exist," only "none were detected by an always-empty stub," a materially different, unstated fact).

## Rule N6 — "Where Things Appear to Be Moving"
**Source field:** `trajectory` (`Explained[Trajectory] | None`).
**Trigger:** present only when `trajectory is not None` (Product Spec Section 10.5's explicit "must be able to omit this section rather than force one").
**Output:** one statement per `TrajectoryStep`, in `Trajectory.arc`'s own order (already the fixed semantic-role order per `INTERPRETATION_RULES_DESIGN.md` Rule P2 — never re-sorted here), naming the card, its orientation, and its role (humanized — Section 7).
**Citations:** `trajectory.citations`, copied verbatim (already ordered to match the arc per the engine's own contract).

## Rule N7 — "What May Be Unclear"
**Source field:** `uncertainty` (`tuple[str, ...]`, always present as a field, possibly empty).
**Trigger:** structurally always "present" as a section (Product Spec 10.7: "a required field, not optional"), but its **content** depends on whether the tuple is empty — see Section 10 for the exact empty-tuple handling rule (Rule N10).
**Output:** one statement per uncertainty string, verbatim (these are already complete, human-readable sentences — no humanization needed).
**Citations:** none — `uncertainty` entries are structural absence-statements ("this spread lacks an Advice position"), not conclusions about drawn evidence, so they were never citable in `InterpretiveModel` itself (confirmed: `uncertainty: tuple[str, ...]` carries no `Citation`, unlike every `Explained[T]` field).

## Rule N8 — Evidence Strength Communication
**Source field:** `evidence_strength` (`EvidenceStrength`, always present).
**Where rendered:** folded into "Your Reading" (Rule N1), not a standalone section — it is framing/metadata for the whole reading, not a conclusion about the cards themselves, consistent with Product Spec 10.11 treating it as a meta-property of the interpretation rather than a numbered Interpretive Model "section" in Section 12's list.
**Mandatory disclaimer:** every rendering of `evidence_strength` must be immediately accompanied by a fixed, non-omittable sentence stating it is **not** a prediction-confidence score — this is not a stylistic choice but a direct, literal requirement: Product Spec Section 10.11 states "this distinction must be stated in the UI wherever this value is shown." The deterministic assembler enforces this by construction: there is no code path that renders `evidence_strength`'s humanized label without also emitting the fixed disclaimer clause in the same statement.
**Citations:** none — `evidence_strength` is a derived category (a point-count threshold per `INTERPRETATION_RULES_DESIGN.md` Rule A9), not itself a citable conclusion; its supporting evidence is already fully cited piecemeal by the sections that fed the count (trajectory, blocker/advice-clarifier structure, compound matches).

## Rule N9 — "Advice" and "Clarification"
**Source fields:** `advice`, `clarification` (`Explained[str] | None` each).
**Trigger:** `advice`'s section present iff `advice is not None`; `clarification`'s section present iff `clarification is not None` (which, per `INTERPRETATION_RULES_DESIGN.md` Rule A6, can only be non-null when `advice` is also non-null — so `clarification`'s section never appears without `advice`'s, by construction of the upstream engine, not by any check this layer adds).
**Output:** one statement each, naming the humanized theme label.
**Citations:** copied verbatim; `clarification`'s citations already include a reference to the `advice` draw it clarifies (Rule A6), preserved as-is.

## Rule N10 — "Overall Reflection" (closing)
**Source field:** none directly; a **fixed-algorithm recap** of already-rendered sections, explicitly **not** a new synthesis.
**Trigger:** always present.
**Output algorithm (deterministic, no new content):** concatenate, in this fixed order, using fixed connective phrases: (1) the Central Theme statement's subject, (2) the Tension statement's label if present, (3) the trajectory's final step's card+role if `trajectory` is present, (4) the Advice statement's subject if present. Every clause is a direct re-reference to a value already rendered in an earlier section — nothing here is computed fresh.
**Citations:** none at the section level; if a future Explainability view wants citations for this section, it should point the reader back to the earlier section each clause restates, not duplicate their citation lists.
**Rationale:** Product Spec Section 12 explicitly requires this section to "still avoid net-new claims." A fixed recap algorithm is the only way to *guarantee* that property for a deterministic template — any attempt at genuine synthesis ("weighing" multiple fields against each other, drawing a conclusion not already stated) would necessarily either duplicate engine logic (violating Section 2, point 3) or invent something the engine never concluded (violating Section 2, point 2).

---

# 7. How Card/Theme/Role Names Are Presented — Humanization Rule

**Finding:** `theme_vocabulary.yaml`'s 107 tags are `snake_case` machine identifiers with no separate authored display-label field (Section 1). Rendering them verbatim (`"self_evaluation"`, `"new_beginnings"`) in a sentence would read as broken UI copy, not prose.

**Decision:** a single, fixed, mechanical **Title Case transform** — replace underscores with spaces, capitalize each word except a small, fixed list of minor words (`"and"`, `"of"`, `"the"` — the only ones that actually occur inside the current vocabulary, e.g. `skill_and_craft → "Skill and Craft"`) — is applied uniformly to every theme tag, `SemanticRole` value, and `EvidenceStrength` value wherever they appear in narrative text. `Card.name`, `SpreadPosition.name`, and `Tension.label`/`CompoundThemeRule.name` need **no transform** — they are already stored as proper human-readable strings (`"The Fool"`, `"Situation"`, `"Clarity vs. Uncertainty"`).

**Why this is not "new reference data" or "invented content":** the transform is a pure, reviewable, content-free string function — it changes formatting, not meaning, and produces the same output for the same input every time, for any of the 107 already-approved tags without exception (verified in Section 1: every existing tag is a plain compound of ordinary English words with no abbreviations or ambiguous compressions that this transform would mangle). It requires no card-content authorship, no interpretive judgment, and no product review beyond confirming the small minor-word list stays accurate as new tags (if any) are ever added to the vocabulary. This is explicitly **not** the same kind of decision as `INTERPRETATION_RULES_DESIGN.md`'s deferred items (M3, T4, etc.) — those require new *interpretive* content; this requires only a formatting utility.

**Known limitation, explicitly left for [A'] (Section 8):** the result is grammatically correct but stylistically plain ("This reading centers on New Beginnings.") — deliberately so. Making it read more naturally (varying phrasing, adding descriptive language) is exactly the kind of wording polish reserved for the optional future AI-assisted pass, never for the deterministic template itself (Section 2, point 2 — descriptive adjectives about a theme not present in the reference data would be a new, unreviewed claim).

---

# 8. Provenance / Citation Preservation Strategy

**Rule (applies to every section defined in Section 6):** a `NarrativeStatement`'s `citations` are always a **direct, unmodified copy** of the citations already present on the `InterpretiveModel` field or entry it renders. The deterministic assembler:

- Never constructs a new `Citation`.
- Never merges, dedupes, or reorders citations across statements (Section 6's Rule N5 note on why per-entry citation lists are kept separate).
- Never drops a citation for brevity.

This makes the Narrative Layer's provenance guarantee a direct, mechanical consequence of the engine's own already-validated guarantee (`INTERPRETATION_RULES_DESIGN.md` Rule A10 — every `Explained[T]` has ≥1 citation) rather than a second, independently-must-be-tested guarantee: if the input `InterpretiveModel` is provenance-complete (already proven, `INTERPRETATION_ENGINE_VALIDATION.md` Section 4), the output `NarrativeDocument` is provenance-complete by construction, with nothing left to separately verify beyond "did the copy operation run" (a trivial equality check, not a content judgment).

**Known citation-display nuance (not a defect, noted for the future presentation layer):** `INTERPRETATION_ENGINE_VALIDATION.md` Section 4 already found that a compound-rule statement can cite the same `card_draw_id` twice (once per contributing theme). This document does not change that — the `NarrativeStatement` for "The Tension" simply inherits it. Any deduping for a "supported by: Card X, Card Y" display list is a presentation-layer [B] concern (Section 11), not something the deterministic assembler should alter, since altering it would mean the assembler is making a judgment call about what counts as "the same" support — arguably harmless here, but exactly the kind of small interpretive decision this document's discipline says belongs to a reviewed layer, not an implicit formatting step.

---

# 9. Determinism Requirements for Template-Based Narrative

Mirroring `INTERPRETATION_ENGINE_DESIGN.md` Section 5's own determinism requirements, restated for this layer:

- **No randomness.** No `random`, no synonym rotation, no varying phrasing between identical runs. A given `InterpretiveModel` must always produce byte-identical `NarrativeDocument` text.
- **No wall-clock dependence** inside the assembly logic itself — `NarrativeDocument.generated_at` is metadata about the render, exactly mirroring `InterpretiveModel.generated_at`'s own already-established role (never an input to *what* is rendered).
- **Independent versioning.** `narrative_template_version` must change whenever the *templates or section logic* change (new connective phrasing, a reworded fixed disclaimer, a new section). This is deliberately separate from `engine_version`/`schema_version` (copied through, not reused) — a wording change to a template is not an engine change, and vice versa, the same separation-of-concerns argument `INTERPRETATION_ENGINE_DESIGN.md` Section 5 already made between `engine_version` and `reference_data_version`.
- **Reproducibility is testable the same way.** Calling the assembler twice on the same `InterpretiveModel` must produce equal `NarrativeDocument` objects (excluding `generated_at`) — the exact test pattern `test_interpretation_engine.py::test_interpret_is_deterministic_for_identical_input` already established; a future `test_narrative_assembly.py` should mirror it directly rather than invent a new determinism-testing idiom.
- **No hidden state.** The assembler is a pure function `NarrativeDocument = assemble(model: InterpretiveModel)` — no database session, no config lookup beyond the fixed template/minor-word constants (Section 7), no environment-dependent behavior.

---

# 10. Uncertainty / Empty-Field Handling

Two genuinely different situations exist in `InterpretiveModel`, and this document deliberately gives them different treatment rather than one generic "omit if falsy" rule:

**Rule N10a — Optional fields that are `None`** (`primary_tension`, `blocker`, `trajectory`, `advice`, `clarification`): the corresponding section is omitted entirely (`present = False`, no `NarrativeSection` emitted, or emitted with an empty `statements` tuple and `present = False` — an implementation choice for Step 7, not decided here). This directly implements Product Spec 10.5/10.8/10.9's "must be able to omit this section rather than force one." **The assembler must never synthesize filler text for a null field** ("No clear tension was found in this reading" is a claim the engine never made — the engine simply didn't evaluate one, a materially different fact, exactly the same distinction Rule N5 already draws for `contradictions`).

**Rule N10b — Required fields that are present but empty** (`uncertainty = ()`, seen in real validated readings — `INTERPRETATION_ENGINE_VALIDATION.md` Case 3/6/10 all show `"uncertainty": []` on strong readings): the section itself remains present (Product Spec 10.7 requires the field to exist even when empty), but its content is a single, fixed, pre-approved template sentence — not silence, and not an invented claim — stating plainly that the checklist evaluated found no gaps to name under its current criteria. This sentence is part of the **template**, not derived from data, so it carries no citations and asserts nothing beyond "the `uncertainty` list is empty," which is definitionally true whenever this branch renders. This is the concrete resolution of the tension `INTERPRETATION_ENGINE_VALIDATION.md` Section 8.2 flagged (a "Strong" reading can still have zero uncertainty statements today, since the checklist is coarse) — the narrative layer's job is to represent that fact honestly, not to paper over it or invent additional uncertainty the engine didn't find.

---

# 11. How Deferred Interpretation Capabilities Remain Excluded

The Narrative Layer inherits every exclusion already established through Steps 3–5, by construction rather than by a separate enforcement mechanism, because of Section 2's "no new facts" rule:

- **R3 (same-suit clustering), R4 (Major Arcana density), R5 (numerological sequences):** not fields on `InterpretiveModel`, so there is nothing for any `NarrativeSection` rule (Section 6) to read — structurally unreachable, the same guarantee `INTERPRETATION_ENGINE_VALIDATION.md` Section 7 already confirmed for the engine's own output.
- **Contradiction detection:** `contradictions` exists as a field and is rendered by Rule N5 when non-empty — but since it is always `()` today, no contradiction text is ever produced; this will change automatically (no narrative-layer code change needed) if and when that engine-level deferral is ever lifted, since Rule N5 already specifies the rendering for a populated list.
- **Question-domain weighting:** `InterpretiveModel` carries no field reflecting question-domain-weighted output at all (only the pass-through `central_question`), so there is nothing to render differently by domain.
- **Correspondence-based content (`CardCorrespondence`, astrology notes, etc.):** not reachable — Section 4 already prohibits the assembler from querying anything beyond the `InterpretiveModel` instance itself, so `CardCorrespondence.astrology_note` and similar fields, however tempting as "flavor text," are structurally unavailable to this layer, not merely avoided by convention.
- **New tarot meanings, speculative symbolism, LLM/AI interpretation, natural-language interpretation generation beyond what's specified here:** none introduced — every sentence this document defines is either a direct field-value rendering (Section 6) or fixed connective/disclaimer boilerplate (Sections 7, 9, 10), never free text describing what a card "really means."

---

# 12. Separation Between Narrative Generation and UI Rendering

`NarrativeDocument` (Section 5) is the boundary artifact. Everything on the [A] side of it (this document) is backend, deterministic, versioned, and testable without a browser. Everything on the [B] side is explicitly **not** designed by this document:

- Visual layout, typography, iconography, color, animation.
- Whether sections are always-expanded or collapsible (e.g. an Explainability panel showing/hiding citations per Product Spec Section 13).
- Localization/translation of the fixed template strings (Section 7's minor-word list, the disclaimer sentences, section titles) — a real future concern, entirely unaddressed here, and worth flagging as a reason `NarrativeDocument`'s `text` fields should probably be built from a translatable template key + parameters rather than a single already-concatenated string, **when** that implementation work happens (not decided here).
- Whether `NarrativeDocument` is persisted (e.g. a new `narratives` table, mirroring `Interpretation`'s one-row-per-run shape) or regenerated on every page view from a stored `InterpretiveModel`. Both are plausible; this document takes no position, consistent with "no implementation" — the existing `Interpretation` table's precedent (a related table, `INTERPRETATION_ENGINE_DESIGN.md` Q1) would be the natural default to evaluate first if and when this is implemented.
- Any API route shape for serving a `NarrativeDocument` to the frontend — `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 9's `POST /readings/{id}/interpret` sketch would need to be revisited once this layer exists, but doing so is out of scope here (no `api/` package exists yet at all, Section 1).

---

# 13. Future Boundary for Optional LLM-Assisted Wording [A']

Not designed here — this section defines only the **boundary conditions** any future design for this capability must satisfy, per the task's explicit instruction to establish the deterministic contract first and independently.

1. **Strictly downstream of [A], never a replacement input path.** If built, it must take `NarrativeDocument` (Section 5) as its sole input — never `InterpretiveModel` directly, and never raw evidence. This preserves the same "no new facts" guarantee one level further down: an AI pass that only ever sees pre-assembled, already-cited sentences has structurally less room to invent a new claim than one given the raw structured model and asked to "write a reading."
2. **Optional, with the deterministic version as the always-available fallback.** [A]'s output must remain a complete, servable narrative on its own (Section 3's diagram) — [A'] can only ever be an enhancement layered on top, never a hard dependency. This directly protects the product from an AI-provider outage or a disabled Reflection Engine call turning into "no reading available at all."
3. **Rephrasing only, never re-conclusion.** Its only sanctioned edit is sentence-level wording/flow polish. It must not add, remove, or alter any factual claim, section presence/absence, or field value from [A]'s output — the same "banned language" constraints Product Spec Section 12 already states (must not invent conclusions, must not introduce predictions the model doesn't support, must not convert Uncertainty content into confident-sounding prose, must not claim divine revelation) apply here in full, and this is specifically **where enforcement effort must concentrate**, since [A]'s fixed templates satisfy those constraints by construction (no generative freedom = no way to violate them) while an LLM pass genuinely could.
4. **Must preserve every citation, attributably.** Whatever prose [A'] produces for a given section must remain traceable back to that section's original `NarrativeStatement.citations` — exact mechanism (e.g. still returning structured statements with rephrased `text` but unchanged `citations`, vs. some other shape) is left for that future design, not decided here.
5. **Must go exclusively through the Reflection Engine, per ADR-0005** — re-affirmed, not reinterpreted. `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 7's note that "`narrative_service` is the only module permitted to import from `reflection_engine/`... enforced with a lint rule or import-boundary check" remains the correct future enforcement mechanism and is not superseded by anything here.
6. **Requires its own dedicated design and content-authoring pass.** `prompts/interpretation.md` and `prompts/system/*.md` are still 0 bytes (Section 1) — authoring them, and designing the actual prompt structure, is explicitly **not** this document's job (per this task's instruction) and is not started, sketched, or implied here beyond the boundary conditions above.
7. **Needs adversarial testing before it ships**, per `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 10's own existing non-functional note: "Narrative Generation should be tested against a fixed set of Interpretive Models with the Reflection Engine mocked, specifically including adversarial cases designed to check the banned-language constraints hold under prompt variation." Restated here as a hard prerequisite for building [A'] at all, not optional polish.

---

# 14. Summary: What This Document Decides vs. Defers

## Decided (design-level, ready for a future implementation step)
- The three-layer split ([A] deterministic assembly / [B] presentation / [A'] optional AI polish) and the strict one-way data flow between them.
- The `NarrativeDocument`/`NarrativeSection`/`NarrativeStatement` shape (Section 5).
- The complete field-to-section mapping, including the resolution of the two fields ([blocker], [evidence_strength]) the Product Spec's illustrative list left ambiguous (Section 6).
- The theme/role humanization rule as a mechanical, content-free transform, not new reference data (Section 7).
- The citation-copy-verbatim provenance strategy (Section 8).
- Determinism and versioning requirements for the assembler (Section 9).
- The distinction between null-field omission and empty-required-field handling (Section 10).
- The boundary conditions any future [A'] design must satisfy (Section 13).

## Explicitly deferred (not decided here, no implementation implied)
- Whether `NarrativeDocument` is persisted, and if so, its migration/table shape.
- The API route(s) that would serve it (no `api/` package exists yet at all).
- Localization/translation strategy for template strings.
- The actual LLM prompt design, `prompts/*.md` content, and [A']'s implementation.
- Any frontend component or visual design ([B] — no frontend application exists yet).
- Whether/when to implement [A] itself — this document establishes the contract; implementing it is a future step this document does not authorize on its own.

---

## Related Documents

- `INTERPRETATION_ENGINE_DESIGN.md` — Step 1's contract; this document's Section 5 sketch follows the same "illustrative signature, not final code" convention Section 4.1 there established.
- `INTERPRETATION_RULES_DESIGN.md` — Step 3's rule specification; this document's Section 6 rule format (Trigger/Output/Citations) directly follows its Section 2 template.
- `INTERPRETATION_ENGINE_VALIDATION.md` — Step 5's empirical findings; Sections 6, 8, 10 above directly cite specific validated cases (empty `uncertainty` on strong readings, duplicate citation `card_draw_id`s, always-empty `contradictions`) rather than re-deriving them.
- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Section 12 (Narrative Generation Architecture, the section structure this document adopts and refines) and Section 13 (Explainability, the citation-display precedent Section 8 above follows).
- `RAIDIAN_WISE_ARCHITECTURE_V1.md` — Section 7 (the pre-implementation `generate_narrative()` sketch this document splits into [A]/[A']) and Section 10 (the non-functional notes on testability and non-determinism this document directly responds to in Section 3).
- `docs/DECISIONS.md` — ADR-0005, the AI-access boundary Section 13 stays outside of and re-affirms.
- `app/schemas/interpretive_model.py` — the actual, implemented input contract every rule in Section 6 reads against.
