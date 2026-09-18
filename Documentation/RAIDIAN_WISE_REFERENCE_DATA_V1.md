# Raidian Wise — Reference Data / Content Foundation

# Document Information

Version: 1.2
Status: Active
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Explains where Raidian Wise's tarot reference content (card meanings, keywords, themes, spread definitions, and astrological/elemental correspondence data) comes from, how it was written, how it is licensed/sourced, and how it is maintained going forward.

Audience:
Contributors and AI development agents editing or reviewing `backend/app/reference_data/`.

Authority:
This document governs the reference-data content and the seed process that loads it. It extends `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` (Sections 7.4 Card, 15.3 theme taxonomy) and must remain consistent with `docs/PRINCIPLES.md` and `docs/PROJECT_VISION.md`.

---

# 1. Source Methodology

Raidian Wise's card content is **original wording**, written specifically for this project — it is not copied or paraphrased from any single modern source. It is grounded in the traditional symbolism of the Rider-Waite-Smith deck, which has been documented and taught consistently across the tarot tradition for over a century (card names, suit/arcana structure, and the core thematic associations of each card — e.g. the Sun's association with vitality and joy, the Tower's association with sudden upheaval — are part of this shared, traditional vocabulary, not any one author's proprietary content).

**A. E. Waite's *The Pictorial Key to the Tarot* (1910)** was used as an important historical reference point for checking each card's meaning against the deck's original intent, since Waite co-created the deck and wrote the first published guide to it. The original 1910 text is in the public domain in the United States. Raidian Wise does not reproduce Waite's text; his work was used as a historical anchor, not a source to paraphrase.

**No modern websites, apps, or copyrighted guidebooks were used or paraphrased.** Modern tarot-meaning content (blogs, apps, contemporary guidebooks) is typically under active copyright, and its specific interpretive phrasing is that author's own creative work — using or lightly rewording it would raise real licensing concerns even where the underlying traditional symbolism is shared. Where Raidian Wise's meanings resemble other modern sources, that similarity should reflect the shared tarot tradition, not derivation from that source.

---

# 2. Authorship of Raidian Wise Interpretations

Every card's `base_meaning_upright`, `base_meaning_reversed`, `keywords`, `primary_themes`, and `secondary_themes` in `backend/app/reference_data/rider_waite_smith/*.yaml` were written for Raidian Wise, in Raidian Wise's own voice, by an AI development agent (Claude) acting under this project's governance documents, and reviewed for adoption by the project owner as part of this phase.

This content is **not** a verbatim or lightly-edited restatement of any single external source. It is original synthesis of traditional, public-domain-documented tarot symbolism, written to satisfy this project's specific content principles (Section 4 below) and to give the future deterministic Interpretation Engine (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, Section 9) structured, non-generic material to work with.

---

# 3. Historical Reference Sources

- **A. E. Waite, *The Pictorial Key to the Tarot* (1910)** — public domain in the US. Used as a historical cross-check for each card's traditional meaning and symbolism.
- **The Rider-Waite-Smith deck itself (1909)** — the card names, arcana/suit/rank structure, and traditional elemental suit associations (Wands/fire, Cups/water, Swords/air, Pentacles/earth) are part of the shared tarot tradition this deck established and are treated as structural, factual reference data rather than any single author's creative content.

