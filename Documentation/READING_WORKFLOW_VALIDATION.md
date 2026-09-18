# Raidian Wise — Reading Workflow Validation (Step 12)

# Document Information

Version: 1.0
Status: Complete — Validation Only, No Design or Behavior Changes
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Validates the complete, already-implemented Reading → Interpretation → Narrative workflow, end to end, at baseline `5344323` (Step 11, `feat: expose interpretation API`, pushed to `origin/main`). This document traces the real HTTP path — `POST .../interpret` → `interpret_reading()` → `engine.interpret()` → `save_interpretation()` → database → `GET .../interpretations/current` → `get_current_interpretation()` → `InterpretiveModel` → `GET .../narrative` → `assemble_narrative()` → `NarrativeModel` — with a new integration test suite (`backend/tests/test_reading_workflow_e2e.py`, 11 tests) and records what was actually observed. No engine, schema, orchestration-behavior, or reference-data change was made to produce this document; the one code change discovered to be necessary turned out not to be — see Section 6.

Audience:
Software engineers and AI development agents planning any future step against this workflow (a real auth layer, a convenience aggregate endpoint, activating a deferred rule), and anyone auditing whether the four already-approved layers (Engine, Narrative, Reading Integration, Interpretation API — Steps 2–3/6–7/8–9/10–11) actually compose correctly when driven through the real API, not just in isolation.

Authority:
Validates `INTERPRETATION_ENGINE_DESIGN.md`, `NARRATIVE_LAYER_DESIGN.md`, `READING_INTEGRATION_DESIGN.md`, and `INTERPRETATION_API_DESIGN.md` against the actual runtime behavior of `app/api/interpretation.py`, `app/services/reading_orchestration.py`, `app/services/interpretation/`, and `app/services/narrative/` acting together. Does not override any of them — a discrepancy found here would be a defect report against the implementation, not a redesign of any approved document.

---

# 0. Method

A new integration test file, `backend/tests/test_reading_workflow_e2e.py`, drives the real FastAPI app (`app.main.app`) through a `fastapi.testclient.TestClient`, with `get_db` overridden to a StaticPool in-memory SQLite engine seeded with the real Rider-Waite-Smith reference data (the same `seed_reference_data` pipeline every other test in this project uses) — no route, dependency, or service is mocked; only the database engine differs from production (SQLite in-memory vs. the configured `DATABASE_URL`), exactly as every other test in this repository already does.

This is deliberately **not** a re-run of Step 9's (`test_reading_orchestration.py`) or Step 11's (`test_api_interpretation.py`) own unit-level suites, both of which continue to pass unchanged (Section 7). Instead, this suite specifically targets the seams *between* layers that a layer's own unit tests, by construction, cannot exercise:

- Whether the value the engine actually computes is the exact value a caller receives back through the full HTTP round trip (not just "the route returns 200").
- Whether the orchestration-level "current interpretation" semantics (highest `sequence`, Step 9) survive being exercised through the API rather than called directly.
- Whether a rule this project has explicitly deferred (R3/R4) can be made to leak into API output even under active, adversarial pressure — not just absence-of-evidence from normal runs.

---

# 1. Workflow Traced

```
Reading (evidence, already spread-complete)
  │
  ▼
POST /readings/{id}/interpret                    [app/api/interpretation.py]
  │  reading_id -> Reading, or 404
  ▼
interpret_reading(session, reading)              [app/services/reading_orchestration.py]
  │  is_spread_complete precondition, or 409
  ▼
engine.interpret(reading, session)                [app/services/interpretation/engine.py]
  │  pure; returns InterpretiveModel
  ▼
save_interpretation(session, reading, model)      [app/services/interpretation/persistence.py]
  │  new Interpretation row (sequence = global max + 1), status transition
  ▼
get_db() commits                                  [app/db/session.py]
  │
  ▼  (later, any number of times)
GET /readings/{id}/interpretations/current        [app/api/interpretation.py]
  │
  ▼
get_current_interpretation(session, reading)      [app/services/reading_orchestration.py]
  │  highest-sequence row for this reading_id
  ▼
InterpretiveModel.model_validate(row.interpretive_model)  [app/api/interpretation.py]
  │
  ▼  (independently, any number of times)
GET /readings/{id}/narrative                       [app/api/interpretation.py]
  │
  ▼
get_narrative_for_reading(session, reading)        [app/services/reading_orchestration.py]
  │  -> get_current_interpretation() -> assemble_narrative(model)   [app/services/narrative/assembler.py]
  ▼
NarrativeModel  (never persisted)
```

