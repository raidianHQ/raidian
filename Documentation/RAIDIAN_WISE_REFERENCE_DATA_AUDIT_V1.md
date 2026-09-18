# Raidian Wise — Reference Data Audit

# Document Information

Version: 1.0
Status: Informational — Read-Only Audit
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
A read-only audit of the completed 78-card Rider-Waite-Smith reference dataset (card meanings, correspondence data, and spreads) prior to beginning the Interpretation Engine. **No files, code, database data, or documentation were modified in producing this report** — every finding below was independently re-derived from the current state of the repository and a fresh, read-only re-extraction of the source spreadsheet.

Audience:
Project owner and contributors evaluating whether the reference dataset is ready to build the Interpretation Engine against.

Authority:
This is an audit report, not a governance document — it records findings, not decisions. Any corrective action it recommends requires a separate, explicit change.

## Methodology

- Card meanings and correspondence data were loaded through the actual application code path (`app.seed.loader.load_card_definitions()` / `load_correspondence_definitions()`), not re-parsed independently — this audits exactly what the seed process would load.
- The source spreadsheet (`Documentation/Source_Data/RaidianWiseDeckTemplate_Jenn.xlsm`, **`Card Key` worksheet only** — `Katchina Knife Layout` was not opened) was re-extracted fresh, read-only, and confirmed **byte-identical** to the extraction used when the correspondence data was originally implemented, confirming the source file has not changed since.
- All 78 correspondence entries were diffed field-by-field against this fresh source extract.
- All 156 card meaning texts (78 upright + 78 reversed) and all 78 astrology notes were scanned for predictive/certainty language patterns.
- Theme-tag and keyword vocabularies were analyzed for frequency, duplication, and overlap.

---

# 1. Card Completeness

All **78/78 cards** present. Zero missing or empty required fields across the entire dataset (name, arcana, rank, image_ref, base_meaning_upright, base_meaning_reversed, keywords, primary_themes, secondary_themes; `suit` is correctly null for all 22 Major Arcana and populated for all 56 Minor Arcana).

| Field | Coverage | Notes |
|---|---|---|
| Name | 78/78 | Unique, canonical RWS names |
| Arcana | 78/78 | 22 major / 56 minor |
| Suit | 56/78 | Correctly null for all majors, present for all minors |
| Rank | 78/78 | "0"–"21" for majors; ace/two…king for minors |
| Upright meaning | 78/78 | — |
| Reversed meaning | 78/78 | — |
| Keywords | 78/78 | 4–6 per card (none below the 4-keyword minimum) |
| Primary themes | 78/78 | 1–3 per card |
| Secondary themes | 78/78 | 1–2 per card |

**Thin theme coverage worth noting** (not a completeness *failure* — every card has at least one tag in each list — but relevant to Section 7):
- **14 cards have only one primary theme**: Four of Cups, Six of Cups, Five of Pentacles, Six of Pentacles, Seven of Pentacles, Nine of Pentacles, Three of Swords, Five of Swords, Six of Swords, Eight of Swords, Nine of Swords, Five of Wands, Eight of Wands, Ten of Wands.
- **74 of 78 cards have only one secondary theme** (4 cards have two); this is the norm for this dataset, not an anomaly on those 4.
- No card's `primary_themes` and `secondary_themes` overlap with themselves (0 redundant tags found).

---

# 2. Correspondence Completeness

| Field | Populated | Null | Notes |
|---|---|---|---|
| Element | 78/78 | 0 | — |
| Zodiac sign(s) | 78/78 | 0 | — |
| Zodiac symbol(s) | 78/78 | 0 | — |
| Astrological influence | 78/78 | 0 | — |
| Astrology note | 78/78 | 0 | See Section 7 for a quality (not completeness) caveat |
| Elemental gender | 6/78 | 72 | Null for all Minor Arcana and 16 of 22 Major Arcana — **mirrors the source spreadsheet's own coverage**, not a Raidian Wise gap |
| Direction | 78/78 | 0 | — |
| Color | 78/78 | 0 | — |
| Animal | 21/78 | 57 | Populated for Major Arcana only, minus The Hermit (source itself has `-` for Hermit); null for all 56 Minor Arcana — mirrors source |
| Stone | 39/78 | 39 | Populated for all majors + all Wands + Ace/Two/Three of Cups; null elsewhere — mirrors source |
| Source reference | 78/78 | 0 | — |
| Tradition label | 56/78 | 22 | Populated (`"Golden Dawn decanic attribution"`) for all Minor Arcana; `null` for all Major Arcana by design (Section 5, `RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md`) |

