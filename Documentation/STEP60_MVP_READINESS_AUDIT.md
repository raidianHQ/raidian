# Step 60 — Final MVP Readiness Audit

**Status:** Read-only audit. No source code, schema, migration, dependency, configuration, or asset was modified in producing this report. Nothing was committed or pushed. Facts below were either re-verified directly against the current repository for this step, or are re-confirmed, unchanged findings from the extensive live/source verification already performed in Steps 46–59 of this same series — each labeled accordingly, per the same "do not treat a question as open merely because an earlier report called it open" discipline Step 58 established.

**Purpose, stated precisely per this step's own framing:** establish a defensible MVP finish line — what is genuinely done, what is genuinely blocking, and what should be explicitly deferred — not to find reasons to keep adding scope.

---

## 1. Roman-Numeral Card Search

**[Re-verified this step]** `Card.rank` is stored as a spelled-out English word for every Minor Arcana card (`ace`, `two`, … `ten`, `page`, `knight`, `queen`, `king`) — re-confirmed directly against `backend/app/reference_data/rider_waite_smith/wands.yaml`. No Roman-numeral (or Arabic-numeral) form exists in `Card.name`, `Card.rank`, or `Card.keywords` anywhere in the seeded dataset.

**Can a user currently search "IV of Wands"?** **No.** `CardEntryPage.tsx`'s filter (`frontend/src/pages/CardEntryPage.tsx`, re-confirmed this step) matches only `card.name.toLowerCase().includes(query)` — a plain substring match against the display name (e.g. "Four of Wands"). A query of "IV of Wands" matches nothing.

**Is Roman-numeral aliasing actually required by the Product Spec?** No. `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6's Card Entry description (re-confirmed unchanged) specifies only *"searchable/filterable card selector (Major Arcana, Cups, Pentacles, Swords, Wands categories)"* — no search-syntax requirement of any kind, Roman numeral or otherwise, appears anywhere in the document.

**Recommendation: (b) explicitly defer to post-MVP.** There is no textual basis to treat this as an MVP requirement, the underlying data does not currently support it without new frontend-only logic, and it is a pure UX-enhancement prioritization call (already the same conclusion Step 58 reached; re-confirmed, not re-litigated, by this step's own fresh source check). Not implemented here.

---

## 2. Spread Review Artwork

**[Re-verified this step]** `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6: *"Spread Review — full visual layout of all positions, cards, and orientations before committing to interpretation."* Re-confirmed by direct re-read: this sentence never uses the word "image," "artwork," "illustration," or "photo" anywhere in the document.

**Reconciled against `CARD_IMAGE_ASSET_DESIGN.md`:** that document's own OD-1 (re-confirmed unchanged) already names this exact phrase as the one place the artwork question is genuinely ambiguous, and explicitly declines to resolve it, for the same reason restated here — the text does not clearly require rendered imagery, and could equally be satisfied by a well-organized, spatially-correct layout of text/tile representations that shows every position, card identity, and orientation, which is exactly what `SpreadReviewPage.tsx` already does.

**Is real card artwork actually an MVP requirement?** **Ambiguous, precisely as previously found — not resolved by this audit.** The exact ambiguity: "visual layout" could mean (a) a spatially organized *arrangement* is visual, independent of whether each card is rendered as a photo or a text tile, or (b) the cards themselves must be rendered as images. Nothing in Section 6, or in the surrounding flow description (Section 3, steps 8–11), disambiguates this.

**Recommendation: text/tile placeholders are acceptable for MVP.** Grounded in three independent facts, not merely convenience: (1) Card Entry — the screen immediately preceding Spread Review — is *explicitly* specified as text-based, with "visual card browsing" *explicitly deferred* (Section 18/19, re-confirmed); it would be an odd, undocumented product stance for the very next screen to suddenly require a completely different, unbuilt visual paradigm with no transition described anywhere. (2) Reading Result's own Section 6 description (re-confirmed, quoted in full in Step 58 and again here) never mentions imagery at all. (3) The current, complete, live-tested MVP flow (Steps 46–59) already demonstrates that text/tile placeholders are sufficient to satisfy every other explicit requirement of the flow end-to-end. **Not implemented or changed here** — this remains a recommendation, and OD-1 remains formally open exactly as `CARD_IMAGE_ASSET_DESIGN.md` left it.

---

## 3. Backend Timestamp Serialization

