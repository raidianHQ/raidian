# Step 58 — Remaining MVP Decisions & Next-Work Audit

**Status:** Read-only audit. No source code, schema, migration, dependency, configuration, or asset was modified in producing this report. Nothing was committed or pushed. Every claim below was verified directly against the current repository for this step — including a live Python/SQLAlchemy/Pydantic probe for the timestamp question (Section 6) that had never been traced to its exact mechanism in any prior step — not merely restated from earlier reports.

---

## 1. Executive Summary

Of the seven audited areas, **three are already fully settled** by an existing governing document and should stop being treated as open (Digital Draw's deferral, draft-Readings' exclusion from History, and AI/Reflection-Engine narrative's MVP substitution) — each is settled by the Product Spec's own literal text or by an already-approved project decision, not by this audit's opinion. **One area (card artwork) is settled for the *current, working* MVP** — a complete, live-tested flow already exists without artwork — while the underlying formal product question (OD-1: does "visual layout" ever require real imagery) remains technically open, unchanged. **Two areas are genuine, small, unresolved implementation-direction questions** (Roman-numeral search, History→Result direct linking) that need a product call, not an engineering one. **One area (timestamp serialization) is newly, precisely root-caused for the first time in this step**: it is a SQLite-specific artifact of how SQLAlchemy's `DateTime(timezone=True)` behaves against SQLite specifically (not a defect in any Raidian-authored serialization code), and is very likely **absent entirely in production** (PostgreSQL, per ADR-0004) — a materially different, more precise characterization than any prior step established.

**No code, schema, or configuration was changed.** One concrete next step is recommended (Section 14): add the History → Reading Result direct link, the smallest remaining piece of work with an already-established direction and zero backend risk.

---

## 2. Roman-Numeral Search Audit

**Product Spec** (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6, re-read directly for this step): Card Entry is specified as *"one interaction per Layout Position: searchable/filterable card selector (Major Arcana, Cups, Pentacles, Swords, Wands categories) + Upright/Reversed toggle."* No mention of Roman numerals, alternate naming, or any search-input format exists anywhere in the Product Spec — this was re-confirmed by a direct search of the entire document for "roman," "numeral," and "IV," finding zero matches outside this audit's own text.

**Are users expected to identify numbered Minor Arcana cards by Roman numeral?** Not addressed by the Product Spec at all. It is true that some physical RWS-tradition decks print Roman numerals (or Arabic numerals) rather than spelled-out words on pip cards — but this is a real-world printing convention the Product Spec never engages with, one way or the other. This is a plausible user-experience scenario, not a documented requirement.

**Does the existing card data contain enough information to support aliases without a backend change?** **[Verified directly]** — `backend/app/reference_data/rider_waite_smith/wands.yaml` (and, by the same seeding convention, every other suit file) stores `rank` as a spelled-out English word (`ace`, `two`, … `ten`, `page`, `knight`, `queen`, `king`) — never a Roman or Arabic numeral, anywhere. `Card.name`, `Card.rank`, and `Card.keywords` (the only fields `GET /cards` exposes) contain no Roman-numeral form for any Minor Arcana rank. **No backend data change is required either way**: a Roman-numeral alias is not "hidden" in the existing data waiting to be exposed — it would have to be a client-side mapping table (`"iv"` → `"four"`, etc.), entirely synthesized by the frontend, matched against the existing `rank`/`name` fields.

**Can `rank` safely support this?** Yes, mechanically — `rank` is already a clean, single-word field per card, well-suited as the match target for a small Roman-numeral→word lookup applied to the search query before filtering. This is a frontend implementation detail, not decided further here.

**Would frontend-only aliases violate any existing data/taxonomy principle?** No documented principle applies. `RAIDIAN_WISE_REFERENCE_DATA_V1.md`'s sourcing principles (re-checked) govern the *provenance of interpretive content* (card meanings, correspondence data) — guarding against copying another author's text. A numeral-to-word lookup table (`"iv"` ↔ `"four"`) is a mechanical, uncopyrightable fact, not sourced content, and would not touch, duplicate, or contradict any reference-data table. **No conflict found.**

**Is this an MVP requirement or a UX enhancement?** **UX enhancement.** There is no textual basis anywhere in the Product Spec to elevate this to a requirement. **Classification: genuinely open, but it is a *prioritization* decision (whether to build it at all), not a product-direction ambiguity** — the "how," if pursued, is already fully clear from this audit.

---

## 3. History → Result Audit

**Product Spec on reopening a saved Reading** (Section 6, re-read directly): names **"Reading Detail"** as *"a saved Reading's full record (evidence + interpretation as generated); MVP does not require re-interpretation, but the schema must not block it."* This is the only Product Spec text describing what happens when a saved Reading is reopened.

**What does "Reading Detail" mean?** A conceptual screen combining evidence and interpretation for a *saved* Reading — re-confirmed unchanged from `READING_RESULT_FLOW_DESIGN.md` Section 2's own prior reading of this exact passage.

**Should a saved/interpreted Reading reopen at Spread Review or Reading Result?** The Product Spec does not say — it describes *what information* Reading Detail shows, never *which route/screen* a user lands on first. `READING_RESULT_FLOW_DESIGN.md` Section 5 (re-confirmed, unchanged) already made an explicit, labeled **[Recommendation]** here: `/readings/:id` (evidence) and `/readings/:id/result` (interpretation) jointly satisfy "Reading Detail" together, with History currently linking to the evidence route first. This remains a recommendation, not a Product Spec mandate.

**Is the existing `/readings/:readingId` + `/readings/:readingId/result` route structure consistent with the Product Spec?** Yes — nothing in the Product Spec constrains route count or URL shape (it names screens conceptually, "illustrative, not final IA" per its own Section 6 heading qualifier), and the two-route split matches the exact reasoning `READING_DETAIL_API_DESIGN.md` already established once for the evidence route alone (one endpoint/route, multiple consuming moments).

**Should History link directly to Result for interpreted readings?** **[Verified, current behavior]** — `frontend/src/pages/ReadingHistoryPage.tsx`, re-read directly: every entry links to `/readings/${reading.id}` (Spread Review) only. There is **no direct History → Result link today.** This exact gap was already named as **Open** in `READING_RESULT_FLOW_DESIGN.md` Section 13 ("exact link/button placement... where on History... a link to `/readings/:id/result` appears") and restated in `FRONTEND_MVP_AUDIT.md` Section 12/17 — **not a new finding**, re-confirmed still true and still unresolved.

**What should happen for a saved Reading that somehow has no interpretation?** Already fully specified and already implemented: `ReadingResultPage.tsx`'s `notInterpreted` state (`GET /interpretations/current` → `404`) renders an explicit "This reading hasn't been interpreted yet" message with a link back to Spread Review — re-confirmed by source read, unchanged since Step 55, live-verified as recently as Step 56/57's own checks. `mark_saved()`'s own docstring explicitly names "SPREAD_COMPLETE + zero Interpretation rows" as "a valid, supported path to SAVED" — so this is not a hypothetical edge case, it is an expected, already-handled state.

**Does closing this gap require a backend change?** **No.** Both `GET /readings` (already returns the Reading's `id`) and `/readings/:id/result` (already handles both the interpreted and not-yet-interpreted cases) already exist — adding a link is a one-line frontend change with zero backend involvement.

---

## 4. Draft History Audit

**Product Spec** (Section 6, re-read directly, re-quoted precisely): *"Reading History — list of **saved** Readings, searchable/filterable."* This is explicit, literal spec text, not an inference.

**What is `GET /readings` explicitly designed to return?** **[Verified directly]** — re-read `backend/app/api/reading.py::list_saved_readings_route`: filters `Reading.status == ReadingStatus.SAVED` unconditionally. This is not an accidental narrowing; `READING_HISTORY_OWNERSHIP_DESIGN.md` Section 7 (cited in the route's own docstring) designed it this way deliberately.

**Are drafts supposed to be resumable?** The Product Spec never describes a "resume a draft" flow. `FRONTEND_INTEGRATION_DESIGN.md` Section 7.3 already found, and this audit re-confirms unchanged: there is no `GET /readings?status=...` filter, and none was ever designed to exist — an in-progress Reading is fully durable in the database but has no listing endpoint at all today.

**Does the Product Spec require abandoned readings to appear in History?** No — the opposite: its own wording restricts History to saved Readings specifically.

**Is the earlier "draft-resume" concern still relevant?** As a *named, unaddressed gap* — yes, still accurately named (a user who closes the browser mid-Reading has no way back to it except bookmarking the exact URL). As an *open product question about whether History's scope is correct* — **no, this is not open**; both the Product Spec's own literal text and `PRODUCT_DECISIONS.md` Q3's explicit, already-approved resolution (*"SAVED is the sole gate for whether a Reading appears in Reading History"*) settle it. **Classification: Already Settled**, not a question to keep re-litigating — the "resume" gap is a separate, distinct, still-open question (whether an *entirely different* resume mechanism should exist someday) from "should History itself include drafts" (which is closed).

**Would changing this require a backend API/schema change?** Yes, if ever pursued — a new filter parameter or a new endpoint (no such thing exists or is designed today) — but this is moot given the Product Spec already settles the question the other way.

---

## 5. Card Artwork Audit

Re-read `Documentation/CARD_IMAGE_ASSET_DESIGN.md` in full, and `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6 again, for this step.

**Card Entry requirements:** Explicit, literal spec text (Section 18/19, re-confirmed unchanged): *"Visual card browsing beyond the searchable selector"* is listed under **"Out (explicitly deferred, per the brief)"** and again under Future Scope. Card Entry's own screen description (Section 6) never mentions images. **Artwork is explicitly NOT required for Card Entry — this is "explicitly deferred," the strongest of the three classifications, not merely "not required."**

**Spread Review requirements:** *"full visual layout of all positions, cards, and orientations"* (Section 6) — the one genuinely ambiguous phrase, re-confirmed still ambiguous: it never says "images" or "artwork." `CARD_IMAGE_ASSET_DESIGN.md`'s own OD-1 names this precisely and leaves it open. **Classification: "required but not yet implemented" is NOT established — the spec's own words don't clearly require imagery at all; this remains genuinely undetermined, not merely unbuilt.**

**Reading Result requirements:** re-checked directly (Section 6): *"narrative sections... optional Scripture for Reflection block... optional 'How did Raidian Wise arrive at this?' explainability panel, Save action."* **No mention of card imagery anywhere in this screen's description.** This is a new, precise confirmation not previously stated this explicitly: Reading Result has no artwork requirement of any kind, explicit or implied.

**Does "visual layout" mean actual artwork or visual tiles?** Not decided by the Product Spec's own text — genuinely ambiguous, unchanged (OD-1). **This audit does not resolve it.**

**Is artwork explicitly required anywhere for MVP?** No — checked against all three relevant screens (Card Entry: explicitly deferred; Spread Review: ambiguous; Reading Result: not mentioned at all). **Nowhere in the Product Spec is artwork an explicit MVP requirement.**

**Licensing/governance decisions, `image_ref`, architecture options:** All unchanged since `CARD_IMAGE_ASSET_DESIGN.md` — public-domain 1909 RWS art, unverified specific-source question (OD-2), five architecture options evaluated but not chosen (OD-3), `image_ref` treated as a logical key, not a URL. Re-confirmed by source: `image_ref` is still never read anywhere in `frontend/src/` for rendering purposes (only carried through as an unused type field).

**Has the current implementation actually removed the need for artwork in MVP?** **Empirically, yes, for a functioning MVP** — the complete flow (Steps 46–57) was built, live-tested end-to-end, and works correctly using only text/tile placeholders, with zero artwork anywhere. This is a strong practical signal that placeholders are *sufficient to ship*, but it is an empirical fact about the current build, **not** a resolution of OD-1's formal product question (whether real artwork should eventually be considered *required*). **Precise distinction, as requested:**
- **"Not required for current MVP"** — true, demonstrated by a working, tested implementation.
- **"Explicitly deferred"** — true only for Card Entry's *visual browsing* specifically (the spec's own words).
- **"Required but not yet implemented"** — **not established anywhere** for any of the three screens; this framing does not match the actual spec text for Spread Review or Reading Result.

---

## 6. Timestamp Serialization Audit

**Root cause, precisely traced for the first time in this step** — a live Python/SQLAlchemy/Pydantic probe against a real, freshly-migrated SQLite database:

```
Column declared: DateTime(timezone=True)
Python object read back from SQLite: datetime.datetime(2026, 9, 19, 16, 54, 42)  -- tzinfo: None
.isoformat(): "2026-09-19T16:54:42"
Pydantic model_dump(mode="json"): {"created_at": "2026-09-19T16:54:42"}
```

**Which backend serializer/configuration produces this?** **None, specifically — this is not a Raidian-authored serializer at all.** Pydantic's default `datetime` JSON encoding (used automatically by every FastAPI route via `response_model`, with no custom encoder configured anywhere in this codebase) simply calls `.isoformat()` on whatever `datetime` object it is given. The actual root cause is one level upstream: **SQLite has no native timezone-aware datetime storage type**, so SQLAlchemy's `DateTime(timezone=True)` column type — despite its own declaration — returns a **naive** Python `datetime` (`tzinfo=None`) when reading from SQLite, regardless of what was originally written. This is standard, well-documented SQLAlchemy+SQLite behavior, not an application-level bug.

**Does this affect only History, or all API consumers of `TimestampMixin` values?** **All of them.** `TimestampMixin` (`app/db/base.py`) is used by every model with `created_at`/`updated_at` — `Reading`, `Interpretation`, `User`, `ReflectionSession`, and others — re-confirmed by source read. The characteristic is a property of the *database driver/column-type interaction*, not of any specific route or model. `ReadingHistoryPage.tsx` is simply the **only current frontend consumer that displays a raw database-sourced timestamp at all** (re-confirmed: `SpreadReviewPage.tsx` and `ReadingResultPage.tsx` do not render `created_at`/`updated_at` anywhere) — which is why the workaround exists in exactly one place, not because the underlying issue is scoped to History.

**Does the Product Spec or project architecture require timezone-qualified timestamps?** No requirement found anywhere — this is a data-correctness/consistency concern, not a product requirement.

**Should this be fixed centrally in the backend?** **[Recommendation, not decided here]** — technically straightforward (e.g., a `field_serializer` on the shared timestamp fields, or coercing to UTC-aware on read), but genuinely optional given: (a) the frontend workaround already fully and correctly compensates wherever it matters today; (b) — the most significant new finding of this audit — **this almost certainly does not reproduce at all in production.** PostgreSQL (the production database per ADR-0004) maps `DateTime(timezone=True)` to a genuine `TIMESTAMPTZ` column, which correctly preserves and returns timezone-aware values through SQLAlchemy — the naive-datetime behavior observed here is specific to SQLite, i.e., **likely a dev/test-only artifact**, not a production defect. This was not previously stated with this precision in any prior step.

**Could changing backend serialization affect existing consumers/tests?** Yes, if pursued — any test asserting an exact ISO string shape would need review, and any other future frontend consumer displaying a raw timestamp would need to either rely on the (now-fixed) backend output or keep its own defensive handling. Not evaluated further here since no change is being made.

**Should the frontend workaround remain?** **Yes** — it is correct, cheap, low-risk, and (per the finding above) may be the *only* place this ever needs to be handled at all, if the underlying behavior turns out to be SQLite-specific and production is unaffected.

---

## 7. Digital Draw Audit

**What does the Product Spec require?** Section 3, step 5: *"Digital Draw — optional, clearly opt-in"* (Physical is "default"). Section 18 (MVP Scope), re-read directly: **"Out (explicitly deferred, per the brief): Digital Draw."** Section 19 (Future Scope): *"Draw: Digital Draw mode, additional decks."*

**MVP, post-MVP, or optional?** **Explicitly post-MVP / explicitly deferred** — this is the Product Spec's own literal classification, not an inference. Not "optional-but-buildable-now" — actively excluded from the current phase's scope.

**Does any backend contract already exist for it?** **No.** Re-confirmed by source: `DrawMethod` enum has a `DIGITAL` value (schema-ready), but no randomization service, no digital-draw endpoint, and no route anywhere calls it. `Reading.draw_method` defaults to `PHYSICAL` and nothing in the built flow ever sets it otherwise.

**Is the physical/manual workflow explicitly intended to remain (for now)?** Yes — `CardEntryPage.tsx`'s own docstring and this project's entire Card Entry design (Steps 49 onward) describe it as "a manual representation of a physical card draw," matching the Product Spec's own "the app is a recorder, not a participant in the draw" framing (`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 8.1, restated from Step 56).

**What would eventually be required?** A new backend randomization service (Product Spec Section 8.2 already specifies a CSPRNG-based, question-blind shuffle requirement), a new digital-draw endpoint, and a new frontend screen ("New Reading — Digital Draw Result," already named in Section 6's screen inventory) — none of which is designed in any current document beyond that naming.

**Would implementing it now execute an existing decision or create a new one?** **It would execute an already-existing decision to defer it** — i.e., building it now would be building something the Product Spec has already, explicitly, said is *not* part of this phase. No new product decision is needed to *not* build it; a new decision *would* be needed to justify building it ahead of the Product Spec's own stated sequencing. **Classification: Already Settled (deferred).**

---

## 8. AI / Reflection Engine Audit

**What is currently deterministic?** **[Verified, re-confirmed unchanged]** Both the Interpretation Engine (`app/services/interpretation/engine.py`) and the Narrative assembler (`app/services/narrative/assembler.py`) — no AI provider call exists anywhere in either, confirmed by source read consistent with every prior step's own finding (Steps 53–57).

**What does the Product Spec say about AI?** Section 3.3/12 (re-read directly): Narrative Generation is described as running *"via the Reflection Engine"* (ADR-0005's sole sanctioned AI gateway), converting the Interpretive Model into prose. The Interpretation Engine itself is explicitly required to be non-AI (*"must never call an AI provider"*, Section 3.3).

**What role is the Reflection Engine supposed to play?** The platform's single AI gateway (ADR-0005) — a cross-cutting Core Service (`docs/ARCHITECTURE.md`) that **does not exist anywhere in this codebase**, re-confirmed by repository-wide search (no module, route, or stub implements it).

**Is AI required for MVP, or future scope?** **Already settled, not open**: `PRODUCT_DECISIONS.md` Q1 (re-read directly) already resolved this — the deterministic Narrative Layer is the **interim MVP substitute**, with the AI/Reflection-Engine pass explicitly named as *"the long-term, still-required target, formally gated on the Reflection Engine (M1) shipping, not abandoned"* — a recommendation, "pending formal governance sign-off" (an ADR or Product Spec revision that Q1's own Section 8 names as still outstanding). **The functional/implementation question is settled; the paperwork ratifying it is not** — a documentation/governance housekeeping gap, not a decision blocking any current work.

**Is the deterministic engine/narrative intentionally the foundation for a future AI layer?** Yes, by design — `NARRATIVE_LAYER_DESIGN.md`'s `[A]`/`[B]`/`[A']` split (re-confirmed unchanged) treats today's deterministic assembly as `[A]`, with `[A']` (an eventual AI rephrase pass, constrained to "rephrase, not reconsider") named as a distinct, separately-designed future addition — not a redesign of `[A]`, an addition alongside it.

**Would introducing AI now change any existing contract or behavior?** Yes, substantially, if ever attempted: it would require the Reflection Engine to exist first (a whole separate platform milestone), and per ADR-0005's own architecture, would have to be inserted *between* the already-stable `InterpretiveModel` and the currently-deterministic `NarrativeModel` output — a real, non-trivial future integration, not evaluated further here since this audit adds/changes nothing.

---

## 9. Overall MVP Status Matrix

| Area | Current State | Product Spec Status | Decision Status | Backend Change Needed? | Frontend Change Needed? | Blocks MVP? |
|---|---|---|---|---|---|---|
| Roman-numeral search | Name-only substring search; no numeral matching | Not addressed either way | Open (whether to build it) | No | Yes, if pursued (small) | No |
| History → Result linking | History links to Spread Review only | Names "Reading Detail" conceptually; no routing mechanics specified | Open (already named, `READING_RESULT_FLOW_DESIGN.md` Section 13) | No | Yes, if pursued (small) | No |
| Draft readings in History | `GET /readings` returns `SAVED` only | Explicit: "list of saved Readings" | **Already settled** | No | No | No |
| Card artwork | Text/tile placeholders everywhere; `image_ref` unused | Explicitly deferred (Card Entry); ambiguous (Spread Review); unmentioned (Reading Result) | Open for Spread Review's OD-1 specifically; settled-deferred for Card Entry | No | No (for status quo) | No |
| Timestamp serialization | SQLite returns naive datetimes; frontend `Z`-append workaround in `ReadingHistoryPage.tsx` | Not addressed | Not a product decision — engineering follow-up, likely dev-only (SQLite) in scope | Optional, if pursued | No (already handled) | No |
| Digital Draw | Not implemented anywhere | Explicitly deferred, Section 18/19 | **Already settled (deferred)** | Yes, substantial, if ever built | Yes, substantial, if ever built | No |
| AI / Reflection Engine | Fully deterministic engine + narrative | Describes an eventual AI-backed narrative pass | **Already settled for MVP** (deterministic is the approved interim substitute); formal ADR/spec ratification still outstanding | No for MVP; yes (large) if ever added | No for MVP | No |

---

## 10. Already Settled

Things this audit found should stop being treated as open:

- **Draft/unsaved Readings do not belong in History** — the Product Spec's own literal text plus `PRODUCT_DECISIONS.md` Q3.
- **Digital Draw is out of scope for this phase** — the Product Spec's own literal text (Section 18/19).
- **The deterministic Narrative Layer is the correct MVP substitute for an eventual AI-backed pass** — `PRODUCT_DECISIONS.md` Q1's already-made recommendation, functionally settled (only its formal governance write-up remains outstanding, a paperwork item, not a live question).
- **Card artwork is not required for Card Entry** — the Product Spec's own explicit deferral language.

---

## 11. Genuine Open Decisions

Questions that actually require a deliberate choice before further implementation:

- **Whether to build Roman-numeral search aliasing at all** (Section 2) — a prioritization call with no spec mandate either way.
- **Whether/where to add a direct History → Reading Result link** (Section 3) — direction (add one) is a reasonable recommendation; exact placement/styling is a small UX call.
- **Whether "full visual layout" (Spread Review) requires real card artwork** — OD-1, still genuinely unresolved by the Product Spec's own ambiguous wording (Section 5).
- **Whether to pursue a centralized backend timestamp-serialization fix** — optional engineering work, likely low-impact given production may be entirely unaffected (Section 6).
- **Whether to formally ratify `PRODUCT_DECISIONS.md` Q1 via an actual ADR or Product Spec revision** — a governance/documentation completeness question, not a functional blocker.

---

## 12. Straightforward Next Work

Items where the product direction is already established and a next step could simply implement them:

- **History → Reading Result direct link** — direction already recommended in `READING_RESULT_FLOW_DESIGN.md`, zero backend change, smallest possible frontend change.
- **Roman-numeral search aliasing** — fully specified implementation path (a frontend-only lookup table), if and only if Section 11's prioritization question is answered "yes."
- **Backend timestamp normalization** — a clear, bounded technical fix, if and only if judged worth the effort given Section 6's findings.

---

## 13. Post-MVP Work

Things that should not distract from the current MVP:

- Digital Draw (explicitly deferred by the Product Spec itself).
- Real AI/Reflection-Engine narrative pass (gated on an entire separate, unbuilt platform service).
- Card artwork sourcing/licensing/hosting architecture (OD-2/OD-3) — no urgency given a fully working placeholder-based MVP.
- Reinterpretation UI (the Product Spec's own "Reading Detail" text: "MVP does not require re-interpretation").

---

## 14. Recommended Next Step

**Recommendation: implement the History → Reading Result direct link.**

Reasoning, grounded in this audit rather than the order items were listed in: of everything reviewed, this is the only item that is simultaneously (a) small and low-risk (one link, zero backend touch, reusing an already-built, already-tested route), (b) already directionally recommended by an approved design document (`READING_RESULT_FLOW_DESIGN.md` Section 5) rather than requiring a fresh product call, and (c) a real, user-visible completion of the MVP flow — closing the one concrete navigation gap `FRONTEND_MVP_AUDIT.md` itself flagged (Section 12) as the sole remaining "not the most direct path" limitation in an otherwise fully working, fully live-tested application.

**Everything else genuinely open (Section 11) is not recommended as the next step**, because each requires an explicit decision from the user first, not just engineering judgment:
- Roman-numeral search has no spec mandate and no urgency signal — building it now would be executing a preference no one has yet stated.
- The backend timestamp fix is optional engineering work whose value depends on a fact (whether production is actually affected) that this audit could reason about but not fully confirm without a real PostgreSQL environment — worth a deliberate "is this worth doing" call, not default action.
- Card artwork's OD-1 requires an actual product-taste decision about what "visual layout" should mean, which no document (including this one) is positioned to make unilaterally.

This step does not implement the recommendation.

---

## 15. Verification / Repository State

- **No source, schema, migration, dependency, or configuration file was modified.** The one live probe performed (Section 6) ran against a disposable, freshly-migrated SQLite database created in the session scratchpad directory and deleted immediately after use — no artifact left in the repository.
- **`git status --untracked-files=all`**: confirmed only `Documentation/STEP58_REMAINING_MVP_DECISIONS_AUDIT.md` is new; every other entry identical to the state at the end of Step 57.
- **`git diff --check`**: clean (only the same pre-existing LF/CRLF warnings seen in every prior step, exit code 0).
- **No test suite was run** — this step made no code change of any kind, so there is nothing to regress against; the most recently established, honestly-reported backend result (474 passed, 2 warnings, Step 50) stands, unchanged and not re-claimed as freshly run.
- **No browser testing of any kind is claimed** — every finding above is either direct source inspection or a live, non-UI Python/HTTP-level probe, each labeled as such.
- Nothing was staged, committed, or pushed.
