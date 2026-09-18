# Raidian Wise — Interpretation Engine Validation (Step 5)

# Document Information

Version: 1.0
Status: Complete — Validation Only, No Implementation Changes
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Empirically validates the deterministic Interpretation Engine as implemented at baseline `18c90e0` (Step 2's engine, unchanged through Step 3's rules design and Step 4's audit) against the approved rules in `INTERPRETATION_RULES_DESIGN.md`. This document runs a representative matrix of Readings against the real seeded Rider-Waite-Smith reference data, inspects the complete `InterpretiveModel` produced for each, and records what was actually observed — determinism, rule coverage, provenance, and any gap between what the design promises and what the code produces. No engine code, schema, or reference-data file was changed to produce this document.

Audience:
Software engineers and AI development agents planning Step 6 and beyond (any future rule approval, narrative-generation layer, or schema change), and anyone auditing whether the engine currently does what it claims to do.

Authority:
Validates `INTERPRETATION_ENGINE_DESIGN.md` (the contract) and `INTERPRETATION_RULES_DESIGN.md` (the rule specification) against the actual runtime behavior of `app/services/interpretation/`. Does not override either document — a discrepancy found here would be a defect report against them, not a redesign.

---

# 0. Method

A standalone harness (not committed to the repository) built 10 Readings against a fresh, fully-seeded in-memory database (the same `seed_reference_data` pipeline the real app and `tests/conftest.py::seeded_session` use), ran `engine.interpret()` on each, and dumped the complete `InterpretiveModel` as JSON for inspection. Several cases were additionally re-run to check determinism, and `relationships.py`'s output was called directly (bypassing the engine) on the richest case to confirm what the engine computes internally versus what reaches its output — the specific question Section 7.1 of the rules design left open.

This is validation, not a new test suite: `backend/tests/` (164 tests) already covers unit-level behavior for every stage; this exercise instead inspects **whole, realistic `InterpretiveModel` outputs end to end**, the way a future consumer (Explainability UI, narrative layer) actually would.

---

# 1. Validation Matrix

| # | Case | Spread | Cards (orientation) | What it targets |
|---|---|---|---|---|
| 1 | Upright card | Single Card | The Fool (upright) | M1, M2 baseline |
| 2 | Reversed card | Single Card | The Fool (reversed) | M1 (meaning-text swap), M3 boundary (no theme shift) |
| 3 | Repeated theme | Celtic Cross | The Moon, Two of Swords, Wheel of Fortune (all contribute `uncertainty`) + 7 fillers | T1 frequency scoring, T2 central issue selection |
| 4 | Deterministic tie-break | Three Card | Four of Wands, Ten of Pentacles, Six of Pentacles | T1's `(-count, theme name)` tiebreak, cross-reading determinism |
| 5 | Applicable compound rule | Three Card | Ace of Swords (clarity), The Chariot, The Moon (uncertainty + intuition) | C1/C2/C3 |
| 6 | Multiple compound matches | Celtic Cross | Ace of Swords, The Tower, The Hermit, The Fool, The Star, The Moon, The Chariot, The Empress, The High Priestess, Strength | C1 registry-order precedence with 2 live matches |
| 7 | Different semantic position roles | Celtic Cross | (same as Case 6) | P1 — situation/blocker/advice/advice_clarifier/significator |
| 8 | Celtic Cross trajectory ordering | Celtic Cross | (same as Case 6) | P2 — fixed role order vs. adversarial `position_order` |
| 9 | Minimal valid reading | Single Card | Four of Wands (upright) | Full-null degradation, A1–A9 on thin evidence |
| 10 | Larger interacting reading | Celtic Cross | Ace of Swords, The Tower, Two of Swords, The Fool, High Priestess (reversed), The Moon, King of Swords, The Empress, The Star, Strength | Richest case; R1/R2 exclusion check under real pressure (3-card Swords cluster, 7 Major Arcana) |

All 10 cases ran against the same reference-data snapshot (`reference_data_version = 54d6b018a1771646998b9c4f25e9dcbad75499c5de4687d705e0a46638bd9d32` in every case — identical to the value already established in `INTERPRETATION_ENGINE_DESIGN.md` Q2's worked example, confirming the seeded content hasn't drifted).

---

# 2. Observed Outputs (per case)

## Case 1 — Upright card (The Fool)
`central_issue = "new_beginnings"` (The Fool's top-listed primary theme), `supporting_themes = ["openness", "potential", "risk_taking"]` (its remaining themes, curated order broken only by T1's count/name sort — all count 1 here so name-ascending applies: `openness < potential < risk_taking`). `primary_tension = null`, `trajectory = null`, `blocker/advice/clarification = null`. `uncertainty` carries all 4 checklist statements. `evidence_strength = "unresolved"`.

## Case 2 — Reversed card (The Fool)
Identical `central_issue`/`supporting_themes`/`evidence_strength` to Case 1. The only observed difference is each citation's underlying `card_draw_id` (a different row) and the meaning text a citation would resolve to if quoted (`base_meaning_reversed` vs. `base_meaning_upright`, confirmed unequal). This is the expected, correct behavior for M1 and the explicitly-deferred M3 (Section 4).

## Case 3 — Repeated theme (`uncertainty` × 3)
`central_issue = "uncertainty"` with **3 citations** (The Moon/Situation, Two of Swords/Challenge, Wheel of Fortune/Foundation) — correctly outranking every count-1 theme. `primary_tension` fired (`clarity_vs_uncertainty`, from The Sun's secondary `clarity` tag vs. the three `uncertainty` contributors) even though `clarity` itself had only 1 supporting draw and never appears in `central_issue`/`supporting_themes`. `supporting_themes` correctly excludes `uncertainty` (already consumed by `central_issue`) and includes `Intuition Within Uncertainty` as a compound entry (C3). `blocker = "indecision"` (Two of Swords/Challenge), `advice = "introspection"` (The Hermit), `clarification = "clarity"` (The Sun, citing both itself and the Advice draw). `evidence_strength = "strong"`.

## Case 4 — Deterministic tie-break
Raw theme scores: `[(2, 'community'), (1, 'balance'), (1, 'contentment'), (1, 'generosity'), (1, 'legacy'), (1, 'material_security'), (1, 'stability')]`. `community` (count 2) correctly wins `central_issue` outright — not actually a tie at the top, but the **count-1 tier below it is listed in exact alphabetical order** (`balance, contentment, generosity, legacy, material_security, stability`), which is the concrete evidence for T1's tiebreak rule. `central_issue.value` was identical across two independently-built Readings with identical draws (`community` both times) — cross-reading content determinism confirmed, matching the existing `test_interpret_is_deterministic_across_independently_built_readings_with_identical_evidence` pattern.

## Case 5 — Applicable compound rule
Intended as a single-match case; **both compound rules fired anyway**, because The Moon alone carries both `uncertainty` (primary) and `intuition` (secondary) — `intuition_within_uncertainty`'s trigger only requires *some* draw with each tag, not two different draws. This is correct per Rule C1/C2 as specified (trigger evaluates raw tag presence across all draws, independent of theme ranking) — see Section 5 (Rule Coverage) for why this is a genuine, useful finding rather than a harness mistake.

## Case 6 — Multiple compound matches
Reproduces the existing rich-reading test fixture. `clarity_vs_uncertainty` → `primary_tension` (registry order — it's listed first in `RULE_REGISTRY`); `intuition_within_uncertainty` → a `supporting_themes` entry. `central_issue = "inner_guidance"` (The Hermit + The High Priestess, count 2). `evidence_strength = "strong"`.

## Case 7 — Structural role coverage
On the Case 6 reading: `situation = Ace of Swords`, `blocker = The Tower`, `advice = The High Priestess`, `advice_clarifier = Strength`, **`significator = None`**. The last is not a defect — confirmed against `app/reference_data/spreads/*.yaml`: none of the three seeded spreads defines a `semantic_role: significator` position, so this branch of P1 is exercised by no real data today (already flagged in `INTERPRETATION_RULES_DESIGN.md` Section 1.1/7's `significator` note; re-confirmed empirically here).

## Case 8 — Trajectory ordering
`trajectory.arc` = `[The Fool (recent_past), Ace of Swords (situation), The Moon (near_future)]` — correct chronological order — even though the Celtic Cross's own `position_order` for these three positions is `4, 1, 6` respectively. P2's fixed-role-order rule is confirmed under real (not just adversarially-constructed test) data.

## Case 9 — Minimal valid reading
Single card, `general` role only. `central_issue = "community"`, `supporting_themes = ["contentment", "stability"]` (all of Four of Wands' own themes). Every structural/temporal field is `null`: `primary_tension`, `trajectory`, `blocker`, `advice`, `clarification`. `uncertainty` carries all 4 checklist statements. `evidence_strength = "unresolved"`. This is the cleanest possible confirmation of A1–A9's null-safe degradation path.

## Case 10 — Larger interacting reading
10-position Celtic Cross engineered to also produce a 3-card same-suit Swords cluster (Ace, Two, King of Swords) and 7 of 10 drawn cards as Major Arcana. `central_issue = "inner_strength"` (The Star + Strength). `primary_tension` fired (`clarity_vs_uncertainty`). `evidence_strength = "strong"`. **Calling `relationships.py::evaluate_relationships` directly on this same reading's context returned `same_suit_clusters = [('swords', ['Ace of Swords', 'Two of Swords', 'King of Swords'])]` and `major_arcana_count = 7` — neither value, nor any trace of them, appears anywhere in the `InterpretiveModel` JSON.** This is the single most important empirical check in this validation pass: R3/R4's deferral (Step 3) holds under real pressure, not just by code inspection.

---

# 3. Rule Coverage

Every field populated across all 10 cases was traced back to one of the approved Step 4 rules; no field's value was observed to originate anywhere else.

| Rule | Exercised in cases | Confirmed correct |
|---|---|---|
| M1 | 1, 2 | Yes — meaning-text selection swaps correctly; theme selection does not |
| M2 | All | Yes — `all_themes` dedup/order confirmed via every `supporting_themes` list |
| P1 | 6, 7, 9 | Yes — role lookups correct; `significator` correctly `None` (data, not code, limitation) |
| P2 | 6, 8 | Yes — fixed role order holds against adversarial `position_order` |
| T1 | 1, 3, 4, 9, 10 | Yes — count ranking and alphabetical tiebreak both directly observed in raw scores |
| T2 | All | Yes — always the count-1 (or higher) top scorer |
| T3 | 1, 3, 4, 5, 6, 9, 10 | Yes — cap of 3 theme entries + all remaining compound matches appended, in that order |
| C1 | 3, 5, 6, 10 | Yes — registry order (`clarity_vs_uncertainty` before `intuition_within_uncertainty`) held in every multi-match case |
| C2 | 3, 5, 6, 10 | Yes — `clarity_vs_uncertainty` always won `primary_tension` when it fired |
| C3 | 3, 5, 6, 10 | Yes — `intuition_within_uncertainty` always landed in `supporting_themes` when it fired alongside the tension match |
| A1–A9 | All (A1 via the pre-existing empty-draws test, not re-run here) | Yes — null-safe degradation (Case 9), full population (Cases 3/6/10), citation enforcement (below) |

**Notable, non-bug finding:** compound rules (C1/C2) trigger on tag *presence* across the whole Reading's draws, independent of whether that tag reached `central_issue` or the top-3 `supporting_themes`. Case 5 demonstrates this cleanly — `clarity` had only 1 supporting draw and never appeared in the ranked theme list, yet `clarity_vs_uncertainty` still fired correctly. This matches the rules as specified (compound triggers read `ReadingContext` directly, not the post-ranking output), but is worth stating explicitly: a compound match's presence in the output is not evidence that its contributing theme was independently "strong," and any future narrative layer should not imply otherwise.

---

# 4. Provenance Coverage

Every non-null `Explained[T]` field observed across all 10 cases carried at least one `Citation`, consistent with the schema-level `Field(min_length=1)` guarantee (A10) — no case produced or could produce a counter-example, since Pydantic construction would fail first. Beyond the structural guarantee, content-level provenance was spot-checked and confirmed correct in every case:

- Theme-based fields (`central_issue`, theme-sourced `supporting_themes` entries) cite exactly the draws that contributed the winning tag, with `contributing_theme` set.
- Compound-based fields (`primary_tension`, compound-sourced `supporting_themes` entries) cite every contributing draw **plus** a trailing rule citation (`source_type: "compound_rule"`, `rule_id`, `rule_tier`) — confirmed in Cases 3, 5, 6, 10.
- Structural fields (`blocker`, `advice`) cite their single source draw; `clarification` additionally cites the `advice` draw it clarifies (Case 3's `clarification` cites both The Sun and The Hermit) — confirmed matches `INTERPRETATION_RULES_DESIGN.md` Rule A4–A6 exactly.
- `trajectory` cites each of its 2–3 steps' own draw, no more and no less.

One observation, not a defect: a compound-rule citation list can cite the **same `card_draw_id` twice** with different `contributing_theme` values when a single card supplies both poles of a rule (Case 5's `intuition_within_uncertainty`, entirely from The Moon). This is intentional under the current `Citation` shape — each citation documents one tag's contribution, not one draw's — but a future Explainability UI rendering "supported by" lists verbatim should dedupe by `card_draw_id` for display, or it will show the same card twice under one conclusion.

---

# 5. Deterministic Behavior Results

| Check | Result |
|---|---|
| Same Reading, `interpret()` called twice (Cases 1, 3, 6, 9, 10) | Identical (`generated_at` excluded) — **all 5 True** |
| Two independently-built Readings, identical draws (Case 4) | Identical `central_issue.value` — **True** |
| `reference_data_version` constant across all 10 cases | **True** (`54d6b018...`) |
| Theme-score ordering stable under repeated computation | **True** (matches existing `test_score_theme_strength_is_deterministic`) |

No non-deterministic behavior was observed in any case. This corroborates, rather than merely repeats, the existing automated determinism tests (`test_interpretation_engine.py`) — the difference here is these checks ran against hand-designed, larger, more thematically-dense readings than the existing test fixtures use, and all still held.

---

# 6. Central Issue / Supporting Themes / Compound Precedence — Specification Conformance

Checked explicitly per the user's question list:

- **Central issue behaves exactly as specified (T2):** always the single top-ranked `ThemeScore`; never appears duplicated in `supporting_themes` (checked in every case with a non-null `central_issue`).
- **Supporting themes behave exactly as specified (T3):** capped at 3 theme entries (never exceeded — Case 1/9's shorter card themes correctly produced fewer than 3 without padding), theme entries always precede compound entries, compound entries were never capped (all firing rules appeared — up to 1 remaining compound entry was observed in this matrix, consistent with only 2 rules existing total).
- **Compound precedence behaves correctly (C1/C2/C3):** in every case with 2 live matches (3, 6, 10), `clarity_vs_uncertainty` (registry position 0) won `primary_tension` and `intuition_within_uncertainty` (registry position 1) was correctly relegated to `supporting_themes`. No case produced the reverse ordering.
- **Trajectory ordering is correct (P2):** confirmed in Cases 6/8/10 against the Celtic Cross's specifically adversarial `position_order` layout.

No conformance gap was found against the approved rule specification anywhere in this matrix.

---

# 7. Deferred Structural Signals — Exclusion Confirmed

Per the explicit boundary for this task, the following were checked for leakage into the final model and **none were found**, across all 10 cases, including the two cases (3, 10) specifically engineered to make them maximally tempting to leak (repeated themes, a 3-card suit cluster, 7/10 Major Arcana):

- **R3 (same-suit clustering):** computed (confirmed via direct `relationships.py` call, Case 10), never appears in any `InterpretiveModel` field, string, or citation.
- **R4 (Major Arcana density):** computed (`major_arcana_count = 7` in Case 10), never influences `evidence_strength` (Case 10 scored `"strong"` from the same 4-signal formula as Case 6, which has only 5 Major Arcana — no density-dependent variation observed) and never appears as text anywhere.
- **Contradiction detection:** `contradictions = []` in all 10 cases, including the thematically richest ones — confirms `contradictions.py`'s always-empty behavior holds under real load, not just its trivial unit test.
- **Question-domain weighting:** not separately re-verified in this harness (all 10 cases used a `question_domain` of `None`, the harness default) — this specific no-op is already directly covered by existing unit tests (`test_question_relevance_is_a_no_op_regardless_of_domain`), so it was not considered a priority to re-derive here; noted as a scope boundary of this validation pass, not a finding.

---

# 8. Discovered Gaps

This section explicitly separates **implementation defects** (none found) from **intentional/deferred behavior** (several, all already documented, now empirically re-confirmed) and **observations worth recording for future steps** (new in this pass).

## 8.1 Defects against an approved rule

**None found.** Every approved rule (M1, M2, P1, P2, T1, T2, T3, C1, C2, C3, A1–A10) produced output matching its specification in `INTERPRETATION_RULES_DESIGN.md` in every case tested. No code change is warranted by this validation pass.

## 8.2 Intentional / deferred behavior (re-confirmed, not new)

- `primary_tension`, `trajectory`, `blocker`, `advice`, `clarification` are `null` whenever their triggering condition isn't met (Cases 1, 2, 4, 9) — this is the designed behavior (Product Spec Section 10.5/10.6/10.8/10.9's explicit "must be able to omit"), not an omission bug.
- `contradictions` is `[]` in every case — `INTERPRETATION_RULES_DESIGN.md` Section 9 already establishes why (no reviewed antonym/opposition data exists).
- `significator` is unreachable (always `None`) given the 3 seeded spreads — a data-coverage fact, not a code defect (Section 4/7.1 note, re-confirmed).
- R3/R4 computed-but-unexposed — confirmed exactly as Step 3 decided (Section 7 above).

## 8.3 New observations worth recording (not defects, no action taken)

1. **Compound-rule firing is independent of theme ranking** (Section 3's "Notable finding") — worth stating explicitly in any future Explainability copy, since a user could otherwise assume a named tension implies its poles are the reading's *strongest* themes, which is not what the current rule actually checks.
2. **A single card can satisfy both tags of a compound rule alone** (Case 5, The Moon) — the rule fires correctly, but this means "Intuition Within Uncertainty" can describe a single card's own internal thematic range, not necessarily a relationship *between* two different drawn cards. This matches the rule's literal trigger definition (`_intuition_within_uncertainty` checks tag presence across all draws, not distinctness of source draws) — flagged here only so a future reviewer deciding whether this is the intended reading of "compound" can do so with the evidence in hand, not as something this validation pass is empowered to change.
3. **Duplicate `card_draw_id` citations within one compound-sourced field** (Section 4) — cosmetic for a future UI, not a data-correctness issue; the underlying evidence is accurate, just presented at citation (not per-draw) granularity, exactly as Q6 in `INTERPRETATION_ENGINE_DESIGN.md` specified.
4. **No InterpretiveModel field corresponds to `structure.py`'s `situation` finding on its own** — it's consumed internally (feeds `has_situation_blocker_adjacency` for `evidence_strength`/`uncertainty`) but never surfaced as its own citable conclusion. This is not a gap against the Product Spec (Section 10's 11 fields don't include a standalone "Situation" field — `central_issue` is the closest analog, and is theme-derived, not role-derived), so no action is implied; recorded only because Step 3's Section 1.1 flagged `structure.py`'s unused outputs generally, and this is the specific remaining piece of that finding beyond R3/R4 and `significator`.

## 8.4 Does the structured output suffice for a future narrative/presentation layer?

Assessed against `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 12's suggested narrative section structure (Central Theme → Tension → What the Spread Shows → Trajectory → Uncertainty → Advice → Clarification → Reflection): **yes, for every field that stage currently populates.** Each maps 1:1 to an `InterpretiveModel` field already observed to carry both a value and complete citations in this validation pass. Two caveats for whoever builds that layer, both already implied by earlier design decisions rather than new requirements:
- It must render an always-possibly-empty `contradictions` list gracefully (Section 8.2) — not a defect, but a real, permanent-for-now constraint on that layer's prompt design.
- It must fetch a card's `base_meaning_upright`/`base_meaning_reversed` text separately via `card_draw_id` if it wants to quote prose — the model itself deliberately carries only structured `value`/`citations`, not quoted meaning text (Q6's "final-field-level citations only" decision, confirmed still true in every case's JSON).

---

# 9. Recommended Next Steps

1. **No engine changes are recommended from this validation pass.** The implementation matches its approved specification exactly across every case tested.
2. If R3/R4 are ever to be promoted (per `INTERPRETATION_RULES_DESIGN.md` Section 7.1's open questions), this validation's Case 10 output is a ready-made before/after fixture — same reading, same seed, so any future PR could diff its `InterpretiveModel` output against the one recorded here to see the exact effect of activating either rule.
3. Contradiction detection remains the most substantial deferred area with no implementation path yet (Section 8.2) — if this project wants that field to ever be non-empty, the next concrete step is authoring and reviewing an antonym/opposition table (as `INTERPRETATION_RULES_DESIGN.md` Section 9 already specifies), not an engine change.
4. Item 8.3.4 (no standalone `situation` output field) is worth a deliberate yes/no from whoever owns the Product Spec before any narrative-layer work begins, simply so it's a decision rather than a silent gap — no urgency implied.
5. This document's harness (10 hand-built cases) is not proposed as a permanent addition to `backend/tests/` — it was deliberately kept outside the repository per this task's "validation, not expansion" boundary. If any individual case here is judged valuable as a *regression* test (Case 8's adversarial trajectory ordering is the strongest candidate, though a similar case already exists as `test_trajectory_uses_semantic_role_order_not_position_order`), that would be a small, separate, explicitly-scoped follow-up — not implied or started by this document.

---

## Related Documents

- `INTERPRETATION_ENGINE_DESIGN.md` — Step 1's contract; Q2's reference-data version hash is reproduced identically across every case in this validation.
- `INTERPRETATION_RULES_DESIGN.md` — Step 3's rule specification; every rule ID referenced above (M1–M2, P1–P2, T1–T3, C1–C3, A1–A10, R1–R5) is defined there.
- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Section 10 (Interpretive Model fields) and Section 12 (Narrative Generation Architecture), referenced in Section 8.4 above.
- `app/services/interpretation/` — the implementation this document validates; unchanged by this document.
- `backend/tests/test_interpretation_engine.py`, `test_interpretation_pipeline_stages.py`, `test_compound_rules.py` — the existing automated test suite this validation pass corroborates against larger, hand-designed readings.