No other named source (book, website, app, or individual author's published interpretations) was consulted or drawn from in writing the meaning text. If a future contributor adds or revises content using a different reference, that source should be added to this list.

---

# 4. Content Principles Applied

Every card's upright and reversed meaning was written to:

- Describe the card as contributing a **possible** theme or perspective, never a certainty. Preferred constructions: "may suggest," "can represent," "may point toward," "can invite reflection on," "may indicate a tension involving..."
- Avoid predictive or deterministic language: no "this will happen," "you will...," "you are destined to...," "the card guarantees...," and no claim that a card conveys divine revelation or God's will (per `RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, Section 14, Disclaimer and Guardrails).
- Stay religiously neutral. Card content is **not** written in explicitly Christian terms, even for cards with historically Christian-adjacent imagery (e.g. The Hierophant, Judgement) — those are described in general, archetypal terms (institutional/traditional wisdom, reckoning/awakening) rather than theological ones. Scripture is a separate, later interpretation layer (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, Section 15) and must never be folded into card meanings themselves.
- Provide **structured, specific content**, not generic one-word labels — each card has multiple keyword phrases (not single generic words) plus separate `primary_themes` and `secondary_themes` tag lists, so the future Interpretation Engine has enough material for theme-strength scoring, card relationships, and compound-theme matching (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, Section 9).

## 4.1 Shared theme vocabulary

`primary_themes` and `secondary_themes` are drawn from a deliberately reused, shared vocabulary (e.g. `new_beginnings`, `letting_go`, `uncertainty`, `transition`, `structure`, `conflict`, `clarity`, `patience`) rather than inventing a unique tag per card. This is intentional: the Interpretation Engine's future compound-theme matching (Section 11 of the product spec) depends on multiple cards in a spread sharing recognizable theme tags. Tags are lowercase `snake_case`, matching the Scripture theme taxonomy's naming style (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, Section 15.3) so the two systems can eventually share vocabulary where themes overlap (e.g. `patience`, `uncertainty`).

**This vocabulary is a closed, enforced list**, not just a convention: `backend/app/reference_data/theme_vocabulary.yaml` is the canonical set (107 tags), and `app/seed/loader.py` rejects any card whose theme tags fall outside it. It started as an open convention (v1.0 of this document) and was consolidated and closed off in the Reference Data Enrichment & Normalization pass — see `RAIDIAN_WISE_THEME_VOCABULARY_V1.md` for the full merge mapping (which near-duplicate tags were folded together, and which similar-looking tags were deliberately kept distinct) and `RAIDIAN_WISE_REFERENCE_DATA_AUDIT_V1.md` (Section 7.1) for the audit finding that prompted it.

---

# 5. Image-Source Policy

No image assets have been added yet — only placeholder `image_ref` path strings (Section 6). This section documents the policy for when actual images are added in a future phase:

- The original 1909 Rider-Waite-Smith artwork by Pamela Colman Smith is in the public domain in the United States (published before 1923).
- Specific **scans, reprints, or colorizations** produced by a commercial publisher (e.g. current printed decks) may carry their own separate copyright on that particular reproduction, even though the underlying 1909 artwork is public domain. Actual image assets must come from a verified public-domain source (e.g. a public-domain scan such as those hosted by Wikimedia Commons or a similarly documented public-domain archive), not photographed or scanned from a copyrighted modern printed edition.
- This verification should happen explicitly when image assets are actually added — it is out of scope for this phase, which only establishes the reference path convention.

---

# 6. `image_ref` Placeholder Convention

Paths follow a predictable, human-readable pattern so a future asset-loading phase can populate them mechanically:

```
rws/major/{rank}-{slug}.png          e.g. rws/major/00-the-fool.png
rws/{suit}/{rank}-of-{suit}.png      e.g. rws/wands/ace-of-wands.png
```

Major Arcana `rank` is zero-padded to two digits (`00`–`21`); Minor Arcana `rank` is the spelled-out rank (`ace`, `two`, ... `king`). No files exist at these paths yet — see Section 5.

---

# 7. Seed Data Architecture

## 7.1 Layout

```
backend/app/reference_data/
  rider_waite_smith/
    deck.yaml          # Deck metadata (name, description, is_default)
    major_arcana.yaml  # 22 Major Arcana card definitions
    wands.yaml         # 14 Wands card definitions
    cups.yaml          # 14 Cups card definitions
    swords.yaml        # 14 Swords card definitions
    pentacles.yaml     # 14 Pentacles card definitions
  spreads/
    single_card.yaml
    three_card.yaml
    celtic_cross.yaml

backend/app/seed/
  loader.py    # Parses + validates the YAML content -- no database access
  seed.py      # Upserts validated content into the database; CLI entrypoint
```

YAML was chosen over JSON or inline Python so the content stays genuinely human-reviewable: real paragraph text without escaped newlines, and comments where useful. It is split by suit/arcana (six small files) rather than one 78-entry file, so a content review or diff stays focused.

## 7.2 Loading (`app/seed/loader.py`)

Pure parsing and validation -- no database import, no side effects. `validate_card_definitions()` and `validate_spread_definition()` check structural correctness (counts, uniqueness, required fields, semantic-role validity, contiguous position ordering) and raise `ReferenceDataError` listing **every** problem found at once, not just the first. This module is fully testable without a database (see `backend/tests/test_reference_data_loader.py`).

## 7.3 Seeding (`app/seed/seed.py`)

Upserts by natural key:

| Entity | Natural key |
|---|---|
| Deck | `name` |
| Card | `(deck_id, name)` |
| Spread | `name` |
| SpreadPosition | `(spread_id, position_order)` |

For each entity, the seed looks up an existing row by its natural key; if found, it updates that row's fields in place; if not, it inserts a new row. This makes the process:

- **Deterministic** — the same YAML always produces the same rows.
- **Repeatable / idempotent** — running it again (e.g. after a content correction) updates existing rows rather than erroring or duplicating them (verified by `test_seed_process_is_repeatable` and `test_reseeding_updates_content_in_place`).
- **Safe against a fresh database** — first run simply inserts everything.

It is deliberately **not** an Alembic migration. Alembic owns schema (Phase 1); this seed owns content, which is expected to be corrected and iterated on far more often than the schema changes. Content fixes are a YAML edit plus a seed re-run, not a new migration file.

## 7.4 Running the seed

From `backend/`, with the virtualenv active:

```
python -m app.seed.seed
```

This connects using the same `RAIDIAN_DATABASE_URL` / `.env` configuration as the rest of the app (`app.core.config`), applies the deck + all 78 cards, then all 3 spreads, and commits.

## 7.5 Maintaining this content

To correct or expand content:

1. Edit the relevant YAML file under `backend/app/reference_data/`.
2. Run the loader validation (imported directly, or via the test suite: `pytest tests/test_reference_data_loader.py`) to catch structural mistakes before touching a database.
3. Re-run `python -m app.seed.seed` against the target database. Existing rows are updated in place.

Adding a new deck in a future phase means adding a new subdirectory under `reference_data/` (its own `deck.yaml` plus card files) and a corresponding `seed_deck()` call — the loader and seed functions already take a `deck_dir` parameter for this reason, so no change to the Rider-Waite-Smith content is required.

---

# 8. Correspondence Data

A second, deliberately separate layer of content: each card's astrological and elemental correspondence data (Element, Zodiac Sign, Zodiac Symbol, Astrological Influence, Elemental Gender, Direction, Color, Animal, Stone, plus a brief astrology note). Full findings, data-quality issues, and the schema-change proposal are recorded in `Documentation/RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md`; this section summarizes what was implemented.

## 8.1 Why this is a separate layer

Correspondence data is a **distinct tradition from Raidian Wise's own RWS card meanings** (Section 1–4 above). Card meanings are original wording written for this project; correspondence data is sourced from an external, project-provided spreadsheet compiling astrological attributions. Keeping them separate — a related `CardCorrespondence` table rather than columns on `Card` — preserves that distinction structurally, not just by convention.

## 8.2 Source

`Documentation/Source_Data/RaidianWiseDeckTemplate_Jenn.xlsm`, **`Card Key` worksheet only** (the workbook's other worksheet, `Katchina Knife Layout`, is an unrelated personal reading and was not used). The original file was read-only inspected and has not been modified.

## 8.3 Sourcing / tradition attribution

- **Minor Arcana (56 cards)**: the decan attributions (e.g. "Mars in Aries") and the source's own references to Golden Dawn card titles (e.g. "Lord of Established Strength") confirm these follow the documented **Golden Dawn decanic attribution system**. Recorded as `tradition_name: "Golden Dawn decanic attribution"`.
- **Major Arcana (22 cards)**: attributions are a mix that doesn't consistently match Golden Dawn or another single identifiable historical system. Recorded as `tradition_name: null` rather than guessed — `source_reference` (the spreadsheet) is still always recorded.

## 8.4 Corrections applied

Two Major Arcana rows had a `Zodiac Sign` that contradicted their own `Astrological Influence` (and, for Strength, the source's own descriptive text):

- **Strength**: source had `Zodiac Sign: Libra` alongside `Astrological Influence: Sun` (Sun rules Leo, not Libra). Corrected to **Leo**.
- **Judgement**: source had `Zodiac Sign: Libra` alongside `Astrological Influence: Pluto` (traditionally associated with Scorpio); likely a copy-down error from the Justice row directly above. Corrected to **Scorpio**.

All other values (including spelling/casing normalization — e.g. "Pices" → "pisces", "FIre"/"water" → "fire"/"water") were preserved as sourced, only reformatted for consistency (lowercase, corrected spelling), never changed in substance.

## 8.5 The `astrology_note` field

The source spreadsheet's `Astrology` column holds full narrative paragraphs per card (not just a short label like its other correspondence fields), written in a voice that suggests derivation from third-party tarot websites (the sheet's `Image Path` column points to `tarotcardmeanings.net`). Per the same content-sourcing principle as Section 1, this prose was **not** copied. Instead, `astrology_note` holds a brief original note synthesizing the correspondence already captured in the structured fields (e.g. *"This card is associated with Leo and the Sun, echoing Strength's connection to warmth, confidence, and steady inner resolve."*) — for Minor Arcana, generated from the card's actual `astrological_influence` value plus its Golden Dawn title where one exists, not freely invented.

**Revised in the Reference Data Enrichment & Normalization pass**: the 20 cards without a numbered-card Golden Dawn title (the 4 Aces and all 16 court cards) originally had a thinner, formulaic note that just restated the raw `astrological_influence` value (flagged in `RAIDIAN_WISE_REFERENCE_DATA_AUDIT_V1.md`, Section 7.2). All 20 were rewritten to explain the relevant qualities of the stated astrological influence (using well-established, generic sign/planet/element associations — not invented history) and connect them to how that influence may color the card's expression, e.g. *"This influence combines Fire's urgency and drive with Air's clarity and speed of thought... Within this card, that combination may be expressed as swift, decisive action..."* (Knight of Swords). Still reflective, non-predictive language throughout; still no attribution beyond what the source data supports.

## 8.6 Schema

See `RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md` Section 4.2 for the full model. Summary: `CardCorrespondence` (`backend/app/models/card_correspondence.py`), one-to-one with `Card` (unique `card_id`, `ON DELETE CASCADE`), migration `f5f0af118106_add_card_correspondences_table.py`.

## 8.7 Content file and loading

`backend/app/reference_data/rider_waite_smith/correspondences.yaml` — one entry per card, keyed by card name, following the same YAML-source → `app/seed/loader.py` (parse + validate) → `app/seed/seed.py` (idempotent upsert by `card_id`) pipeline as card meanings and spreads. `seed_card_correspondences()` requires the deck's cards to already be seeded in the same session (it looks cards up by name to attach each correspondence row).

---

## Related Documents

- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Card, Spread, and theme-taxonomy requirements this content satisfies.
- `RAIDIAN_WISE_ARCHITECTURE_V1.md` — technical architecture this seed process fits within.
- `RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md` — full findings, data-quality analysis, and schema proposal behind Section 8.
- `RAIDIAN_WISE_REFERENCE_DATA_AUDIT_V1.md` — the read-only audit that identified the two issues Section 4.1 and Section 8.5 above address.
- `RAIDIAN_WISE_THEME_VOCABULARY_V1.md` — the full theme-tag consolidation mapping and rationale behind Section 4.1.
- `docs/PRINCIPLES.md`, `docs/PROJECT_VISION.md` — governing philosophy (reflection over prediction, humility over certainty) this content's language follows.
