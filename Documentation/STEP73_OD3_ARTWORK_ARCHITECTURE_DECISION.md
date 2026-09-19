# Step 73 — OD-3 Spread Review Artwork Architecture Decision

**Status:** Architecture investigation/decision only. No code, schema, dependency, image/binary file, or configuration was added or changed in this step. No artwork was downloaded.

---

## 1. Executive Summary

OD-1 (artwork required) and OD-2 (Wikimedia Commons "Rider-Waite-Smith tarot deck (TaionWC)," the "Pam-A" 1910 scan) are both resolved. This step investigates OD-3: how those 78 verified files should actually be incorporated and served by the running application.

Direct re-inspection of the repository (Vite config, `package.json`, `index.html`, `frontend/public/`, backend source, `docs/DECISIONS.md`, `README.md`) confirms no deployment infrastructure exists yet at all — GitHub Pages and Render remain a documented *intent* (ADR-0004, Accepted), not a configured reality. No backend static-file mechanism exists. No CDN/object-storage account or credential exists. The existing `image_ref` field is a Raidian-Wise-authored placeholder convention that does not share a filename scheme with the TaionWC source files, so some acquisition-time mapping is required regardless of which architecture is chosen — this is a pre-existing fact, not a new complication introduced by any option.

**Recommendation: Option A — frontend-bundled static assets**, evaluated below against the other four options using direct repository evidence, not assumption.

---

## 2. Current Architecture

Re-verified directly this step:
- **Frontend:** React 19 + Vite ^8.2.2 + TypeScript, built via `tsc -b && vite build` (`frontend/package.json`). No `base` path configured in `frontend/vite.config.ts` (plugins only: `react()`, `tailwindcss()`). No `homepage` field in `package.json`. `frontend/src/main.tsx` wraps the app in `<BrowserRouter>` with no `basename` prop — both default to root (`/`).
- **Backend:** FastAPI 0.141.1 (`backend/app/main.py`), CORS-enabled for the frontend origin, no static-file mount of any kind (`grep -rn "StaticFiles|\.mount(|/static" backend/app` returns zero matches, re-confirmed this step).
- **Existing `public/` convention:** `frontend/public/` contains exactly two files today — `favicon.svg`, `icons.svg`. `favicon.svg` is referenced in `frontend/index.html` as a root-absolute path (`<link rel="icon" ... href="/favicon.svg" />`); `icons.svg` is unreferenced anywhere in the codebase (a pre-existing, unused Vite-scaffold leftover, unrelated to this decision).
- **No CI/CD exists:** `.github/` does not exist. No GitHub Actions workflow of any kind.
- **No deployment config exists:** no `render.yaml`, no `Procfile`, anywhere in the repository.

---

## 3. Deployment Constraints

`README.md` (Hosting section) and `docs/DECISIONS.md` ADR-0004 (Status: **Accepted**) both name the intended split: **GitHub Pages** for the frontend, **Render** for the backend — i.e., two different origins in production. This is a real, ratified architectural constraint on the options below, even though nothing has been configured yet. The cross-origin split means any image request the frontend makes to the backend (Option B) is a cross-origin `<img>` load — browsers permit this by default with no preflight, so it does not require extending `CORSMiddleware`, but it does mean image delivery would depend on the API service's own uptime/latency rather than a static host's.

GitHub Pages project sites (the common free-tier pattern, e.g. `<org>.github.io/raidian/`) serve from a subpath, not domain root. Nothing in this repository currently accounts for that: no Vite `base`, no router `basename`, and the existing favicon reference already uses a root-absolute path that would break under a subpath deployment exactly as much as a card-image path would. **This is a pre-existing, already-present deployment gap, unrelated to artwork** — it applies equally to the favicon today. It must be resolved once, project-wide, whenever real deployment is actually attempted (via `base` + `import.meta.env.BASE_URL`, or a custom domain that serves from root) — it is not made worse or better by any OD-3 option chosen here.

---

## 4. Existing `image_ref` Architecture

