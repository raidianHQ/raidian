# Scriptural Reflection Foundation — Design & Separation Record

Documents the foundation implementation of the optional Scriptural
Reflection layer described in `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section
15, `docs/PROJECT_VISION.md`'s "Scripture Integration" section, and
`docs/ARCHITECTURE.md`'s "Scripture Engine". This is the FOUNDATION only
— card selection, Digital Draw, and the deterministic synthesis layer
(`INTERPRETATION_ENGINE_DESIGN.md`, the deterministic-synthesis work
extending `InterpretiveModel` with `theme_strength` etc.) are unchanged
and remain the sole source of truth for tarot interpretation. No AI
Narrative Layer is implemented by this work.

---

## 1. The separation this document exists to make explicit

**Tarot Interpretation** (`app/services/interpretation/`,
`app/schemas/interpretive_model.py`) and **Scriptural Reflection**
(`app/services/scripture/`, `app/schemas/scripture_model.py`) are two
architecturally separate layers that happen to share one thing: the
Interpretation Engine's own theme vocabulary.

| | Tarot Interpretation | Scriptural Reflection |
|---|---|---|
| Source of truth | `Card`/`CardCorrespondence`/`Spread`/`SpreadPosition` reference data | `ScriptureReference` reference data |
| Input | A `Reading`'s drawn cards | An already-computed `InterpretiveModel.theme_strength` |
| Responds to | Cards, positions, structural roles | **Themes only, never a card directly** |
| Output | `InterpretiveModel` | `ScripturalPerspective` (its own schema — never a field of `InterpretiveModel`) |
| Optional? | No — the reading's own record | Yes — a separate, opt-in fetch |
| Persisted? | Yes (`Interpretation` table) | No — recomputed on every call, like `NarrativeModel` |
| Uses an LLM? | No | No |

**Explicitly not implemented, and explicitly rejected by design:** `Card
-> Scripture` or `Card -> "God's message"`. Nothing in this layer ever
reads a `Card`, `CardDraw`, or `CardCorrespondence` row, and nothing in
it claims that a card — or the reading as a whole — represents God's
will. See Section 5 (Guardrails) below.

The two layers share code in exactly one place —
`app/services/reading_orchestration.py`, which is the one module in this
project permitted to combine database access with either the
Interpretation Engine, the Narrative Layer, or the Scripture Layer. That
module's own docstring states explicitly that this grouping is about
*where database access is permitted to happen*, not about Scripture
being part of the tarot engine's source-of-truth meanings.

---

## 2. Architecture

```
Deterministic Interpretation (already implemented)
        |
        v
InterpretiveModel.theme_strength   -- "Approved Theme Vocabulary" already
        |                              scored/ranked/cited by the engine
        v
ScriptureReference lookup           -- exact theme-tag match against the
(app/services/scripture/selection)     approved, seeded reference table
        |
        v
ScripturalPerspective               -- structured, citation-backed,
(app/schemas/scripture_model.py)       never persisted
```

`select_scripture_reflections(session, model)` iterates
`model.theme_strength` in its own existing order (count desc, theme name
asc — already-approved Rule T1, unmodified) and, for each theme, looks
up `ScriptureReference` rows with an **exact** tag match. No fuzzy
matching, no synonym table, no scoring beyond `theme_strength`'s own
existing order, and no LLM call anywhere in this path. A theme with no
approved row simply contributes nothing — this is the expected, common
case for most readings today, not an error.

`get_scripture_for_reading(session, reading)`
(`reading_orchestration.py`) mirrors `get_narrative_for_reading()`
exactly: fetch the reading's current persisted `Interpretation`,
reconstruct its `InterpretiveModel` via `model_validate`, hand it to the
downstream layer. Nothing about this path can feed back into
`interpret()`/`save_interpretation()` — it is read-only with respect to
both `Reading` evidence and `Interpretation` content (see
`test_scripture_selection.py`'s
`test_does_not_mutate_the_source_interpretive_model` and
`test_writes_no_rows_to_the_database`).

---

## 3. Data model

New table: `scripture_references` (`app/models/scripture.py`,
migration `31bea9b1c3f1`). Reference data, seeded the same way as
`Card`/`CardCorrespondence`/`Spread` (`app/seed/loader.py` +
`app/seed/seed.py`, upserted by natural key
`(theme, book, chapter, verse_start, translation)`).

Columns: `theme` (must exist verbatim in `theme_vocabulary.yaml`,
enforced at load time — never an independent taxonomy), `book`
(validated against the 66 canonical Bible book names), `chapter`,
`verse_start`, `verse_end` (nullable, for a single-verse reference),
`reference_display` (a human-curated display string, e.g.
`"Philippians 4:6-7"`), `translation` (validated against an approved,
public-domain-only allowlist), `context_note` and `reflection_connection`
(original commentary written for this project — never a quotation).

**No passage text column exists at all.** This is a licensing decision
(`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 15.1: "Do not embed
copyrighted Bible translation text in the MVP"), enforced structurally —
there is no field to accidentally populate with copyrighted text, not
merely a convention to remember. `translation` is a citation label only;
Section 16 Q5 (which translations are cleared for showing actual verse
text) remains open and unresolved by this work.