Every arrow above was independently exercised by at least one test in the new suite; Section 2 maps each of the task's 14 required scenarios to the specific test(s) that cover it.

---

# 2. Test Scenarios and Results

| # | Required scenario | Test(s) | Result |
|---|---|---|---|
| 1 | Complete Reading interpreted through the API | `test_full_workflow_trace_interpret_persist_retrieve_narrative` | Pass — `201`, correct body |
| 2 | Interpretation actually persisted | `test_full_workflow_trace_interpret_persist_retrieve_narrative` (raw `SELECT` against `Interpretation`, bypassing every service/API layer) | Pass |
| 3 | Reading status transitions correctly | `test_full_workflow_trace_interpret_persist_retrieve_narrative` (DRAFTING→INTERPRETED); `test_reinterpreting_a_saved_reading_preserves_saved_status` | Pass |
| 4 | Persisted Interpretation retrievable via current endpoint | `test_full_workflow_trace_interpret_persist_retrieve_narrative` | Pass — identical `id`/`interpretive_model` |
| 5 | Retrieved model matches the model the engine produced | `test_retrieved_interpretive_model_matches_the_engine_output` (direct `engine.interpret()` call vs. the same content retrieved through the full API) | Pass |
| 6 | Narrative endpoint derives from the current Interpretation | `test_narrative_reflects_the_current_highest_sequence_interpretation` (two rows inserted, `current_theme` at `sequence=2` must win over `stale_theme` at `sequence=1`, inserted second) | Pass |
| 7 | Narrative generation creates/modifies no DB records | `test_narrative_generation_creates_no_rows_and_does_not_mutate_the_reading` (row count and `Reading.updated_at` unchanged across 2 calls) | Pass |
| 8 | Reinterpretation creates new row, preserves history | `test_reinterpretation_creates_a_new_row_and_preserves_history` | Pass |
| 9 | `sequence` determines current, not insertion order | `test_current_endpoint_uses_sequence_not_insertion_order` (row inserted first given a *higher* sequence than a row inserted second — current must be the first) | Pass |
| 10 | Reinterpreting a SAVED Reading preserves SAVED | `test_reinterpreting_a_saved_reading_preserves_saved_status` | Pass |
| 11 | Incomplete Reading — documented error, engine never invoked, no row created | `test_incomplete_reading_returns_409_engine_never_invoked_no_row_created` (monkeypatches `engine.interpret` to raise `AssertionError` if called at all) | Pass — `409`, zero rows, status untouched |
| 12 | Provenance / reference-data version survive the full round trip | `test_provenance_and_reference_data_version_survive_the_full_round_trip` | Pass — identical 64-hex-char version across POST/current/narrative; every `card_draw_id` citation resolves to a real `CardDraw` |
| 13 | All four routes registered and functional | `test_all_four_routes_are_registered_and_functional` (OpenAPI schema + one live call per route) | Pass |
| 14 | Existing tests continue to pass | Full suite run, Section 7 | Pass — `254 passed, 0 failed` |

An additional test beyond the task's numbered list was added because tracing this workflow raised a question the prior design documents answered but no test had yet put under real pressure:

| Extra scenario | Test | Result |
|---|---|---|
| Deferred rules R3/R4 cannot leak into API output, even adversarially | `test_deferred_relationship_rules_cannot_leak_into_the_output` | Pass — see Section 6 |

---

# 3. Findings

## 3.1 The full chain composes correctly

Every hop in Section 1's diagram was confirmed to behave exactly as its own governing design document specifies, when driven end-to-end rather than tested in isolation. No integration-level surprise was found: the four layers (Engine, Narrative, Reading Integration, API) compose exactly as their design documents predicted.

## 3.2 The engine's determinism holds across the transport boundary