Traced end-to-end, fresh this step:
- **Seed YAML** (`backend/app/reference_data/rider_waite_smith/wands.yaml` etc.): e.g. `image_ref: rws/wands/four-of-wands.png` — Raidian Wise's own placeholder convention (`rws/{suit}/{rank}-of-{suit}.png` for Minor Arcana, `rws/major/{2-digit-rank}-{slug}.png` for Major Arcana per `RAIDIAN_WISE_REFERENCE_DATA_V1.md` Section 6), confirmed populated for all 78 cards.
- **Seed loader** (`backend/app/seed/loader.py:119`): `image_ref` is a required, non-empty text field, validated for presence only — no format/pattern enforcement.
- **Seed writer** (`backend/app/seed/seed.py:67`): `card.image_ref = card_def["image_ref"]` — written verbatim, no transformation.
- **Model** (`backend/app/models/card.py:52`): `image_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)`.
- **API schema/response** (`backend/app/schemas/reference_data_api.py:82`, `backend/app/api/reference_data.py:109`): passed through verbatim as `image_ref: str | None` on `CardSummary`, no transformation, no URL-building.
- **Frontend type** (`frontend/src/api/cards.ts:25`): `image_ref: string | null`, explicitly documented as "carried through for type-completeness only" — not currently rendered anywhere.
- **Spread Review / Card Entry:** neither `SpreadReviewPage.tsx` nor `CardEntryPage.tsx` reads `image_ref` today (unchanged since Steps 50/67/68).

**Does the TaionWC source share `image_ref`'s filename scheme?** **No.** TaionWC's Minor Arcana files use a two-digit-number-plus-suit scheme (e.g. `Wands04.jpg` for the Four of Wands), while Raidian's own `image_ref` uses a spelled-out-rank scheme with a `.png` extension (`rws/wands/four-of-wands.png`). These do not match 1:1 by construction. **This means some acquisition-time mapping (a rename step, or a small lookup table pairing each source filename to its corresponding `image_ref` value) is required no matter which architecture option is ultimately chosen** — it is not created or avoided by any one option, and it does not require a database/schema change either way, since `image_ref` is already a plain string column with no format constraint.

**Can `image_ref` remain unchanged and simply become a logical asset key?** **Yes**, confirmed by this trace — this reconfirms Step 48's original recommendation (`CARD_IMAGE_ASSET_DESIGN.md` Section 7) with fresh evidence: `image_ref`'s current shape (a relative, path-like string) is already exactly what a frontend-owned or backend-owned base-path join needs, for any of Options A–C.

---

## 5. Option A Evaluation — Frontend-bundled static assets

Files placed under `frontend/public/cards/...`, resolved from `image_ref` by the frontend at render time.
- **GitHub Pages compatibility:** Direct fit — GitHub Pages serves static files with zero backend involvement, which is exactly what this option needs. No new hosting mechanism required.
- **Vite behavior:** Anything under `frontend/public/` is copied verbatim into `dist/` at build time and served at a path relative to `base` (default `/`, or whatever subpath is eventually configured). This is the same mechanism already used for `favicon.svg`.
- **Subpath deployment:** Requires the same `base`/`import.meta.env.BASE_URL` handling the repository will need regardless of artwork (Section 3) — not a new requirement created by this option.
- **Cacheability:** Static files under a build's `dist/` get normal long-lived HTTP caching from any static host, including GitHub Pages, with no extra configuration.
- **Simplicity:** Highest of the four real options — no new service, no new mount, no new account.
- **Portability:** Works under any static host, not just GitHub Pages, since it introduces no GitHub-Pages-specific mechanism.
- **Repository size:** 78 fixed, small (public-domain scan, typically tens to a few hundred KB each) image files — a bounded, one-time, known-size addition, not an open-ended growth pattern, since the deck is fixed for MVP/post-MVP (multi-deck/user-uploaded content is explicit Future Scope, not current scope).
- **Backend changes required:** None.
- **Can `image_ref` remain unchanged?** Yes (Section 4).

## 6. Option B Evaluation — Backend-served static assets

