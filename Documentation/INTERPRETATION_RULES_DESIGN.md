# Raidian Wise — Interpretation Rules Design (Step 3)

# Document Information

Version: 1.1 (Approved — Design Only, No Implementation)
Status: Approved. Rules R3 and R4 (Section 7.1) are explicitly deferred, not open proposals — see Section 12.
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Defines Step 3 of the deterministic Interpretation Engine: the specific, testable rules by which the evidence already available from the reference-data layer and a `Reading`'s `CardDraw` rows becomes the content of an `InterpretiveModel`. Step 1 (`INTERPRETATION_ENGINE_DESIGN.md`) defined the contract — inputs, outputs, determinism requirements, responsibility boundaries. Step 2 (baseline `a65c435`) implemented the pipeline's structural skeleton — nine stage modules under `app/services/interpretation/`, wired together by `engine.py`. This document is the rule-by-rule specification layered on top of that skeleton: what each stage actually decides, why, with what precedence against other rules, and with what provenance. No engine code, schema, or reference-data file is changed by this document.

Audience:
Software engineers and AI development agents who will implement Step 4 (turning the rules marked "Proposed" below into code, once approved) and anyone reviewing what the engine currently does versus what it has been asked to do but cannot yet, for lack of reviewed data.

Authority:
Concretizes `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Sections 9–13 and `RAIDIAN_WISE_ARCHITECTURE_V1.md` Sections 5–7 against the actual Step 2 implementation (`app/services/interpretation/`, `app/schemas/interpretive_model.py`), the same way `INTERPRETATION_ENGINE_DESIGN.md` concretized them against the pre-Step-2 codebase. Does not override that document — it is the next layer down from it. Does not override `docs/DECISIONS.md` ADR-0005.

---

# 0. Scope

This document defines **Step 3 only**: the rules the engine's stages apply, stated precisely enough to be tested. It does **not**:

- Implement any rule marked "Proposed" or "Deferred" below.
- Change any model, migration, reference-data file, or existing pipeline module.
- Invent tarot meanings, theme mappings, or symbolic correspondences not already present in the reviewed reference data (`app/reference_data/`) or the resolved decisions in `INTERPRETATION_ENGINE_DESIGN.md`.

The **closed deterministic system constraint** governs every rule below, proposed or supported:

```
Approved reference data + explicit reviewed rules + reading input
  → deterministic interpretation