**[Re-confirmed this step, plus one new architecture-level check]** Step 58's root cause, re-confirmed unchanged: SQLite has no native timezone-aware storage type, so SQLAlchemy's `DateTime(timezone=True)` columns return **naive** Python `datetime` objects when read from SQLite regardless of the column's own declaration — Pydantic's default `.isoformat()` serialization faithfully reflects that missing offset. This affects every `TimestampMixin` consumer (`Reading`, `Interpretation`, `User`, `ReflectionSession`), not just History specifically; `ReadingHistoryPage.tsx` remains the only current frontend consumer that displays a raw database timestamp.

**New this step:** re-read `docs/DECISIONS.md` ADR-0004 directly — **Status: Accepted** (not draft/proposed) — explicitly names **SQLite (development)** and **PostgreSQL (production)** as the settled technology stack. This is a load-bearing, already-ratified architectural fact, not a project guess: PostgreSQL's `TIMESTAMPTZ` (what `DateTime(timezone=True)` maps to on that dialect) genuinely preserves and returns timezone-aware values through SQLAlchemy, unlike SQLite. **This strengthens, with a firmer citation than Step 58 had, the conclusion that the naive-timestamp behavior is very likely a development-only artifact, absent from the intended production deployment.**

**Is the current frontend workaround safe for the intended deployment architecture?** **Yes, and additionally forward-compatible** — re-confirmed by direct inspection of `toAbsoluteDate()`'s own detection regex (`/Z$|[+-]\d{2}:\d{2}$/`, `frontend/src/pages/ReadingHistoryPage.tsx`): it only appends `Z` when *no* timezone designator is already present. Against a production PostgreSQL deployment emitting a properly-suffixed timestamp (e.g. `...+00:00`), this regex would correctly detect the existing designator and skip appending anything — the workaround degrades to a safe no-op rather than double-appending or corrupting an already-correct value. **The workaround is safe today (SQLite dev) and remains correct even if the underlying behavior changes (Postgres prod) without any frontend change being required.**

**Is a backend serialization fix necessary before MVP, or can it be safely deferred?** **Can be safely deferred.** No Product Spec or architecture document requires a specific timestamp wire format; the one current consumer already compensates correctly and safely; and the underlying behavior is plausibly already correct in the actual production database target. Not modified here.

---

## 4. Reinterpretation