`test_retrieved_interpretive_model_matches_the_engine_output` independently called `engine.interpret()` directly and compared it (`generated_at` excluded) against the same reading's interpretation retrieved through `POST` → `GET current`. The two were **field-for-field identical**. This is a stronger check than Step 9/11's own tests perform (which check that persistence/serialization round-trips a *given* model losslessly) — this confirms the engine itself produces the *same* model twice, independently, and that nothing in the API/orchestration/persistence path silently alters it in transit.

## 3.3 `sequence` is a global counter, not a per-reading version number — confirmed by direct observation, not just docstring

While building the R3/R4 poison test (Section 6), two *different* Readings' first-ever interpretations were observed to receive `sequence = 1` and `sequence = 2` respectively — not `1` and `1`. This matches `Interpretation.sequence`'s own docstring and `persistence.py::_next_sequence`'s implementation exactly (`SELECT MAX(sequence)` across the whole table, not scoped to `reading_id`) — it is not a defect. It is, however, a real, empirically-confirmed fact worth surfacing for whoever eventually builds a frontend against `InterpretationSummary.sequence`/`InterpretationHistoryEntry.sequence`: **that field must never be displayed to a user as "interpretation #N for this reading."** A Reading's second-ever interpretation could easily carry `sequence = 47` if other Readings were interpreted in between. A future UI wanting to show "version 2 of this reading's interpretation" must derive that number from the position of the entry within `GET .../interpretations`' own ordered list, not from the `sequence` value itself. Neither `READING_INTEGRATION_DESIGN.md` nor `INTERPRETATION_API_DESIGN.md` states this pitfall explicitly (both correctly describe *why* `sequence` is global, but neither warns against this specific misuse) — recorded here as a documentation gap, not a code defect; no design document is amended by this validation pass.

## 3.4 A read-only request's implicit `commit()` is confirmed to be a true no-op

`INTERPRETATION_API_DESIGN.md` Section 14 predicted that `get_db()`'s `commit()` call on a `GET` request's path is "a harmless no-op, not a risk," since no write occurs. `test_narrative_generation_creates_no_rows_and_does_not_mutate_the_reading` directly confirms this: `Reading.updated_at` (a column with `onupdate=func.now()`) is bit-for-bit unchanged after two `GET .../narrative` calls, proving no implicit `UPDATE` was ever emitted, not merely that no application code intended one.

---

# 4. Defects Discovered

