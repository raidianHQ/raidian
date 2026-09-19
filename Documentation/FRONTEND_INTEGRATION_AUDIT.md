# Frontend Integration Audit — After First Human End-to-End Run (Step 51)

**Status:** Read-only audit. No application code, schema, migration, dependency, or historical documentation file was modified in producing this report. Nothing was committed or pushed. Every claim below was verified directly against the current repository — file reads, a full frontend source inventory, and direct backend route/schema reads — not restated from any prior step's report without re-checking.

**Point-in-time:** immediately after Steps 46–50 (frontend foundation, New Reading, Card Entry, the Card Entry search bugfix, and Spread Review) plus a first human manual run through the real application.

---

## 1. Frontend Architecture — Verified Directly

Full current source inventory (`frontend/src/`, re-listed for this step, not assumed):

```
App.tsx
api/auth.ts, api/cards.ts, api/client.ts, api/readings.ts, api/spreads.ts
auth/AuthContext.tsx, auth/context.ts, auth/useAuth.ts
components/AppShell.tsx, components/ProtectedRoute.tsx
main.tsx
pages/CardEntryPage.tsx, pages/HomePage.tsx, pages/LoginPage.tsx,
pages/NewReadingPage.tsx, pages/RegisterPage.tsx, pages/SpreadReviewPage.tsx
vite-env.d.ts
```

**Routing** (`App.tsx`, current content re-read for this step):

```tsx
<Routes>
  <Route element={<AppShell />}>
    <Route path="/login" element={<LoginPage />} />
    <Route path="/register" element={<RegisterPage />} />
    <Route element={<ProtectedRoute />}>
      <Route path="/" element={<HomePage />} />
      <Route path="/readings/new" element={<NewReadingPage />} />
      <Route path="/readings/:readingId/draw" element={<CardEntryPage />} />
      <Route path="/readings/:readingId" element={<SpreadReviewPage />} />
    </Route>
    <Route path="*" element={<Navigate to="/" replace />} />
  </Route>
</Routes>
```
Six routes total, all real (not placeholder). No route exists yet for Reading History, Interpretation, or Narrative — confirmed by the inventory above: there is no `pages/*History*`, `*Interpretation*`, or `*Narrative*` file anywhere in the tree.