FastAPI/Starlette `StaticFiles` mount (not implemented here).
- **Deployment implications:** Couples image availability to the API service's (Render's) own uptime/cold-start/latency profile, rather than a dedicated static host's.
- **CORS implications:** None blocking — cross-origin `<img>` loads do not trigger CORS preflight, so `CORSMiddleware`'s existing allow-list would not need to change.
- **Frontend/backend coupling:** Adds a new responsibility (serving static binary content) to a service whose current architecture (per `backend/app/main.py`) is purely a JSON API — a real, if modest, architectural mixing not currently present anywhere else in the backend.
- **URL construction:** Would require the frontend to build backend-relative image URLs (`VITE_API_BASE_URL` + a new `/assets/cards/...` path), a small but real new piece of plumbing not needed by Option A.
- **Render behavior:** Feasible (`StaticFiles` ships with Starlette, no new dependency), but no such mechanism exists today and would need to be added specifically for this.
- **Complexity vs. benefit:** For 78 fixed, public files with no access-control requirement, this adds real complexity (new mount, new URL scheme, new deploy-time coupling) with no corresponding benefit over Option A.

## 7. Option C Evaluation — External CDN/object storage

Evaluated conceptually only; nothing created.
- **Infrastructure requirements:** A new external account (e.g. an S3-compatible bucket or similar) — currently, no such account, credential, or configuration exists anywhere in this repository.
- **Credentials/configuration:** Would require new secrets management, which the project has not yet built (no secrets infrastructure beyond `.env`/environment variables for JWT/CORS today).
- **Reliability:** Generally excellent for a mature CDN, but this is a reliability profile the project does not currently need — 78 static files served alongside a Vite-built frontend already get adequate reliability from whatever host serves that frontend.
- **Cost:** Low at this fixed scale, but non-zero and entirely avoidable.
- **Portability:** Ties the project to a specific external vendor for content that doesn't require one.
- **Verdict:** Disproportionate for a fixed, 78-file, public-domain, single-deck asset set. This option exists for a future multi-deck/user-generated-content scenario (explicit Future Scope, not current scope), not for what OD-3 actually needs to solve today.

## 8. Option D Evaluation — Third-party hot-linking

- **External availability / URL stability:** Raidian Wise would depend on Wikimedia Commons' own uptime, URL structure, and bandwidth/rate-limiting policies for a core, user-facing product feature it does not control.
- **Hot-linking policies:** Wikimedia does not prohibit hotlinking outright, but production applications are broadly discouraged from relying on it for exactly this reason — no SLA, no guarantee against future URL/structure changes.
- **Reproducibility:** A future Commons-side file replacement, rename, or deletion could silently break Spread Review with no ability for Raidian Wise to fix it independently.
- **Application independence:** Directly conflicts with Raidian Wise's established architectural preference for deterministic, self-contained behavior — the same principle already governing the interpretation engine and narrative assembler (zero external/AI calls, fully deterministic, confirmed repeatedly across Steps 53–61). Introducing a live third-party runtime dependency for card art would be a real, avoidable inconsistency with that existing value.
- **Source vs. host distinction:** OD-2 selected Wikimedia Commons as the **verified source to acquire the files from once**, not as a designated runtime image host — these are different roles, and conflating them is exactly the mistake this step was asked to avoid (Section "Important distinction" above).
- **Verdict:** Rejected. Not appropriate for this application.

## 9. Option E Evaluation — Continue text placeholders

No longer a viable **final** architecture, per OD-1's resolution (`Documentation/STEP71_OD1_PRODUCT_DECISION.md`) — Spread Review must display actual rendered card artwork. Option E remains accurate only as a description of Spread Review's **current, interim** state, and remains Card Entry's **permanent** approach (Card Entry's own "visual card browsing" deferral is unaffected by OD-1, confirmed in Step 71). It is evaluated here only for completeness, not as a candidate for Spread Review's end state.

---

## 10. Comparative Technical Analysis

| Dimension | A (frontend-bundled) | B (backend-served) | C (CDN) | D (hot-link) |
|---|---|---|---|---|
| New infrastructure required | None | New mount (code only) | New account/credentials | None |
| New dependency | None | None (Starlette ships `StaticFiles`) | Likely (SDK or config) | None |
| Backend change | None | Yes | Possibly (signed URLs) | None |
| Fits documented hosting intent (ADR-0004) | Direct fit (GitHub Pages) | Adds new API responsibility | Adds a third host | N/A — no Raidian-owned host at all |
| `image_ref`/schema change | None | None | None | None |
| Runtime third-party dependency | None | None | Vendor-dependent | Wikimedia Commons (uncontrolled) |
| Consistent with deterministic/self-contained architecture value | Yes | Yes | Yes (with added ops surface) | No |
| Appropriate for 78 fixed files, no growth expected | Yes | Overkill | Overkill | N/A |

