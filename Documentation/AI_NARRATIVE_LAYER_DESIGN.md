# AI Narrative Layer — Design & Separation Record

Documents the AI Narrative Layer implementation
(`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 12, ADR-0005's "Reflection
Engine", `docs/ARCHITECTURE.md`'s "Reflection Engine" Core Service). This
sits strictly downstream of, and never replaces, the deterministic
Interpretation Engine (`INTERPRETATION_ENGINE_DESIGN.md`), the
deterministic-synthesis extension to `InterpretiveModel`
(`theme_strength`/`relationships`/`deterministic_synthesis`), and the
deterministic Scriptural Reflection foundation
(`SCRIPTURAL_REFLECTION_FOUNDATION_DESIGN.md`) — all three remain the sole
source of truth for what a reading means. This layer only narrates
already-decided content; it never decides anything itself.

---

## 1. The separation this document exists to make explicit

| | Interpretation Engine | Narrative Layer | Scripture Layer | **AI Narrative Layer** |
|---|---|---|---|---|
| Deterministic? | Yes | Yes | Yes | **No — the only non-deterministic layer in this project** |
| Uses an LLM? | No | No | No | **Yes — its entire reason to exist** |
| Source of truth for card/theme meaning? | Yes | No (renders Interpretation Engine output) | No (renders Scripture reference data) | **No — never** |
| Input | A Reading's drawn cards | An `InterpretiveModel` | An `InterpretiveModel` | An `InterpretiveModel` + optional `ScripturalPerspective` (never raw Card Draws) |
| Output | `InterpretiveModel` | `NarrativeModel` | `ScripturalPerspective` | `AINarrativeResponse` |
| Persisted? | Yes (`Interpretation`) | No (recomputed) | No (recomputed) | **Yes (`AINarrative`) — see Section 5 for why this differs** |
| Can it invent a card meaning, relationship, theme, or Scripture reference? | N/A (it is the source) | No | No | **No — enforced at the input boundary and, for Scripture, re-checked on the way out (Section 6)** |

ADR-0005 (`docs/DECISIONS.md`): "Artificial intelligence shall be accessed
exclusively through the Reflection Engine. Individual application
components should never communicate directly with AI providers." This
implementation is the first (and, as of this work, only) caller of that
gateway.

---

## 2. Architecture

```
InterpretiveModel (already persisted)  +  ScripturalPerspective (optional, opt-in per call)
                              |
                              v
              DeterministicReadingContext        -- app/schemas/ai_narrative.py
              (a thin wrapper, not a reshaping --
               see its own docstring)
                              |
                              v
              build_system_prompt() / build_user_prompt()   -- app/services/reflection_engine/prompts.py
              (prompts/system/*.md + prompts/interpretation.md,
               authored as part of this work -- Section 3)
                              |
                              v
              ReflectionEngineClient.complete()   -- app/services/reflection_engine/client.py
              (Protocol; AnthropicReflectionEngineClient is the one
               concrete implementation, app/services/reflection_engine/anthropic_client.py)
                              |
                              v
              generate_ai_narrative()             -- app/services/ai_narrative/generation.py
              (parse JSON, validate shape, enforce
               "no invented Scripture" -- Section 6)
                              |
                              v
              AINarrativeResponse                 -- app/schemas/ai_narrative.py
                              |
                              v
              save_ai_narrative()                 -- app/services/ai_narrative/persistence.py
                              |
                              v
                    AINarrative (persisted)
```

`app/services/reading_orchestration.py::generate_ai_narrative_for_reading()`
wires the whole pipeline together (the same DB-access-boundary role that
module already plays for Interpretation/Narrative/Scripture) and is the
only place that fetches the current `Interpretation`, optionally computes
a `ScripturalPerspective` via the existing Scripture Layer, and calls
into this new layer. `app/api/ai_narrative.py` is a thin HTTP wrapper
around it, mirroring `app/api/interpretation.py` and
`app/api/scripture.py` exactly.

---

## 3. Prompts

`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 12 names four prompt files and
notes they were "currently empty and need to be authored before this
layer can function." Authoring them was part of this implementation, not
a separate content task:

- `prompts/system/reflection_engine.md` — role framing (you are the
  Reflection Engine; you narrate, you do not reinterpret).
- `prompts/system/safety.md` — the hard constraints from Product Spec
  Section 12/14 (no invented conclusions, no predictions, uncertainty
  stays uncertain, no divine-revelation framing, no decision-making
  advice) plus `docs/NAMING_CONVENTIONS.md`'s banned/preferred language
  lists, restated in full so both the Interpretation Engine's own output
  vocabulary and this prompt are built against the same list without
  duplicating it in code (Section 14's own instruction).
- `prompts/system/tone.md` — the reflective-humility tone guidance
  (`docs/ROADMAP.md` Phase 4's own naming for this file).
- `prompts/interpretation.md` — the per-request task instructions and the
  required JSON output shape.

These live at the repository root (`prompts/`), exactly where the Product
Spec places them and where the (previously empty) files already existed —
not under `backend/app/`. `app/services/reflection_engine/prompts.py`
resolves this path relative to its own file location, which assumes the
repository is checked out whole; a future deploy that ships `backend/`
alone will need to bundle `prompts/` alongside it (noted in that module's
own docstring). The five other files under `prompts/` (`journal_summary.md`,
`onboarding.md`, `reflection_questions.md`, `scripture_matching.md`) are
untouched — they belong to other, not-yet-built engines
(`docs/ARCHITECTURE.md`'s Journal/Growth Engines), and `scripture_matching.md`
in particular is deliberately never authored by this work, because Scripture
selection must remain non-AI (Section 6 below, and
`SCRIPTURAL_REFLECTION_FOUNDATION_DESIGN.md`).

---

## 4. Provider / client approach

`app/services/reflection_engine/client.py` defines `ReflectionEngineClient`
as a one-method `Protocol` (`complete(system_prompt, user_prompt) -> str`)
— the entire seam ADR-0005 requires. `AnthropicReflectionEngineClient`
(`anthropic_client.py`) is the one concrete implementation: a direct HTTP
POST to Anthropic's Messages API using `httpx2` (already a transitive
project dependency via `starlette.testclient`, see `requirements.txt`),
not a new SDK dependency — a single JSON request/response does not need
one, per "do not introduce a new AI provider abstraction unless the
repository actually needs one."

Credentials (`RAIDIAN_AI_API_KEY`, plus `RAIDIAN_AI_MODEL`/`RAIDIAN_AI_BASE_URL`/etc.,
`app/core/config.py`) are read server-side only and never appear in any
response schema or frontend code. `RAIDIAN_AI_API_KEY` defaults to blank;
an unconfigured deployment fails closed (`ReflectionEngineNotConfiguredError`,
mapped to HTTP 503) rather than silently attempting a call.

No test in this project makes a real AI provider call.
`tests/reflection_engine_fakes.py::FakeReflectionEngineClient` (implementing
the same Protocol) stands in for the provider in every service/API test;
`tests/test_anthropic_reflection_client.py` separately exercises the HTTP
client's own request-building/error-handling logic against `httpx2`'s
`MockTransport`-style response construction — still no real network call.

---

## 5. Input / output schema

`app/schemas/ai_narrative.py`:

- **`DeterministicReadingContext`** — the AI's entire factual basis: an
  `InterpretiveModel` plus an optional `ScripturalPerspective`. Not a
  reshaping/duplication of either — see the schema's own docstring for why
  that would risk drift. Matches Product Spec Section 12's "Input: a
  finished Interpretive Model only — never raw Card Draws."
- **`AINarrativeResponse`** — `opening_summary`, `overall_narrative`,
  `key_themes` (natural-language statements, not the bare tag names),
  `card_relationships`, `reflective_synthesis`, `reflection_questions`,
  and `scriptural_reflection` (present only when Scripture was supplied),
  plus provenance (`provider`, `model`, `schema_version`,
  `source_schema_version`, `generated_at`). Unlike `InterpretiveModel`'s
  `Explained[T]`/`Citation` machinery, nothing here carries a citation —
  an AI-generated sentence's precise provenance cannot be mechanically
  verified the way a deterministic rule's can (see the schema's own
  docstring). The content it can draw from is constrained at the input
  boundary and validated on the way out instead (Section 6).

### Persistence decision

The task instructions left this to judgment: "Do not persist generated AI
output unless there is already an established persistence pattern and you
determine it is appropriate." This implementation **does persist**
(`AINarrative`, migration `12ad6e6757dc`), FK'd to `Interpretation`
(mirroring `Interpretation`'s own FK-to-`Reading`, same global
`sequence` counter, same compute/persist split as
`interpretation/persistence.py`). Reasoning:

- A real AI call costs money and takes real latency, and is not
  deterministic — recomputing on every page view/refresh (the way
  `NarrativeModel`/`ScripturalPerspective` deliberately do) would be
  wasteful and would show the user a different reflection on every
  visit for no benefit.
- `Interpretation`'s own persistence pattern already exists and fits this
  case exactly: a paid/slow/non-deterministic generation that should be
  retained once produced, with regeneration creating new history rather
  than overwriting.

Generation (`generate_ai_narrative`, the network call + validation) and
persistence (`save_ai_narrative`) are kept as separate functions, so a
failed generation performs no database write at all — the deterministic
Reading/Interpretation is untouched either way (verified by
`tests/test_api_ai_narrative.py::test_failed_generation_leaves_the_deterministic_interpretation_untouched_and_creates_no_ai_narrative_row`).

---

## 6. Guardrails

- **Safety constraints are prompt-enforced** (Section 3) — the model is
  told, in `prompts/system/safety.md`, never to invent conclusions, never
  to predict, never to convert uncertainty into confidence, never to
  claim divine revelation, never to give decision-making instructions,
  and never to introduce a Scripture reference beyond what it was given.
- **Scripture is structurally re-checked, not just prompted.**
  `generate_ai_narrative()` rejects (raises `AINarrativeValidationError`)
  any response containing a non-null `scriptural_reflection` when the
  request's `DeterministicReadingContext.scripture` was `None` — "AI
  cannot receive/introduce unsupported Scripture references" is enforced
  in code, not only by prompt instruction. The AI is never given the
  ability to look up Scripture itself; it can only narrate the exact
  `ScripturalPerspective` the already-deterministic Scripture Layer
  already selected.
- **Malformed responses are rejected, not repaired.** The provider's raw
  text is parsed as JSON (tolerating one optional markdown fence) and
  validated against a strict (`extra="forbid"`) Pydantic model; any
  parse/shape failure raises `AINarrativeValidationError` and nothing is
  persisted.
- **Provider failure is distinguished from validation failure.**
  `AINarrativeProviderError` (network/timeout/non-2xx/not-configured) and
  `AINarrativeValidationError` (malformed or unsafe response) are
  separate exception types; `app/api/ai_narrative.py` maps
  not-configured to 503 and every other case to 502 — never a 500 that
  would suggest an application bug.

---

## 7. What is deliberately deferred

- **No "regenerate with feedback" or streaming** — one request, one
  response, matching Section 12's own scope.
- **No caching/deduplication of identical requests** — every call is a
  new generation and a new `AINarrative` row (Section 5's own reasoning
  already covers why re-computation itself is avoided by persisting, but
  this project does not attempt to detect "the same request as before").
- **No UI redesign** — `ReadingResultPage.tsx` gained one new, clearly
  labeled, opt-in "AI Reflection" section following the same pattern as
  its existing "Scriptural Reflection (Optional)" section; nothing about
  the deterministic Narrative/explainability sections changed.
- **The other four `prompts/` files** (`journal_summary.md`,
  `onboarding.md`, `reflection_questions.md`, `scripture_matching.md`) —
  out of scope; see Section 3.
- **Any change to Scripture selection** — still purely deterministic
  (`app/services/scripture/selection.py`, unmodified by this work); the
  AI Narrative Layer only ever reads its already-computed output.

---

## Related documents

- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 12 (Narrative Generation
  Architecture), Section 3.3 (reconciling the Interpretation Engine with
  ADR-0005), Section 14 (Disclaimer and Guardrails).
- `docs/DECISIONS.md` — ADR-0005 (Reflection Engine Architecture).
- `docs/ARCHITECTURE.md` — names the Reflection Engine Core Service.
- `docs/NAMING_CONVENTIONS.md` — the banned/preferred language list
  `prompts/system/safety.md` restates.
- `SCRIPTURAL_REFLECTION_FOUNDATION_DESIGN.md` — the deterministic
  Scripture Layer this work reads from but never modifies.
- `app/services/reading_orchestration.py` — the shared DB-access-boundary
  module docstring, updated alongside this document.
