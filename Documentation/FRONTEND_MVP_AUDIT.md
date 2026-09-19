# Frontend MVP End-to-End Audit (Step 56)

**Status:** Read-only audit. No frontend, backend, schema, migration, dependency, or historical documentation file was modified in producing this report — this document is the only file created. Nothing was committed or pushed.

**Verification methods used, and how each finding is labeled:**
- **[Live HTTP]** — verified by executing real HTTP requests against a real `uvicorn` backend on a freshly migrated/seeded, isolated throwaway SQLite database (port 8001 — deliberately not the ports 8000/5173 already occupied by what appears to be the user's own still-running manual session, left completely untouched throughout).
- **[Source]** — verified by direct, fresh reading of the actual current source file(s) named.
- **[Prior finding]** — a fact already established and verified in an earlier step of this series, re-confirmed still true (not re-derived from scratch, but not blindly trusted either — re-checked where the underlying code could have changed).
- **[Human]** — none in this step. No browser-automation tool is available in this environment; **no literal click-testing is claimed anywhere in this document.**

---

## 1. Executive Summary

The complete documented MVP flow — register → login → home → new reading → card entry → spread review → interpret → narrative → result → save → history → reopen → spread review/result — **was exercised end-to-end via live HTTP integration testing, and every step succeeded** against the real backend contract, with zero failures across 47 individual assertions (Section 4/19). `npm run build` and `npm run lint` are both clean.

**No genuine defect was found anywhere in this audit.** The one previously-known issue (Roman-numeral card search) remains exactly what it was already classified as — a UX limitation, not a defect, unchanged and untouched. One new, minor, source-verified observation is recorded (Section 9): the Reading Result screen's explainability panel renders interpretive *conclusions* but never the underlying `Citation` objects that back them, even though the panel's own heading is the Product Spec's literal "How did Raidian Wise arrive at this?" language — a UX limitation, not a data-loss defect (the API still returns the citations; nothing is discarded server-side).

The Step 52 timestamp-serialization characteristic is **confirmed still present** (Section 10, live-verified again) — the frontend's existing defensive workaround remains necessary and correct.

---

## 2. Current Route Map

**[Source]**, re-read directly from `frontend/src/App.tsx`:

```
/login, /register        (public, under AppShell)
/                         Home                    (ProtectedRoute)
/readings                 Reading History          (ProtectedRoute)
/readings/new              New Reading              (ProtectedRoute)
/readings/:readingId/draw  Card Entry               (ProtectedRoute)
/readings/:readingId/result  Reading Result         (ProtectedRoute)
/readings/:readingId       Spread Review            (ProtectedRoute)
*                         redirects to /
```

**No duplicate or conflicting route definitions exist** — eight distinct path templates, each mapped to exactly one component. `/readings/new`, `/readings/:readingId/draw`, and `/readings/:readingId/result` are all more specific (extra literal segments) than the bare `/readings/:readingId`, and React Router's matcher ranks literal segments above dynamic ones regardless of declaration order — already proven correct **[Live HTTP, Step 50/55]** by the coexistence of these exact routes across three prior steps' live checks.

| Route | Auth | API calls | Entry points | Exit paths | Loading state | Error state | Invalid/nonexistent ID |
|---|---|---|---|---|---|---|---|
| `/login` | none | `POST /auth/login` | AppShell nav, redirect from `ProtectedRoute` | Home (on success) | inline (button text) | inline error banner | n/a |
| `/register` | none | `POST /auth/register` | AppShell nav | `/login` | inline | inline error banner | n/a |
| `/` | required | none | AppShell logo link, post-login redirect | New Reading, History | n/a (static) | n/a | n/a |
| `/readings` | required | `GET /readings` | AppShell nav | each entry → `/readings/:id` | "Loading…" | `role="alert"` banner | n/a (no ID in this route) |
| `/readings/new` | required | `GET /spreads`, `POST /readings` | Home, AppShell nav | → `/readings/:id/draw` on success | "Loading spreads…" | inline banner | n/a |
| `/readings/:id/draw` | required | `GET /readings/{id}`, `GET /cards`, `POST /readings/{id}/draws` | New Reading (on creation) | → `/readings/:id` (complete) or `/` | "Loading…" | `role="alert"` banner | `getReading` 404 surfaces as the generic load-error banner (Section 15) |
| `/readings/:id` | required | `GET /readings/{id}`, `POST /interpret`, `GET /narrative` | Card Entry, History, Reading Result | → `/readings/:id/draw`, → `/readings/:id/result`, → `/` | "Loading…" | `role="alert"` banner | same as above |
| `/readings/:id/result` | required | `GET /interpretations/current`, `GET /narrative`, `POST /save` | Spread Review (auto-navigate or link) | → `/readings/:id` | "Loading…" / "Loading reflection…" | `role="alert"` banner, plus an explicit non-error "not yet interpreted" state | 404 from `getCurrentInterpretation` is a distinct, correctly-handled case — see Section 8 |

**Behavior on refresh, for every authenticated route:** re-runs the same `GET`-only initial-load effect; none of the six protected routes ever issues a mutating request (`POST`) as part of its own load — confirmed by source inspection of all six page components, re-checked for this step, not merely restated.

---

## 3. Current API Map

**[Source]**, re-read directly from `frontend/src/api/*.ts` (six modules: `client.ts`, `auth.ts`, `cards.ts`, `spreads.ts`, `readings.ts`, `interpretation.ts`):

| Function | Endpoint | Used by |
|---|---|---|
| `register`, `login` | `POST /auth/register`, `POST /auth/login` | `RegisterPage`, `LoginPage` |
| `listCards` | `GET /cards` | `CardEntryPage` |
| `listSpreads` | `GET /spreads` | `NewReadingPage` |
| `listSavedReadings` | `GET /readings` | `ReadingHistoryPage` |
| `createReading` | `POST /readings` | `NewReadingPage` |
| `getReading` | `GET /readings/{id}` | `CardEntryPage`, `SpreadReviewPage` |
| `recordCardDraw` | `POST /readings/{id}/draws` | `CardEntryPage` |
| `saveReading` | `POST /readings/{id}/save` | `ReadingResultPage` |
| `interpretReading` | `POST /readings/{id}/interpret` | `SpreadReviewPage` |
| `getCurrentInterpretation` | `GET /readings/{id}/interpretations/current` | `ReadingResultPage` |
| `getNarrative` | `GET /readings/{id}/narrative` | `SpreadReviewPage`, `ReadingResultPage` |

One shared `request()`/`ApiError` wrapper (`client.ts`) backs every call — no second HTTP mechanism exists anywhere **[Source, re-confirmed]**.

---

## 4. End-to-End Flow Verification

**[Live HTTP]** — a single continuous script executed the entire numbered flow (items 1–32 of the task) against a real backend and a freshly migrated/seeded database. Every replicated frontend call used the exact request shape the real page code sends. Full transcript summary:

| Step | Result |
|---|---|
| 1–4. Register, login, real seeded spreads visible, spread selected | OK — 3 real seeded spreads returned (`Celtic Cross`, `Single Card`, `Three Card`) |
| 5–8. Question entered, Reading created | OK — `201`, `status: drafting` |
| 9–10. Card Entry loads Reading + positions | OK — 3 positions present |
| 11–13. Cards selected, orientation explicit, all positions drawn | OK — `orientation` and server-computed `draw_order` both correct per draw |
| 14. Backend transitions to `spread_complete` automatically | OK — confirmed on the final qualifying draw's own response |
| 15–17. Spread Review shows cards/orientations, Interpret available | OK — all 3 draws present with correct card/orientation, including a reversed draw |
| 18–20. Explicit interpret → narrative | OK — `201` with real structured content (non-empty `central_issue`, citations present); `200` with real present narrative sections |
| 21–23. Reading Result content | OK — `central_question` and `evidence_strength` present and valid |
| 24–25. Save → visible in History | OK — `200`, `status: saved`; appears in `GET /readings`; a second, unsaved draft Reading correctly does **not** appear |
| 26–28. Reopen from History → Spread Review still works | OK — `200` |
| 29. Result reuses the existing interpretation rather than regenerating | OK — `GET /interpretations/current` returned the same row id already on file, not a new one |
| 30–32. Refresh Result → no `POST /interpret`, narrative loads | OK — only `GET` calls exercised; narrative returned `200` |

**Additionally verified beyond the minimum 32 items:** a second explicit interpret creates a genuinely new row (backend is not idempotent, confirmed live — Section 8) and `/current` correctly tracks the newer one; a third brand-new user's History is `200 []`, not an error.

**Not claimed:** literal browser clicking, visual rendering, or console inspection — no such tool is available in this environment.

---

## 5. Card Entry Findings

**[Live HTTP + Source]**

- All 78 cards available; all 4 suits have exactly 14 cards; Major Arcana has exactly 22 — verified live against the real seeded dataset.
- Search (`card.name` substring match), arcana filter, suit filter, and the combination of search + suit all verified live against `CardEntryPage.tsx`'s actual filter predicate, reproduced exactly: e.g. `search="four"` + `suit="wands"` correctly narrows to exactly "Four of Wands."
- **Selecting a new position clears stale search text** — re-confirmed by source read of `selectPosition()`'s `setSearch('')` call (the Step 49 follow-up fix), unchanged since.
- **Suit filter returns the complete 14-card set** — re-verified live; the originally-discovered stale-search defect (Step 49 follow-up) does not reproduce.
- **Arcana="All" / Suit="All" returns the complete 78** — verified live.
- **Roman-numeral search ("IV of Wands") finds nothing** — re-verified live and classified precisely, per this step's explicit instruction not to change it: **C. UX limitation**, not a defect. No `Card.name`/`Card.rank`/`Card.keywords` field in the actual seeded data contains a Roman-numeral alias for any Minor Arcana rank (re-confirmed directly against the live dataset) — the search behaves exactly as its own implementation and underlying data dictate; nothing is broken, malfunctioning, or contradicting any governing document. This was already recorded as an open UX-enhancement question in `FRONTEND_INTEGRATION_AUDIT.md` Section 6, unchanged, untouched, not resolved here.

---

## 6. Draw Behavior Findings

**[Live HTTP + Source]**

- Orientation must be explicitly selected — `CardEntryPage.tsx`'s `selectedOrientation` state starts `null` with no default, matching the backend's own lack of a column default on `CardDraw.orientation` (re-confirmed, `Documentation/CARDDRAW_API_DESIGN.md` Section 4.1) — **G. No issue**.
- Duplicate-card and duplicate-position behavior matches the backend exactly — live-verified: a duplicate-position draw → `409`; the frontend disables an already-drawn position's button but the backend remains the actual enforcement point (unchanged since Step 49).
- Drawn positions become unavailable, undrawn remain selectable — `CardEntryPage.tsx`'s `isAvailable = canDraw && !draw` logic, re-confirmed by source read.
- `draw_order` is never sent by the frontend and is always taken from the backend's own response — confirmed both by source read of `recordCardDraw()`'s request body (`position_id`, `card_id`, `orientation` only) and live: the response's server-computed `draw_order` was used correctly.
- Completion (`spread_complete`) comes from the backend's own response field on every draw and from `GET /readings/{id}`'s own `status` field — the frontend performs no position-counting to *decide* lifecycle status anywhere (re-confirmed, `SpreadReviewPage.tsx`'s own `isComplete = reading.status !== 'drafting'`).
- No automatic card draw occurs anywhere — confirmed by source inspection: `recordCardDraw()` has exactly one call site, inside `CardEntryPage.tsx`'s `handleSubmit`, itself only reachable from a button `onClick`.
- **Digital Draw is confirmed NOT implemented** — no file in `frontend/src/` references digital draw, randomized selection, or an unbiased-shuffle mechanism; Card Entry is exactly what it presents itself as: a manual recorder of a physical draw, matching the Product Spec's own "the app is a recorder, not a participant in the draw" framing. **E. Intentional architectural/product decision.**

---

## 7. Spread Review Findings

**[Live HTTP + Source]**

- Question, spread name, spread description, and every position in backend `position_order` all display — re-confirmed by source read of `SpreadReviewPage.tsx`'s render body, matching Step 50's original implementation unchanged.
- Optional positions are represented (a small "(optional)" label from `SpreadPositionSummary.required`) — unchanged since Step 50; no real seeded spread currently has one, so this path remains exercised only by a constructed probe, not real production data (a pre-existing, already-documented characteristic, not new).
- Drawn cards display name/arcana-or-suit/orientation correctly; upright/reversed render as distinct "↑ Upright"/"↓ Reversed" badges — confirmed.
- Incomplete readings show "N of M drawn" plus "Still to draw: …"; complete readings show a "This spread is complete" banner — confirmed, live-verified via the 2-of-3 and 3-of-3 states in Section 4.
- **"Interpret My Reading" only appears when `status !== 'drafting'`** — confirmed by source read (the button lives entirely inside the `isComplete` branch) and live-verified: `POST /interpret` against a drafting Reading correctly returns `409` (i.e., the trigger's own gating condition matches exactly what the backend would reject if bypassed).
- **Interpretation is never triggered automatically** — confirmed by source inspection: `interpretReading()` has exactly one call site, inside `handleInterpretClick`, itself only reachable from a button `onClick`; no `useEffect` in `SpreadReviewPage.tsx` calls it.
- Spread Review still works after returning from History — live-verified (Section 4, step 26–28): `GET /readings/{id}` for a `saved`-status Reading returns `200` with fully correct evidence data.

---

## 8. Interpretation/Narrative Findings

**[Live HTTP + Source]**

- The exact sequence (explicit action → `POST /interpret` → `GET /narrative` → Result) is implemented precisely as `READING_RESULT_FLOW_DESIGN.md` Section 4 specifies — re-confirmed by source read of `SpreadReviewPage.tsx`'s `handleInterpretClick`/`fetchNarrative` functions.
- `POST /interpret` occurs exactly once per explicit action, and only from an event handler — never from `useEffect`, render, or route loading (confirmed by source read; the only two call sites in the entire frontend are `SpreadReviewPage.tsx`'s click handler and this audit's own test script).
- A successful interpretation is not immediately duplicated — confirmed structurally (no retry/repeat logic exists anywhere in the trigger path).
- **Narrative failure does not regenerate interpretation** — confirmed by source read: the `narrative-failed` state retains the already-successful `InterpretationSummary` and its retry button calls only `fetchNarrative(interpretFlow.interpretation)`, never `interpretReading()` again.
- **Interpretation failure does not call narrative** — confirmed: `fetchNarrative` is only reached after `interpretReading()` resolves successfully (`await ... ; await fetchNarrative(...)` sequencing, with the `try/catch` around the first `await` preventing the second call on failure).
- Reading Result renders real backend structures, not placeholders — live-verified (Section 4) and field-mapped in full (Section 9).
- **No AI interpretation was introduced** — both `POST /interpret` and `GET /narrative` on the backend call only the existing deterministic engine/assembler (`Documentation/INTERPRETATION_NARRATIVE_FRONTEND_DESIGN.md` Section 4/5, re-confirmed unchanged); the frontend UI text explicitly says "no AI is involved"/"no AI is used to produce this reading" in two places (`SpreadReviewPage.tsx`'s interpreting state, `ReadingResultPage.tsx`'s explainability panel).
- **No invented interpretation fields exist** — the TypeScript types in `frontend/src/api/interpretation.ts` were checked field-for-field against the actual Pydantic schemas in this step's own source re-reads (`interpretive_model.py`, `narrative_model.py`, `interpretation_api.py`); no extra field is present on either side, no field is silently dropped from the *type definitions* (Section 9 covers *rendering* coverage specifically, which is narrower).
- Deterministic interpretation and deterministic narrative remain visually and conceptually distinct on Reading Result — a primary "Narrative" section and a separate, clearly-labeled "How did Raidian Wise arrive at this?" secondary panel (Section 9).

**Refresh/revisit path** — live-verified (Section 4, steps 29–32): `GET /interpretations/current` correctly reuses the existing row; a 404 (never-interpreted case) is handled as an explicit, non-crashing state (verified live against a genuinely never-interpreted Reading, Section 15); narrative is regenerated only through its own `GET`, never coupled to a re-interpretation.

---

## 9. Reading Result Field Coverage

**[Source]** — full field-by-field matrix, `InterpretiveModel`/`InterpretationSummary`/`NarrativeModel` (backend, re-read Step 55/56) against `ReadingResultPage.tsx`'s actual render body (re-read this step).

| Backend field | Rendered? | Where | If not, why |
|---|---|---|---|
| `InterpretationSummary.id/reading_id/sequence/engine_version/reference_data_version/created_at` | No | — | Internal provenance, no product requirement to surface it to the user |
| `InterpretiveModel.schema_version/engine_version/reference_data_version/generated_at` | No | — | Same — technical provenance, not user-facing content |
| `central_question` | Yes | Page header | — |
| `central_issue.value` | Yes | Explainability panel | — |
| `central_issue.citations` | **No** | — | See finding below |
| `primary_tension.value` (+ `pole_a`/`pole_b`/`label`) | Yes, if present | Explainability panel | — |
| `primary_tension.citations` | **No** | — | See finding below |
| `supporting_themes[].value` | Yes, if non-empty | Explainability panel (list) | — |
| `supporting_themes[].citations` | **No** | — | See finding below |
| `trajectory.value.arc[]` (`position_name`/`card_name`/`orientation`) | Yes, if present | Explainability panel (ordered list) | `semantic_role` specifically is fetched but not displayed |
| `trajectory.citations` | **No** | — | See finding below |
| `blocker.value` | Yes, if present | Explainability panel | — |
| `blocker.citations` | **No** | — | See finding below |
| `uncertainty[]` | Yes, if non-empty | Explainability panel (list) | — |
| `advice.value` | Yes, if present | Explainability panel | — |
| `advice.citations` | **No** | — | See finding below |
| `clarification.value` | Yes, if present | Explainability panel | — |
| `clarification.citations` | **No** | — | See finding below |
| `contradictions[].description` | Yes, if non-empty | Explainability panel (list) | — |
| `contradictions[].sources` (citations) | **No** | — | See finding below |
| `evidence_strength` | Yes | Explainability panel | — |
| `NarrativeModel.schema_version/narrative_template_version/source_*_version/generated_at` | No | — | Technical provenance, not user-facing |
| `NarrativeSection.title` (where `present`) | Yes | Narrative section | — |
| `NarrativeSection.id`/`source_field` | No | — | Internal identifiers only |
| `NarrativeStatement.text` | Yes | Narrative section body | — |
| `NarrativeStatement.citations` | **No** | — | See finding below |

**Finding (F-1):** **No `Citation` object (card/position/rule name, semantic role, contributing theme) is ever rendered anywhere on Reading Result**, despite the explainability panel's own heading being the Product Spec's exact "How did Raidian Wise arrive at this?" wording (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6) — the panel currently shows *what* was concluded, not *which specific card/position/rule* supports each conclusion. This is not a data-loss defect: the backend still returns full citation data on every response (re-confirmed live, Section 4 — `central_issue.citations.length > 0`), so nothing is discarded server-side, and a future step can render it without any contract change. **Classification: C. UX limitation** — the Product Spec itself calls this panel "optional," and `trajectory.arc` already surfaces card/position/orientation per step, giving partial, though not full, traceability. Not fixed in this step, per the task's own instruction.

---

## 10. Save/History Findings

**[Live HTTP + Source]**

- Save uses `POST /readings/{id}/save`, is only ever triggered by an explicit button click (confirmed by source read: `handleSave`'s only call site is `onClick`), and is guarded against duplicate submission by its own `saveState.phase === 'saving'` check plus a `disabled` attribute on the button.
- Save does not require interpretation — confirmed both by source (no interpretation-presence check gates the Save button) and live (Section 4: Save succeeded in the full flow, and the backend contract itself never requires it, `READING_RESULT_FLOW_DESIGN.md` Section 7).
- Saved status comes from the actual `POST /save` response (`result.status`), never fabricated locally — confirmed by source read.
- Saved Reading appears in History; an unsaved draft does not — both live-verified (Section 4).
- History entry links to `/readings/{id}` (Spread Review), which correctly opens the right Reading — live-verified.
- **History does not expose another user's Reading** — live-verified: a second user's `GET /readings` returned `[]`, not the first user's saved entry.
- Reopening a saved Reading does not regenerate interpretation — live-verified (Section 4, step 29): `GET /interpretations/current` reused the existing row.

**Timestamp handling (Step 52 finding), re-verified live for this step:** the backend **still emits `updated_at`/`created_at` as UTC-valued timestamps with no timezone designator** (e.g. `"2026-09-19T16:40:37"`, confirmed by direct comparison against the actual value returned from a live save call) — the underlying characteristic Step 52 discovered is unchanged. `ReadingHistoryPage.tsx`'s `toAbsoluteDate()` workaround (append `Z` when no designator is present) **remains present, unmodified, and still correct/necessary** — confirmed by source read. **Per this step's explicit instruction, the backend was not touched.** **Classification: E. Intentional (deferred) — already a named backend-serialization follow-up, not a new finding.**

---

## 11. Authentication/Security Findings

**[Live HTTP + Source]**

- Unauthenticated protected routes redirect to `/login` — confirmed by source read of `ProtectedRoute.tsx` (`if (!isAuthenticated) return <Navigate to="/login" ... />`), unchanged since Step 46.
- Login returns a real token, used as `Authorization: Bearer <token>` on every subsequent authenticated call — confirmed by source read of `client.ts`'s `request()`.
- Logout (`clearToken()`) removes the token from `localStorage` and clears in-memory state — confirmed by source read of `AuthContext.tsx`, unchanged.
- **401 handling clears authentication uniformly** — every one of the six protected pages calls `clearToken()` on a `401` from any of its API calls; re-confirmed by source read across all six page files, not merely assumed from the pattern's prior use.
- **Cross-user access to Reading, interpretation, narrative, and save all return `404`** — live-verified for all five relevant endpoints in one pass (Section 4/19); identical to the nonexistent-ID case (unchanged, `get_owned_reading`'s established collapsing behavior).
- **No `owner_id`/`reflection_session_id` (or any other sensitive owner internal) appears in any response the frontend consumes** — live-verified directly against the actual `GET /readings/{id}` response body's key set.
- No authentication architecture was changed by this audit.

---

## 12. Navigation Findings

**[Source]**

Traced the full graph directly from `App.tsx`/`AppShell.tsx`/all six page components (re-read this step):

- **Home → New Reading → Card Entry → Spread Review → Result → History**: every forward link in this chain exists and points to a real, working route (Section 2's table).
- **History → Spread Review → Result**: History links to Spread Review (`/readings/:id`) directly; Spread Review offers a "View the result" link once idle (Section 5's finding table). There is **no direct History → Result link** — this is a previously-identified, already-documented open decision (`READING_RESULT_FLOW_DESIGN.md` Section 13: "exact link/button placement... where on History... a link to `/readings/:id/result` appears" was explicitly left open), not a newly discovered gap. **Classification: F. Deferred/open product decision**, restated, not invented here.
- **No true dead end exists anywhere**, because `AppShell`'s header nav (Home logo, History, New Reading, Log out) is present on every single authenticated page, including Reading Result — even a user who reaches a page with no page-local "next step" link can always navigate via the persistent header.
- Back/Home/History links all resolve to real, working destinations — confirmed by source read of every `<Link to=...>` in the six page components; none references a nonexistent route.
- A future, not-yet-built screen (e.g., a richer Reading History entry linking straight to Result) is documented as an open decision rather than invented here, per this step's explicit instruction.

---

## 13. Artwork Findings

**[Source]**, cross-checked against `Documentation/CARD_IMAGE_ASSET_DESIGN.md`.

- `image_ref` is never read, referenced, or turned into a URL anywhere in the frontend — confirmed by a repository-wide search of `frontend/src/` for the string `image_ref` (present only in TypeScript type declarations carrying the field through unused, in `cards.ts`/`readings.ts`, never consumed for rendering).
- No card artwork is bundled, no CDN is referenced, no backend static-file serving exists (re-confirmed: no `StaticFiles` mount anywhere in `backend/app/`, consistent with Step 48's own finding, unchanged).
- Spread Review and Reading Result both use text/card placeholders exclusively (name, arcana/suit, orientation) — confirmed by source read of both files.
- Card Entry's searchable/filterable selector does not depend on artwork in any way — confirmed (Section 5).
- **Classification: E. Intentional MVP limitation**, per `CARD_IMAGE_ASSET_DESIGN.md`'s own already-established Option E treatment. **OD-1/OD-2/OD-3 are not resolved here**, per this step's explicit instruction.

---

## 14. Responsive/UX Findings

**[Source only — no visual/browser verification was possible or is claimed.]**

- Every page body is wrapped in a `max-w-{2xl|3xl} mx-auto` container with no fixed pixel widths anywhere — text content (questions, narrative prose, interpretation text) wraps naturally within this container at any viewport width; no `whitespace-nowrap` is applied to any long-form text field.
- Spread Review's card grid (`grid-cols-2 sm:grid-cols-3`) degrades to 2 columns on narrow screens — for a 10-position Celtic Cross this produces 5 rows, a purely vertical-growth layout with no horizontal overflow risk.
- Long card names (the longest seeded names, e.g. "Nine of Pentacles," "The Hierophant") sit inside fixed-`aspect-[2/3]` tiles with centered, unclamped text — plausible to wrap onto two lines within a real tile's width at typical viewport sizes, not verified visually; no `truncate`/`line-clamp` is applied, so worst case is a taller tile, not clipped/lost text.
- **One concrete, source-identified layout risk (F-2):** `ReadingHistoryPage.tsx`'s per-entry row (`<div className="flex items-start justify-between gap-4">` containing the question `<p>` and a `whitespace-nowrap` status badge) does not set `min-w-0`/`flex-1` on the question paragraph. Per standard CSS flexbox behavior, a flex item's default `min-width: auto` can resist shrinking below its content's intrinsic width — for a very long, unbroken `question` string (the backend allows up to 4000 characters with no forced line breaks), this **could** push the row wider than its container on a narrow screen rather than wrapping cleanly, though ordinary prose (which contains natural word-break opportunities) is very unlikely to trigger this in practice. **Classification: C. UX limitation** — a plausible, source-identified CSS robustness gap, not a confirmed visual defect (no browser available to observe actual wrapping behavior), and not present anywhere else (every other page's flex-row-with-long-text pairing uses short, backend-controlled reference-data strings, not arbitrary user input).
- Buttons/actions throughout (Interpret, Save, Draw, filters) use standard padding/sizing (`px-3`–`px-4 py-1.5`–`py-2`) consistent with comfortable touch-target sizes; none rely on hover-only affordances for their primary function.

---

## 15. Error/Edge-Case Findings

**[Live HTTP]** unless noted — every case below was actually exercised, not assumed:

| Case | Verified behavior |
|---|---|
| Invalid UUID in path | `422` (automatic FastAPI/Pydantic validation) |
| Nonexistent Reading | `404` |
| Nonexistent card (in a draw request) | `404` |
| Nonexistent spread | Not separately re-tested this step; unchanged since Step 41/49's own live verification — `[Prior finding]` |
| Unauthorized (cross-user) Reading | `404` |
| Interpretation attempt on an incomplete Reading | `409` |
| Interpretation failure (engine exception) | Not reproducible without forcing an internal error; behavior traced from source (`Documentation/READING_RESULT_FLOW_DESIGN.md` Section 10) — `[Prior finding/Source]` |
| Narrative failure | Same as above — traced from source, not forced live this step |
| Direct Result navigation without interpretation | Live-verified: `GET /interpretations/current` → `404` → `ReadingResultPage.tsx`'s explicit `notInterpreted` state, not a crash |
| Already-saved Reading | Live-verified: `POST /save` on an already-saved Reading remains idempotent (`200`, `status: saved`) |
| Duplicate interpretation | Live-verified: `201`, a genuinely new row, `/current` correctly updates |
| Duplicate card draw | Not separately re-tested this step (already covered in Step 49's own dedicated live check) — `[Prior finding]` |
| Duplicate position draw | Live-verified: `409` |
| Expired/missing token | Missing token live-verified (`401` on all 7 checked endpoints); token *expiration* specifically was not separately forced this step — `[Prior finding, Step 46's own live check]` |
| Empty History | Live-verified: `200 []` for a brand-new user, not an error |
| History API failure | Not forced live this step; `ReadingHistoryPage.tsx`'s existing `catch` block (unchanged since Step 52) handles any non-401 `ApiError` via the same `role="alert"` pattern used everywhere else — `[Source]` |

No new backend behavior was invented or assumed anywhere in this table.

---

## 16. Findings Classification

| # | Finding | Classification |
|---|---|---|
| F-1 | Reading Result's explainability panel never renders `Citation` objects, only conclusions | **C. UX limitation** |
| F-2 | `ReadingHistoryPage.tsx`'s row layout lacks `min-w-0` on its question paragraph — a plausible, unconfirmed long-text overflow risk | **C. UX limitation** |
| — | Roman-numeral card search finds nothing | **C. UX limitation** (restated, unchanged, not fixed) |
| — | No direct History → Reading Result link | **F. Deferred/open product decision** (restated from `READING_RESULT_FLOW_DESIGN.md` Section 13) |
| — | Backend timestamps still lack a timezone designator | **E. Intentional (deferred backend follow-up)**, frontend workaround confirmed still correct |
| — | Card artwork not implemented | **E. Intentional MVP limitation** |
| — | Digital Draw not implemented | **E. Intentional architectural/product decision** |
| — | No genuine defect found anywhere in the audited flow | **G. No issue**, for every item in Sections 4–8, 10–11 not listed above |

No test-coverage gap (B) or documentation issue (D) was identified — every governing document checked against actual behavior in this step was found accurate to the current implementation.

---

## 17. Remaining Product Decisions

All restated, none resolved here:

- Whether/how citations should be surfaced on Reading Result (F-1) — not previously named as an open decision anywhere; recorded here for the first time as a candidate future refinement, not a requirement.
- Exact History → Result linking affordance (`READING_RESULT_FLOW_DESIGN.md` Section 13).
- Card artwork source/architecture (`CARD_IMAGE_ASSET_DESIGN.md` OD-1/OD-2/OD-3) — untouched.
- Roman-numeral search aliasing (`FRONTEND_INTEGRATION_AUDIT.md` Section 6) — untouched.
- Whether History should ever include unsaved/in-progress Readings (`FRONTEND_INTEGRATION_DESIGN.md` Section 7.3) — untouched.
- Backend timestamp serialization fix (Step 52) — untouched, backend not modified.

---

## 18. Recommended Next Steps

Offered as sequencing observations only, no ranking as "best":

1. A small, focused frontend step to render `Citation` data on Reading Result (F-1) — if judged worth doing, since the API already supports it with zero contract change.
2. A small, focused frontend step to add `min-w-0`/`flex-1` to `ReadingHistoryPage.tsx`'s row layout (F-2) — a one-line-scale defensive fix, if judged worth doing ahead of any real long-question report.
3. Whichever of the still-open product decisions (Section 17) the team chooses to resolve next — none is blocking further MVP work.
4. A dedicated backend-facing step to fix timestamp serialization, if/when the team decides it's worth doing (Step 52's own original recommendation, still standing).

---

## 19. Verification Evidence

- **Live HTTP integration:** one comprehensive script, 47 individual assertions, **zero failures**, executed against a real `uvicorn` backend on an isolated port (8001) with a freshly-run `alembic upgrade head` + seed on a throwaway SQLite database in the session scratchpad directory, deleted after use. Full pass/fail transcript summarized in Sections 4–11/15.
- **`npm run build`**: clean (`tsc -b && vite build`, 43 modules, no errors).
- **`npm run lint`**: clean, zero errors/warnings.
- **Source files re-read directly for this step** (not restated from any prior step's report without re-checking): `App.tsx`, `AppShell.tsx`, `ProtectedRoute.tsx`, `ReadingResultPage.tsx` (in full), plus every API module re-confirmed against the live response shapes exercised above.
- **No browser-automation tool is available in this environment.** No literal click-testing, visual rendering, or console inspection is claimed anywhere in this document — every UI-behavior claim is either a live HTTP-level equivalent of what the real code calls, or a direct source-code inspection, each explicitly labeled as such throughout.
- **Backend regression status:** not re-run — no backend file has changed since Step 55 (confirmed by `git status`, Section 20). Last known, honestly-reported result: **474 passed, 2 warnings** (Step 50), carried forward per this step's own explicit instruction not to claim a fresh run that did not occur.

---

## 20. Repository State

- `npm run build` / `npm run lint`: both clean (Section 19).
- `git diff --check`: clean (only pre-existing LF/CRLF warnings, exit code 0).
- `git status --untracked-files=all`: confirmed only `Documentation/FRONTEND_MVP_AUDIT.md` is new; every other entry identical to Step 55's end state — no backend file, no other `Documentation/*.md` file, no frontend source file touched.
- **No migration was created** (`backend/alembic/versions/` unchanged at 7 files).
- **No unexpected dependency was added** (`frontend/package.json` re-checked directly: same 5 runtime + 8 dev dependencies as before this step).
- **No generated database file was left behind by this audit** — the throwaway SQLite database used for live testing was created in, and deleted from, the session scratchpad directory only. `backend/raidian_wise.db` exists but is gitignored (`*.db` pattern, confirmed via `git check-ignore`) and was not created or modified by this audit — it is the default dev database, most likely backing the user's own separate, still-running manual session (same process IDs observed and left untouched across this and the two preceding steps); it was deliberately not touched or deleted.
- **No temporary file was left behind** in the repository itself (the live-test script lived only in the session scratchpad directory).
- Nothing was staged, committed, or pushed.