**API layer**: one shared `fetch` wrapper (`api/client.ts`'s `request<T>()` + `ApiError`), five thin per-resource modules (`auth.ts`, `cards.ts`, `readings.ts`, `spreads.ts`) that each call it. No second HTTP mechanism exists anywhere. `readings.ts` currently exposes exactly four functions: `listSavedReadings`, `createReading`, `getReading`, `recordCardDraw` — no interpretation/narrative call exists in the frontend anywhere (confirmed by inventory; no file imports `/interpret`, `/interpretations`, or `/narrative`).

**Authentication**: `AuthContext`/`useAuth`/`context.ts` (Step 46), `localStorage`-backed under `raidian.token`, `ProtectedRoute` redirecting unauthenticated visitors to `/login`. Unchanged since Step 46; still the only auth mechanism.

**Page/component structure**: 6 pages, 2 shared components (`AppShell`, `ProtectedRoute`), no third-party UI library, no component beyond what's listed above. Everything under `pages/` corresponds to a real, wired route — nothing is documented-but-unbuilt at the routing layer.

**Implemented vs. documented-only**: every endpoint `FRONTEND_INTEGRATION_DESIGN.md`'s Section 5 endpoint table lists as needed for Register/Login/Home/New Reading/Card Entry/Spread Review is both documented and actually wired. Everything that table lists for Interpretation, Reading Result, Save, and History (`POST /interpret`, `GET /interpretations(/current)`, `GET /narrative`, `POST /save`, `GET /readings`) is documented and exists on the backend, but has **zero** frontend integration — no page, no API-layer function, no call site.

---

## 2. Current User Journey — Traced Directly

| Step | Route | API calls | Page |
|---|---|---|---|
| Register | `/register` | `POST /auth/register` | `RegisterPage.tsx` |
| Login | `/login` | `POST /auth/login` | `LoginPage.tsx` |
| Home | `/` | *(none)* | `HomePage.tsx` — static welcome + "Start a new reading" link |
| New Reading | `/readings/new` | `GET /spreads`, then `POST /readings` on submit | `NewReadingPage.tsx` |
| Card Entry | `/readings/:readingId/draw` | `GET /readings/{id}` + `GET /cards` on mount, `POST /readings/{id}/draws` per card | `CardEntryPage.tsx` |
| Completion | *(same page, banner)* | *(reuses the same `GET /readings/{id}` refetch after each draw)* | `CardEntryPage.tsx`'s completion banner |
| Spread Review | `/readings/:readingId` | `GET /readings/{id}` | `SpreadReviewPage.tsx` |

The journey terminates at Spread Review. From there, the only outbound links are "Continue drawing" (back to Card Entry, shown only while `status === 'drafting'`) and "Back to home" (`/`). There is no link anywhere in the built application from Spread Review to Interpretation, Save, or History, because none of those screens exist.

---

## 3. Reading History Readiness

**`GET /readings`, re-read directly** (`backend/app/api/reading.py`, `list_saved_readings_route`):

```python
readings = session.scalars(
    select(Reading)
    .join(ReflectionSession, Reading.reflection_session_id == ReflectionSession.id)
    .where(
        ReflectionSession.owner_id == current_user.id,
        Reading.status == ReadingStatus.SAVED,
    )
    .order_by(Reading.updated_at.desc())
).all()
```

- **Response shape**: `list[ReadingSummary]` — `id, status, question, question_domain, created_at, updated_at`. No pagination (returns the full list; an empty history returns `[]`, not `404`).
- **Filter**: `status == SAVED` only, unconditionally — a `DRAFTING`, `SPREAD_COMPLETE`, or `INTERPRETED` Reading is **never** returned by this endpoint, by explicit design (`READING_HISTORY_OWNERSHIP_DESIGN.md` Section 7; independently re-confirmed here by direct code read, not restated). Every row this endpoint returns will always have `status: "saved"` — a History UI would not need to render any other status.
- **Ordering**: `updated_at` descending (newest-first). Not `created_at` — worth noting precisely, since a Reading's `updated_at` changes on every draw and on save, not only at creation.
- **Question/spread information**: `question` and `question_domain` are present directly on each row. `spread`/`spread_id` are **not** present on `ReadingSummary` — a History list card could show the question but not the spread name without a second call.
- **Linking to `/readings/{reading_id}`**: yes, directly and with no backend change. Every `ReadingSummary.id` is a valid `reading_id` for the already-implemented, already-audited `GET /readings/{reading_id}` (Spread Review's own data source) — a History row can link straight to the existing `/readings/:readingId` route with no new endpoint and no new frontend data-fetching pattern; `SpreadReviewPage.tsx` already handles a `SAVED`-status Reading correctly today (it renders any non-`drafting` status as "complete," `SAVED` included — verified by direct code read of `SpreadReviewPage.tsx`'s `isComplete = reading.status !== 'drafting'` check).
- **Backend changes required**: **none**, for a History UI whose scope is "list saved Readings, click through to their Detail/Review view." The only thing `GET /readings` cannot support is listing *unsaved* (drafting/spread_complete/interpreted) Readings — restated from `FRONTEND_INTEGRATION_DESIGN.md` Section 7.3, re-confirmed by this step's own direct read of the route: no such filter exists, and none was ever designed to. Whether that matters depends on whether "Reading History" is scoped to saved-only (matching the Product Spec's own literal wording, Section 6: "Reading History — list of **saved** Readings") or is expected to also surface in-progress work — an open product question, not decided here (Section 8).

---

## 4. Interpretation / Narrative Readiness

**Endpoints that already exist** (`backend/app/api/interpretation.py`, re-read in full for this step), all under `/readings/{reading_id}` and all gated by the same `get_owned_reading` dependency every other Reading route uses:

