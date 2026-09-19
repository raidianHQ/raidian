# Interpretation & Narrative Frontend Integration Design Audit (Step 53)

**Status:** Read-only design/audit. No frontend, backend, schema, migration, dependency, or historical documentation file was modified in producing this report. Nothing was committed or pushed. Every claim below was verified directly against the current repository — source reads of every cited file, not restated from any prior step's report without re-checking.

---

## 1. Executive Summary

**No backend work is required before an Interpretation/Narrative frontend can be built.** The entire orchestration layer that `READING_INTEGRATION_DESIGN.md` (Step 8) and `INTERPRETATION_API_DESIGN.md` (Step 10) proposed as future work is **already fully implemented, tested, and reachable via four real, authenticated, ownership-gated HTTP endpoints** — this was not previously stated this plainly anywhere in the repository's own documentation, since both of those design documents predate the endpoints' actual implementation and still describe them as "PROPOSED"/"does not exist yet." This document's first job is simply to state, with direct evidence, that the gap those two documents described has since closed (Section 3/4).

**The Product Spec already settles the single biggest open question this step was asked to investigate: the screen boundary.** `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6 names a distinct **"Interpreting"** transient state and a distinct **"Reading Result"** screen — one combined screen showing narrative sections, an optional explainability panel (interpretation citations), and the Save action — not two separate "Interpretation screen" and "Narrative screen." This is a **fact already established by an existing governing document**, not a recommendation this audit is making (Section 8/9).

**A second, separately-named "Reading Detail" screen also exists in the Product Spec's own screen inventory**, distinct from "Reading Result": it is what a user sees when *revisiting* a saved Reading later (via History), showing "evidence + interpretation as generated." The already-built `/readings/:readingId` route (`SpreadReviewPage.tsx`, Steps 50/52) already serves this exact URL slot for evidence — it does not yet fetch or render interpretation content. Whether that page is extended to also show interpretation, or a new dedicated flow is built, is Section 9's recommended-but-not-decided boundary question.

**One genuinely new, verified technical finding**, directly relevant to Step 52's own open item: `Interpretation.created_at` shares the exact same timestamp-serialization characteristic already found and worked around for `Reading.created_at`/`updated_at` (Section 11) — but `InterpretiveModel.generated_at` and `NarrativeModel.generated_at` do **not**, because they are produced differently (in-memory, not from a database round-trip). This distinction was not previously documented anywhere.

No implementation of any kind was performed in this step.

---

## 2. Product Requirements

Read directly from `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` for this step (Sections 3, 6, 9–14, 17–18), not restated from memory or prior citations.

**Flow (Section 3, steps 8–14):**
> 8. User reviews the completed spread (all positions filled, all cards visible, orientation shown) before proceeding.
> 9. User explicitly triggers **Interpret My Reading** — interpretation is never automatic on spread completion. This is a deliberate UX gate, not just a button: it reinforces that the app is interpreting a fixed, already-real event, not generating content as cards are picked.
> 10. The Interpretation Engine analyzes the Reading and produces a structured **Interpretive Model**.
> 11. The Narrative Generation layer converts the Interpretive Model into natural-language prose (via the Reflection Engine, per Section 3.3).
> 12. If Scripture for Reflection is enabled, relevant Scripture is generated/looked up from the Interpretive Model's themes and shown in a visually separate section.
> 13. User can save the Reading.
> 14. The saved record preserves: cards, positions, question, orientation, layout, deck, draw method, and interpretation engine version — permanently, independent of future re-interpretation.

**User-triggered, not automatic — already decided, treated as settled by this audit, per the task's own instruction.** Step 9's wording is unambiguous and is not contradicted anywhere else in the Product Spec.

**Screen inventory (Section 6), the exact entries relevant to this step:**
> - **Spread Review** — full visual layout of all positions, cards, and orientations before committing to interpretation; edit-in-place still available here.
> - **Interpreting** — transient state while the Interpretation Engine + Narrative Generation run.
> - **Reading Result** — narrative sections (Central Theme, Tension, What the Spread Shows, Trajectory, What May Be Unclear, Advice, Clarification, Overall Reflection), optional Scripture for Reflection block (visually separated), optional "How did Raidian Wise arrive at this?" explainability panel, Save action.
> - **Reading History** — list of saved Readings, searchable/filterable.
> - **Reading Detail** — a saved Reading's full record (evidence + interpretation as generated); MVP does not require re-interpretation, but the schema must not block it.

**Presentation of interpretations (Explainability, Section 13, re-confirmed present):** an optional "How did Raidian Wise arrive at this?" panel is explicitly named as part of "Reading Result," directly implying the structured `InterpretiveModel` (with its citations) is meant to be user-facing, not merely an internal artifact the narrative is built from.

**Loading/error/retry behavior:** the Product Spec does not specify any loading/error/retry UX beyond naming "Interpreting" as a transient state. No retry semantics, no polling, no partial-failure behavior are specified anywhere in the Product Spec — consistent with `INTERPRETATION_API_DESIGN.md` Section 8's finding that the operation is synchronous and fast (Section 5 below).

**Reading History / resume:** Section 6 names both "Reading History" (list of *saved* Readings) and a separate "Reading Detail" screen it links to — already built (Step 52) for evidence; not yet extended for interpretation content (Section 9).

**One Product Spec/reality tension worth naming precisely (not new — already recorded in `PRODUCT_DECISIONS.md` Q1, restated here because it is directly load-bearing for this step):** Section 3 step 11 and Section 12 both describe Narrative Generation as running "via the Reflection Engine" (an AI gateway, per ADR-0005). **The actually-implemented Narrative Layer is deterministic, template-based, and calls no AI provider at all** — `PRODUCT_DECISIONS.md` Q1 already resolved (as a recommendation, "pending formal governance sign-off," not yet a ratified ADR/spec revision) that this deterministic layer is the *interim MVP substitute*, with an eventual AI-backed pass deferred indefinitely pending the platform's still-unbuilt Reflection Engine. This is pre-existing, already-documented drift, not a new finding — restated here only because any interpretation/narrative frontend work necessarily surfaces the deterministic `NarrativeModel`, not an AI-generated one, and should not describe it to a user as AI-assisted.

---

## 3. Existing Backend API Surface

Re-read directly from `backend/app/api/interpretation.py` (all four routes, in full) for this step — not assumed from `INTERPRETATION_API_DESIGN.md`'s own "proposed" framing.

| Method | Path | Auth | Request body | Response | Status codes |
|---|---|---|---|---|---|
| `POST` | `/readings/{reading_id}/interpret` | `Depends(get_owned_reading)` | none | `InterpretationSummary` | `201` success; `401` unauthenticated; `404` Reading not found/not owned; `409` Reading not spread-complete |
| `GET` | `/readings/{reading_id}/interpretations/current` | `Depends(get_owned_reading)` | — | `InterpretationSummary` | `200` success; `401`; `404` (not found, or never interpreted) |
| `GET` | `/readings/{reading_id}/interpretations` | `Depends(get_owned_reading)` | — | `list[InterpretationHistoryEntry]` | `200` (empty list `[]` if never interpreted — not `404`); `401`; `404` (Reading not found) |
| `GET` | `/readings/{reading_id}/narrative` | `Depends(get_owned_reading)` | — | `NarrativeModel` | `200`; `401`; `404` (not found, or never interpreted) |

**Ownership:** identical mechanism to every other Reading-scoped route (`get_owned_reading` — collapses nonexistent/not-owned/`NULL`-owner into one `404`), confirmed by direct import in `interpretation.py`. No separate ownership logic exists for these four routes.

**Reading-status requirements:** only `POST /interpret` has one — `reading.is_spread_complete` (the derived property, not `reading.status` directly) must be `True`, else `409` (`ReadingNotReadyForInterpretationError`, re-read directly from `reading_orchestration.py`). The three `GET` routes have no status requirement at all — they are gated only on "has this Reading ever been interpreted," independent of its current `status` value (a `SAVED` Reading's interpretation/narrative are exactly as retrievable as an `INTERPRETED` one's).

**Idempotency, re-verified directly against `interpret_reading()`'s own code and docstring:** **not idempotent.** Every successful `POST /interpret` call creates a new `Interpretation` row and returns `201`, even against unchanged evidence — there is no dedup, no conditional-request handling, no "nothing changed" response. Confirmed both by the orchestration function's own explicit docstring ("A new Interpretation row is always created on success, never reusing or overwriting a prior one... No duplicate-run detection or skipping is performed") and by `persistence.save_interpretation()`'s unconditional `Interpretation(...)` construction on every call.

**Repeated calls:** `POST /interpret` always regenerates (a new row every time). The three `GET` endpoints always return the **current** result (highest `Interpretation.sequence` for that Reading) — never a different or stale one, and never generate anything themselves.

**Interpretation vs. Narrative — independent or sequentially dependent?** Narrative is **derived from** Interpretation (an `Interpretation` row must exist for `GET /narrative` to return anything — `404` otherwise), but the two are **separately triggered/retrieved**: there is no combined endpoint, and `GET /narrative` does not itself create or require a fresh `POST /interpret` call in the same request — it reads whatever the *current* Interpretation already is. `PRODUCT_DECISIONS.md` Q5 (re-read directly) already resolved this as a **deliberate, permanent design**, not a temporary gap: "keep separate, unchanged... An AI-backed narrative call is far more likely to eventually need asynchronous handling... Keeping narrative retrieval on its own endpoint costs nothing and means... only `GET narrative`'s internals need to change" once the future AI-backed pass (Section 2) exists.

### 3.1 Discrepancies against the design documents

Comparing the actual implementation (above) against `INTERPRETATION_API_DESIGN.md`'s own Section 2/3/6 tables (its most detailed, most literally-comparable sections):

- **Route paths, HTTP methods, and response schemas match exactly** — `InterpretationSummary` (`id, reading_id, sequence, engine_version, reference_data_version, created_at, interpretive_model`) and `InterpretationHistoryEntry` (`id, sequence, engine_version, reference_data_version, created_at`) are both implemented field-for-field identical to that document's "illustrative, not final" sketches.
- **Status codes match, plus one addition the design document itself anticipated but explicitly declined to design: `401`.** `INTERPRETATION_API_DESIGN.md` Section 4/17 (Q1) explicitly stated authentication was "missing infrastructure that must be added later, by a separate, dedicated design effort" and that every route it designed would, "if implemented today exactly as designed, be fully unauthenticated." That separate effort (`AUTHENTICATION_OWNERSHIP_DESIGN.md`/`AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md`, Steps 20–23) has since happened, and `get_owned_reading` is now applied to these four routes exactly at the "insertion point" that document named (Section 5: "the future authorization check belongs exactly at [the] resolution point... verify the authenticated caller owns... that specific Reading before proceeding to any orchestration call"). **This is not a discrepancy or defect — it is the anticipated gap being closed by a later, separately-scoped series, in exactly the shape that document said it should be.**
- **`get_db()`'s commit-on-success gap, identified as a concrete existing defect by `INTERPRETATION_API_DESIGN.md` Section 14, has been fixed** — re-read directly from `backend/app/db/session.py`: the current `get_db()` commits on success and rolls back on exception, matching that document's own proposed fix essentially verbatim (its docstring even cites both design documents by name).
- **No other discrepancy found.** Idempotency, status-code-for-incomplete-spread (`409`), never-interpreted-yet behavior (`404` for singular resources, `200 []` for the history list), and the deliberate interpretation/narrative endpoint separation all match the design documents exactly.

---

## 4. Existing Interpretation Engine

Not redesigned here (per this step's own boundary) — summarized from direct source inspection for the purpose of establishing what a frontend would actually be consuming.

- **`app/services/interpretation/engine.py::interpret(reading, session) -> InterpretiveModel`** — deterministic, already proven so (`INTERPRETATION_ENGINE_VALIDATION.md`). Its only precondition is a non-empty `reading.card_draws` (weaker than "spread complete"); the *actual* completeness gate lives one layer up, in `reading_orchestration.interpret_reading()`'s `is_spread_complete` check (Section 3), exactly as `READING_INTEGRATION_DESIGN.md` Section 3 proposed and as the current code implements.
- **`InterpretiveModel`** (`app/schemas/interpretive_model.py`, re-read in full): `schema_version`, `engine_version`, `reference_data_version`, `generated_at`, `central_question`, `central_issue` (`Explained[str]`), `primary_tension` (`Explained[Tension] | None`), `supporting_themes` (`tuple[Explained[str], ...]`), `trajectory` (`Explained[Trajectory] | None`), `blocker` (`Explained[str] | None`), `uncertainty` (`tuple[str, ...]`), `advice` (`Explained[str] | None`), `clarification` (`Explained[str] | None`), `contradictions` (`tuple[Contradiction, ...]`), `evidence_strength` (`EvidenceStrength`). Every `Explained[T]` carries `citations: tuple[Citation, ...]` (`min_length=1` — a citation-bearing field can never be empty), and each `Citation` already embeds human-readable `card_name`/`position_name`/`position_semantic_role`, not just raw IDs — **a frontend explainability panel would not need to cross-reference `card_draw_id` back to Card Entry/Spread Review data to render a citation; the display text is already present in the API response.**
- **`generated_at`** is produced via `datetime.now(timezone.utc)` inside `engine.interpret()` — a real, in-memory, timezone-aware Python value at serialization time, not a database column (relevant to Section 11).
- **`compute_reference_data_version(session)`** runs fresh inside every `interpret()` call, stored on the resulting row — already correct by construction, nothing for the orchestration or API layer to do extra.

This layer is not implemented, extended, or found inconsistent by this step. `INTERPRETATION_RULES_DESIGN.md`'s supported/proposed/deferred rule classification is unchanged and not revisited.

---

## 5. Existing Narrative Layer

- **`app/services/narrative/assembler.py::assemble_narrative(model: InterpretiveModel) -> NarrativeModel`** — pure, deterministic, database-free (re-confirmed: `NARRATIVE_LAYER_DESIGN.md` Section 2/4's purity boundary is preserved by `reading_orchestration.get_narrative_for_reading()`, which performs the only database read in the entire narrative path and hands an already-materialized `InterpretiveModel` to this function).
- **`NarrativeModel`** (`app/schemas/narrative_model.py`, re-read in full): `schema_version`, `narrative_template_version`, `source_schema_version`, `source_engine_version`, `source_reference_data_version`, `generated_at`, `sections: tuple[NarrativeSection, ...]`. Every `NarrativeSection` (`id`, `title`, `source_field`, `present: bool`, `statements`) **always appears**, even when its source field was null (`present=False`, empty `statements`) — a frontend can render a fixed section list/order without conditionally hiding sections itself; `present` already tells it what to skip. Each `NarrativeStatement` carries pre-rendered `text` plus its own `citations` (copied verbatim from the source `InterpretiveModel` entry) — **narrative prose already arrives with its own citations attached, ready to render, with no additional client-side assembly.**
- **`generated_at`** here too is `datetime.now(timezone.utc)`, computed at call time — every `GET /narrative` call produces a fresh value (Section 9 below: never persisted/cached, recomputed on every call).
- **Deliberately not persisted, not cached, deterministic and re-derivable at any time** (`READING_INTEGRATION_DESIGN.md` Section 9, re-confirmed unchanged by any later document or code).

Not redesigned here. The `[A]`/`[B]`/`[A']` split (deterministic assembly / presentation / future AI rephrase) is unchanged; `[A']` remains entirely undesigned and out of scope for this step, same as every prior step in this series.

---

## 6. Current Reading Lifecycle

Re-verified directly against `app/models/enums.py::ReadingStatus`, `app/models/reading.py`, and `app/services/interpretation/persistence.py::save_interpretation`.

**Four values, exactly:** `drafting`, `spread_complete`, `interpreted`, `saved`. No fifth value exists; none is proposed by this document.

**Transitions, as actually implemented (re-verified, not assumed from `PRODUCT_DECISIONS.md`'s own recommendation text):**

| From | To | Trigger | Where |
|---|---|---|---|
| *(none)* | `drafting` | Reading created | `create_reading()` — column default |
| `drafting` | `spread_complete` | The draw that fills the last required position | `Reading.add_card_draw()` — automatic, synchronous with the draw itself |
| `drafting` / `spread_complete` | `interpreted` | `POST /interpret` succeeds | `save_interpretation()`: `if reading.status != SAVED: reading.status = INTERPRETED` |
| `interpreted` | `interpreted` | `POST /interpret` again (reinterpretation) | Same code path — idempotent reassignment, new `Interpretation` row regardless |
| `spread_complete` / `interpreted` | `saved` | `POST /readings/{id}/save` | `Reading.mark_saved()` — `409` (`ReadingNotSaveableError`) if still `drafting` |
| `saved` | `saved` | `POST /interpret` again | **Status is preserved, not regressed** — the one conditional branch in `save_interpretation()`; a new `Interpretation` row is still created |
| any | *(backward)* | — | **Never** — no code path anywhere assigns a status "earlier" than the current one |

**Which frontend actions are available in each state**, derived directly from the above (not invented):

| `reading.status` | Card Entry (`POST /draws`) | Interpret (`POST /interpret`) | View interpretation/narrative (`GET`s) | Save (`POST /save`) |
|---|---|---|---|---|
| `drafting` | Available (until the last required position is filled) | `409` — blocked (`is_spread_complete` is false) | `404` — none exists yet | `409` — blocked |
| `spread_complete` | `409` — blocked (evidence is locked) | Available | `404` until first triggered | Available |
| `interpreted` | `409` — blocked | Available (reinterpretation) | Available | Available (idempotent no-op if already saved... N/A here, not yet saved) |
| `saved` | `409` — blocked | Available (reinterpretation; status stays `saved`) | Available | Idempotent no-op (`mark_saved()` returns immediately) |

No new status is invented by this table — it is a direct transcription of already-implemented, already-tested behavior.

---

## 7. Current Frontend Flow (Post-Step-52)

Re-verified directly against the current `frontend/src/App.tsx`, `AppShell.tsx`, and every page file (six routes, all real — no placeholder route exists).

```
/login, /register  ──(public)──►  AppShell
/                   ──(auth)───►  HomePage: "Start a new reading" -> /readings/new
                                            "View reading history" -> /readings