```

The engine may only ever *apply* rules that a human has reviewed and approved (by being merged as code, the same discipline `INTERPRETATION_ENGINE_DESIGN.md` Q4 already established for compound-theme rules). It must never *discover* a rule from patterns in the data at run time — no clustering, no learned weights, no inferred correlations. Every rule in this document, including every "Proposed" one, is proposed as a specific, human-authored, human-reviewable trigger — never as "let the engine find patterns and act on them."

---

# 1. Repository Inspection Summary (Step 3 baseline: `a65c435`)

## 1.1 What Step 2 actually computes, stage by stage

Confirmed by reading every module under `app/services/interpretation/` and `engine.py`'s orchestration:

| Stage | Module | Computes | Reaches `InterpretiveModel`? |
|---|---|---|---|
| 1–2 | `meanings.py` | Resolved meaning text per draw; theme frequency scores (`ThemeScore`, sorted `(-count, theme)`) | Yes — via `central_issue`/`supporting_themes` |
| 3–4 | `relevance.py` | Explicit no-ops (pass through unchanged) | N/A |
| 5 | `relationships.py` | Same-suit clusters (2+ shared suit), Major Arcana count | **No** — computed, discarded (`engine.py` line: "computed; not yet consumed") |
| 6 | `compounds.py` | Compound-theme rule matches (2 rules) | Yes — via `primary_tension`/`supporting_themes` |
| 7 | `structure.py` | Single draw per structural role: situation, blocker, advice, advice_clarifier, **significator** | Partially — situation is computed but never read by `engine.py`; blocker/advice/advice_clarifier reach output; **significator is computed but never read anywhere** |
| 8 | `trajectory.py` | Fixed-role-order arc (recent_past → situation → near_future) | Yes — via `trajectory` |
| 9 | `contradictions.py` | Always `()` | Yes (as an always-empty field) |
| 10–11 | `evidence.py` | Uncertainty checklist; evidence-strength point count | Yes — both fields |

Two concrete gaps fall out of this table, both real findings from this inspection (not implementation bugs — Step 2 documented them as deliberately out of scope, but Step 3 is exactly the point at which they should be decided):

1. **`relationships.py`'s output (same-suit clusters, Major Arcana density) is computed and then discarded.** It influences nothing in the final model today.
2. **`structure.py`'s `situation` and `significator` findings are computed but never consumed.** `situation` is arguably implicit in `trajectory` (which already includes the situation-role draw when present), so its omission is lower-stakes; `significator` has no other path into the output at all.
3. **`significator` is additionally unreachable in practice today**: none of the three seeded spreads (Single Card, Three Card, Celtic Cross — `app/reference_data/spreads/*.yaml`) define a position with `semantic_role: significator`. This is not a bug; it means `StructuralFindings.significator` is always `None` given current reference data, and any rule about it is currently untestable against real seeded content.

## 1.2 What reference data actually supports

- **78 cards**, each with `base_meaning_upright`/`base_meaning_reversed` (prose, citation-only per `INTERPRETATION_ENGINE_DESIGN.md` Section 3.1) and `primary_themes`/`secondary_themes` drawn from the closed 107-tag `theme_vocabulary.yaml`. **There is no `reversed_themes` or orientation-conditional theme field on `Card`.** Orientation currently only selects which meaning text is cited (`context.py`'s `build_reading_context`); it has no effect on which theme tags count toward theme scoring or compound matching, because there is no data to drive such an effect. This is confirmed by reading `app/models/card.py` and every card YAML file — no such field exists.
- **`Suit`** (wands/cups/swords/pentacles) and **`Arcana`** (major/minor) are plain, always-populated structured fields — this is what makes `relationships.py`'s two relationship types (Section 1.1) mechanically well-defined without inventing anything.
- **`Card.rank`** is a free-text string (`"0"`–`"10"`, `"Page"`, `"Knight"`, etc., confirmed via `app/models/card.py`: `Mapped[str | None]`). It is not a normalized integer, and no product-spec or architecture text defines what a "numerological sequence" rule should mean structurally (three ascending ranks? three of the same rank across suits? something else). This confirms `relationships.py`'s existing decision not to implement it — there is genuinely no reviewed definition to implement, not just an oversight.
- **`CardCorrespondence`** remains citation-only per `INTERPRETATION_ENGINE_DESIGN.md` Q5 — nothing in this document revisits that; no rule below is triggered by, or scored using, correspondence fields.
- **`theme_vocabulary.yaml`** has no marked antonym/opposition pairs, no marked synonym-strength weights, and no marked "primary vs. secondary theme value" — it is a flat, unweighted, unordered-within-groups list (`RAIDIAN_WISE_THEME_VOCABULARY_V1.md` confirms the section headers are "for human readability only," per the file's own header comment). Any rule that would require treating two tags as opposites, or weighting one theme tag above another, has no data to point to today.
- **`SemanticRole`** has 8 values; only 3 spreads exist, and between them they exercise 6 of the 8 roles in seeded data (situation, recent_past, influence_blocker, near_future, advice, advice_clarifier, general — `significator` is defined in the enum but not in any seeded spread, Section 1.1).

## 1.3 What this means for Step 3

Most of what Step 2 already built is *correctly* conservative — it declines to do things (position weighting, question weighting, contradiction detection, numerological sequences) precisely because no reviewed rule exists for them, and this inspection confirms that's still true: no new reference data or product-spec content has appeared since Step 2 to change any of those conclusions. Step 3's real work is therefore narrower than "design everything": it is (a) **formalizing, as testable rule specifications, the rules Step 2 already implements** (so they're reviewable as *rules*, not just as code), and (b) **explicitly deciding the two live gaps in Section 1.1** — whether `relationships.py`'s output and `structure.py`'s `significator` finding should be wired into the model, and if so, exactly how, as a **proposed** rule requiring separate approval before implementation (per this task's explicit instruction not to implement anything here).

---

# 2. Rule Specification Format

Every rule below (supported, proposed, or deferred) is stated in this fixed shape, so Step 4 can implement or test any one of them without re-deriving intent:

```
Rule <ID> — <name>
Status:      Supported (implemented, Step 2) | Proposed (requires approval) | Deferred (blocked on data/taxonomy)
Trigger:     the precise condition under which this rule fires
Inputs:      exactly which fields/objects it reads
Output:      exactly what it produces, and which InterpretiveModel field (if any) it feeds
Precedence:  what happens if this rule and another rule could both apply to the same output
Provenance:  which Citation(s) it attaches, and how
Test:        the existing test(s) that verify it (Supported), or "none — blocked on approval/data" (Proposed/Deferred)
```

---

# 3. Card-Level Interpretation Rules

## Rule M1 — Meaning Text Resolution by Orientation
**Status:** Supported (implemented — `context.py`, `build_reading_context`)
**Trigger:** Every `CardDraw`, unconditionally.
**Inputs:** `CardDraw.orientation`, `Card.base_meaning_upright`, `Card.base_meaning_reversed`.
**Output:** `DrawContext.meaning_text` = the upright text if `orientation == UPRIGHT`, else the reversed text. Citation/display only (`INTERPRETATION_ENGINE_DESIGN.md` Section 3.1) — never parsed or scored.
**Precedence:** None — unconditional per-draw resolution, no conflict possible.
**Provenance:** Carried as part of the `Citation.card_draw_id` reference; the text itself is not separately cited, only referenced.
**Test:** `test_interpretation_context.py::test_context_resolves_upright_meaning_text`, `::test_context_resolves_reversed_meaning_text`.

## Rule M2 — Theme Extraction (Primary + Secondary, Deduplicated, Order-Preserved)
**Status:** Supported (implemented — `context.py`, `DrawContext.all_themes`)
**Trigger:** Every `CardDraw`, unconditionally.
**Inputs:** `Card.primary_themes`, `Card.secondary_themes` (both `list[str]`, closed vocabulary).
**Output:** `DrawContext.all_themes` — primary themes followed by secondary themes, in stored (curated) order, deduplicated (a tag present in both lists counts once). This is the sole atomic unit of theme-level evidence (Section 4).
**Precedence:** None.
**Provenance:** Each theme's origin card/draw is preserved implicitly (the caller always has the owning `DrawContext`).
**Test:** `test_interpretation_context.py::test_all_themes_preserves_primary_then_secondary_order_and_dedupes`.

## Rule M3 — Orientation Does Not Modify Theme Selection *(Deferred — states a constraint, not a gap)*
**Status:** Deferred, blocked on data.
**What would trigger it:** A rule that reversed orientation shifts, suppresses, or adds theme weight (a common tarot convention — "reversed cards suggest blocked or internalized versions of their themes") would require a `reversed_themes` (or equivalent) field on `Card`, populated through the same authored, reviewed process as `primary_themes`/`secondary_themes` were (`RAIDIAN_WISE_REFERENCE_DATA_V1.md`).
**Why not implemented:** No such field exists (Section 1.2). Inventing a mechanical transform (e.g. "reversed cards' primary themes become secondary") would be exactly the kind of unreviewed interpretive invention the design constraints prohibit — it is itself a claim about what reversal *means*, and that claim has never been authored or reviewed as reference-data content.
**What would resolve it:** A dedicated content-authoring pass (the same shape as the original Reference Data / Content Foundation phase), producing either a new structured field or an explicit written rule for how reversal modulates theme relevance, reviewed the same way the original 78 cards' themes were.

---

# 4. Position-Level Interpretation Rules

## Rule P1 — Role-Filtered Structural Selection
**Status:** Supported (implemented — `structure.py`, `evaluate_structure`)
**Trigger:** For each of `situation`, `influence_blocker`, `advice`, `advice_clarifier`, `significator`: does any `SpreadPosition` in this Reading's Spread carry that `semantic_role`, and was a card drawn into it?
**Inputs:** `SpreadPosition.semantic_role` (per position), `ReadingContext.draws`.
**Output:** `StructuralFindings` — at most one `DrawContext` per role (a Spread has at most one position per role by construction, since `semantic_role` is a single value per position). `None` when the Spread has no position with that role.
**Precedence:** N/A — each role is looked up independently; no two roles can compete for the same slot.
**Provenance:** The selected draw's own `Citation` (via `citation_for_draw`), attached when the finding reaches a final field (Rule A4/A5/A6 below).
**Test:** `test_interpretation_pipeline_stages.py::test_structure_finds_advice_and_clarifier_in_celtic_cross`, `::test_structure_fields_are_none_when_spread_lacks_the_role`.

**Note on `significator`:** mechanically identical to the other four roles, and already implemented — but see Section 1.1/1.3: no seeded Spread currently defines a `significator` position, so this branch is exercised only by hypothetical/future spread content, not by any of the three shipped spreads. No change proposed; documented here so a future spread author knows the engine-side support already exists.

## Rule P2 — Trajectory Uses Fixed Semantic-Role Order, Not `position_order`
**Status:** Supported (implemented — `trajectory.py`)
**Trigger:** Unconditional per Reading; evaluates `recent_past`, then `situation`, then `near_future`, in that literal fixed order, regardless of each role's `position_order` in the Spread.
**Inputs:** `ReadingContext.draws_with_role()` for each of the three roles, in the fixed tuple `_TRAJECTORY_ROLE_ORDER`.
**Output:** `Explained[Trajectory]` with one `TrajectoryStep` per role present; `None` if fewer than 2 roles are present (a single point has no arc).
**Precedence:** N/A — the three roles are looked up independently and assembled in the fixed order; no ambiguity.
**Provenance:** One `Citation` per included step, via `citation_for_draw`.
**Test:** `test_interpretation_pipeline_stages.py::test_trajectory_uses_semantic_role_order_not_position_order` — the deliberately adversarial Celtic Cross case (Recent Past at `position_order` 4, Situation at 1) is the regression guard for this rule specifically.

## Rule P3 — No Numeric Position-Weighting of Themes *(Deferred — reaffirms `relevance.py`'s existing no-op)*
**Status:** Deferred, blocked on a reviewed formula.
**What would trigger it:** A rule boosting a theme's score when it comes from a structurally significant position (e.g. `situation` or `significator`) over a `general` position.
**Why not implemented:** No formula for *how much* to boost, or which roles qualify, is specified anywhere in `RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, `RAIDIAN_WISE_ARCHITECTURE_V1.md`, or `INTERPRETATION_ENGINE_DESIGN.md` — this is the same conclusion Step 2's `relevance.py` already reached and documented (`apply_position_relevance`'s docstring). Nothing found in this inspection changes that. Structural position context is not lost in the meantime — it is already fully preserved on every `Citation` (`position_name`, `position_semantic_role`), so Explainability is unaffected either way.
**What would resolve it:** A product-level decision naming specific roles and specific weights (or a ranking scheme), reviewed and authored the same deliberate way compound-theme rules are (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 11.3's anti-overfitting discipline applies equally well here).

---

# 5. Theme-Level Interpretation Rules

## Rule T1 — Theme Frequency Scoring with Fixed Tiebreak
**Status:** Supported (implemented — `meanings.py`, `score_theme_strength`)
**Trigger:** Unconditional per Reading.
**Inputs:** Every draw's `all_themes` (Rule M2).
**Output:** `tuple[ThemeScore, ...]` — one entry per distinct theme tag appearing on any drawn card, `count` = number of distinct drawing cards contributing that tag (a tag appearing as both primary and secondary on the *same* card still counts once, per M2's own dedup — but a tag repeated across *different* cards counts once per card). Sorted by `(-count, theme name ascending)` — a fixed, content-derived tiebreak, never dict/set order.
**Precedence:** N/A — this is the base ranking every downstream theme-based rule (T2, T3) reads from.
**Provenance:** One `Citation` per contributing draw, attached to that theme's `ThemeScore.citations`.
**Test:** `test_interpretation_pipeline_stages.py::test_score_theme_strength_orders_by_count_desc_then_name_asc`, `::test_score_theme_strength_is_deterministic`, `::test_every_theme_score_has_at_least_one_citation`.

## Rule T2 — Central Issue = Top Theme Score
**Status:** Supported (implemented — `engine.py`, `_derive_central_issue`)
**Trigger:** Unconditional (a Reading always has at least one draw, enforced by `interpret()`'s own precondition check, so `theme_scores` is never empty).
**Inputs:** `theme_scores[0]` — the single highest-ranked entry from Rule T1's output (after Rule T1's tiebreak has already resolved ties deterministically).
**Output:** `InterpretiveModel.central_issue: Explained[str]` = that theme's tag, with that `ThemeScore`'s own citations forwarded unchanged.
**Precedence:** This *is* the tiebreak-consumer for T1 — no further tiebreak needed since T1 already produces a total order.
**Provenance:** Forwarded directly from `ThemeScore.citations` (T1).
**Test:** `test_interpretation_engine.py::test_interpret_produces_a_fully_populated_model_for_a_rich_reading` (asserts `central_issue is not None`); indirectly exercised by every determinism test.

## Rule T3 — Supporting Themes = Next-Ranked Themes (capped) + Remaining Compound Matches
**Status:** Supported (implemented — `engine.py`, `_derive_supporting_themes`)
**Trigger:** Unconditional.
**Inputs:** `theme_scores` (T1) excluding the entry already used for `central_issue` (T2); `remaining_compound_matches` (Rule C3, Section 6).
**Output:** `InterpretiveModel.supporting_themes: tuple[Explained[str], ...]` — up to **3** (the fixed constant `_SUPPORTING_THEMES_LIMIT`) next-highest-ranked themes by T1's order, **followed by** every compound match not already consumed as `primary_tension`, each contributing its own rule name as the `value` (e.g. `"Intuition Within Uncertainty"`).
**Precedence:** Theme-score entries always precede compound-match entries in the output list (fixed sub-order); within each group, order is T1's order (themes) or `RULE_REGISTRY` order (compounds, Rule C1). No cap is applied to the compound-match portion — all remaining matches are always included (there are only 2 rules total today, Section 6, so this has never mattered in practice, but the rule as implemented has no cap on that portion).
**Provenance:** Theme entries forward `ThemeScore.citations`; compound-match entries forward `match.citations` plus a rule citation (`citation_for_matched_rule`).
**Test:** `test_interpretation_engine.py::test_every_explained_field_carries_at_least_one_citation` (covers all `supporting_themes` entries); `test_compound_rules.py::test_match_order_follows_registry_order_deterministically` (covers the compound-match sub-order feeding into this).

## Rule T4 — No Primary/Secondary Theme Weighting *(Deferred — reaffirms current equal-weight behavior)*
**Status:** Deferred, blocked on a reviewed weight value.
**What would trigger it:** A rule scoring a card's `primary_themes` more heavily than its `secondary_themes` in T1's count (e.g. primary = 2 points, secondary = 1).
**Why not implemented:** `theme_vocabulary.yaml` and every card's authored content (`RAIDIAN_WISE_REFERENCE_DATA_V1.md`) establish primary vs. secondary as a *curation* distinction (which themes the content author judged most central to a card) but never assign it a numeric weight, and no such weight appears in the product spec. T1's current equal-weight-per-distinct-card behavior is not an oversight — it is the only behavior directly supported by the data as authored (a card "having" a theme, primary or secondary, is binary; only *how many drawn cards* have it is unambiguous).
**What would resolve it:** A product decision on a specific weight ratio, treated with the same review discipline as a compound-theme rule promotion.

---

# 6. Compound-Theme Rules

## Rule C1 — Fixed Registry Evaluation Order
**Status:** Supported (implemented — `compounds.py`, `match_compounds`)
**Trigger:** Unconditional; every rule in `RULE_REGISTRY` is evaluated, in the registry's own literal tuple order, every run.
**Inputs:** `ReadingContext` (each rule's own `trigger` callable reads whatever subset it needs — both current rules read `_draws_with_theme` for two specific tags).
**Output:** `tuple[CompoundMatch, ...]`, always in registry order among whichever rules fired (never draw order, never a `set`/`dict`-derived order).
**Precedence:** Registry order **is** the precedence — it is what Rule C2 (below) consumes to pick a single `primary_tension` when multiple tension-type rules fire.
**Provenance:** Each `CompoundMatch.citations` = every contributing draw's citation (one per draw supporting either pole).
**Test:** `test_compound_rules.py::test_match_order_follows_registry_order_deterministically`, `::test_match_compounds_is_deterministic_across_repeated_calls`.

## Rule C2 — Primary Tension = First Tension-Type Match, Registry Order
**Status:** Supported (implemented — `engine.py`, `_derive_primary_tension`)
**Trigger:** At least one `CompoundMatch` with `pattern_type == "tension"` exists.
**Inputs:** `compound_matches` (C1).
**Output:** `InterpretiveModel.primary_tension: Explained[Tension] | None` = the first such match's `Tension`, plus its citations and a rule citation. `None` if no tension-type match fired.
**Precedence:** If two tension-type compounds both fire (not currently possible with only 1 tension-type rule seeded, but the rule is written generally), the earlier one in `RULE_REGISTRY` wins; the other becomes an ordinary entry consumed by Rule T3/C3.
**Provenance:** Forwarded `CompoundMatch.citations` + `citation_for_matched_rule`.
**Test:** `test_interpretation_engine.py::test_interpret_produces_a_fully_populated_model_for_a_rich_reading` (asserts the exact expected label on a fixture with both rules firing).

## Rule C3 — Non-Primary Matches Forward Into Supporting Themes
**Status:** Supported (implemented — `engine.py`, `_derive_primary_tension`'s `remaining` return value, consumed by `_derive_supporting_themes`)
**Trigger:** Any `CompoundMatch` not selected by C2 (either a `"theme"`-type match, or a `"tension"`-type match that lost precedence to an earlier one).
**Inputs:** `remaining_compound_matches`.
**Output:** Feeds Rule T3 (Section 5) — each remaining match becomes one `supporting_themes` entry.
**Precedence:** See T3 — compound entries always come after theme-score entries.
**Provenance:** See T3.
**Test:** `test_interpretation_engine.py::test_interpret_produces_a_fully_populated_model_for_a_rich_reading` (both `clarity_vs_uncertainty` — as `primary_tension` — and `intuition_within_uncertainty` — as a `supporting_themes` entry — fire together on the Celtic Cross fixture).

## Currently supported compound rules (data-verified)

| Rule ID | Pattern | Trigger tags (verbatim in `theme_vocabulary.yaml`) |
|---|---|---|
| `clarity_vs_uncertainty` | tension | `clarity`, `uncertainty` |
| `intuition_within_uncertainty` | theme | `intuition`, `uncertainty` |

## Deferred compound rules — named in the product brief, not implementable without inventing a mapping

Per `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 11's seed list, `compounds.py`'s own docstring, and re-confirmed by this inspection against the current 107-tag vocabulary:

| Named compound | Blocking tag(s) | Why blocked |
|---|---|---|
| Security vs. Change | `security`, `change` | Neither exists verbatim; `change` was normalized into `transition` during the Reference Data Enrichment pass, and there is no `security` tag (closest is `material_security`, a narrower concept, not confirmed equivalent). |
| Security vs. Departure | `security`, `departure` | Same `security` issue; no `departure` tag exists at all. |
| Emotional Transition | `emotional_transition` (or an implied `emotional` + `transition` pairing) | No single tag; pairing `emotional_connection` with `transition` would be an invented mapping, not a confirmed one. |
| Clarity Leading to Change | `clarity`, `change` | `change` blocked as above; also implies a *sequential* relationship ("leading to") that no other compound rule models — a new pattern type, not just a tag swap. |
| Release Through Restructuring | `release`, `restructuring` | Neither tag exists; closest candidates (`letting_go`, `transformation`) are plausible but unconfirmed substitutions. |

**No new mapping is proposed here**, per this task's explicit instruction ("Do not invent mappings merely to increase coverage"). Resolving any of these requires a deliberate, reviewed content decision (does "Security" in the original brief mean `material_security`? `stability`? both?) — the same kind of authored decision the original theme-vocabulary consolidation pass made, not something this design document should decide unilaterally.

---

# 7. Card-to-Card Relationships

## Rule R1 — Same-Suit Clustering
**Status:** Supported (implemented — `relationships.py`) — **computed, not yet wired to any output field** (Section 1.1 gap).
**Trigger:** 2 or more drawn cards share the same `Suit`.
**Inputs:** `DrawContext.suit` for every draw.
**Output:** `tuple[SuitCluster, ...]`, sorted by suit name for determinism.
**Precedence:** N/A today (unconsumed).
**Provenance:** N/A today (unconsumed) — would need citations defined if wired to output (Section 7.1 below).
**Test:** `test_interpretation_pipeline_stages.py::test_relationships_detects_same_suit_cluster`, `::test_relationships_no_cluster_when_suits_dont_repeat`.

## Rule R2 — Major Arcana Density
**Status:** Supported (implemented — `relationships.py`) — **computed, not yet wired to any output field** (Section 1.1 gap).
**Trigger:** Unconditional; counts drawn cards with `Arcana.MAJOR`.
**Inputs:** `DrawContext.arcana` for every draw.
**Output:** `int` (`CardRelationships.major_arcana_count`).
**Precedence:** N/A today (unconsumed).
**Provenance:** N/A today (unconsumed).
**Test:** `test_interpretation_pipeline_stages.py::test_relationships_counts_major_arcana_density`.

## 7.1 Deferred — Wiring R1/R2 into the model *(explicitly decided, not merely unproposed)*

These are the clearest concrete gaps this inspection found (Section 1.1) — genuinely deterministic, mechanically well-defined signals that are computed and then thrown away. Two candidate rules were sketched as a starting point for review. Both have now been explicitly decided:

**Rule R3 — Same-Suit Cluster as an Interpretive-Conclusion Field**
**Status: DEFERRED.** The engine may continue to compute this structural evidence (`relationships.py`'s `SuitCluster` output, Rule R1) — that computation is descriptive/internal and is not itself an interpretive conclusion, so it is unaffected by this decision. The engine must **not** interpret that evidence or expose it as part of any `InterpretiveModel` field (`supporting_themes` or any other) until an explicit rule — with an approved trigger, threshold, and target field — is separately reviewed and approved. This document does not approve one.
- *Candidate shape, recorded for a future approval pass only (not itself approved):* a `supporting_themes`-style entry per cluster (e.g. `value = "Recurring Swords"`, citing every draw in the cluster, `source_type = "structural_rule"`).
- *Open questions that would need to be settled before any future approval:* (a) is "2+ shared suit" the right threshold, or should it require 3+ given a 10-position spread has more chances for incidental overlap than a 3-position one? (b) does this belong in `supporting_themes` (implying it's theme-like) or does it need a new `InterpretiveModel` field (a schema change, out of scope for a "no redesign" constraint)? (c) what's the actual interpretive claim being made — "cards of one suit recurring" doesn't have an authored meaning anywhere in the reference data the way individual theme tags do.

**Rule R4 — Major Arcana Density as an Evidence-Strength Signal**
**Status: DEFERRED.** The engine may continue to compute this structural evidence (`relationships.py`'s `major_arcana_count`, Rule R2) — that computation is descriptive/internal and is not itself an interpretive conclusion. The engine must **not** use it as an evidence-strength scoring input (Rule A9) or expose it as any other interpretive conclusion until an explicit rule — with an approved trigger and threshold — is separately reviewed and approved. This document does not approve one.
- *Candidate shape, recorded for a future approval pass only (not itself approved):* an additional point in Rule A9's evidence-strength count, or a dedicated `uncertainty`-style statement on the low end ("This spread drew few Major Arcana cards").
- *Open questions that would need to be settled before any future approval:* (a) what threshold, and does it scale with spread size (3-card vs. 10-card) or stay fixed? (b) is "more Major Arcana" actually evidence of *stronger* support, or does that conflate two different things (thematic weight vs. structural completeness) that Rule A9 currently keeps cleanly separate (Section 10)?

Neither R3 nor R4 is implemented by this document, and neither is approved for implementation. Both are deferred pending a dedicated future review — the computation stays (Rules R1/R2 are unaffected), only its use as an interpretive conclusion is withheld.

## Rule R5 — Numerological Sequences *(Deferred — no definition exists to implement)*
**Status:** Deferred, blocked on a taxonomy that does not exist anywhere in this project's reviewed documentation.
**Why not implemented:** `Card.rank` is an unstructured string (Section 1.2); no product-spec, architecture, or prior design text defines what a "meaningful" numerological sequence is (ascending ranks across positions? repeated ranks across suits? something tied to numerology traditions not otherwise present in this project's reference data at all?). `relationships.py`'s own docstring already reaches this conclusion; this inspection found nothing new to change it.
**What would resolve it:** A dedicated content-authoring decision (likely its own reviewed phase, given how much interpretive judgment "numerological sequence" implies) — not something inferable from existing structured fields alone.

---

# 8. Question/Context Relevance

**Status:** Unchanged — reaffirmed no-op (`relevance.py`), per `INTERPRETATION_ENGINE_DESIGN.md` Q3.

This inspection found no new evidence changing Q3's resolution: `question_domain` still has no fixed taxonomy anywhere in the repository (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 16's Q6 remains unresolved), and no product-spec or architecture text has been added since Step 2 that would supply one. Per this task's explicit instruction, no taxonomy is created here. `apply_question_relevance` remains a documented pass-through; nothing proposed.

---

# 9. Contradiction Rules

**Status:** Unchanged — reaffirmed always-empty (`contradictions.py`).

This inspection specifically checked whether the current reference data supports **any** explicit, mechanically-triggerable contradiction rule, as this task requested. Conclusion: **no**.

- The two existing compound rules (Section 6) model a *held tension* ("Clarity vs. Uncertainty" — both poles present, meant to be surfaced together), which is a different concept from a *contradiction* in the product spec's sense (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 10.10: "competing signals that... can't be reconciled"). Reusing a tension-pattern match as a "contradiction" would misrepresent what a tension match is meant to convey — the compounds.py docstring already makes this distinction explicitly, and this inspection confirms it still holds.
- A genuine contradiction rule would require an authored, reviewed table of theme tags (or compound patterns) that are considered mutually exclusive or opposed — e.g. is `hope` in tension with `grief`? Is `stability` in contradiction with `upheaval`, or are they simply two different cards' honest content that can coexist in one reading without being a "contradiction" at all? **No such table exists anywhere in `theme_vocabulary.yaml` or any card's content** (Section 1.2) — the vocabulary is deliberately flat, with no marked antonym relationships. Deciding which tags oppose which is a genuine interpretive judgment call, exactly the kind this document's own governing constraint (Section 0) prohibits inventing.
**What would resolve it:** A dedicated, reviewed authoring pass producing an explicit opposition/antonym table (structurally similar to how compound-theme rules were authored) — not scoped or started here.

---

# 10. Interpretation Assembly Specification

This section states, precisely, how `engine.py`'s `interpret()` currently assembles the final `InterpretiveModel` from the stage outputs above — the formal specification for what is otherwise only implicit in reading the code.

## Rule A1 — Precondition
**Trigger:** `interpret()` is called.
**Rule:** If `reading_context.draws` is empty, raise `ValueError` — an empty Reading is a caller error (interpretation is only meaningful once a Reading is spread-complete), not a degraded-but-valid output.
**Test:** `test_interpretation_engine.py::test_interpret_raises_on_a_reading_with_no_card_draws`.

## Rule A2 — Metadata Stamping
**Rule:** Every run stamps `schema_version` (`InterpretiveModel`'s own shape version), `engine_version` (this pipeline's logic version), `reference_data_version` (a content hash of the reference data actually read this run — `INTERPRETATION_ENGINE_DESIGN.md` Q2), and `generated_at` (wall-clock metadata, explicitly never an input to *what* is concluded — Section 5 of that document). None of these four values affects any other field's content.

## Rule A3 — `central_question`
**Rule:** `Reading.question`, carried through verbatim, unconditionally. No paraphrasing, no truncation.

## Rules A4–A6 — Structural Fields (Blocker, Advice, Clarification)
**Rule:** Each of `blocker`, `advice`, `clarification` is `None` unless `structure.py` (Rule P1) found the corresponding role-draw; when present, its value is the draw's first `primary_theme` (falling back to the card's own name if it has none), cited to that draw. `clarification` additionally cites the `advice` draw (not just the `advice_clarifier` draw), since a clarification is meaningless without the thing it clarifies.
**Precedence:** These three fields are populated independently of theme-scoring (Section 5) and compound-matching (Section 6) — a card that fills the `advice` role contributes to `advice` *and* still counts toward theme scoring / compound matching like any other drawn card. No conflict: the same evidence can legitimately support multiple output fields simultaneously, each with its own citation.
**Test:** `test_interpretation_engine.py::test_interpret_produces_a_fully_populated_model_for_a_rich_reading`, `test_interpretation_pipeline_stages.py::test_structure_finds_advice_and_clarifier_in_celtic_cross`.

## Rule A7 — `trajectory`
**Rule:** Directly `derive_trajectory`'s output (Rule P2), unmodified.

## Rule A8 — `uncertainty`
**Rule:** A fixed-order checklist (`evidence.py`, `identify_uncertainty`) — checks, in this literal sequence: no trajectory → statement; no advice position → statement (else no advice-clarifier → a different statement); no blocker position → statement; no compound match fired → statement. Always a tuple (possibly empty), never omitted (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 10.7's explicit requirement that this field exists even on strong readings).
**Test:** `test_interpretation_pipeline_stages.py::test_uncertainty_and_evidence_strength_for_a_thin_spread`, `::test_uncertainty_and_evidence_strength_for_a_rich_spread`.

## Rule A9 — `evidence_strength`
**Rule:** A point count (`evidence.py`, `score_evidence_strength`): +1 if a trajectory was derived, +1 if situation/blocker are both present, +1 if advice/clarifier are both present, +1 per fired compound match. `0` → `"unresolved"`, `1` → `"weak"`, `2`–`3` → `"moderate"`, `4+` → `"strong"`. Documented in-code as a deliberately simple, provisional heuristic — **not** a probability (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 10.11).
**Note:** As Section 7.1 observes, this count currently ignores `relationships.py`'s output entirely (same-suit clusters, Major Arcana density) — not an oversight, but a real scope boundary this document surfaces rather than silently accepts (Proposed Rule R4).

## Rule A10 — Every `Explained[T]` Carries ≥1 Citation
**Rule:** Enforced structurally, not just by convention — `Explained.citations` is `Field(min_length=1)` at the Pydantic schema level (`app/schemas/interpretive_model.py`). An `Explained` field with zero citations cannot be constructed; this makes "an unsupported conclusion" a construction-time error, not a possible-but-untested state.
**Test:** `test_interpretive_model_schema.py` (schema-level tests); `test_interpretation_engine.py::test_every_explained_field_carries_at_least_one_citation` (integration-level confirmation across a real run).

---

# 11. Rule Precedence & Conflict Handling

Consolidated precedence ladder across every rule in Sections 3–10, for the case where more than one rule's output could plausibly compete for the same `InterpretiveModel` field:

1. **`primary_tension` vs. `supporting_themes`** — a compound match that is `pattern_type == "tension"` and is the *first* such match in `RULE_REGISTRY` order always wins `primary_tension` (Rule C2); every other match (tension or theme type) falls through to `supporting_themes` (Rule C3). This is the only place two rules from the *same* stage (compound matching) compete for different final fields, and it is fully deterministic by construction (registry order is a fixed literal).
2. **`central_issue` vs. `supporting_themes`** — the single top-ranked theme (Rule T1's total order) always becomes `central_issue` (T2) and is explicitly excluded from `supporting_themes` (T3) — no double-reporting.
3. **`supporting_themes` internal order** — theme-score entries (T1 order) always precede compound-match entries (registry order) — a fixed, two-part sequence, never interleaved by score or any other criterion.
4. **Structural fields (`blocker`, `advice`, `clarification`, `trajectory`) do not compete with theme/compound fields at all** — they are populated from entirely independent evidence lookups (role-based draw selection, Rule P1/P2) and can legitimately cite the *same* underlying `CardDraw` that also contributed to a theme score or compound match, each with its own field-scoped citation set (Rule A4–A7). This is by design, not an oversight: `RAIDIAN_WISE_PRODUCT_SPEC_V1.md`'s Interpretive Model fields (Section 10) are not mutually exclusive lenses on the same evidence.
5. **`uncertainty` and `evidence_strength` never compete with each other or with any other field** — both are derived *from* the presence/absence of the other fields' findings (Rule A8/A9 read `structure`, `trajectory`, `compound_matches` directly, not the assembled `InterpretiveModel`), evaluated in each function's own fixed, literal order.

**R3 and R4 (Section 7.1) are DEFERRED, not merely unproposed, so no precedence is assigned** — while deferred, neither populates any `InterpretiveModel` field, so there is nothing to arbitrate against. Assigning precedence (e.g. "does a same-suit cluster's supporting-theme entry come before or after compound-match entries?") is itself a design decision that should happen at a future, dedicated approval pass, informed by whatever trigger/threshold/target field that pass actually approves — not pre-decided here against a rule this document deliberately declines to approve.

---

# 12. Summary Tables

## 12.1 Rules currently supported by existing data (implemented in Step 2, formalized here)

| ID | Name |
|---|---|
| M1 | Meaning Text Resolution by Orientation |
| M2 | Theme Extraction (dedup, order-preserved) |
| P1 | Role-Filtered Structural Selection |
| P2 | Trajectory Fixed Semantic-Role Order |
| T1 | Theme Frequency Scoring, Fixed Tiebreak |
| T2 | Central Issue = Top Theme Score |
| T3 | Supporting Themes = Next-Ranked + Remaining Compounds |
| C1 | Fixed Registry Evaluation Order |
| C2 | Primary Tension = First Tension-Type Match |
| C3 | Non-Primary Matches → Supporting Themes |
| R1 | Same-Suit Clustering (computed, unconsumed) |
| R2 | Major Arcana Density (computed, unconsumed) |
| A1–A10 | Assembly rules (Section 10) |

## 12.2 Rules proposed, requiring product/architecture approval before implementation

None. R3 and R4 (same-suit clustering and Major Arcana density as interpretive conclusions, Section 7.1) were the only candidates sketched, and both were explicitly **decided as deferred** rather than left open — see Section 12.3. Nothing in this document currently sits in an open "proposed, awaiting a yes/no" state.

## 12.3 Rules deferred, requiring additional reference data, a taxonomy, or a dedicated future approval that does not yet exist

| ID | Name | Missing |
|---|---|---|
| M3 | Orientation-conditional theme shift | A `reversed_themes`-equivalent authored field |
| P3 | Position-weighted theme scoring | A reviewed weight formula |
| T4 | Primary/secondary theme weighting | A reviewed weight ratio |
| — | 5 named compounds (Security vs. Change, Security vs. Departure, Emotional Transition, Clarity Leading to Change, Release Through Restructuring) | A reviewed tag mapping for each (Section 6) |
| R3 | Same-suit cluster as an interpretive conclusion | An explicit, separately approved rule (trigger/threshold/target field) — Section 7.1. The underlying evidence (Rule R1) may still be computed; only its use as a conclusion is withheld. |
| R4 | Major Arcana density as an evidence-strength signal | An explicit, separately approved rule (trigger/threshold) — Section 7.1. The underlying evidence (Rule R2) may still be computed; only its use in scoring is withheld. |
| R5 | Numerological sequences | A reviewed definition of "meaningful sequence" |
| — | Contradiction detection (any rule) | A reviewed antonym/opposition table (Section 9) |
| — | Question-domain weighting | The still-unresolved product-level taxonomy (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 16, Q6) |

---

# 13. Closed-System Constraint — Restated

Every rule above, in every status column, was checked against this test before being written down: *does this rule's trigger point to a specific, already-reviewed piece of reference data or design decision, or does it require the engine (or this document) to decide, on its own authority, what something means?* Rules that failed this test were placed in Section 12.3 (Deferred) rather than implemented — a Deferred rule names *what data or decision is missing*, not a best-guess substitute for it. Section 12.2 (Proposed) is currently empty by explicit decision: R3 and R4, the only candidates this inspection surfaced, were considered and deliberately deferred (Section 7.1, Section 12.3) rather than left as open proposals — for both, the underlying structural evidence may still be computed, but the engine must not interpret it or expose it as an interpretive conclusion until a future, separately reviewed rule approves doing so. Nothing in this document authorizes implementing R3, R4, or any other deferred rule.

---

## Related Documents

- `INTERPRETATION_ENGINE_DESIGN.md` — Step 1's contract (inputs/outputs/determinism) and Step 1's six resolved design questions, which this document builds on without revisiting.
- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Sections 9–13, the conceptual pipeline and Interpretive Model fields every rule above maps back to.
- `RAIDIAN_WISE_ARCHITECTURE_V1.md` — Sections 5–7, the technical sketch (`interpret()`'s illustrative signature, `CompoundThemeRule`'s shape) Step 2 implemented and this document specifies rules against.
- `RAIDIAN_WISE_THEME_VOCABULARY_V1.md` — the 107-tag vocabulary's consolidation rationale, referenced throughout Sections 5–6 for which tag mappings are and are not confirmed.
- `RAIDIAN_WISE_REFERENCE_DATA_AUDIT_V1.md` — the correspondence-data consistency findings `INTERPRETATION_ENGINE_DESIGN.md` Q5 already responded to; unchanged by this document.
- `app/services/interpretation/` — the Step 2 implementation every "Supported" rule in this document formalizes.