The three partial fields (Elemental Gender, Animal, Stone) are **source-inherited gaps**, not something lost in implementation — the source spreadsheet itself only populated them for a subset of cards, and that subset is preserved exactly (verified in Section 3).

---

# 3. Source Fidelity

Every correspondence-comparable field (element, zodiac_signs, astrological_influence, elemental_gender, direction, color, animal, stone) was diffed against the fresh `Card Key` extract for all 78 cards — **624 field comparisons**.

**Result: 2 diffs, both the documented, approved corrections. Zero undocumented deviations.**

| Card | Field | Source value | Implemented value |
|---|---|---|---|
| Strength | zodiac_signs | `libra` | `leo` |
| Judgement | zodiac_signs | `libra` | `scorpio` |

Every other field, for every other card, matches the source exactly once normalized (lowercased; `"Pices"`→`"pisces"`, `"Sagitarius"`→`"sagittarius"` spelling fixed; multi-value fields split consistently). No value was silently altered, dropped, or invented beyond the two corrections below.

---

# 4. Corrections

Exactly two corrections were made, both approved in `RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md` before implementation:

1. **Strength**: source had `Zodiac Sign: Libra` alongside `Astrological Influence: Sun` — self-contradictory, since Sun rules Leo, not Libra, and the source's own `Astrology` text for this row explicitly says *"Strength tarot card is astrologically influenced by Leo... Sun is the ruling planet of Leo."* Corrected to **Leo**.
2. **Judgement**: source had `Zodiac Sign: Libra` alongside `Astrological Influence: Pluto` — Pluto's traditionally associated sign is Scorpio, not Libra; the row directly above (Justice) also reads `Libra`, consistent with a copy-down error. Corrected to **Scorpio**.

The audit found **no other corrections, silent or otherwise** — every other value-level difference the diff might have caught was zero (Section 3).

---

# 5. Ambiguities

These were not corrected (only Strength and Judgement were approved for correction) — they are documented here so the Interpretation Engine phase inherits them knowingly rather than discovering them later.

**The Major Arcana's `Zodiac Sign` field does not follow one consistent logic across all 22 rows.** Checking each row's stated sign against its stated planet's traditional rulership:

- Most rows are internally consistent (e.g. Emperor: Aries/Mars — Mars rules Aries; Devil: Capricorn/Saturn — Saturn rules Capricorn).
- A few are not, but are **not self-contradictory** the way Strength/Judgement were — they simply don't follow a sign-is-ruled-by-planet pattern:
  - **The Magician** (Aries/Mercury) — Mercury doesn't rule Aries (Mars does). Mercury *is* the Magician's correct Golden Dawn planetary attribution; Aries appears to be an added sign following different logic.
  - **The High Priestess** (Virgo/Moon) — Moon doesn't rule Virgo (Mercury does). Same pattern as above.
  - **The World** (Taurus/Saturn) — Saturn doesn't rule Taurus (Venus does; Saturn rules Capricorn/Aquarius). Unlike Magician/High Priestess, this one has no clear alternate explanation from the data alone.
  - **Wheel of Fortune** (Taurus, Scorpio, Leo, Aquarius / Jupiter) — a different, legitimate logic: these are the four fixed/"kerubic" signs traditionally pictured on the card's four corner figures, not signs ruled by Jupiter.

This means the Major Arcana correspondence data should **not** be treated as "sign is always this planet's own sign" by any future rule in the Interpretation Engine — it's a mix of ruled-sign pairs and other pairings the source doesn't explain.