**[Re-verified this step]** Backend: `POST /readings/{id}/interpret` remains **not idempotent** — every call creates a new `Interpretation` row (re-confirmed unchanged, `app/services/interpretation/persistence.py::save_interpretation`, live-verified as recently as Step 55/56). Frontend: a repository-wide search of `frontend/src/` for "reinterpret" (case-insensitive) found **zero** matches referring to any UI element — the only two hits are unrelated comment text (`client.ts`'s docstring, `ReadingHistoryPage.tsx`'s timestamp comment). `interpretReading()` has exactly one call site in the entire frontend (`SpreadReviewPage.tsx`'s explicit-click handler) — confirmed fresh this step. **No Reinterpret button or affordance exists anywhere.**

**Is any reinterpretation UI required by the MVP Product Spec?** **No — explicitly not required.** `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6's own "Reading Detail" description (re-confirmed, quoted verbatim in Step 53/58): *"MVP does not require re-interpretation, but the schema must not block it."* This is the strongest possible textual confirmation: the Product Spec itself, by name, excuses MVP from building this. Not implemented here.

---

## 5. Digital Draw

**[Re-confirmed this step]** `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 18 (MVP Scope), re-read directly: **"Out (explicitly deferred, per the brief): Digital Draw."** Section 19 (Future Scope) repeats it. No backend contract exists for it (`DrawMethod.DIGITAL` is schema-ready but unused by any route; no randomization service exists — re-confirmed by repository search, unchanged since Step 51/56). Card Entry remains exactly what the Product Spec calls it: a manual recorder of a physical draw. **Explicitly deferred, confirmed, not implemented.**

---

## 6. Deterministic Interpretation / Narrative

**[Re-confirmed this step]** Both `engine.interpret()` and `assemble_narrative()` remain fully deterministic — no AI provider call exists anywhere in either module (re-confirmed by source read, unchanged since Steps 53–57). `PRODUCT_DECISIONS.md` Q1 (re-read directly) already resolved the deterministic Narrative Layer as the **approved interim MVP substitute** for the Product Spec's originally-described AI/Reflection-Engine pass, with that AI pass explicitly named as a long-term target gated on an entire separate, unbuilt platform service (the Reflection Engine).

**Is the remaining governance/ADR work required before MVP, or is it documentation follow-up?** **Documentation follow-up only — does not block MVP.** Q1's Section 8 already names exactly what remains outstanding: a formal ADR or Product Spec revision *recording* the already-made, already-functioning decision. This is paperwork ratifying a decision the codebase has been correctly operating under this entire series (Steps 6–7 through 55) — it changes no code, no behavior, and no contract; it only makes the Product Spec's own text stop being technically inaccurate about what MVP delivers. Not resolved or performed here (out of this audit's own scope), but explicitly classified as non-blocking.

---

## 7. Save / History / Result Lifecycle

**[Re-confirmed this step, incorporating Step 59's completed navigation work]**

- **Final intended lifecycle** (re-traced against `app/models/reading.py` and `app/models/enums.py`, unchanged): `drafting → spread_complete → interpreted → saved`, no backward transitions, reinterpreting a `saved` Reading never regresses its status. Unchanged since Step 53/54's own full state-machine documentation.
- **Saved readings remain accessible:** yes — via History (`GET /readings`, saved-only) → either "View Spread Review" (`/readings/:id`, unchanged) or "View Result" (`/readings/:id/result`, added Step 59) → both routes independently confirmed live and via source in Step 59.
- **History remains saved-only:** re-confirmed by fresh source read of `backend/app/api/reading.py::list_saved_readings_route` — the `Reading.status == ReadingStatus.SAVED` filter is unchanged; Step 59 touched only `ReadingHistoryPage.tsx`'s rendering, not the API call or filter.
- **View Result does not trigger a new interpretation:** confirmed by source — the "View Result" link (`ReadingHistoryPage.tsx`) passes no router state, so `ReadingResultPage.tsx` always falls into its existing Mode B path (`GET /interpretations/current` + `GET /narrative`, both read-only); `interpretReading()` remains called from exactly one place in the entire frontend (Section 4, above), which is not this link.
- **Direct Result visits and refreshes use the existing persisted-interpretation flow:** re-confirmed — Mode B is, by construction, the *only* path reachable without router state, and router state never survives a reload or a fresh navigation from elsewhere (React Router's in-memory `location.state`, confirmed unchanged).
- **Spread Review remains distinct from Reading Result:** two separate routes (`/readings/:id` vs. `/readings/:id/result`), two separate components, confirmed unchanged in `App.tsx` (Section — routes re-listed at the top of this audit's own investigation).

**No blocking issue found in this area.**

---

## 8. Authentication / Ownership

**[Re-verified this step]** `ProtectedRoute.tsx` (re-read in full, unchanged): redirects to `/login` (preserving the origin path in router state) whenever `isAuthenticated` is false — wraps all six authenticated routes in `App.tsx` (re-confirmed: `/`, `/readings`, `/readings/new`, `/readings/:id/draw`, `/readings/:id/result`, `/readings/:id`); `/login`/`/register` correctly sit outside it; the catch-all route redirects to `/`. **No route is unintentionally left unprotected**, and no protected route is unreachable.

Backend ownership: `get_owned_reading` (re-confirmed unchanged across this entire series) resolves `reading_id → Reading` and collapses nonexistent/not-owned/`NULL`-owner into one identical `404` — applied uniformly to every Reading-scoped route including all four interpretation/narrative endpoints and `save`. 401-on-any-failure → `clearToken()` is implemented consistently across every one of the six page components (re-confirmed by source read across all of them in Steps 55–57, unchanged since).

**No obvious MVP blocker found.** Authentication architecture is not redesigned or touched by this audit.

---

## 9. Overall MVP Assessment

| Area | Current State | Evidence | MVP Required? | Blocking Issue? | Recommended Action |
|---|---|---|---|---|---|
| Register/Login/Home | Fully implemented, live-tested | Steps 46, 56 live HTTP + source | Yes | No | None |
| New Reading (spread + question) | Fully implemented, live-tested | Steps 47, 56 | Yes | No | None |
| Card Entry (manual, text-based) | Fully implemented, live-tested | Steps 49, 56 | Yes | No | None |
| Spread Review | Fully implemented, live-tested | Steps 50, 56 | Yes | No | None |
| Interpret My Reading / Interpreting state | Fully implemented, explicit-trigger-only, live-tested | Steps 55, 56 | Yes | No | None |
| Narrative retrieval | Fully implemented, live-tested | Steps 55, 56 | Yes | No | None |
| Reading Result (structured + narrative + citations) | Fully implemented, live-tested | Steps 55, 57, 56 | Yes | No | None |
| Save | Fully implemented, idempotent, live-tested | Steps 55, 56 | Yes | No | None |
| History (saved-only) | Fully implemented, live-tested | Steps 52, 56 | Yes | No | None |
| History → Result / Spread Review navigation | Fully implemented, live-tested | Step 59 | Yes (closes the one named nav gap) | No | None |
| Roman-numeral search | Not implemented | Section 1 | No | No | Defer to post-MVP |
| Card artwork (Spread Review) | Not implemented, text/tile placeholders | Section 2 | Ambiguous | No | Defer; placeholders acceptable for MVP |
| Backend timestamp serialization | SQLite-only artifact; frontend workaround in place and forward-compatible | Section 3 | No | No | Defer; optional backend follow-up |
| Reinterpretation UI | Not implemented | Section 4 | No (Product Spec explicitly excuses it) | No | Defer to post-MVP |
| Digital Draw | Not implemented | Section 5 | No (explicitly deferred by Product Spec) | No | Defer to post-MVP |
| AI / Reflection Engine narrative | Not implemented; deterministic substitute in place | Section 6 | No for MVP (already-approved substitute) | No | Governance/ADR write-up only, non-blocking |
| Authentication / ownership | Fully implemented, consistent across every route | Section 8 | Yes | No | None |

---

## MVP Readiness Conclusion

**The documented frontend MVP can reasonably be considered implementation-complete.** Every screen and transition in the flow this step was asked to review — Register → Login → Home → New Reading → Spread Selection/Question → Card Entry → Spread Review → Interpret My Reading → Interpreting → Narrative → Reading Result → Save → History → View Spread Review / View Result → reopen saved reading — is built, wired to real (never mocked) backend contracts, and has been independently, repeatedly live-verified across Steps 46–59. This step found no new gap in that flow and no reason to reopen any of the seven investigated questions as blocking.

## Genuine Blockers

**None identified.**

## Items Explicitly Deferred to Post-MVP

- Roman-numeral card search aliasing (Section 1).
- Real card artwork for Spread Review, and the underlying OD-1/OD-2/OD-3 product/sourcing/architecture questions (Section 2) — text/tile placeholders are recommended as acceptable for MVP.
- Backend timestamp serialization normalization (Section 3) — optional, low-priority, likely dev-only in scope.
- Reinterpretation UI (Section 4) — the Product Spec itself excuses MVP from this.
- Digital Draw, including its backend randomization service and its own screens (Section 5) — the Product Spec's own explicit deferral.
- The formal AI/Reflection-Engine ADR or Product Spec revision (Section 6) — documentation/governance follow-up, not implementation.

## Proposed Step 61

**None proposed.** Per this audit's own finding, nothing in the reviewed flow genuinely needs to be implemented before the current MVP can be considered complete. If the team wishes to proceed further, the natural candidates are exactly the deferred items above — each already labeled with which single further decision (not implementation) would need to be made first — but none is presented here as a required Step 61, consistent with this step's own instruction not to propose implementation unless something is genuinely still needed.

---

## Verification / Repository State

- **No source, schema, migration, dependency, configuration, or asset file was modified.** Every fact above was established by direct, read-only source inspection (files re-read fresh this step: `backend/app/reference_data/rider_waite_smith/wands.yaml`, `frontend/src/pages/CardEntryPage.tsx`, `frontend/src/App.tsx`, `frontend/src/components/ProtectedRoute.tsx`, `frontend/src/api/interpretation.ts`, `docs/DECISIONS.md` ADR-0004, plus a repository-wide grep for "reinterpret" across `frontend/src/`) or by re-confirming, not re-deriving, findings from Steps 46–59's own extensive prior live/source verification, each cited by step number above.
- No new live backend spin-up was performed for this step — the Save/History/Result lifecycle (Section 7) and the broader end-to-end flow were exhaustively live-verified as recently as Steps 56 and 59, with no implementation change in between beyond Step 59's own already-verified History navigation addition; re-running the identical checks against an unchanged implementation would not have produced new information.
- **No browser testing of any kind is claimed** — every finding above is either direct source inspection or a citation of already-performed, already-reported live HTTP verification from a named prior step.
- `git status --untracked-files=all`: confirmed only `Documentation/STEP60_MVP_READINESS_AUDIT.md` is new; every other entry identical to the state at the end of Step 59.
- `git diff --check`: clean (only the same pre-existing LF/CRLF warnings seen in every prior step, exit code 0).
- Nothing was staged, committed, or pushed.
