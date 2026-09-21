# Frontend Integration Audit & Design (Step 45)

Read-only design/audit. No frontend, backend, test, or existing
documentation file was modified in producing this report. No UI was
implemented. Every claim below was independently verified against the
current repository — direct reads of every file in `frontend/`, a live
OpenAPI schema dump of the current backend, and a repository-wide search
for card-image assets — not assumed from any prior step.

---

# 1. Executive Summary

The `frontend/` directory is a **completely unmodified** `npm create
vite@latest` React + TypeScript scaffold — not a single line of
Raidian-specific code exists yet. No routing library, no HTTP client, no
environment/API-base-URL handling, no auth-token handling, and no
design system are installed or wired in, despite Tailwind CSS being
present as an unused dependency. This is the expected, correct starting
point for this step — not a defect.

The backend contract (Steps 22–44) is stable, fully tested, and now
covers the entire authenticated Reading lifecycle plus public reference
data. Mapping it against the Product Spec's actual MVP screen list
(Section 3) surfaces **one significant, previously-undiscovered gap**:
**no card image asset exists anywhere in this repository, and nothing
serves the images `Card.image_ref` values (e.g.
`"rws/major/00-the-fool.png"`) point to.** Every other screen maps
cleanly onto an existing endpoint. Two smaller, already-known gaps
(no Login/Register screen in the Product Spec's own screen inventory;
no way to list or resume an abandoned in-progress Reading) are restated
precisely rather than re-discovered.

This document does not resolve any of these. Section 9 names them
precisely; Section 11 proposes an implementation sequence that does not
depend on resolving the image-asset question first.

---

# 2. Current Scaffold Inventory — Exact

Every non-`node_modules` file in `frontend/`, confirmed via direct
listing and full reads:

```
frontend/
  .gitignore
  README.md                  (Vite's own default README, unedited)
  eslint.config.js
  index.html                 (<title>frontend</title> -- never renamed)
  package.json
  package-lock.json
  public/favicon.svg
  public/icons.svg
  src/App.css
  src/App.tsx                (Vite's default demo component, unedited)
  src/assets/hero.png
  src/assets/react.svg
  src/assets/vite.svg
  src/index.css
  src/main.tsx
  tsconfig.app.json
  tsconfig.json
  tsconfig.node.json
  vite.config.ts
```

**Confirmed, precisely:** this is not a partially-customized scaffold —
`App.tsx` is still Vite's own demo component (a click counter, links to
vite.dev/react.dev/GitHub/Discord/X/Bluesky), `App.css`/`index.css` are
Vite's own default styling (a purple `--accent: #aa3bff`, dark-mode
media query, the demo's own `.hero`/`#next-steps` layout), and
`src/assets/` contains only the template's own placeholder images. No
file contains any reference to Raidian, tarot, readings, or this
project's own domain vocabulary.

**Dependencies** (`package.json`, re-read fresh):
```json
"dependencies": {
  "@tailwindcss/vite": "^4.3.3",
  "react": "^19.2.8",
  "react-dom": "^19.2.8",
  "tailwindcss": "^4.3.3"
},
"devDependencies": {
  "@eslint/js", "@types/node", "@types/react", "@types/react-dom",
  "@vitejs/plugin-react", "eslint", "eslint-plugin-react-hooks",
  "eslint-plugin-react-refresh", "globals", "typescript",
  "typescript-eslint", "vite"
}
```
**No routing library, no HTTP client, no state-management library, no
form library, no UI component library is installed.** Scripts: `dev`
(`vite`), `build` (`tsc -b && vite build`), `lint` (`eslint .`),
`preview` (`vite preview`) — all Vite defaults, unmodified.

**TypeScript configuration** (`tsconfig.app.json`, re-read fresh):
target `es2023`, `moduleResolution: "bundler"`, `noUnusedLocals`/
`noUnusedParameters`/`noFallthroughCasesInSwitch` enabled. **`"strict"`
is not set anywhere in either `tsconfig.app.json` or `tsconfig.json`**
— TypeScript's own default (`strict: false`) therefore applies. This is
a real, if minor, divergence from the Vite React-TS template's more
commonly-seen `strict: true` default, worth correcting before
substantial application code is written (Section 11) — not a blocker to
this design step itself.

## 2.1 Routing / Navigation

