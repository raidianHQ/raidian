# Raidian Wise — Theme Vocabulary Normalization

# Document Information

Version: 1.0
Status: Active
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Documents the Reference Data Enrichment & Normalization pass that consolidated the card theme-tag vocabulary, in response to `RAIDIAN_WISE_REFERENCE_DATA_AUDIT_V1.md` (Section 7.1: "theme vocabulary is more fragmented than intended"). Records exactly which tags were merged, why, and — just as importantly — which similar-looking tags were deliberately kept separate and why, so the reasoning is auditable rather than just the outcome.

Audience:
Contributors and AI development agents editing `backend/app/reference_data/theme_vocabulary.yaml` or any card's `primary_themes`/`secondary_themes`.

Authority:
This document governs the theme vocabulary. `backend/app/reference_data/theme_vocabulary.yaml` is the enforced source of truth (validated by `app/seed/loader.py`); this document is its rationale and audit trail.

---

# 1. What Changed

| | Before | After |
|---|---|---|
| Unique theme tags in use (`primary_themes` + `secondary_themes` combined) | 115 | 107 |
| Tags used by only one card | 60 of 115 | 51 of 107 |
| Enforcement | None — any string was accepted | Closed vocabulary — `app/seed/loader.py` rejects any tag not in `theme_vocabulary.yaml` |

Eight tags were merged into an existing tag. No new tags were invented, no card's traditional meaning was changed, and no card was given a theme it doesn't genuinely carry — see Section 3 for what was deliberately left alone and why.

**Revision note:** an initial ninth merge (`healing` → `recovery`) was proposed and briefly implemented, then reverted on review — `healing` and `recovery` were judged to be distinct enough concepts to keep separate after all. See Section 4 for the restored distinction and rationale. The counts in this document reflect the final, approved state (8 merges, `healing` retained).

---

# 2. Methodology

1. Every one of the 78 cards' actual `primary_themes` and `secondary_themes` was pulled directly from the implemented content (not redesigned from scratch).
2. Every tag used more than once, and every tag co-occurring with another tag *on the same card*, was treated as a candidate: same-card co-occurrence between two close-meaning tags (e.g. a card listing both `surrender` and `letting_go`) was the strongest signal for a genuine redundancy, since the card's own content was already treating them as interchangeable.
3. Each single-use tag was individually reviewed against the question: *does this represent a genuinely distinct concept from every existing tag, or is it a synonym of one that already exists?* Only merges answering "synonym" were made. This review is not fully reproduced here (it would be as long as the vocabulary itself), but Section 3 gives representative examples of pairs that were reviewed and kept separate, so the standard applied is visible.
4. Where a merge would have reduced a card's `primary_themes` from two tags to one (because the two merged into the same canonical tag), a second, accurate replacement tag was added from the *existing* vocabulary — never a newly invented one — so no card lost thematic richness as a side effect of cleanup (Section 4).

---

# 3. The Merge Mapping

| Old tag | Canonical tag | Card(s) affected | Rationale |
|---|---|---|---|
| `surrender` | `letting_go` | The Hanged Man | The card's own content already used both interchangeably ("surrender... letting go of control"); no meaningful distinction between them as tags. |
| `painful_ending` | `endings` | Ten of Swords | `painful_ending` is a qualified subtype of `endings`, not a distinct concept; the card's meaning text already carries the "painful" quality in prose. |
| `perseverance` | `inner_strength` | Nine of Wands | Both describe the same resilience-under-difficulty quality; co-occurred on the same card. |
| `moderation` | `balance` | Temperance | Near-exact synonyms; the card listed both simultaneously. |
| `disruption` | `upheaval` | The Tower | Near-exact synonyms; the card listed both simultaneously. |
| `connection` | `emotional_connection` | The Lovers | `connection` on The Lovers meant the same relational bond `emotional_connection` already names across the Cups suit — genuine synonym, and folding it in gives The Lovers meaningful overlap with an existing, well-used hub instead of standing alone. |
| `change` | `transition` | Wheel of Fortune | Both single-use-adjacent and co-occurring with `cycles` on the same card; `transition` (movement from one state to another) already covers what `change` was doing here, while `cycles` remains Wheel of Fortune's distinctive tag for its turning-wheel imagery. |
| `swift_action` | `momentum` | Knight of Swords | Both describe rapid movement; merging connects Knight of Swords to the existing cross-suit "quick movement" cluster (the Wands momentum cards) rather than leaving it isolated. |

`healing` → `recovery` was also proposed for The Star, on the reasoning that both name "restoration after difficulty" as a functional signal for a deterministic engine. On review this was rejected: see Section 4 for why the two are kept distinct.

