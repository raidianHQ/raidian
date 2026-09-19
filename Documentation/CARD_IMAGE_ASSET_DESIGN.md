# Card Image / Asset Strategy — Design & Audit

**Status:** Design/Audit (read-only step). No code, schema, or dependency changes were made in this step.
**Step:** 48
**Scope:** Investigate the card-image/artwork question end-to-end and produce an implementation-ready design for a future implementation step (Step 49). Card Entry itself is **not** implemented here.

---

## 1. Executive Summary

Raidian Wise has never shipped a single card-artwork image. Every `Card.image_ref` value is a placeholder path string (e.g. `rws/major/00-the-fool.png`) written by seed data, and nothing in the backend or frontend serves, resolves, or renders any file at that path. This was first surfaced by Step 45 and is reconfirmed independently here.

The genuinely new finding of this step is that **the artwork licensing policy is not an open question invented for this step — it already exists**, in `Documentation/RAIDIAN_WISE_REFERENCE_DATA_V1.md` (Sections 5–6), a governance document that predates the entire Reading/CardDraw implementation series and was not previously cited by Steps 39 or 45. That document already establishes:

- The 1909 Rider-Waite-Smith artwork is in the US public domain.
- A specific modern *scan or reprint* of that artwork can carry its own separate copyright, independent of the underlying 1909 work.
- Actual image assets must come from a verified public-domain source (Wikimedia Commons is named as an example), not photographed from a copyrighted modern printed deck.
- Verifying and sourcing the actual files is explicitly deferred to "a future phase" — i.e., to whichever step first adds real artwork.

This step does not change that policy, does not perform that verification, and does not claim any specific file is safe to use. It treats that policy as the authoritative, already-decided starting point and builds the rest of the design on top of it: the `image_ref` contract, the missing-image/fallback behavior, the Card Entry and Spread Review requirements against the contracts that already exist (`GET /cards`, `GET /readings/{reading_id}`), and five architecture options for how images would actually be served, evaluated but not ranked.

The Product Spec itself turns out to say more than prior steps credited it for: MVP **Card Entry** is specified as a text-based "searchable/filterable card selector," and "visual card browsing" is explicitly listed as deferred, out-of-MVP scope (Section 18/19). MVP **Spread Review**, by contrast, is specified as a "full visual layout of all positions, cards, and orientations" — language that is suggestive of artwork but does not explicitly say "images" or "artwork." This is a real, unresolved ambiguity, documented in Section 9 and Section 11 below, not resolved by this step.

**Bottom line for Step 49:** Card Entry can be built now, against the existing `GET /cards` contract, without resolving the artwork question — the Product Spec does not require images there. Spread Review is the one place where the artwork question is load-bearing, and it remains genuinely open pending a product decision (Section 11).

---

## 2. Repository Asset Findings