**None exists.** No `react-router-dom`, `@tanstack/react-router`, or any
routing package is installed; `main.tsx` renders `<App />` directly with
no router wrapper. The entire "app" today is the single, static demo
component Vite generated.

## 2.2 Styling / Design System

**Tailwind CSS is installed but completely inert.** `@tailwindcss/vite`
and `tailwindcss` are `package.json` dependencies, but `vite.config.ts`
(re-read fresh: `plugins: [react()]` only) does not include the
Tailwind Vite plugin, and `index.css` contains no `@import "tailwindcss"`
directive anywhere. The actual, currently-active styling is Vite's own
demo CSS (`App.css`/`index.css`), built on plain CSS custom properties,
with no component library, no typography scale, no color-token system
beyond the demo's own single `--accent` purple, and no connection
whatsoever to `docs/PRINCIPLES.md`'s stated guiding philosophy (Section
3) or any Raidian-specific visual identity.

**No design system exists** — per this conversation's own established
convention (`artifact-capabilities`/design-system tooling used
elsewhere is unrelated to this repository), there is nothing to reuse
or extend; Section 11 names "wire up Tailwind and establish base design
tokens" as an early, concrete implementation task, not a resolved
decision about what those tokens should be.

---

# 3. Backend Contract — Re-Confirmed Live

A fresh `app.openapi()['paths']` dump (not assumed from Step 44's own
report) confirms the complete, current, stable surface:

| Method | Path | Auth |
|---|---|---|
| POST | `/auth/register` | none |
| POST | `/auth/login` | none |
| GET | `/spreads` | none (public) |
| GET | `/cards` | none (public) |
| GET | `/decks` | none (public) |
| POST | `/readings` | Bearer |
| GET | `/readings` | Bearer |
| GET | `/readings/{reading_id}` | Bearer, owned |
| POST | `/readings/{reading_id}/draws` | Bearer, owned |
| POST | `/readings/{reading_id}/save` | Bearer, owned |
| POST | `/readings/{reading_id}/interpret` | Bearer, owned |
| GET | `/readings/{reading_id}/interpretations` | Bearer, owned |
| GET | `/readings/{reading_id}/interpretations/current` | Bearer, owned |
| GET | `/readings/{reading_id}/narrative` | Bearer, owned |

CORS is live and correctly scoped to `http://localhost:5173`/
`http://127.0.0.1:5173` by default (Step 41), matching this scaffold's
own, unoverridden Vite dev-server port (re-confirmed:
`vite.config.ts` sets no `server.port`, so Vite's documented default,
5173, applies).

---

# 4. Product Spec MVP Screens → Backend Endpoints