## 3.1 Richness preserved after merging

Three cards would have dropped from two `primary_themes` to one as a side effect of deduplication (both of their original tags merged to the same canonical tag). Each was given a second, accurate tag already present in the vocabulary — not invented — so no card lost thematic richness:

| Card | Before | After |
|---|---|---|
| The Hanged Man | `surrender`, `letting_go` | `letting_go`, **`patience`** (the suspended waiting the card involves) |
| Ten of Swords | `painful_ending`, `endings` | `endings`, **`exhaustion`** (already used elsewhere for this card's rock-bottom quality; matches the card's own secondary theme neighbor) |
| Nine of Wands | `perseverance`, `inner_strength` | `inner_strength`, **`vigilance`** (the card's traditional "wariness/guardedness" quality; also now shared with Page of Swords, a sensible cross-suit "watchfulness" link) |

The other five merges did not reduce any card's tag count (the replacement tag wasn't already present on that card).

---

# 4. Deliberately Kept Separate

The point of this pass was consolidation *without* erasing real distinctions. These are representative examples of near-looking pairs that were reviewed and kept as separate canonical tags, to make the standard visible rather than just its results:

- **`healing` vs. `recovery`** — reviewed twice: initially merged, then restored on reconsideration. The two name genuinely different processes: `healing` is restoration, renewal, emotional/spiritual repair (The Star's quiet, hopeful mending); `recovery` is regaining strength or functioning after difficulty (the Swords suit's harder-won return to capacity, and Ten of Swords' rock-bottom-then-rebuilding arc). A spread returning `healing` and one returning `recovery` are pointing at different things, even though both sit in the same emotional neighborhood — collapsing them would have cost the Interpretation Engine exactly the kind of distinction it needs. The Star keeps `healing`.
- **`fear` vs. `anxiety`** — both appear on Nine of Swords (in different slots) and Moon uses `fear` alone. Collapsing them would create a same-card primary/secondary duplicate. More importantly, they're functionally different signals: `fear` is apprehension about a threat (Moon's broader unknown); `anxiety` is a state of unfocused worry/rumination (Nine of Swords' specific quality). Kept separate.
- **`grief` vs. `loss`** — related but distinct: `loss` names the circumstance (something taken away); `grief` names the emotional response to it. A reading may surface one without the other.
- **`contentment` vs. `fulfillment` vs. `joy`** — three different emotional registers (satisfied ease; a sense of purpose realized; active delight) used deliberately across different Cups cards. Merging any pair would blur textures that matter for a reading about feeling states.
- **`willpower` (The Magician) vs. `determination` (Chariot, the Wands suit)** — both are "strength of resolve," but `willpower` carries Magician's specific creative-manifestation flavor while `determination` carries Chariot's forward-pushing-through-obstacles flavor. Merging would fold Magician's distinct identity into a cluster it doesn't archetypally belong to.
- **`abundance` (The Empress) vs. `material_security` (the Pentacles suit)** — different registers: `abundance` is generative/creative plenty; `material_security` is personal resource stability. The Empress isn't a Pentacles card and merging would misrepresent her meaning as financial rather than generative.
- **`discipline` vs. `diligence`** — self-control/order (Emperor) vs. sustained careful effort (Pentacles court/numbered cards). Different contexts, different interpretive use.
- **`honest_communication` / `communication` / `diplomacy`** — three distinct communication *styles* (direct truthfulness; general message-exchange; tactful mediation) that a reading about communication issues would want to distinguish, not collapse into one.

---

# 5. Enforcement

`backend/app/reference_data/theme_vocabulary.yaml` is the closed vocabulary (107 tags). `app/seed/loader.py`'s `load_theme_vocabulary()` loads it, and `validate_card_definitions()` rejects any card whose `primary_themes`/`secondary_themes` contains a tag not in this file — this runs automatically as part of the existing seed and test pipeline, so a future content edit introducing a typo or a near-duplicate tag fails validation rather than silently re-fragmenting the vocabulary.

Adding a genuinely new tag later remains possible (edit `theme_vocabulary.yaml`), but should follow the same standard applied here: check it isn't a synonym of an existing tag first (Section 4 shows what that review looks like).

---

## Related Documents

- `RAIDIAN_WISE_REFERENCE_DATA_AUDIT_V1.md` — the audit finding (Section 7.1) this pass addresses.
- `RAIDIAN_WISE_REFERENCE_DATA_V1.md` — Section 4.1, updated to point here.
- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Section 11 (Compound-Theme Architecture), the future consumer of this vocabulary.