/readings           ──(auth)───►  ReadingHistoryPage: GET /readings (saved only) -> click-through to /readings/{id}
/readings/new       ──(auth)───►  NewReadingPage: GET /spreads, POST /readings -> navigate to /readings/{id}/draw
/readings/:id/draw  ──(auth)───►  CardEntryPage: GET /readings/{id} + GET /cards, POST /readings/{id}/draws per card
                                            on completion: "View spread review" -> /readings/{id}, "Back to home" -> /
/readings/:id       ──(auth)───►  SpreadReviewPage: GET /readings/{id} only
```

**Nowhere in this flow does the frontend call `/interpret`, `/interpretations`, `/interpretations/current`, or `/narrative`** — confirmed by a repository-wide search of `frontend/src/`: no file contains any of those four path fragments. `SpreadReviewPage.tsx`'s completion banner ("This spread is complete... Interpreting this reading is not available yet") is explicit, accurate, static text — not a stub or a dead button.

**Where interpretation should logically enter the flow:** `SpreadReviewPage.tsx` is the only place in the current flow that already knows a Reading's `id` and `status`, and already renders a "spread is complete" state precisely when `status !== 'drafting'` — the exact condition `POST /interpret` also requires. This is the natural entry point for an "Interpret My Reading" action **as a call site**, matching the Product Spec's own flow ordering (Spread Review → Interpreting → Reading Result, Section 2). This is not the same question as "should the *result* render inside this same page or a new one" (Section 8/9) — it only identifies where the *trigger* naturally belongs, which the Product Spec's own step ordering already answers unambiguously.

**Not assumed:** this document does not assume Spread Review should *automatically* generate anything on load or on reaching `spread_complete` — Section 2's explicit-trigger requirement forecloses that regardless of screen-boundary choice.

---

## 8. Interpretation/Narrative Integration Options

Evaluated without ranking, per this step's instruction, even though Section 9 shows the Product Spec has in fact already settled the primary question.

**Option A — Interpretation as a section within Spread Review.** User sees interpretation content appended below the existing card grid on the same `/readings/:id` page once `status !== 'drafting'`. Trigger: a button rendered inline. API calls: `POST /interpret` on click, then `GET /narrative` (sequencing per Section 11). Persisted state: none beyond what already exists (`Interpretation` row). After refresh: the same page re-fetches `GET /readings/{id}` (unchanged) and would need a *second* fetch (`GET /interpretations/current` + `GET /narrative`) to know whether to show the interpretation section — `ReadingDetail` itself carries no interpretation-presence signal (Section 12). Return path: already on the Reading's own page; no navigation needed.

**Option B — Interpretation/Narrative as one separate "Reading Result" route.** A new route (e.g. `/readings/:id/result`), reached via a button/link from Spread Review. Trigger: an explicit button on Spread Review, or on the new route's own initial load. API calls: same as Option A, just on a different page. Persisted state: same. After refresh: this new route would need the same two-call check as Option A to render correctly, plus it must handle "not yet interpreted" (redirect back to Spread Review, or show its own trigger) since a direct URL visit is always possible. Return path: an explicit "Back to Spread Review" / "Back to History" link, same pattern as every other page in the current app.

**Option C — Interpretation and Narrative combined into one result screen.** Both `InterpretiveModel` (structured, citation-bearing) and `NarrativeModel` (prose) rendered together on one screen (either A's location or B's), e.g. prose sections as the primary content with an optional/expandable "How did Raidian Wise arrive at this?" panel showing the structured citations. API calls: both `/interpret` (or its `GET` equivalents on reload) and `/narrative`, sequenced per Section 11. This is not a *backend* combination (Section 3 confirms the two endpoints stay separate) — only a *frontend rendering* choice to show both on one screen.

**Option D — Interpretation and Narrative as separate screens.** A "structured/explainability" screen and a distinct "narrative/prose" screen, reached separately. API calls split across two page loads instead of one. Every other property (trigger, persistence, refresh, return) mirrors B, duplicated across two routes instead of one.

For **every** option: no new persisted state beyond the existing `Interpretation` row is required; the trigger is always an explicit user action (Section 2); refresh-correctness always depends on the same missing-signal gap named in Section 12; and the return path is always a plain link back into the existing route structure (History or Spread Review), since no new backend capability is needed for any of them.

---

## 9. Recommended Implementation Boundary — Established by the Product Spec, Not Invented Here

**The repository does establish this boundary — it is not left open.** `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6 (Section 2 above, quoted directly) names:
- **"Interpreting"** — a transient loading state (matches Option C/B's "generation in progress" moment, whichever route it lives on).
- **"Reading Result"** — one screen, combining narrative sections, an *optional* explainability panel (the structured `InterpretiveModel`/citations), and the Save action. This is **Option C** (combined), on a **screen distinct from Spread Review** (Option B/D's "separate route" shape, not Option A's "section within Spread Review") — the Product Spec lists "Spread Review" and "Reading Result" as two separate screen-inventory entries, not one.

**This is a fact this audit verified from the Product Spec's own text, not a preference this audit is expressing.** Per this step's own instruction ("If the Product Spec clearly settles the boundary, report that fact"), this document reports it as settled: **a dedicated "Reading Result" screen, entered from Spread Review via an explicit trigger, combining structured and narrative content with an optional explainability panel, plus the Save action.**

**What remains genuinely a frontend implementation choice, not settled by the Product Spec:**
- The exact route path/shape for "Reading Result" (`/readings/:id/result`, a query-param mode on the existing route, etc.) — not named by the Product Spec, which only names the screen conceptually.
- Whether "Reading Result" and the separately-Product-Spec-named **"Reading Detail"** screen (revisiting a *saved* Reading later, "evidence + interpretation as generated") are the same implemented route or two — the Product Spec names them as two conceptually distinct screens but does not forbid one implementation serving both, and `READING_DETAIL_API_DESIGN.md`'s own precedent (`GET /readings/{reading_id}` already serving both "Spread Review" and "Reading Detail" via one route, Step 42/50) suggests reuse is consistent with this project's established practice — but this document does not decide it (Section 15).
- The API sequencing shape (Section 11) — explicitly left open by `FRONTEND_INTEGRATION_DESIGN.md` Section 6, re-confirmed still unresolved.

---

## 10. Frontend State/Route Requirements

Derived directly from Sections 6–9, not speculative:

- A trigger point on `SpreadReviewPage.tsx` (or wherever Spread Review's completion banner ends up), active exactly when `reading.status !== 'drafting'` — matching the same condition already used for that banner today, requiring no new data the page doesn't already have.
- A new route for "Reading Result" (exact path undecided, Section 9), which needs: the Reading's `id` (from the URL, same pattern as every existing Reading-scoped route), the current `InterpretiveModel` (`GET /interpretations/current`, or the `POST /interpret` response directly on first generation), and the current `NarrativeModel` (`GET /narrative`).
- A "not yet interpreted" state for that route (a direct URL visit, or a refresh before triggering) — distinct from a loading state, and distinct from the "Interpreting" transient state itself.
- A Save action, reachable from this screen per the Product Spec — already fully backed by the existing, unmodified `POST /readings/{id}/save` and its frontend precedent nowhere yet exists in the built app (no Save UI has been built anywhere in this project's frontend so far, confirmed by the same repository-wide search as Section 7 — a real, previously-unflagged-as-such gap: Save has no frontend integration at all yet, independent of interpretation).

---

## 11. API Sequencing

Restates, does not resolve, `FRONTEND_INTEGRATION_DESIGN.md` Section 6's own framing, re-verified still accurate and still open:

- **Shape (a):** call `POST /interpret` then immediately `GET /narrative` before rendering "Reading Result" at all.
- **Shape (b):** render the structured/citation content from `POST /interpret`'s own response first (no second call needed — `InterpretationSummary` already embeds the full `interpretive_model`), then separately fetch `GET /narrative` for the prose layer, potentially rendering it in as it arrives.

Both are fully supported by the existing contract (Section 3) with no backend change either way. **On refresh / direct navigation to an already-interpreted Reading**, shape (a)/(b) converge: the page must call `GET /interpretations/current` (not `POST /interpret`, which would create a *new* row — see Section 13) plus `GET /narrative`. This document does not choose between (a)/(b) — it is a rendering-strategy choice, not a backend gap, exactly as `FRONTEND_INTEGRATION_DESIGN.md` already concluded.

---

## 12. Refresh/Resume Behavior

Traced against the actual API contract, not assumed:

| Scenario | What the backend already supports | Missing information? |
|---|---|---|
| Completes a reading, leaves | `Reading.status` persists as `spread_complete` (or later). `GET /readings/{id}` still works. | None — already fully supported (Step 50). |
| Returns through History | `GET /readings` lists it once `saved` (Step 52) → click-through to `/readings/{id}`. | None for evidence. **For interpretation presence**, see next row. |
| Refreshes Spread Review | `GET /readings/{id}` re-fetches full evidence state, unchanged behavior. | **`ReadingDetail` carries no signal of whether an Interpretation exists.** Re-confirmed directly: `ReadingDetail`'s schema (`app/schemas/reading_api.py`) has no `interpretation`/`has_interpretation`/`interpretation_count` field of any kind — `READING_DETAIL_API_DESIGN.md` Section 5 deliberately excluded one ("named here as an available future refinement, not designed further"). A page needing to decide "show an Interpret button, or a View Result button?" must make a **second** call (`GET /interpretations/current`, treating `404` as "not yet interpreted") — there is no way to answer this from `ReadingDetail` alone today. |
| Starts interpretation, leaves | Not a distinct state — `POST /interpret` either completes (synchronously, Section 3's `Synchronous` finding) or doesn't; there is no partial/pending state to resume, since the entire operation is a single fast, local, in-request computation with no background job. | None — there is no "interpretation in progress" state that could be interrupted and resumed; a page reload after a completed `POST /interpret` behaves identically to any other "returns after interpretation exists" case. |
| Returns after interpretation exists | `GET /interpretations/current` returns the full `InterpretationSummary` (`200`). | None — fully supported. |
| Returns after narrative exists | `GET /narrative` recomputes and returns the current `NarrativeModel` fresh, every time (never stale, never cached) — "returns after" is meaningless as a distinct state from "returns after interpretation exists," since narrative is always freshly derivable the instant an Interpretation exists. | None. |

**The one genuine missing piece, stated precisely per this step's instruction not to propose speculative implementation:** there is no cheap, single-call way for a page to know "has this Reading ever been interpreted?" without either (a) a second request to `GET /interpretations/current` (accepting its `404` as the negative signal) or (b) a new field added to `ReadingDetail`/`ReadingSummary` (a backend schema change, not authorized by or designed in this step). This is not a defect — `READING_DETAIL_API_DESIGN.md` already named and declined to add this field, on the grounds that no consumer needed it yet. A "Reading Result"/"Reading Detail" screen would be the first real consumer that does.

---

## 13. Error and Repeat-Generation Behavior

Traced directly against `interpretation.py`/`reading_orchestration.py`/`interpretation_api.py` — no invented semantics.

| Scenario | Actual backend behavior |
|---|---|
| Unauthorized user (no token) | `401`, identical body shape to every other route (`get_current_user`'s own rejection, via `get_owned_reading`). |
| Wrong / cross-user reading ID | `404`, identical body to a nonexistent ID — no distinction is ever exposed (same ownership-collapsing pattern as every other Reading-scoped route). |
| Incomplete reading (`POST /interpret`) | `409`, `detail: "reading {id} is not spread-complete: not every required position on its spread has a drawn card"` region — exact message re-read from `ReadingNotReadyForInterpretationError`, surfaced verbatim via the route's `HTTPException`. |
| Interpretation already exists, `POST /interpret` called again | **Succeeds, `201`, creates a genuinely new `Interpretation` row.** Not blocked, not deduplicated, not a `409`. |
| Narrative "already exists," `GET /narrative` called again | Not a meaningful scenario — every call recomputes; there is no persisted narrative to conflict with or return a stale copy of. |
| Repeated interpretation request | Same as "already exists" above — always creates another row (Section 3's idempotency finding). |
| Repeated narrative request | Always returns the current narrative freshly computed; harmless, no side effect, no rate-limit or dedup logic anywhere. |
| Backend failure (unexpected exception inside `interpret()`/`assemble_narrative()`) | Not caught by any route-level `try`/`except` in the current code (re-confirmed: `interpretation.py` only catches `ReadingNotReadyForInterpretationError`) — an unexpected exception propagates to FastAPI's default handler, an unstructured `500`. No retry, no partial-state cleanup needed (Section 3's transaction-boundary finding: nothing is left half-written, since `get_db()` rolls back the whole request on any exception). |

**No retry or idempotency semantics exist anywhere in this surface, and none should be invented by a future frontend design** — repeated user clicks on "Interpret My Reading" will genuinely create repeated `Interpretation` rows; a future implementation step should disable the trigger while a request is in flight (ordinary UI debouncing, not a backend concern) rather than relying on the backend to deduplicate.

---

## 14. Backend Gaps

Consistent with Section 3's finding, restated precisely: **no gap blocks building an Interpretation/Narrative frontend today.** The only items worth naming are refinements, not blockers:

- **No interpretation-presence signal on `ReadingDetail`/`ReadingSummary`** (Section 12) — already known, already named, already declined once (`READING_DETAIL_API_DESIGN.md` Section 5), not a defect.
- **No combined "Reading Result" convenience endpoint** — `INTERPRETATION_API_DESIGN.md` Section 9 already anticipated and declined to build one ("a future convenience aggregate endpoint... is a plausible later addition... not designed in detail here"), on the grounds that it would only compose already-existing calls. Still true; a frontend can fully build "Reading Result" today with the three-call sequence Section 11 describes, at the cost of those extra round-trips (all local/fast per Section 3's synchronous finding — not a real performance concern at this scale).
- **No Save-action frontend exists at all** (Section 10) — independent of interpretation, but directly relevant since the Product Spec places Save on the same "Reading Result" screen. The backend contract (`POST /readings/{id}/save`) has existed and been stable since Step 24; nothing new is needed there either.

Neither item requires backend code, schema, or migration changes to unblock a frontend implementation step; both are named as things a future step should decide whether to build (a new field/endpoint) or work around (extra calls), not things this step is deciding.

---

## 15. Open Product Decisions

Carried forward, not resolved:

- **Whether "Reading Result" and "Reading Detail" (Product Spec's two separately-named screens) are one implemented route or two** (Section 9) — this document's own new finding; not addressed by any prior document, since no prior step reached this specific question.
- **API sequencing shape for rendering Reading Result** — (a) vs. (b), Section 11, already named open by `FRONTEND_INTEGRATION_DESIGN.md` Section 6, still open.
- **Whether an interpretation-presence signal should be added to `ReadingDetail`** — Section 12/14, already named and declined once, still open.
- **Card artwork source/architecture** (`CARD_IMAGE_ASSET_DESIGN.md` OD-1/OD-2/OD-3) — restated, not touched by this step; irrelevant to interpretation/narrative rendering specifically (neither `InterpretiveModel` nor `NarrativeModel` references `image_ref` anywhere).
- **Roman-numeral card search aliasing** (`FRONTEND_INTEGRATION_AUDIT.md` Section 6) — restated, not touched by this step; unrelated to interpretation/narrative.
- **Whether History should include unsaved/in-progress Readings** (`FRONTEND_INTEGRATION_DESIGN.md` Section 7.3, `FRONTEND_INTEGRATION_AUDIT.md` Section 8) — restated, not touched here; tangentially relevant only in that an interpreted-but-unsaved Reading is exactly the case `PRODUCT_DECISIONS.md` Q3 already named as "correctly excluded from History... even though its data is fully durable," which remains true and unaffected by anything in this document.
- **The AI/Reflection-Engine narrative drift** (`PRODUCT_DECISIONS.md` Q1's still-outstanding governance action) — restated (Section 2), not resolved here; a future frontend should present the narrative as Raidian Wise's own deterministic reflection, not as an AI-generated response, until/unless that governance action changes what actually generates it.

Nothing above is decided by this document. None was silently resolved in the course of writing it.

---

## 16. Proposed Implementation Sequence for the Next Steps

Offered as a sequencing recommendation only, following this project's own established design → implementation pairing:

1. **A narrower, implementation-ready design step** resolving Sections 9/11/12/15's genuinely open questions (Reading Result vs. Reading Detail route boundary; sequencing shape; whether to add an interpretation-presence field) — the natural next step, since this document deliberately stopped short of deciding them.
2. **Implementation of the "Interpret My Reading" trigger** on Spread Review (or wherever Section 15's boundary decision places it), calling `POST /interpret` and navigating to the result screen.
3. **Implementation of the "Reading Result" screen** itself — structured content, narrative prose, optional explainability panel, Save action — consuming the already-existing, already-verified API surface (Section 3) with no backend change.
4. **Reading History → Reading Detail extension**, if Section 9's boundary decision calls for one — extending the existing `/readings/:id` route (or building a distinct one) to also show interpretation/narrative for a previously-saved Reading, reusing the same calls Step 2/3 already establish.

No step beyond this document is authorized by it.

---

## 17. Verification Evidence

- **Direct source reads performed for this step** (not reused from any prior step's report without re-checking): `backend/app/api/interpretation.py` (full), `backend/app/services/reading_orchestration.py` (full), `backend/app/services/interpretation/persistence.py` (full), `backend/app/models/enums.py` (`ReadingStatus`), `backend/app/models/reading.py` (`is_spread_complete`, `add_card_draw`, `mark_saved`, in full), `backend/app/db/session.py` (`get_db`), `backend/app/models/interpretation.py` (`TimestampMixin` usage), `backend/app/services/narrative/assembler.py` and `backend/app/services/interpretation/engine.py` (`generated_at` construction), `backend/app/schemas/interpretive_model.py`, `backend/app/schemas/narrative_model.py`, `backend/app/schemas/interpretation_api.py`.
- **Design documents re-read in full for this step:** `Documentation/READING_INTEGRATION_DESIGN.md`, `Documentation/INTERPRETATION_API_DESIGN.md`. `INTERPRETATION_ENGINE_DESIGN.md`/`INTERPRETATION_RULES_DESIGN.md`/`NARRATIVE_LAYER_DESIGN.md` were grepped directly for frontend/API assumptions (Section 4/5's summary) rather than fully re-read line-by-line, since all three explicitly predate and disclaim any frontend/API scope — confirmed by direct quotation of their own "no frontend exists yet"/"no API layer exists" boundary statements, not merely assumed from their titles.
- **`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Sections 3, 6 re-read directly** for this step (Section 2's quotations are verbatim).
- **`PRODUCT_DECISIONS.md` Q1/Q3/Q5 re-read directly**, cross-checked against actual current code behavior (e.g. Q5's "keep separate" recommendation checked against the actual, current absence of a combined endpoint — confirmed true).
- **Timestamp finding (Section 1, Section 11 cross-reference):** `Interpretation.created_at`'s shared `TimestampMixin` origin confirmed by direct class definition read (`class Interpretation(Base, UUIDPrimaryKeyMixin, TimestampMixin)`). `generated_at`'s different origin (`datetime.now(timezone.utc)`, in-memory, not a DB round-trip) confirmed by direct grep of both `engine.py` and `assembler.py`. This distinction was verified by source-code inspection only, not by an additional live HTTP round-trip (unlike Step 52's original finding, which *was* empirically verified live) — noted explicitly per this document's own "distinguish verified facts from recommendations" discipline; the reasoning (a real Python `tzinfo`-aware object serializes with an explicit offset, while a value round-tripped through SQLite's non-timezone-preserving storage does not) is standard, well-established behavior, not conjecture, but is flagged here as source-verified rather than live-verified for full transparency.
- **`git status` before this step:** identical to the end of Step 52 (no unexpected changes). **`git status` after this step:** only `Documentation/INTERPRETATION_NARRATIVE_FRONTEND_DESIGN.md` added as a new untracked file — verified below.
- **`git diff --check`:** run after creating this document — see the Step 53 final report for the exact output.
- No code was executed, no server was started, and no test suite was run for this step — a pure documentation/source-reading audit with zero code changes of any kind, so there is nothing to regress against; the most recently established backend test count (474 passed, 2 pre-existing warnings, unchanged since Step 50) stands.