Re-read directly from `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Sections 5/6
(the step-by-step flow and the screen inventory), mapped against Section
3's live endpoint list:

| Product Spec Screen | Backend Endpoint(s) | Notes |
|---|---|---|
| Home | `GET /readings` (history preview) | The Product Spec's own "view recent readings" wording is ambiguous about whether this means *saved* readings only or also in-progress drafts — Section 9 names this precisely. |
| New Reading — Layout Selection | `GET /spreads` | Public; no auth needed to browse. |
| New Reading — Question (+ domain) | *(no endpoint yet — local form state)* | Bundled into the eventual `POST /readings` call (Section 6). |
| New Reading — Draw Method | *(no endpoint — local form state; Digital Draw has no backend implementation, Section 9)* | `POST /readings`'s own `draw_method` field, defaulting to `PHYSICAL`. |
| — (Reading creation itself) | `POST /readings` | Fires once Spread + Question (+ optional domain/draw_method) are all known — exact firing point is a frontend flow decision, Section 6. |
| New Reading — Card Entry (Physical) | `GET /cards` (selector), `POST /readings/{id}/draws` (per card) | One `POST` call per Layout Position, matching the Product Spec's own "one interaction per Layout Position" wording. |
| New Reading — Digital Draw Result | *(no endpoint — not implemented server-side, Section 9)* | `DrawMethod.DIGITAL` exists in the schema but has no corresponding random-draw route anywhere. |
| Spread Review | `GET /readings/{reading_id}` | The exact gap this route (Steps 42–44) was built to close. |
| Interpreting (transient) | `POST /readings/{reading_id}/interpret` | The response itself is the content the next screen needs — no separate fetch required. |
| Reading Result | *(same `POST .../interpret` response)*, or `GET .../interpretations/current` + `GET .../narrative` on reload | Two viable data-flow shapes, named precisely in Section 6. |
| Save action (part of Reading Result) | `POST /readings/{reading_id}/save` | |
| Reading History | `GET /readings` | Saved-only, newest-first — unchanged since Step 24. |
| Reading Detail | `GET /readings/{reading_id}` | Same route as Spread Review — one endpoint, two consuming screens. |
| Basic Settings (deck info) | `GET /decks` | Confirmed sufficient (Step 40/41's own reasoning). |
| Standing Disclaimer | *(static content — no endpoint needed)* | Purely a frontend content/copy concern. |
| **Login / Registration** | `POST /auth/login` / `POST /auth/register` | **Not named anywhere in the Product Spec's own screen inventory** — already identified as a genuine Product Spec gap by `READING_HISTORY_OWNERSHIP_DESIGN.md` Section 8 (Step 21-era finding, re-confirmed here, not newly discovered): "no Login, Signup, or Account screen appears anywhere" in the spec's own list. The frontend must design these two screens without Product Spec screen-inventory guidance on their content/flow (the *API contract* itself is fully specified — Step 22 — only the *screen design* is unaddressed). |

**Every screen the Product Spec names in its MVP scope maps onto an
existing, stable endpoint except two: Digital Draw (deferred,
pre-existing, not new) and the underlying image assets Card Entry/
Spread Review/Reading Result all visually depend on (new finding,
Section 9).**

---

# 5. API Client Layer — Design (Not Implemented)

**Base URL:** `import.meta.env.VITE_API_BASE_URL`, Vite's own standard
mechanism for build-time-injected, client-exposed environment variables
(the `VITE_` prefix is required by Vite itself for a variable to reach
client code at all). No `.env`/`.env.example` currently exists in
`frontend/` — one should be added (Section 11) with a local-dev default
(`http://localhost:8000`, matching this backend's own default `uvicorn`
port convention) and the production value left as a deployment-time
override, mirroring the exact same "safe local default, override
required for real deployment" pattern this project's own backend
`Settings` class already uses for `jwt_secret_key`/`cors_allowed_origins`.

**HTTP mechanism:** native `fetch` — no HTTP client library is
currently installed, and nothing about this backend's contract (plain
JSON bodies, Bearer auth header, standard status codes) requires one.
A small, hand-written wrapper (not a new dependency) is sufficient:
one function per resource area (`auth.ts`, `readings.ts`,
`referenceData.ts`), each calling a shared `request()` helper that
attaches `Authorization: Bearer <token>` when a token is present,
sets `Content-Type: application/json` for any request with a body, and
throws a typed error on a non-2xx response (parsing the backend's own
consistent `{"detail": "..."}` error shape, confirmed unchanged across
every route audited in Steps 29–44).

**Response typing:** hand-written TypeScript interfaces mirroring the
backend's own Pydantic schemas one-for-one (`ReadingSummary`,
`ReadingDetail`, `ReadingCardDrawSummary`, `CardDrawSummary`,
`SpreadSummary`, `SpreadPositionSummary`, `CardSummary`, `DeckSummary`,
`InterpretationSummary`, `InterpretationHistoryEntry`, `NarrativeModel`)
— not code-generated from the live OpenAPI schema in this design (a
generator could be adopted later; naming it here as a *future*
convenience, not a requirement, since the schema surface is small and
stable enough to hand-maintain for MVP).

## 5.1 Authentication Token Handling