### Seed content

Seven themes are seeded, each with one reference: `fear`, `anxiety`,
`patience`, `relationships`, `grief`, `hope`, `uncertainty`. These are
the subset of the product spec's own suggested Scripture theme taxonomy
(Section 15.3: fear/anxiety, wisdom, decisions, patience, waiting,
relationships, forgiveness, grief, hope, money/stewardship, work,
change, uncertainty, trust, surrender) that already exists **verbatim**
as a tag in `theme_vocabulary.yaml`. The remaining nine concepts have no
exact tag match — mapping them would mean guessing which existing tag
the brief's words "really" meant, the same invented-mapping judgment
`compounds.py`'s own docstring already refuses to make for its five
unmapped named compounds, for the same reason. All seven references use
the KJV (public domain).

---

## 4. API

`GET /readings/{reading_id}/scripture` (`app/api/scripture.py`, its own
router — a deliberate, separate file from `app/api/interpretation.py`,
extending the architectural separation all the way to the API surface).
Same ownership/authentication as every other Reading-scoped route
(`get_owned_reading`, unmodified). 404 if the reading has never been
interpreted; 200 with a possibly-empty `reflections` list otherwise —
an empty list is a valid, expected outcome, never an error.

### How "optional" is satisfied at this foundation stage

`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 15.2 describes a persisted,
three-state user preference (Scripture Off / Include Scripture / Ask Me
Each Reading) plus a preferred-translation setting. **This foundation
does not implement that setting** — no new column on `User`, no new
preferences table. Instead, "optional" is satisfied structurally: this
is a separate endpoint a caller (today, the frontend) chooses to call or
not call. `POST /interpret` and `GET /narrative` are completely
unaffected by whether `GET /scripture` is ever invoked (see
`test_api_scripture.py`'s `test_interpret_and_narrative_never_call_the_scripture_layer`).
The persisted per-User/per-Reading preference remains real, scoped
future work.

---

## 5. Guardrails

A fixed disclaimer (`app/schemas/scripture_model.py::DISCLAIMER`) is
attached to every `ScripturalPerspective`, never optional to omit at a
construction site:

> "Scripture is offered here as an optional source of reflection, not as
> proof that this reading — or any card in it — represents God's will.
> These references respond to the reading's themes, never to a card
> directly, and are not a substitute for one's own study, prayer, or
> pastoral guidance."

This directly implements `docs/PROJECT_VISION.md`'s "Scripture
Integration" section ("does not claim that scripture validates a card
reading") and `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 15's explicit
"Card -> God's message" ban.

Every `ScriptureReflection.theme_citations` is copied verbatim from the
source `InterpretiveModel.theme_strength` entry it responds to — never
recomputed, never pointing at a card the selection logic looked at
directly (it never does).

---

## 6. What is deliberately deferred

- **Passage/translation text** — blocked on Section 16 Q5 (translation
  licensing), unresolved.
- **The nine unmapped seed-taxonomy themes** (wisdom, decisions, waiting,
  forgiveness, money/stewardship, work, change, trust, surrender) —
  blocked on a deliberate tag-mapping decision or new
  `theme_vocabulary.yaml` content, the same restraint `compounds.py`
  already applies to its own unmapped named compounds.
- **Persisted user preference** (Section 15.2's three-state setting +
  preferred translation) — not needed for "optional" to already hold
  true today (Section 4 above); real future work.
- **More than one reference per theme in the general case** — the schema
  and selection logic already support it (no schema change needed later,
  confirmed by `test_a_theme_can_have_more_than_one_approved_reference`);
  only the seed content itself is currently one-per-theme.
- **Any AI/LLM involvement** — out of scope for this task entirely;
  Scripture selection is, and must remain, a deterministic database
  lookup.

---

## Related documents

- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 15 (Scripture for Reflection
  Architecture) and Section 16 Q5 (translation licensing, open).
- `docs/PROJECT_VISION.md` — "Scripture Integration" section.
- `docs/ARCHITECTURE.md` — names the future "Scripture Engine" service.
- `RAIDIAN_WISE_REFERENCE_DATA_V1.md` Section 4.1 — the shared theme
  vocabulary this layer reuses rather than duplicating.
- `INTERPRETATION_RULES_DESIGN.md` — the compound-theme rules' own
  "do not invent a tag mapping" precedent this document's Section 3
  follows for the unmapped seed-taxonomy themes.
- `app/services/reading_orchestration.py` — the shared DB-access-boundary
  module docstring, updated alongside this document.