---

## 11. Recommended Architecture

**Option A — Frontend-bundled static assets** (`frontend/public/cards/...`).

## 12. Why the Recommendation Fits Raidian Wise

This is not chosen for being the easiest path — it is chosen because it is the only option requiring **zero new infrastructure, zero new dependency, and zero new backend responsibility** for a **fixed, single, 78-file, already-verified-public-domain deck** in an application that currently has **no deployment infrastructure of any kind**. It directly matches the one hosting decision this project has actually ratified (ADR-0004: GitHub Pages for the frontend), reuses the exact convention already in place for `favicon.svg`, and is consistent with the project's own established preference for deterministic, self-contained behavior (the same principle already governing the interpretation/narrative engine). Options B and C both solve problems Raidian Wise does not currently have (API-service asset coupling, or multi-tenant/dynamic content scale); Option D introduces exactly the kind of external runtime dependency the rest of this application's architecture deliberately avoids.

## 13. Impact on Backend

None. No backend code, schema, dependency, or configuration change is required by Option A.

## 14. Impact on Frontend

A new `frontend/public/cards/` directory (not created in this step) and a small, frontend-owned resolver function mapping `image_ref` → a build-relative asset path, used by `SpreadReviewPage.tsx` (and optionally `CardEntryPage.tsx`, though Card Entry's own scope remains unaffected by OD-1). Not implemented here — this is architecture selection only, per this step's explicit boundaries.

## 15. Impact on Database/Schema

None. `image_ref`'s existing shape and column definition already accommodate this option with no widening, narrowing, renaming, or migration.

## 16. Impact on Deployment

None immediate — Option A requires no new deployment step beyond what the frontend build already does. It does inherit the pre-existing, artwork-unrelated GitHub Pages subpath/`base` question (Section 3), which will need to be resolved once, project-wide, whenever real deployment is attempted — not created or worsened by this decision.

## 17. Asset Acquisition Implications

Not performed in this step (explicitly out of scope). When acquisition eventually happens: the 78 verified TaionWC files (Section 4) will need to be downloaded once and mapped to Raidian's existing `image_ref` naming convention (either by renaming files to match `image_ref` exactly, or via a small lookup table) — this mapping step is required regardless of architecture and is not new work created by choosing Option A specifically.

## 18. Missing/Fallback Image Strategy Requirements

Not implemented in this step. Restating Step 48's still-valid, unimplemented recommendation (`CARD_IMAGE_ASSET_DESIGN.md` Section 8) for a future implementation step: a card with a null or unresolvable `image_ref` should render a calm, clearly-labeled fallback (at minimum the card's name and orientation) rather than a broken-image icon, since `image_ref` remains a nullable column at the schema level.

## 19. Implementation Prerequisites

Before any implementation step acts on this decision: (1) acquire and locally verify the 78 TaionWC files against the licensing evidence in `Documentation/STEP72_OD2_ARTWORK_SOURCE_INVESTIGATION.md`; (2) decide the exact `frontend/public/cards/` naming/mapping convention; (3) decide the missing-image fallback UI (Section 18); (4) decide whether Card Entry's scope is touched at all (it is not required to be, per OD-1). None of these are performed by this step.

## 20. Explicit OD-3 Decision

**OD-3: RESOLVED — Frontend-bundled static card artwork (Option A).**

This resolves *how* verified artwork should be served. It does not download any file, does not implement any rendering, and does not select the exact acquisition/mapping mechanics (Section 19) — those remain for a future implementation step.

## 21. Verification Results

- `git diff --check`: run, reported in the final report below.
- No build was required or run — no source/configuration file was changed by this step.
- No backend tests were required or run — no backend code was changed.
- No browser testing performed or claimed.
- Confirmed: no image/artwork/binary file was added anywhere in the repository by this step.
- Confirmed: OD-1 and OD-2 remain resolved, unchanged, and untouched by this step.
- Confirmed: no implementation (rendering, fallback, static-serving, dependency) occurred.

## 22. Git Status

See the Step 73 final report for the exact `git status` output captured after this document was written.