**Other source ambiguities, preserved verbatim:**
- **Page of Cups**: `Astrological Influence: "female Earth of Water, Male Air of Water"` — unusual phrasing (a Golden Dawn elemental sub-attribution concept for court cards, awkwardly worded in the source). Preserved as-is; the generated `astrology_note` reproduces it verbatim too.
- **Court cards generally** (King/Queen/Knight/Page across all suits): `Astrological Influence` is given as a terse sign-pair or phrase (e.g. King of Wands: `"Sagittarius, Scorpio"`; Queen of Swords: `"Virgo/Libra"`) rather than the fuller "Planet in Sign" phrasing used for numbered 2–10 cards. This is a formatting inconsistency inherent to the source, not an implementation artifact.
- **Major Arcana `Suit` column** in the source spreadsheet duplicates the card name (e.g. `Suit: "Fool"` for The Fool) rather than a real suit — confirmed unusable and not referenced anywhere in the implementation; `Card.suit` is correctly `null` for all 22 majors regardless.

---

# 6. Authored vs. Derived Content

| Content | Origin |
|---|---|
| Card name, arcana, suit/rank structure | Standard RWS deck structure (public domain); not from the spreadsheet |
| `base_meaning_upright`, `base_meaning_reversed`, `keywords`, `primary_themes`, `secondary_themes` | **100% Raidian Wise original wording**, informed by traditional RWS symbolism and A. E. Waite's *Pictorial Key to the Tarot* as a historical reference — **not derived from the Card Key spreadsheet at all** |
| `image_ref` | Raidian Wise's own placeholder path convention; not from the spreadsheet |
| `element`, `zodiac_signs`, `zodiac_symbols`, `astrological_influence`, `elemental_gender`, `direction`, `color`, `animal`, `stone` | **Directly extracted from the `Card Key` worksheet**, normalized for spelling/casing only (Section 8), with the two corrections in Section 4 |
| `source_reference`, `tradition_name` | Authored metadata *describing* the spreadsheet source; not itself sourced from a spreadsheet cell |
| `astrology_note` | **100% Raidian Wise original text**, synthesized from the structured correspondence fields already extracted — deliberately **not** the spreadsheet's own `Astrology` column, whose narrative paragraphs were judged unsafe to copy (see `RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md`, Section 3) |

This separation is structural, not just documented: card meanings live on `Card`, correspondence data lives on the related `CardCorrespondence` table (`RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md`, Section 4.2).

---

# 7. Interpretation Readiness

Findings specifically relevant to building the deterministic Interpretation Engine next.

## 7.1 Theme vocabulary is more fragmented than intended

Across 78 cards there are **105 unique `primary_themes` tags**, of which **69 are used by only one card**. Secondary themes fare somewhat better (48 unique tags, 27 used once). `RAIDIAN_WISE_REFERENCE_DATA_V1.md` (Section 4.1) states themes were "deliberately reused" so the future compound-theme matching (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, Section 11) has overlap to detect — in practice, reuse is real but thinner than that description implies: most-reused tags top out around `new_beginnings` (7 cards), `authority` (5), `emotional_connection`/`determination`/`momentum` (4 each). **Recommendation: a deliberate vocabulary-consolidation pass (merging near-synonyms, e.g. checking whether some of the 69 single-use tags should collapse into an existing reused tag) before building the theme-scoring stage of the Interpretation Engine**, or compound-theme matching will have less to work with than the design intended.

## 7.2 Twenty astrology notes are formulaic and add little beyond the raw field

All 4 Aces and all 16 court cards (20 of 78) have a note of the form *"In the Golden Dawn tradition, this card is associated with **[astrological_influence verbatim]**."* — versus the 58 numbered 2–10 cards, whose notes additionally name the card's traditional Golden Dawn title (e.g. *"...traditionally called the Lord of Established Strength"*). This is an honest limitation of the generation approach (Section 6): for cards without a numbered-card GD title, there was no additional traditional fact to synthesize from safely. If `astrology_note` is meant to be surfaced as meaningful Explainability content, these 20 are weaker than the other 58 and may need enrichment.