Verified directly in this step (not inherited from Step 45's report):

- Repo-wide search for `*.png, *.jpg, *.jpeg, *.gif, *.webp, *.svg` (excluding `node_modules/`, `.git/`) found exactly four files, none of them card artwork:
  - `frontend/public/favicon.svg`, `frontend/public/icons.svg` — hand-authored UI chrome, unrelated to cards.
  - `frontend/dist/favicon.svg`, `frontend/dist/icons.svg` — build output copies of the same two files (`dist/` is gitignored, not a real asset source).
- No backend static-file-serving mechanism exists. Repo-wide search for `StaticFiles`, `.mount(`, `/static` inside `backend/` returned zero matches. FastAPI's `StaticFiles` is not imported anywhere, and no route mounts a filesystem directory.
- No CDN, object-storage, or external image-hosting configuration exists anywhere. `frontend/.env`, `frontend/.env.example`, and `frontend/vite.config.ts` contain only `VITE_API_BASE_URL`; no image-base-URL or asset-host variable exists.
- `frontend/public/` contains no `cards/` subdirectory or anything resembling a card-asset convention.
- The README's Hosting section (`README.md`, line 62–65) states the intended hosting split: **GitHub Pages** (frontend) and **Render** (backend) — i.e., frontend and backend are intended to be different origins/hosts in production, consistent with the CORS work already done. This is a stated intention only: no deployment config exists yet (no `render.yaml`, no GitHub Actions workflow, no CI/CD of any kind was found in the repository). Architecture options below are evaluated against this documented intent, with that caveat made explicit.

**Conclusion:** the "zero images anywhere, nothing serves them" finding from Step 45 is reconfirmed independently, with two additions not previously stated as explicitly: (a) there is no backend static-serving *mechanism* to even point at a directory if images existed, and (b) the intended production hosting topology is cross-origin (GitHub Pages + Render), which is a real constraint on the architecture options in Section 6.

---

## 3. `image_ref` Data & Consumer Trace

Every reference to `image_ref` in the backend, found by repository-wide search and read directly (not assumed from memory):

| Location | Role |
|---|---|
| `backend/app/models/card.py:52` | Column definition: `image_ref: Mapped[str \| None] = mapped_column(String(255), nullable=True)`. Nullable at the schema level, despite seed data always populating it. |
| `backend/app/seed/loader.py:119,125-128` | `image_ref` is one of `required_text_fields` for seed **validation**: must be a non-empty string. Validation checks presence and non-emptiness only — no format/pattern check (not a path-shape check, not a URL check, not an extension check). |
| `backend/app/seed/seed.py:67` | `card.image_ref = card_def["image_ref"]` — the seed loader writes the YAML-declared placeholder string straight into the column, verbatim, no transformation. |
| `backend/app/api/reference_data.py:109` | `_to_card_summary()` copies `card.image_ref` verbatim into the `CardSummary.image_ref` API field — no transformation, no URL-building, no existence check. |
| `backend/app/schemas/reference_data_api.py:73,82` | `CardSummary.image_ref: str \| None` — declared and documented as a passthrough field, not as a resolved URL. |
| `backend/app/services/interpretation/reference_data_version.py:33` | `_card_payload()` includes `"image_ref": card.image_ref` in the payload hashed by `compute_reference_data_version()`. See finding below — this is new and not previously documented anywhere in this project. |

**What `image_ref` currently *is*, by direct evidence, not assumption:** a free-form string, validated only for presence, carried unmodified from YAML seed data through the database into the public API response. Nothing in the codebase treats it as a URL (no `http`/`https` prefixing, no base-URL joining) or as a resolved filesystem path (nothing opens or reads a file at that path). It is best described today as an **opaque placeholder identifier** with a human-readable, path-shaped convention — not yet contractually a URL, a relative static-asset path, or a database lookup key, because nothing currently *consumes* it as any of those things. This distinction matters directly for Section 7 below.

**New finding — `reference_data_version` provenance coupling:** `compute_reference_data_version()` (`backend/app/services/interpretation/reference_data_version.py`) computes a SHA-256 hash over all reference data content (Decks, Cards, CardCorrespondences, Spreads, theme vocabulary), sorted by name, deliberately excluding volatile fields like `id`/`created_at`/`updated_at` so that two runs using identical *content* produce an identical hash (`INTERPRETATION_ENGINE_DESIGN.md` Section 3.1/9 Q2). **`image_ref` is not excluded** — it is part of the hashed Card payload. This means: whenever `Card.image_ref` values change (e.g., placeholder strings replaced with real paths, or a format/prefix change), `compute_reference_data_version()` will produce a different hash than it did before the change, for every Card. This is not a bug and not new risk specific to this step — the hash is *designed* to change whenever reference-data content changes, the same way fixing a typo in `base_meaning_upright` would change it too. It is, however, a concrete, previously-undocumented consequence worth naming explicitly: **any future change to `image_ref` values is a reference-data content change**, not a purely cosmetic frontend concern, and will be reflected in the provenance hash of every interpretation created after that change. This is directly relevant to the `image_ref` contract recommendation in Section 7.

---

## 4. Product Spec Requirements

Read directly from `Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md` for this step (not relied on from memory or prior step citations).

**Card Entry (Section 6, screen inventory, line 128; Section 3, flow step 6, line 108):**
> "New Reading — Card Entry (Physical) — one interaction per Layout Position: searchable/filterable card selector (Major Arcana, Cups, Pentacles, Swords, Wands categories) + Upright/Reversed toggle; duplicate-card guard with override-to-correct."

No mention of images, artwork, thumbnails, or visual card browsing in this description. The selector is specified by search/filter behavior (by arcana/suit) and an orientation toggle.

**MVP Scope explicitly excludes image-based card entry (Section 18, line 519; Section 19, line 535):**
> Out (explicitly deferred, per the brief): "... Visual card browsing beyond the searchable selector ..."
> Future Scope — Card entry: "visual card browsing."

This is an explicit requirement, not an inference: the Product Spec explicitly scopes *image-based* card entry **out of MVP**, and explicitly scopes the *searchable/filterable, non-visual* selector **into MVP**. Card Entry, as specified, does not require card artwork to be built or to be considered complete.

**Spread Review (Section 6, line 130; Section 3, flow step 8, line 110):**
> "Spread Review — full visual layout of all positions, cards, and orientations before committing to interpretation; edit-in-place still available here."
> "User reviews the completed spread (all positions filled, all cards visible, orientation shown) before proceeding."

This is the one place in the spec where "visual layout" and "cards visible" language appears for an MVP-in-scope screen (Section 18 explicitly lists "Spread Review" as In). It is genuinely ambiguous whether "visual layout... cards visible" *requires* card artwork images, or is satisfiable by a well-organized spatial layout showing each position's card **name** and orientation without photographic/illustrated artwork. The spec does not say "displays card artwork" or "shows the card's image" anywhere. Per this step's own instruction not to convert an implied requirement into a hard one without evidence, **this document does not decide that question** — it is carried forward as Open Product Decision OD-1 (Section 10).

**Card entity (Section 7.4, lines 176–193):** `image_ref` is listed as one of the Card entity's fields, with no further elaboration of its meaning, format, or intended consumer anywhere in the Product Spec. The Product Spec does not define `image_ref` — that definition lives entirely in `RAIDIAN_WISE_REFERENCE_DATA_V1.md` (Section 3 below).

**Deck (Section 7.1, line 144–149; Q4, line 476):** a single initial deck (Rider-Waite-Smith or equivalent) is proposed for MVP, with deck-switching UI an explicitly open question (Q4) not yet resolved. No MVP requirement for a deck-selection screen exists yet. This step does not resolve Q4; it is restated as context for Open Product Decision OD-4 (deck-selection UI is out of this step's scope per the task's own boundaries, and remains so).

**Conclusion:** the Product Spec draws a real, textual distinction between Card Entry (explicitly non-visual for MVP) and Spread Review (ambiguously visual for MVP). Prior steps (39, 45) treated "the card-image question" as a single undifferentiated gap; this step's direct re-read shows it is really two separate questions with two different MVP-scope answers, one settled by the spec and one not.

---

## 5. Artwork Provenance / Licensing Findings

**This document does not provide legal advice and does not declare any specific artwork file or source "safe to distribute."** What follows distinguishes what is already established internally, what is independently corroborated by an authoritative external source, and what remains genuinely unresolved.

**Established by this repository's own governance documentation** (`Documentation/RAIDIAN_WISE_REFERENCE_DATA_V1.md`, Sections 5–6, read in full for this step):

- Section 5, "Image-Source Policy": the original 1909 Rider-Waite-Smith artwork by Pamela Colman Smith is stated to be in the US public domain (published before 1923). A specific scan, reprint, or colorization produced by a commercial publisher may carry its own separate copyright on that particular reproduction, even though the underlying 1909 artwork is public domain. The policy requires that actual image assets come from a verified public-domain source (an example given: a public-domain scan such as those hosted by Wikimedia Commons, or a similarly documented public-domain archive), not photographed or scanned from a copyrighted modern printed edition. The same section explicitly states that verifying and sourcing the actual files is **out of scope for that phase**, deferred to whenever images are actually added.
- Section 6, "`image_ref` Placeholder Convention": defines the exact path convention seed data already follows (`rws/major/{2-digit-rank}-{slug}.png`, `rws/{suit}/{rank}-of-{suit}.png`), confirming the placeholder strings in the database are a deliberate, pre-planned convention, not an accidental artifact.
- `Documentation/RAIDIAN_WISE_REFERENCE_DATA_AUDIT_V1.md` (read for this step): independently confirms `image_ref` in the current dataset is "Raidian Wise's own placeholder path convention; not from the spreadsheet" (line 127) — i.e., the placeholder values were authored specifically for this project's convention, not copied from any external source, so the *placeholder strings themselves* carry no provenance concern. The audit does not add any new licensing information beyond what Section 5/6 of the reference-data document already states.
- `Documentation/RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md` (read for this step): contains one relevant, previously-unsurfaced detail — the original correspondence-data source spreadsheet apparently contained an "Image Path" column holding "an external image URL" (line 40), but this column was explicitly excluded from that proposal's scope and never adopted, evaluated, or carried into `image_ref`. **This is a dangling, unverified breadcrumb, not a viable source.** No document establishes what that URL pointed to, who controlled it, or under what license. It should not be treated as a candidate image source without separate investigation from first principles — it is named here only so a future step does not have to rediscover it, and so it is not mistaken for an already-vetted option.

**Independently corroborated by authoritative external context (general, well-established public-domain fact, not sourced from any specific web page in this step):** works published in the United States before 1923 are in the public domain under US copyright law; the Rider-Waite-Smith deck was first published in 1909. This is consistent with, not contradicted by, the repository's own Section 5 statement. This step did not perform new web research to verify a *specific* candidate image source (e.g., checking the license terms on a particular Wikimedia Commons file page) because the repository's own governance document already states the correct general legal framework, already names Wikimedia Commons as an example of a plausible verified-public-domain source, and already explicitly defers the concrete file-level verification to "when image assets are actually added" — i.e., to Step 49 or whichever step actually selects and adds files. Performing that file-level verification now, without a chosen architecture or a chosen file, would be premature and would not change any decision this step is scoped to make.

**Genuinely unresolved, not decided by this step:**
- Which specific files, from which specific source, will actually be used (Open Product Decision OD-2).
- Whether that source's specific scan/reproduction is confirmed public-domain or otherwise appropriately licensed at the *file* level — this requires checking the actual file's own license/attribution metadata at the time a real source is chosen, not a general statement about the 1909 artwork.
- Whether any attribution requirement applies (even public-domain-marked scans on some archives carry a requested, non-mandatory attribution convention; this must be checked per-file, not assumed either way).

---

## 6. Architecture Options (A–E)

Evaluated below without ranking, per this step's instructions. All five are compatible with the "no new dependencies" constraint of this step itself; several would require a new dependency (or new infrastructure) *if chosen and implemented* in a later step — that is noted per option, not treated as disqualifying here.

**Option A — Frontend-bundled static assets.** Image files live inside `frontend/public/` (or `frontend/src/assets/`) and ship as part of the Vite build output, served by whatever serves the built frontend.
- Fits the documented hosting intent directly: GitHub Pages already serves static files with no additional infrastructure, so this option requires no new hosting mechanism, no new dependency, and no backend change at all.
- Couples the artwork's release cadence to the frontend's own deploy — acceptable for a fixed, small, single-deck MVP (78 images), less so if decks become dynamic/user-uploadable later (explicitly Future Scope, not MVP).
- `image_ref` values would need to resolve to a path under the frontend's own static root (e.g. `/cards/rws/major/00-the-fool.png`), which is a light transformation from the current raw placeholder string, not an identical mapping.

**Option B — Backend-served static files.** FastAPI mounts a `StaticFiles` directory (e.g. `/assets/cards/...`) and serves images itself, alongside the JSON API.
- No such mechanism currently exists (Section 2) — this option requires adding one (a few lines of FastAPI setup, no new dependency since `StaticFiles` ships with FastAPI/Starlette).
- Under the documented hosting split (GitHub-Pages frontend, Render backend), this makes every `<img>` request cross-origin from the browser's perspective. This is not a CORS-blocking problem the way `fetch`/`XHR` calls are — browsers load cross-origin images by default without preflight — so it does not require extending the existing `CORSMiddleware` allow-list. It does mean image requests depend on the API service's own uptime/latency profile rather than a CDN-style static host's.
- Keeps all Raidian Wise-authored content (data and assets) under one deploy unit conceptually, which is a real simplicity argument even though it adds a new responsibility to the API service.

**Option C — External CDN / object storage** (e.g., an S3-compatible bucket or similar, referenced by full URL).
- Most scalable and most naturally supports future multi-deck/user-content scenarios (explicitly Future Scope, not MVP), but requires new external infrastructure, a new account/credential, and likely a new dependency (an SDK, or at minimum new deployment configuration) — the heaviest option relative to MVP's actual current needs (one fixed deck, 78 fixed images).
- `image_ref` would most naturally become (or resolve to) a full absolute URL.

**Option D — Externally-hosted third-party source, requested directly at render time** (e.g., hot-linking a public archive's own URLs per card, with no local copy at all).
- Lowest implementation effort of any option — no hosting, no build step, no backend change.
- Creates a hard runtime dependency on a third party's uptime, URL stability, and rate limits for a user-facing MVP feature; if the third party changes a path or throttles requests, Raidian Wise's Spread Review breaks with no ability to fix it independently.
- Raises the same per-file licensing/attribution question as any other source (Section 5), with the added wrinkle that the *specific* URL scheme of a third-party archive is outside Raidian Wise's control and could change without notice.

**Option E — No real artwork for MVP; a non-image placeholder representation.** Card Entry and Spread Review both ship using a designed placeholder (e.g., a card-shaped panel showing the card's name, arcana/suit/rank, and an orientation indicator) instead of illustrated artwork, with real artwork explicitly deferred to Future Scope.
- Directly consistent with the Product Spec's own explicit deferral of "visual card browsing" (Section 4) and requires no new infrastructure, no dependency, and no licensing decision at all for MVP.
- Fully resolves Card Entry (which the spec does not require images for) but only conditionally resolves Spread Review, depending on how Open Product Decision OD-1 (whether "visual layout... cards visible" requires artwork) is ultimately decided — a well-designed non-image placeholder may or may not be judged to satisfy that language.
- Zero cost to reverse later: whichever of Options A–D is eventually chosen for real artwork, a placeholder-first MVP does not foreclose it, since the `image_ref` contract (Section 7) is designed to accommodate a later transition either way.

---

## 7. `image_ref` Contract Recommendation

The task's own example distinguishes a **logical asset key** (an opaque identifier the frontend maps to a real location itself, e.g. via a lookup table or naming convention it owns) from a **served URL** (a value the backend hands the frontend that is already directly usable in an `<img src>`, requiring no frontend-side interpretation).

Today, by direct evidence (Section 3), `image_ref` is neither, cleanly — it is a raw placeholder string that nothing resolves. Recommendation for whichever architecture option is eventually chosen (Section 6):

- **Treat `image_ref` as a logical asset key, not a served URL, for now.** The current placeholder convention (`rws/major/00-the-fool.png`) already reads naturally as a key/relative-path rather than an absolute URL, and every option in Section 6 except D can resolve a logical key into a real location via a single, frontend-owned (Option A) or backend-owned (Options B/C) base-path/base-URL join — a small, centralized transformation, not a data model change. Treating it as a served URL instead would require the *backend* to already know its own eventual serving location (or a CDN's) at seed-authoring time, which is a premature coupling given no architecture option has been chosen yet.
- **This has a concrete, evidence-based consequence already surfaced in Section 3: changing `image_ref` values changes `compute_reference_data_version()`'s output.** Whichever option is chosen, if it requires *transforming* `image_ref` values (e.g., Option A/B/C prefixing a base path, or replacing the placeholder scheme entirely), that transformation is a reference-data content change like any other, and will change the provenance hash for all interpretations created afterward. This is expected, correct behavior of that hash (not a defect to work around), but it should be a deliberate, acknowledged consequence when Step 49 (or a later step) actually performs such a transformation — not a surprise discovered after the fact.
- **No schema change is implied or recommended by this step.** `Card.image_ref: str | None` already accommodates a logical key of the current shape; nothing here requires widening, narrowing, or renaming the column.

---

## 8. Missing/Fallback Image Behavior

Regardless of which architecture option is eventually chosen, no real image files exist today, and (Option E aside) may not exist even after Step 49 ships if Step 49's scope stops short of sourcing real artwork. The frontend must therefore already tolerate a missing image without this being an error state:

- A card with a null `image_ref` (schema-legal, `nullable=True`, even though every seeded card currently has a value) and a card whose `image_ref` points to a file that does not (yet) exist at the resolved location are both **expected, non-error conditions**, not edge cases to guard against defensively — they are, in fact, the *default* state of every card in the system today.
- Recommended behavior: render a calm, clearly-labeled placeholder (consistent with Option E's placeholder design, Section 6) showing at minimum the card's name and orientation whenever an image is absent or fails to load, rather than a broken-image icon or an empty gap. This keeps Card Entry and Spread Review fully usable today, independent of whichever image-sourcing timeline is eventually chosen, and means adopting Option E now is not a separate throwaway effort — it is the fallback every other option needs anyway.
- This is a UI/frontend behavior recommendation only; it does not require any backend contract change (`GET /cards` and `GET /readings/{reading_id}` already return `image_ref` as nullable, and the frontend already receives it as `string | null` per the existing TypeScript types in `frontend/src/api/spreads.ts`/`readings.ts`).

---

## 9. Card Entry Requirements for Step 49

Audited directly against the existing `GET /cards` contract (`backend/app/api/reference_data.py`, `backend/app/schemas/reference_data_api.py`), not against a hypothetical one.

- `GET /cards` already returns `id, name, arcana, suit, rank, image_ref` (`CardSummary`) for all 78 cards, correctly ordered (Section 2's `_card_sort_key` fix from Step 41), and is public (no auth) — everything the Product Spec's actual Card Entry requirement (a searchable/filterable selector by arcana/suit, Section 4) needs is already present in this contract.
- Per Section 4's finding, the Product Spec does not require artwork for Card Entry, and explicitly defers "visual card browsing" beyond the searchable selector to Future Scope. **Step 49 can build Card Entry's searchable/filterable selector and Upright/Reversed toggle against the existing `GET /cards` contract with no backend changes, independent of any Section 6 architecture decision.** `image_ref` can be carried through and rendered per Section 8's fallback behavior if desired (e.g., a small thumbnail next to each search result) as a pure enhancement, but is not required for Card Entry to be considered spec-complete.
- Not evaluated or required by this step: the duplicate-card guard's UI (mentioned in the spec alongside Card Entry) — its backend enforcement was not part of this step's scope and is unaffected by anything in this document.

---

## 10. Spread Review Requirements

Audited directly against the existing `GET /readings/{reading_id}` contract (`backend/app/api/reading.py`, `backend/app/schemas/reading_api.py`), not against a hypothetical one.

- `ReadingDetail` already embeds, per card draw, the full `CardSummary` (including `image_ref`) and `SpreadPositionSummary`, plus `orientation` — every field the Product Spec's Spread Review requirement ("all positions filled, all cards visible, orientation shown") needs is already present in this contract, with no gaps and no additions required.
- Whether Spread Review's "full visual layout... cards visible" requires artwork rendering, or is satisfied by a text/name-based layout (per Option E), is Open Product Decision OD-1 (Section 11) — **not resolved by this step**, and not something the existing API contract needs to change to support either answer, since `image_ref` (present or null) flows through either way.
- No change to `GET /readings/{reading_id}` is recommended by this step, for either interpretation of OD-1.

---

## 11. Open Product Decisions

Restated explicitly, not silently resolved:

- **OD-1 (new in this step).** Does the Product Spec's Spread Review requirement ("full visual layout of all positions, cards, and orientations," "all cards visible") require rendered card artwork, or is it satisfiable by a well-designed non-image layout (card name + orientation, per Option E)? The spec's own text does not use the words "image" or "artwork" for this screen. This determines whether Step 49 can ship Spread Review without resolving OD-2/OD-3 first.
- **OD-2 (restated from Step 45, still open).** Which specific artwork source/file set will actually be used, and has its specific license been verified at the file level (Section 5)? Not resolved by this step; this step only confirms the *policy* under which that verification must eventually happen.
- **OD-3 (new in this step, follows from Section 6).** Which architecture option (A–E) should Raidian Wise adopt for serving/hosting card images, given the documented GitHub-Pages/Render hosting split? Evaluated but not decided here.
- **OD-4 (restated from the Product Spec's own Q4, unaffected by this step).** Deck-selection UI scope for MVP — a single hardcoded deck with no switcher, or a Deck table/selector visible from day one. Out of this step's scope; restated only because it is adjacent context for OD-3 (a future multi-deck scenario would push toward Option C).
- **Whether card artwork is mandatory for MVP launch at all**, versus MVP shipping with Option E's placeholder and real artwork following as a fast-follow — not decided by this step; Section 6 shows Option E is a real, low-cost, spec-consistent choice for Card Entry regardless, and a conditionally sufficient one for Spread Review depending on OD-1.

---

## 12. Recommended Implementation Sequence for Step 49

Offered as a sequencing recommendation only; Step 49 itself, and any product decisions listed in Section 11, remain for the user to authorize/resolve, not for this step to preempt.

1. Resolve OD-1 (does Spread Review require artwork) — this determines whether Step 49 can ship end-to-end without touching OD-2/OD-3 at all.
2. Build Card Entry against the existing `GET /cards` contract (Section 9) — independent of OD-1/OD-2/OD-3, can proceed regardless of their outcome.
3. Build Spread Review against the existing `GET /readings/{reading_id}` contract (Section 10) using Option E's placeholder behavior (Section 6/8) as the default rendering — satisfies Card Entry fully and satisfies Spread Review under one resolution of OD-1, deferring OD-2/OD-3 without blocking either screen from shipping.
4. Treat sourcing and integrating real artwork (resolving OD-2 and OD-3, and only then performing the file-level license verification Section 5 defers) as a separate, later step, only if/when OD-1 is resolved in a way that requires it.

---

## 13. Explicit Non-Scope

Not done in this step, by instruction:
- No code, schema, migration, or frontend changes.
- No dependency added.
- No artwork downloaded, added, selected, or hotlinked.
- No legal advice given, and no specific file or source declared safe to distribute.
- No product decision (OD-1 through OD-4, or the MVP-mandatory question) resolved.
- No Digital Draw scope touched.
- Card Entry itself was not implemented.

---

## 14. Audit / Verification Evidence

- `git status` before this step: matched the state carried forward from Step 47 (no unexpected changes); `git status` after this step shows only `Documentation/CARD_IMAGE_ASSET_DESIGN.md` as a new untracked file — no other file was created or modified.
- `git diff --check` run after creation: no whitespace errors reported.
- Repository searches performed directly for this step (not reused from any prior report): image-file glob search, `StaticFiles`/`.mount(`/`/static` grep, `image_ref` grep across `backend/`, RWS/Rider-Waite mention grep across the repository, README hosting-section read, deployment-config file search (`render*`, GitHub Actions workflows) — all reported inline in the relevant sections above with exact file paths and line numbers.
- `Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Sections 3, 6, 7.1, 7.4, 18, 19 read directly for this step.
- `Documentation/RAIDIAN_WISE_REFERENCE_DATA_V1.md` Sections 5, 6 read directly (already read prior to the mid-conversation summary; re-confirmed, not re-read a second time, since nothing about the file changed).
- `Documentation/RAIDIAN_WISE_REFERENCE_DATA_AUDIT_V1.md`, `Documentation/RAIDIAN_WISE_CORRESPONDENCE_DATA_PROPOSAL_V1.md` read directly for this step (licensing/image-related excerpts quoted in Section 5).
- Backend test suite: run after documentation creation, read-only step, no test changes expected or made.

