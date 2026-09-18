# Raidian Wise — Correspondence Data: Findings & Proposed Schema Change

# Document Information

Version: 1.0
Status: Approved and Implemented
Owner: RaidianHQ
Last Updated: September 2026

**Decisions (approved):**
1. `Astrology` field — write brief original notes (not verbatim source prose). Implemented in `correspondences.yaml`'s `astrology_note` field.
2. Strength / Judgement `Zodiac Sign` errors — corrected to Leo and Scorpio respectively, documented in `RAIDIAN_WISE_REFERENCE_DATA_V1.md` Section 8.4.
3. Schema — `CardCorrespondence` model approved as proposed (Section 4.2). Implemented in `backend/app/models/card_correspondence.py`; migration `f5f0af118106_add_card_correspondences_table.py`.
4. Tradition labeling — `tradition_name: null` for Major Arcana rows where not confidently identifiable. Implemented as proposed.

Purpose:
Documents what was found in `Documentation/Source_Data/RaidianWiseDeckTemplate_Jenn.xlsm` (the project's required source spreadsheet) and proposes a schema change to represent its correspondence data, per the instruction to document any schema change before implementing it. No migration, model, or content has been written yet.

---

# 1. What Was Inspected

The workbook has two worksheets. Per your clarification, only **`Card Key`** is in scope for Raidian Wise; `Katchina Knife Layout` (a personal reading, unrelated to this project) was **not** read for content and nothing from it has been extracted, seeded, or incorporated. The original `.xlsm` file was opened read-only and has not been modified.

`Card Key` has 78 data rows (one per RWS card, matching our existing deck exactly) and 28 columns. Ten of those map directly to the correspondence fields you named:

| Your field | Sheet column | Populated |
|---|---|---|
| Element | `Element` | 78/78 |
| Zodiac Sign | `Zodiac Sign` | 78/78 |
| Zodiac Symbol | `Zodiac Symbol(s)` | 78/78 |
| Astrological Influence | `Astrological Influence` | 78/78 |
| Elemental Gender | `Elemental Gender` | 6/78 (Major Arcana only, first 6 cards) |
| Direction | `Direction` | 78/78 |
| Color | `Color` | 78/78 |
| Animal | `Animal Reference` | 22/78 (Major Arcana only; all 56 Minor Arcana blank) |
| Stone | `Stone Reference` | 39/78 (Wands suit + a few early Cups; rest blank) |
| Astrology | `Astrology` | 78/78 (free-text paragraphs — see Section 3) |

The remaining columns (`Card Title & Meaning`, `Divinatory Meaning`, `Radiant Wise Description`, `Symbolic & Divinatory Meaning`, `Image Path`, etc.) are **not** part of this proposal — they hold narrative meaning text and an external image URL, not correspondence data, and are addressed in Section 3.

---

# 2. Data Quality Observations

I did not correct anything — these are flagged for your decision.

**Spelling/casing inconsistencies** (cosmetic; I'd normalize these in storage while keeping the underlying value): `Element` appears as `Fire`, `FIre`, `Water`, `water` inconsistently; `Pices` (Pisces) and `Sagitarius` (Sagittarius) are misspelled throughout; the Major Arcana's `Suit` column is unusable (it duplicates the card name, e.g. `Suit: 'Fool'` — not the wands/cups/swords/pentacles taxonomy; only populated correctly for Minor Arcana). None of this affects the ten fields' substance.

**Two likely data-entry errors**, both in `Zodiac Sign` for Major Arcana:

- **Strength**: `Zodiac Sign = Libra`, but `Astrological Influence = Sun` and the sheet's own `Astrology` text says *"Strength tarot card is astrologically influenced by Leo... Sun is the ruling planet of Leo."* Sun does not rule Libra (Venus does) — this row appears to contradict itself. Traditional attribution (and the sheet's own prose) points to **Leo**.
- **Judgement**: `Zodiac Sign = Libra`, `Astrological Influence = Pluto`. Pluto's traditionally associated sign is Scorpio, not Libra; the row directly above (Justice) also has `Zodiac Sign = Libra`, which suggests this may be a copy-down error rather than an intentional attribution.

I'd like your call on these: preserve exactly as entered (documented as a known inconsistency), correct them (documented as an editorial correction with rationale), or you tell me the intended values.

---

# 3. The `Astrology` Field: A Content-Sourcing Concern

Unlike the other nine fields (which are short categorical labels — `Fire`, `Aquarius`, `♒`, `Uranus`), `Astrology` holds a full paragraph per card, written in a distinct narrative voice (e.g. *"Venus asks you the question, 'what is your pleasure?'"*; *"The golden dawn designers called this card the 'Lord of Established Strength'"*). The `Card Key` sheet also includes an `Image Path` column pointing to `tarotcardmeanings.net` — a third-party commercial site — which suggests some of this sheet's descriptive content may originate from, or closely follow, published web sources rather than being original to the spreadsheet's author.

This matters because it directly touches the content-sourcing principle from the prior phase (`RAIDIAN_WISE_REFERENCE_DATA_V1.md`, Section 1): *"No modern websites... were used or paraphrased"* for our card meanings, specifically to avoid reproducing another author's copyrighted interpretive text. Copying the `Astrology` paragraphs verbatim into Raidian Wise's dataset would risk exactly that, for the same reason.

To be clear, the **factual correspondence itself is not the concern** — "Death corresponds to Scorpio, ruled by Pluto" is traditional, structural attribution data, the same kind of fact as "Wands are Fire." The concern is specifically the multi-sentence descriptive *prose* explaining that correspondence.

Three ways to handle it — I'd like you to pick one rather than me deciding silently:

1. **Omit the prose; keep only the structured `astrological_influence` field.** Simplest, zero risk, but drops the "Astrology" field's descriptive content, not just its wording.
2. **(Recommended) Write a brief original note per card** (1–2 sentences, Raidian Wise's own reflective voice, same approach already used for card meanings) synthesizing the correspondence already captured in the structured fields. Preserves the field's *purpose* without reproducing anyone else's sentences.
3. **Store the sheet's paragraph text verbatim**, if you know its provenance (e.g. you or "Jenn" wrote it originally) and are comfortable with that risk. I have no way to verify this myself.

---

# 4. Proposed Schema Change

## 4.1 Option considered: add columns to `Card`

Rejected. It would mix `Card`'s existing RWS-meaning identity (`base_meaning_upright`, `keywords`, etc. — our own original wording) with a specific external correspondence tradition's attributions on the same row, which cuts directly against your instruction to *"preserve the distinction between established RWS meanings and correspondence traditions."* It would also force every future Card (including any future deck that may not use astrological correspondences at all) to carry ten mostly-nullable columns.

## 4.2 Proposed: a related `CardCorrespondence` model

A new table, one-to-one with `Card` (mirroring the `ReflectionSession`–`Reading` one-to-one pattern already established in Phase 1: a unique foreign key on the child side):

```
card_correspondences
  id                      uuid, pk
  card_id                 uuid, fk -> cards.id, unique, ON DELETE CASCADE
  source_reference        string, not null   -- e.g. "RaidianWiseDeckTemplate_Jenn.xlsm — Card Key worksheet"
  tradition_name          string, nullable   -- e.g. "Golden Dawn decanic attribution" where identifiable;
                                              -- null where the specific named tradition isn't confidently identifiable
                                              -- (see Section 5 — this applies to most Major Arcana rows)
  element                 string, not null   -- normalized lowercase: fire | water | air | earth
  zodiac_signs            json list, not null -- e.g. ["aquarius"] or ["aries","leo","sagittarius"]
  zodiac_symbols          json list, not null -- unicode glyphs, aligned with zodiac_signs
  astrological_influence  string, not null   -- e.g. "Mars in Aries", "Uranus", "Spirit of Fire"
  elemental_gender        string, nullable   -- masculine | feminine (only ~6 cards have this in the source)
  direction                string, not null  -- south | west | east | north
  color                   string, not null   -- red | black | yellow | white
  animal                  string, nullable   -- Major Arcana only in the source; null for all Minor Arcana
  stone                   string, nullable   -- partial coverage in the source
  astrology_note          text, nullable     -- see Section 3 for what goes here
  created_at / updated_at
```

Rationale:
- Keeps `Card` (RWS meaning) and `CardCorrespondence` (astrological/elemental tradition) as separate, independently-sourced entities — directly satisfying the "preserve the distinction" instruction.
- `source_reference` and `tradition_name` give every correspondence row a documented provenance, satisfying "record sources/traditions where known" — including being honest about what's *not* confidently known (Section 5).
- One-to-one for now, but as its own table it can become one-to-many later (e.g. if a second correspondence tradition is added for the same cards) without restructuring `Card`.
- Nullable fields (`elemental_gender`, `animal`, `stone`) reflect the source's actual partial coverage rather than inventing values to fill gaps.

## 4.3 Reference-data content architecture

Following the existing pattern (`RAIDIAN_WISE_REFERENCE_DATA_V1.md`, Section 7): a new `correspondences.yaml` per deck directory (`backend/app/reference_data/rider_waite_smith/correspondences.yaml`), keyed by card name, loaded and validated by an extension to `app/seed/loader.py`, and upserted by `app/seed/seed.py` alongside (not instead of) the existing card-meaning seeding — same idempotent-upsert approach already in place.

---

# 5. Sourcing / Tradition Attribution — What's Actually Known

Being precise here matters for "record sources/traditions where known":

- **Minor Arcana (56 cards)**: the `Astrological Influence` values (e.g. "Mars in Aries" for Two of Wands) and the sheet's own references to *"the golden dawn designers"* and their historical card titles (e.g. *"Lord of Established Strength"*) confirm these follow the documented **Golden Dawn decanic attribution system** (originated by S. L. MacGregor Mathers, widely published in Israel Regardie's *The Golden Dawn*). I can confidently label `tradition_name: "Golden Dawn decanic attribution"` for these.
- **Major Arcana (22 cards)**: the attributions are a mix — some cards match Golden Dawn exactly (e.g. Hierophant=Taurus/Venus, Justice=Libra/Venus), others clearly don't (e.g. Fool=Aquarius/Uranus, where Golden Dawn assigns only the element Air, no sign or planet). This looks like a broader, eclectic modern synthesis rather than a single named historical system, and I can't independently identify one source it consistently follows. I'd propose `tradition_name: null` for these rows rather than mislabeling them as "Golden Dawn," with `source_reference` still pointing to the provided spreadsheet either way.

---

# 6. Decisions (Resolved)

1. **Strength / Judgement `Zodiac Sign` values** (Section 2) — **corrected** to Leo and Scorpio respectively.
2. **`Astrology` field handling** (Section 3) — **brief original notes** (option 2).
3. **Schema approach** (Section 4.2) — **approved as proposed**.
4. **Tradition labeling** (Section 5) — **`tradition_name: null`** for Major Arcana rows where not confidently identifiable.

All four are implemented — see `backend/app/models/card_correspondence.py`, `backend/alembic/versions/f5f0af118106_add_card_correspondences_table.py`, `backend/app/reference_data/rider_waite_smith/correspondences.yaml`, and `RAIDIAN_WISE_REFERENCE_DATA_V1.md` Section 8.

---

## Related Documents

- `RAIDIAN_WISE_REFERENCE_DATA_V1.md` — the reference-data architecture this extends.
- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Section 7 (Data Model), which this proposal's `CardCorrespondence` model extends.