**None.** Every one of the 14 required scenarios, plus the additional adversarial check in Section 6, passed on the first correctly-written attempt at the assertion (two early drafts of the R3/R4 poison test had test-authoring mistakes of their own — comparing across two different Readings' random `card_draw_id`s, and forgetting `sequence` is global — both caught and fixed before this document was written; see Section 6 for detail). No implementation code was modified to make any test pass; per this task's instructions, an actual defect blocking the approved workflow would have been stopped on and reported here rather than silently fixed, and none was encountered.

---

# 5. Architectural Gaps Discovered

No **new** gap was discovered beyond what `INTERPRETATION_API_DESIGN.md` already names explicitly (no auth/authz, no pagination, no per-interpretation-ID detail route). One **documentation** gap was surfaced (Section 3.3: the global-vs-per-reading `sequence` pitfall) — recorded above rather than fixed here, since amending an approved design document is out of this validation step's scope.

---

# 6. Deferred-Rule Leakage — Explicit Confirmation

`INTERPRETATION_RULES_DESIGN.md` Section 7.1/12.3 defers Rules R3 (same-suit clustering) and R4 (Major Arcana density) as *interpretive conclusions* — the underlying evidence may still be computed. Direct inspection of `app/services/interpretation/engine.py` line 153 confirms the code-level mechanism: `evaluate_relationships(reading_context)` is called, and **its return value is not assigned to anything** — it is computed and immediately discarded, never passed to any downstream stage or output field.

`test_deferred_relationship_rules_cannot_leak_into_the_output` turns this static observation into a dynamic proof: the same Reading was interpreted twice — once normally, once with `evaluate_relationships` monkeypatched to return deliberately extreme, obviously-poisoned data (5 fabricated same-suit clusters, a 999-entry "Major Arcana" tuple of garbage objects that would raise `AttributeError` on first real use). The two resulting `InterpretiveModel`s, served through the full `POST /interpret` API call, were **byte-for-byte identical** (aside from row identity, `sequence`, and `generated_at`, which necessarily differ between any two interpretation runs). If R3/R4's evidence were consumed anywhere in the pipeline, this test would have failed loudly (most likely with an `AttributeError`, since the poisoned `major_arcana_draws` tuple contains bare `object()` instances) rather than silently passing.

**This is the strongest confirmation available that R3/R4's deferral is real and enforced by the actual code path, not merely by the current data never happening to trigger a leak.** No deferred rule (R3, R4, or any other rule marked Deferred in `INTERPRETATION_RULES_DESIGN.md` Section 12.3) was found to influence any API response in this validation pass.

Two earlier drafts of this specific test are worth recording as a methodology note, not a product defect:
1. The first draft compared the poisoned run against a baseline taken from a **different** Reading, and failed — not because poisoning leaked, but because two different Readings have different random `CardDraw` UUIDs, which appear inside citations. Fixed by reinterpreting the **same** Reading twice.
2. The second draft then failed on `sequence` alone (Section 3.3) — fixed by excluding that field from the comparison, since it is expected, correct, global-counter behavior, not something reinterpretation is claimed to hold constant.

---

# 7. Full Test Suite Result

```
254 passed in 51.13s
```

(243 tests as of the Step 11 baseline `5344323`, plus the 11 new tests in `backend/tests/test_reading_workflow_e2e.py`.) Zero failures, zero skips. No existing test file was modified.

---

# 8. Boundaries Observed

Confirmed against this task's explicit "Do NOT" list — none of the following occurred at any point in this validation pass:

- No new interpretation rule was added or activated (R3/R4 remain deferred — actively re-confirmed, Section 6).
- No deterministic behavior (engine, narrative, orchestration, or API) was changed.
- No authentication or authorization was added.
- No narrative persistence or caching was added — `test_narrative_generation_creates_no_rows_and_does_not_mutate_the_reading` positively confirms the opposite remains true.
- No AI/LLM logic was added.
- No reference data was changed — the reference-data version hash observed in this pass (`54d6b018a1771646998b9c4f25e9dcbad75499c5de4687d705e0a46638bd9d32`) is identical to the one recorded in `INTERPRETATION_ENGINE_VALIDATION.md` (Step 5), confirming the seeded dataset has not drifted across seven subsequent steps.
- No schema was redesigned.
- No frontend was touched (none exists).
- `README.md` was not modified.

---

# 9. Recommended Next Steps

1. **No code change is recommended from this validation pass.** The implementation matches every governing design document's contract exactly, exercised end to end through the real API.
2. Whoever eventually documents the API for frontend consumption should carry forward Section 3.3's finding explicitly (global vs. per-reading `sequence`) — a small addition to `INTERPRETATION_API_DESIGN.md` or its eventual OpenAPI `description` fields, not an urgent fix.
3. `backend/tests/test_reading_workflow_e2e.py` is proposed as a permanent addition to the suite (unlike Step 5's validation harness, which was deliberately kept out of the repository) — these are genuine integration tests covering seams no existing unit-level file exercises, not a one-off audit artifact. This document does not commit them; that remains a separate, explicit approval step.

---

## Related Documents

- `INTERPRETATION_ENGINE_DESIGN.md`, `INTERPRETATION_RULES_DESIGN.md`, `INTERPRETATION_ENGINE_VALIDATION.md` — the Engine's contract, rule specification, and prior (unit-level) validation this document extends to the full stack.
- `NARRATIVE_LAYER_DESIGN.md` — the Narrative Layer's contract, confirmed here to compose correctly with Reading Integration and the API.
- `READING_INTEGRATION_DESIGN.md` — `sequence`, the transition-aware status logic, and the caller-commits transaction convention, all re-confirmed under real HTTP traffic in this pass.
- `INTERPRETATION_API_DESIGN.md` — the API contract this document validates against the actual `app/api/interpretation.py`, including Section 14's `get_db()` fix, now empirically confirmed to be a true no-op on read paths (Section 3.4).
- `backend/tests/test_reading_workflow_e2e.py` — the new integration suite this document reports on.