## 7.3 Major Arcana correspondence logic is inconsistent (Section 5)

If the Interpretation Engine (or a future compound-theme rule) ever reasons from "this sign's ruling planet," it will get inconsistent results across Major Arcana rows — some rows are ruled-sign pairs, some aren't, and the data doesn't self-describe which is which per row. Any rule built on this should be scoped to Minor Arcana (where the Golden Dawn decan logic is consistent) or treat Major Arcana correspondence as descriptive flavor rather than a dependable structural fact.

## 7.4 Predictive/certainty language: clean

**Zero hits** across all 156 meaning texts and all 78 astrology notes for banned patterns (`will happen`, `you will`, `guarantee`, `destined`, `certain to`, `prophecy`, `the universe has decided`, `your guides`, `is going to`, `shall`, etc.). This is a genuinely clean result, not a partial one.

## 7.5 No duplicate/conflicting themes within a single card

Checked every card's own `primary_themes` against its own `secondary_themes` for overlap — zero found. No card contradicts itself by tagging the same theme as both primary and secondary.

## 7.6 No single theme dominates

The most-used primary tag (`new_beginnings`) appears on 7 of 78 cards (9%) — not broad enough to be a concern for over-triggering compound-theme rules.

## 7.7 Missing correspondence values must be treated as "no data," not errors

Given Section 2's coverage gaps (elemental_gender, animal, stone), any Interpretation Engine logic that reads these fields must handle `null` as the normal case for most cards, not a data-quality problem to flag.

## 7.8 Two cosmetic artifacts, preserved verbatim, carry no interpretive risk but could look like bugs if displayed raw

- **The High Priestess** — `animal: "Camel, Dog,  and Stork"` (double space before "and"), preserved exactly as sourced.
- **Ace of Cups** — `astrological_influence: "Cancer, Scorpio, Pisces and Spirit of Water."` (trailing period, unlike every other card's value), preserved exactly as sourced.

Neither affects the `astrology_note` text (which strips trailing punctuation when building its own sentence) or any validated/tested behavior — flagged only because both would read oddly if shown verbatim in a future UI.

---

# 8. Spelling and Terminology

**In the source spreadsheet** (normalized during implementation, not left as-is):
- **4 rows** had `Element` casing inconsistencies (`"FIre"` or lowercase `"water"` instead of `"Fire"`/`"Water"`): High Priestess, Chariot, Temperance, Moon.
- **31 rows** had `Zodiac Sign` spelling errors (`"Pices"` for Pisces, `"Sagitarius"` for Sagittarius) — normalized throughout.

**In the implemented dataset**, checked independently of the source:
- Theme tags (`primary_themes`/`secondary_themes`): **0 casing issues** — consistently lowercase `snake_case` across all 78 cards.
- `element`, `direction`, `color`: exactly 4 canonical values each (`fire/water/air/earth`, `north/south/east/west`, `red/black/yellow/white`) — no stray variants remain.
- The two cosmetic artifacts in Section 7.8 are the only remaining formatting irregularities found, both inherited verbatim from source values that weren't part of the approved correction scope.

---

## Summary

The dataset is complete (78/78 cards, all required fields populated), faithful to its source (624/624 comparable fields match exactly except the two approved corrections), and clean on the safety dimension that matters most before building the Interpretation Engine (zero predictive-language hits). The two things worth addressing before or during Interpretation Engine work are the theme-vocabulary fragmentation (7.1) and the twenty thin astrology notes (7.2) — both are content-quality refinements, not data-integrity problems.

## Related Documents

- `RAIDIAN_WISE_REFERENCE_DATA_V1.md` — the reference-data architecture and card-meaning sourcing this audit verifies.
- `RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md` — the approved schema and the two corrections this audit re-confirms.
- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Section 9 (Interpretation Architecture) and Section 11 (Compound-Theme Architecture), which Section 7 of this audit evaluates readiness against.