**Storage: `localStorage`.** This project's own backend design document
(`AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md` Section 13.2/14.1,
re-read fresh) already named this as the leading candidate, explicitly
because the already-approved "no refresh tokens" decision (Step 20/21)
makes a pure in-memory-token approach impractical (it would force a full
re-login on every page reload, not merely after the token's own expiry).
That document left the final choice as "a frontend-implementation-time
choice, not a blocking one" — this design adopts `localStorage` as the
concrete recommendation for the implementation step to build against,
not a silent re-opening of that document's own framing.

**Attachment:** every authenticated request's `request()` call reads the
token from `localStorage` and sets the `Authorization` header; requests
to the three public reference-data routes never attach one.

**Expiry handling:** the backend gives no distinct signal for "expired"
vs. any other invalid-token condition (Step 29/39's own finding,
unchanged: `get_current_user` collapses every failure into an identical
`401`). The frontend's `request()` wrapper should treat any `401` from
an authenticated call uniformly — clear the stored token and redirect
to Login — since the backend provides no finer-grained signal to act on
differently.

**Logout:** client-side token removal only — no server endpoint exists
or is needed (re-confirmed, Section 3's live route list has no
`/auth/logout`), consistent with this project's own already-approved,
stateless-JWT design.

---

# 6. Frontend Data Flow

For each stage this step asks about, the exact request/response shape
and sequencing, grounded in the live contract (Section 3):

## Register / Login
1. `POST /auth/register` → `{id, email, created_at}` (no token) — the
   frontend must then separately call login, since registration does
   not authenticate (Step 44/39's own re-confirmed finding).
2. `POST /auth/login` → `{access_token, token_type}` — store per
   Section 5.1, then navigate to Home.

## New Reading — Spread Selection
`GET /spreads` (public, no token needed even if the user later needs to
log in to actually create a Reading — the Layout Selection screen
itself can be browsed pre-auth, an option this design leaves open, not
mandatory) → render `name`/`description`/`position_count` per Spread
for the Layout Selection list; the full embedded `positions` array
(already present in every response, Step 41's own "smallest number of
endpoints" reasoning) is not needed until Card Entry, but requires no
second fetch since it is already in hand.

## New Reading — Question / Draw Method
Pure local component/form state — no backend call. Accumulates
`spread_id` (from the selection above), `question`, `question_domain`,
`draw_method` in memory (or a lightweight client-side store, Section
11) until enough information exists to create the Reading.

**Exact Reading-creation firing point — a frontend flow decision, not
resolved here:** `POST /readings` requires only `spread_id` and
`question` (`draw_method` and `deck_id` both have server-side defaults,
Step 27). The frontend could fire this call as early as immediately
after Question entry (before Draw Method is even shown, since it
defaults to `PHYSICAL`), or hold off until Draw Method is explicitly
confirmed. Both are valid against the current contract; this document
recommends firing it once Draw Method is confirmed (preserving the
Product Spec's own literal step ordering, "5. User chooses a draw
method" before "6. ...draws cards") without treating that recommendation
as a resolved requirement — the actual implementation step should
confirm this against whatever wizard/state-management shape it adopts.

## Card Selection / Drawing Cards
`GET /cards` (public, optionally `?deck_id=`) → render the
searchable/filterable selector (client-side filtering only, per Step
40's own dataset-size reasoning — 78 rows, no server-side search).
Once the user confirms a card + orientation for a given Layout
Position: `POST /readings/{reading_id}/draws` with
`{position_id, card_id, orientation}` — `draw_order` is never sent
(server-computed, Step 32). The response's `reading_status` field tells
the frontend immediately whether this draw completed the spread,
without a separate fetch.

## Spread Review / Reading Detail
`GET /readings/{reading_id}` → the full, already-designed
`ReadingDetail` shape (Steps 42–44): `status`, `question`,
`question_domain`, `draw_method`, the embedded `spread` (with ordered
positions), and `card_draws` (each with its embedded `position`/`card`
and `orientation`/`draw_order`). One call renders the entire Spread
Review screen, including still-empty positions (visible via
`spread.positions` even when no matching `card_draws` entry exists yet)
— exactly the capability this route was built to provide. The same
endpoint, called later against a `SAVED` Reading's `id` from History,
serves the Reading Detail screen identically.

## Interpretation
`POST /readings/{reading_id}/interpret` → `InterpretationSummary`,
including the full `interpretive_model` (citations with
`card_name`/`position_name` already embedded, Step 39's own finding) —
**sufficient on its own to render the Reading Result screen's
evidence-backed sections without a further call.** For the prose
narrative specifically: `GET /readings/{reading_id}/narrative` →
`NarrativeModel` with ready-to-render section text. **Two viable
sequencing shapes, not resolved here:** (a) call `/interpret` then
immediately call `/narrative` before rendering Reading Result at all, or
(b) render the structured/citation content from `/interpret`'s own
response first, then separately fetch `/narrative` for the prose layer.
Either is fully supported by the existing contract; this is a frontend
rendering-strategy choice, not a backend gap.

## Save
`POST /readings/{reading_id}/save` → updated `ReadingSummary`
(`status: "saved"`). Triggers the Reading Result screen's "Save" action;
after success, the Reading becomes visible in History for the first
time (Step 24's own `status == SAVED` filter).

## History
`GET /readings` → `list[ReadingSummary]`, saved-only, newest-first. Each
entry's `id` is now directly usable with `GET /readings/{id}` (Reading
Detail) — the exact capability Step 39's Gap 1/3 identified as missing
and Steps 42–44 closed.

---

# 7. Backend Contract Gaps Newly Visible From This Mapping

## 7.1 No card image assets exist anywhere — new finding

A repository-wide search for image files found only the Vite template's
own placeholder assets (`hero.png`, `react.svg`, `vite.svg`) and this
project's `favicon.svg`/`icons.svg` — **zero card-artwork files of any
kind, and no static-file-serving route in the backend for any asset
path.** `Card.image_ref` values (e.g. `"rws/major/00-the-fool.png"`,
confirmed via live query in Step 40) are strings pointing at a path
convention with nothing behind it anywhere in this codebase.

**This was not previously named by any Step 17–44 document** — every
prior audit focused on the Reading/CardDraw/ownership *data* contract,
never on whether the *visual assets* that contract's own `image_ref`
field implies actually exist. It becomes visible only once the real
frontend's actual rendering need (Card Entry's selector, Spread
Review's "full visual layout... of all positions, cards" per the
Product Spec's own wording) is mapped against the real repository
contents.

**Not resolved here.** Plausible directions — bundling licensed
Rider-Waite-Smith artwork as frontend static assets, serving them from
a new backend static-file route, or pointing at a third-party
image CDN — each carry different licensing, deployment, and
architecture implications this document does not evaluate or choose
between. Named as an open question, Section 9.

## 7.2 No Product Spec screen for Login/Registration — restated, not new

Already identified by `READING_HISTORY_OWNERSHIP_DESIGN.md` Section 8
(pre-dating this entire Reading/CardDraw series). Re-confirmed
unresolved: the Product Spec's own screen inventory (Section 6) still
does not name a Login, Signup, or Account screen anywhere, even though
the backend API contract for both has been complete and stable since
Step 22. The frontend implementation step will need to design these
screens' content/flow without Product Spec guidance — the *data*
contract is not in question, only the *screen design*.

## 7.3 No way to list or resume an in-progress (unsaved) Reading — new finding

`GET /readings` (History) filters `status == SAVED` only (unchanged
since Step 24, by explicit design — `READING_HISTORY_OWNERSHIP_DESIGN.md`
Section 7). A user who starts a Reading, draws some cards, and closes
the browser before saving has a `DRAFTING`/`SPREAD_COMPLETE` Reading row
that is **not visible through any endpoint** unless the frontend itself
remembers that specific `reading_id` (e.g., in `localStorage`) and
offers its own "resume" affordance. There is no `GET /readings?status=...`
filter, and none was ever designed to exist. This directly affects how
literally to interpret the Product Spec's Home-screen wording ("view
recent readings") — Section 9.

## 7.4 Digital Draw — restated, not new

`DrawMethod.DIGITAL` exists in the enum and is accepted by
`POST /readings`, but no endpoint anywhere performs a randomized draw or
implements the Product Spec's own Digital Draw requirements (an
unbiased CSPRNG shuffle, blind to the question, Section 8 of the spec).
Already self-documented in the model's own docstring as deferred
(re-confirmed present, unchanged) — not a new discovery, restated here
because it directly affects the Draw Method screen's actual buildable
scope for MVP.

---

# 8. Response Schema Sufficiency for the Frontend

Re-checked directly against every schema named in Section 6 — no
response the frontend needs for any mapped screen depends on an
undocumented field or a second, unlisted endpoint, **except** the image
question in Section 7.1, which is not a *data* gap (every schema
already carries `image_ref`) but an *asset-availability* gap.

---

# 9. Open Product/Design Questions — Not Resolved

| Question | Status |
|---|---|
| Where do card images actually come from? | **New, unresolved — Section 7.1.** Requires a product/licensing/architecture decision this document does not make. |
| Should Home / "recent readings" include in-progress drafts, or only saved history? | **New, unresolved — Section 7.3.** The Product Spec's own wording is ambiguous; the backend has no endpoint for the "include drafts" interpretation today regardless. |
| Exact point in the New Reading wizard where `POST /readings` fires | **Frontend flow decision, recommended but not mandated — Section 6.** |
| Sequencing of `/interpret` vs. `/narrative` calls when rendering Reading Result | **Frontend rendering-strategy choice, not a backend gap — Section 6.** |
| Login/Registration screen content and flow | **Restated open Product Spec gap, pre-existing — Section 7.2.** Data contract is settled; screen design is not. |
| Digital Draw | **Restated, already deferred — Section 7.4.** Not part of MVP's actual buildable scope regardless of the Product Spec's own listed intent, unless separately authorized as new backend work. |
| Auth-token storage mechanism | **Recommended (`localStorage`) — Section 5.1** — not silently mandated; the cited backend design document's own framing ("frontend-implementation-time choice") is preserved, with a concrete recommendation supplied for the implementation step to confirm or override. |

**No product decision is silently resolved by this document.**

---

# 10. TypeScript / Tooling Notes (Minor, Not Blocking)

- `strict` mode is not enabled anywhere in the current TypeScript
  configuration (Section 2) — recommended to enable before substantial
  application code is written (Section 11), not required to unblock
  this design.
- Tailwind is an installed but entirely unwired dependency (Section
  2.2) — wiring it in (the Vite plugin + the CSS `@import`) is a small,
  mechanical first implementation task, not a design decision in
  itself; the *design tokens* built on top of it are a separate,
  later choice this document does not make.

---

# 11. Recommended Implementation Sequence

Mirroring this project's own established Design → Implementation
pairing, broken into small, independently-verifiable steps rather than
one large frontend build:

1. **Tooling foundation** — enable TypeScript `strict` mode; wire up the
   Tailwind Vite plugin and base `@import`; add `react-router-dom` (or
   an equivalent) and establish the route skeleton (Home, Login,
   Register, New Reading wizard, Reading Detail, History, Settings) with
   placeholder screens only — no API integration yet. Add `.env.example`
   documenting `VITE_API_BASE_URL`.
2. **API client layer** — implement the `request()` wrapper and
   per-resource client modules (Section 5), plus the hand-written
   TypeScript interfaces mirroring the backend schemas (Section 5).
   Verify against the live backend (already running, already tested)
   with a minimal smoke screen before building real UI on top of it.
3. **Auth flow** — Register and Login screens, token storage (Section
   5.1), a route guard redirecting unauthenticated users away from
   protected screens, and the uniform 401-handling behavior (Section
   5.1).
4. **Reference data + New Reading wizard (read-only parts first)** —
   Layout Selection (`GET /spreads`) and the Card Entry selector
   (`GET /cards`), rendered without images initially (Section 7.1 is
   still open at this point) or with a simple placeholder/fallback,
   confirming the decision from Section 9 does not block *starting*
   this work.
5. **Reading creation + drawing** — wire `POST /readings` at the
   flow point Section 6 recommends, then `POST /readings/{id}/draws`
   per position, using each response's `reading_status` to drive the
   wizard's own progression logic.
6. **Spread Review / Reading Detail** — `GET /readings/{id}`, one screen
   component serving both the in-progress Spread Review view and the
   later, saved Reading Detail view (Section 6).
7. **Interpretation + Reading Result** — `POST /readings/{id}/interpret`
   plus (per whichever sequencing Section 6 leaves open is chosen)
   `GET /readings/{id}/narrative`.
8. **Save + History** — `POST /readings/{id}/save`,
   `GET /readings` rendering the History list, each entry linking to
   the same Reading Detail component from step 6.
9. **Settings (deck info)** — `GET /decks`, the smallest remaining
   mapped screen.
10. **Resolve Section 9's open questions as they become blocking** —
    specifically, the card-image question (7.1) should be resolved
    before step 4/6's screens are considered feature-complete, but does
    not block starting or sequencing the work above.

This sequence deliberately defers the two genuinely unresolved product
questions (images, draft-resumability) to the points where they
actually become blocking, rather than stalling the whole effort on
them up front.

---

# 12. Verification

- No file was created, modified, or deleted in `frontend/`, `backend/`,
  or any existing `Documentation/*.md` file during this audit.
- `git status --porcelain` at the start and end of this step is
  identical except for this document's own addition,
  `Documentation/FRONTEND_INTEGRATION_DESIGN.md` — the sole new file.
- No test suite run was required or performed (no code changed); the
  backend's own last-confirmed state (Step 44: 474 passed, single
  migration head `5dc3cb471b18`) is unaffected and unchanged.
- Nothing was committed or pushed.