| Method | Path | Response | Notes |
|---|---|---|---|
| `POST` | `/interpret` | `InterpretationSummary` (`201`) | Not idempotent — every call creates a new `Interpretation` row. `409` if the Reading is not spread-complete. |
| `GET` | `/interpretations/current` | `InterpretationSummary` | `404` if never interpreted. |
| `GET` | `/interpretations` | `list[InterpretationHistoryEntry]` | Lightweight, no embedded model, newest-first. |
| `GET` | `/narrative` | `NarrativeModel` | Recomputed on every call from the current Interpretation, never cached/persisted. `404` if never interpreted. |

**Request/response shapes**: `POST /interpret` takes no body. `InterpretationSummary` embeds the full `InterpretiveModel` verbatim (`schema_version`, `engine_version`, `reference_data_version`, `generated_at`, `central_question`, `central_issue`, `primary_tension`, `supporting_themes`, `trajectory`, `blocker`, `uncertainty`, `advice`, `clarification`, `contradictions`, `evidence_strength` — each evidence-bearing field wrapped in an `Explained[T]` carrying its own `citations`). `NarrativeModel` returns `sections: tuple[NarrativeSection, ...]`, each with `id`, `title`, `present`, and `statements` (each statement pre-rendered `text` plus its own `citations`) — i.e. narrative content arrives pre-assembled, ready to render as prose without further client-side logic.

**Precondition, re-verified directly** (`backend/app/services/reading_orchestration.py::interpret_reading`): gated on `reading.is_spread_complete` (the live, derived property), not on `reading.status` directly — in practice these agree for every Reading reachable through the built frontend (the only place `status` reaches `spread_complete` is the same condition that makes `is_spread_complete` true), but it is worth recording precisely since it is the actual guard, not the status string.

**Does Spread Review have everything it needs to invoke these?** Yes, with no backend change. `SpreadReviewPage.tsx` already has the `reading.id` and already knows `reading.status`; calling `POST /readings/{id}/interpret` when `status !== 'drafting'` (the same condition already used to show the "complete" banner) requires no new data the page doesn't already hold. `SpreadReviewPage.tsx` does **not** currently make this call anywhere — confirmed by direct read; no `interpret`/`narrative` string appears in the file.

**Automatic vs. explicit trigger — already settled by the Product Spec, not an open question:** `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 3, flow step 9 (re-verified directly for this step): *"User explicitly triggers Interpret My Reading — interpretation is never automatic on spread completion. This is a deliberate UX gate, not just a button: it reinforces that the app is interpreting a fixed, already-real event, not generating content as cards are picked."* This is an explicit, already-approved product requirement, not something this audit is deciding or recommending — a future implementation step should build an explicit "Interpret My Reading" action, not an automatic one.

**What genuinely remains open** (named, not decided, per `FRONTEND_INTEGRATION_DESIGN.md` Section 6/9, re-confirmed still unresolved by this step's direct re-read):
- Sequencing of `POST /interpret` vs. `GET /narrative` when rendering the eventual Reading Result screen — call both together before rendering, or render the structured/citation content first and fetch narrative separately. Both are fully supported by the existing contract; this is a frontend rendering-strategy choice.
- Whether `Interpretation`/`NarrativeModel` should be embedded in a Spread-Review-adjacent screen or a wholly separate "Reading Result" screen/route — not designed by this audit.
- Interpretation history / reinterpretation UI (`GET /interpretations`, multiple `Interpretation` rows per Reading) — the data already exists and is already exposed; no frontend surface for it has been designed.

---

## 5. Spread Review Assessment (Step 50, Re-Inspected Directly)

Re-read `frontend/src/pages/SpreadReviewPage.tsx` in full for this step (not restated from Step 50's own report):

- **Displays**: `reading.status` (as a literal, mapped-to-readable-label badge), `reading.question`, `reading.spread.name` + `description`, every `reading.spread.positions` entry in backend order, and — for each drawn position — the card's `name`, `arcana`/`suit`, and `orientation`.
- **Intentionally does not display**: any interpretation or narrative content (no call to `/interpret`, `/interpretations`, or `/narrative` anywhere in the file — confirmed), any overall reading summary/reflection, any card artwork or `image_ref`-derived content, and no draw-order number (recorded but not rendered — a deliberate display choice, not a data gap, since `draw_order` is present in `card_draws[]` and simply isn't surfaced in the tile).
- **Completion determination**: `const isComplete = reading.status !== 'drafting'` — a direct, verbatim branch on the backend's own status string. The page performs no position-counting or required/optional arithmetic to *decide* completion; the only client-side counting it does (`positions.length - undrawnPositions.length`) is purely for the incomplete-state progress line's display text, derived from data the backend already returned (`card_draws` vs. `spread.positions`), not a recomputation of the lifecycle rule itself.
- **Undrawn positions**: rendered as a distinct dashed-border, muted tile reading "Not yet drawn"; also named in a "Still to draw: …" summary line while `status === 'drafting'`.
- **Optional positions**: rendered identically to required ones except for a small "(optional)" label under the position name (from `SpreadPositionSummary.required`) — no seeded spread currently has one, so this path is exercised only by the throwaway-DB probe used in Step 50's own live verification, not by any real production spread.
- **Orientation display**: an explicit "↑ Upright" / "↓ Reversed" badge (text + arrow glyph), not a rotated/upside-down card — chosen for readability over a literal visual flip.
- **Current navigation limitations**: "Continue drawing" only appears while incomplete; "Back to home" is the only other link. No link to Interpretation, Save, or History exists (none of those screens exist yet — Section 1/2). A completed Reading that the user leaves without saving has no way back to it from anywhere in the built UI except re-navigating to the exact `/readings/:readingId` URL directly — this is the same "no resume affordance" gap `FRONTEND_INTEGRATION_DESIGN.md` Section 7.3 already named for Card Entry, now confirmed to extend to Spread Review too.
- **Artwork placeholder treatment**: a bordered, `aspect-[2/3]` (tarot-card-proportioned) tile with the card's name/arcana/suit and orientation badge, no image anywhere, no `image_ref` read anywhere in the file — matching `CARD_IMAGE_ASSET_DESIGN.md`'s Option E treatment exactly.

---

## 6. Search UX Finding — Card Entry, Restated Precisely

Re-confirmed directly against the current `frontend/src/pages/CardEntryPage.tsx` filter logic: the search box matches only `card.name.toLowerCase().includes(query)`. "Four of Wands" is findable (it is the card's literal `name`, confirmed against `backend/app/reference_data/rider_waite_smith/` seed data's naming convention). A query like "IV of Wands" is **not** findable, because no Roman-numeral alias exists anywhere in `CardSummary` or in the underlying seed data — `Card.name`, `Card.rank`, and `Card.keywords` (the only searchable/exposed fields) contain no Roman-numeral form for any Minor Arcana card. **This is not a defect in the Step 49 filtering bugfix** (which fixed a stale-search-text problem, unrelated to alias coverage) **and not a card-data defect** (the seed data was never specified to include Roman-numeral aliases by any governing document). It is a genuine, previously-unrecorded UX-enhancement question: whether the search should also match an alias/alternate-name field that does not currently exist in the data model. Not resolved here.

---

## 7. Human Validation Findings

The following are the user's own reported observations from manually operating the real, running application (register → login → home → new reading → card entry → spread complete → spread review) in this environment. **No browser-automation tool is available here, so none of the following were independently re-verified by this audit through automated clicking, screenshots, or browser console inspection — they are recorded as reported, human-performed observations, distinct from this document's own direct code/API verification elsewhere.**

1. Registration/login works when the backend is running.
2. Spread selection and question entry work.
3. Card Entry works.
4. The previously discovered stale-search bug was fixed.
5. Suit filtering now correctly exposes the complete Wands set.
6. Card selection and orientation work.
7. A completed Three Card reading successfully reaches Spread Review.
8. Spread Review correctly displays question, spread, positions, cards, orientations, and completion status.
9. Spread Review currently has no interpretation or overall reading summary.
10. "Back to home" returns to Home, which offers starting a new reading rather than showing reading history.
11. There is currently no Reading History UI even though `GET /readings` already exists.
12. Spread Review uses text-based placeholder card tiles rather than artwork.

Findings 8–12 are also independently corroborated by this audit's own direct code inspection (Sections 3–5 above) — i.e., what the human observed matches what the current source code actually implements.

---

## 8. Product Gaps

| Area | Implemented & working | Implemented but intentionally minimal | Missing frontend functionality | Backend available, not integrated | Unresolved product decision |
|---|---|---|---|---|---|
| **Auth (register/login)** | Yes | — | — | — | — |
| **New Reading / Card Entry** | Yes | Search matches name only (Section 6) | — | — | Roman-numeral alias search |
| **Spread Review** | Yes | Text placeholder tiles; no artwork | — | — | Whether artwork is required (`CARD_IMAGE_ASSET_DESIGN.md` OD-1) |
| **Reading History** | — | — | No route, no page, no History link anywhere | `GET /readings` (saved-only, no pagination) | Whether History should include unsaved/in-progress Readings |
| **Interpretation** | — | — | No "Interpret My Reading" action anywhere | `POST /interpret`, `GET /interpretations(/current)` | Reading Result screen sequencing (Section 4) — trigger itself is *not* open (Product Spec mandates explicit) |
| **Narrative / overall reflection** | — | — | No prose/summary display anywhere | `GET /narrative` (pre-rendered, cache-free) | Whether narrative is shown together with or separately from structured interpretation |
| **Save** | — | — | No Save action anywhere in the built UI | `POST /readings/{id}/save` | — (contract settled, `SAVE_READING_DESIGN.md`) |
| **Digital Draw** | — | — | Not built (intentionally) | No backend implementation exists either | Deferred, per Product Spec (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 18) |
| **Card artwork** | — | — | Not built (intentionally) | No static-serving mechanism exists | Source/licensing/architecture (`CARD_IMAGE_ASSET_DESIGN.md`) |
| **Resume an unsaved Reading** | — | — | No affordance anywhere; only reachable by exact URL | `GET /readings/{id}` (works fine once you have the ID) | Whether/how to surface unsaved Readings at all (`FRONTEND_INTEGRATION_DESIGN.md` Section 7.3) |
| **Journaling / broader reflection experience** | — | — | Not started — no page, no design document scoping it for Raidian Wise specifically | Unclear — not audited beyond what this step's scope covers | Entirely undesigned for this application; out of this audit's investigation depth |

---

## 9. Recommended Next Implementation Sequence

The suggested sequence in the task (History → Interpretation Frontend Design → Interpretation UI → Narrative/Reflection UI) was checked against the actual repository state rather than accepted as-is:

- **Reading History** — verified genuinely ready with zero backend changes (Section 3). A reasonable next step, and the smallest of the remaining gaps: one new route, one new page, reusing `getReading`/`SpreadReviewPage` for the click-through target.
- **Interpretation Frontend Integration Design** — also verified warranted: two real, unresolved frontend design questions exist (Section 4's sequencing-shape and screen-boundary questions) that a design/audit step should settle *before* writing interpretation UI code, matching this project's own established design → implementation pairing convention used throughout Steps 20 onward.
- **Interpretation UI** — the natural implementation step following that design, consuming `POST /interpret` + `InterpretiveModel`'s citation-bearing structure.
- **Narrative/Reflection UI as a separate Step 55, "if the existing architecture warrants it"** — checked directly: the architecture does distinguish these as two separate concerns (`InterpretiveModel` vs. `NarrativeModel`, two separate endpoints, `INTERPRETATION_API_DESIGN.md` Section 9's own reasoning for keeping them separate), so treating narrative rendering as its own step is consistent with the backend's own boundary, though whether it needs to be a *separate numbered step* versus folded into the Interpretation UI step is itself one of the open sequencing questions Section 4 names, not something this audit resolves.

No ranking beyond this ordering is offered, and no product decision (Sections 4/8's open items) is made here — a future design step for Interpretation should explicitly resolve them before implementation, the same pattern this project used for every prior surface (CORS/reference-data, Reading Detail, CardDraw, Card Entry).

---

## Verification

- `git diff --check`: run after creating this document — see report below.
- `git status`: confirmed only this new file added; no application file touched.
- No migration created (this step performed no database or backend work of any kind).
- Backend test suite was not re-run for this step — this is a pure documentation/audit step with zero code changes of any kind (frontend or backend), so there is nothing for the suite to regress against; the most recently established count (474 passed, 2 pre-existing warnings, Step 50) stands unchanged.
