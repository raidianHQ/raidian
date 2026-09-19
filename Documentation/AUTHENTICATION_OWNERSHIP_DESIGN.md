# Raidian Wise — Authentication & Ownership Architecture Design/Audit (Step 20)

# Document Information

Version: 1.0 (Draft for Review — Not Yet Approved)
Status: Proposed — Audit and Design Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Resolves the architectural design needed to introduce user identity and ownership into Raidian Wise, extending Step 19's (`READING_HISTORY_OWNERSHIP_DESIGN.md`) ownership-placement recommendation into a full authentication and authorization architecture: account model, token architecture, authorization boundary, existing-route retrofit, migration strategy, testing strategy, frontend boundary, and security/privacy analysis. This document implements nothing.

Audience:
Whoever holds product/governance authority over Raidian Wise (to accept, amend, or reject the recommendations and resolve the open decisions in Section 15), and the engineers who will implement whatever is accepted.

Authority:
Builds directly on `READING_HISTORY_OWNERSHIP_DESIGN.md` (Step 19), `SAVE_READING_DESIGN.md` (Step 17), `PRODUCT_DECISIONS.md` (Step 14), `READING_LIFECYCLE_DESIGN.md` (Step 13), `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` (Step 15), and `INTERPRETATION_API_DESIGN.md`. Does not override `docs/PRINCIPLES.md`, `docs/ARCHITECTURE.md`, or `docs/DECISIONS.md` — per ADR-0006's governance hierarchy (Charter → Vision → **Principles** → **Architecture** → **Decisions** → Agents → Roadmap → Naming Conventions), this document's own recommendations rank below all three and are offered as input to a future, higher-authority decision, not a substitute for one.

---

# 0. Scope

Read-only architecture/design and repository audit only. No application code, schema, migration, dependency, frontend code, or API route is created or modified. No existing test is modified. Where a question is genuinely unresolved by the repository or governance stack (Section 15), this document preserves that ambiguity rather than resolving it. Where a decision requires product/governance judgment (Section 4's authentication mechanism), this document recommends but does not decide — the same posture `PRODUCT_DECISIONS.md` Q1 and `READING_HISTORY_OWNERSHIP_DESIGN.md` Section 5 already modeled.

---

# 1. Executive Summary

Repeating Step 19's finding, now verified against a wider sweep (frontend included): **zero identity, authentication, or authorization infrastructure exists anywhere in this repository, on either side of the stack.** No `User` model, no password/token/session library in `backend/requirements.txt`, no FastAPI security dependency, no middleware, no secret-key configuration in `app/core/config.py`, and — newly confirmed by this step — the `frontend/` directory is the unmodified Vite+React scaffold: no router, no API client, no login form, no token storage of any kind. `docs/ROADMAP.md` places Authentication in **M1 (Core Architecture)** and Reading History in **M3 (Personal Growth)** — a roadmap-level confirmation, not previously stated this precisely, that Reading History is sequenced *after* Authentication by design, not merely blocked on it incidentally.

This document confirms Step 19's Option B ownership placement (`ReflectionSession.owner_id`) survives a full authentication-architecture pass unchanged, recommends Option 1 (app-managed credentials + JWT) as the smaller, fully self-contained authentication mechanism while explicitly declining to select it as final, designs the minimum `User` model and token architecture needed to make that mechanism concrete, and defines exactly where the resulting ownership check belongs — one reusable dependency, inserted at the same `reading_id → Reading` resolution point every one of the four shipped routes already uses (`_get_reading_or_404`). No part of this document changes the already-approved Reading/Draw lifecycle (Section 10 finds no lifecycle redesign is required).

---

# 2. Current-State Audit

Direct, repository-wide inspection — not inferred from any prior report.

## 2.1 Backend

| Searched for | Found? | Where |
|---|---|---|
| `class User` / any account model | **No** | Zero matches anywhere in `app/` |
| Password hashing library (`passlib`, `bcrypt`, `argon2`, etc.) | **No** | Confirmed against `backend/requirements.txt` directly (reproduced below) |
| JWT/token library (`python-jose`, `pyjwt`, `authlib`, etc.) | **No** | Same |
| OAuth/OIDC client library | **No** | Same |
| FastAPI security dependency (`OAuth2PasswordBearer`, `HTTPBearer`, a `get_current_user`) | **No** | `get_db()` (`app/db/session.py`) remains the only dependency anywhere in the API layer (`app/api/interpretation.py`, re-confirmed) |
| Middleware of any kind | **No** | `app/main.py` registers none |
| Secret/key configuration | **No** | `app/core/config.py`'s `Settings` class has exactly one field, `database_url` — no `SECRET_KEY`, no signing key, no token TTL, nothing security-adjacent |
| Migration referencing identity/ownership | **No** | All four existing migrations (`2520310c3acf`, `3468c874958d`, `74ffb042dc2d`, `f5f0af118106`) confirmed unrelated |
| API error convention for auth failures (401/403) | **No precedent** | Only `404` (`_get_reading_or_404`) and `409` (`ReadingNotReadyForInterpretationError`) exist as HTTP error mappings anywhere today |

`backend/requirements.txt` (full, current contents):
```
fastapi==0.141.1
uvicorn==0.52.4
SQLAlchemy==2.0.52
alembic==1.19.1
pydantic==2.13.4
pydantic-settings==2.15.0
psycopg2-binary==2.9.12
python-dotenv==1.2.3
PyYAML==6.0.3
pytest==9.1.1
httpx2==2.13.0
```
No auth-adjacent package of any kind. `python-dotenv` and `pydantic-settings` exist for `DATABASE_URL` configuration only (`app/core/config.py`), not for secrets generally.

`app/api/interpretation.py`'s own module docstring, unchanged since Step 11 and re-confirmed here: *"No authentication or authorization exists anywhere in this codebase yet... every route below is fully unauthenticated and performs no ownership check. This is an explicitly flagged interim state (acceptable only pre-launch, with no real user data), not an oversight."* This document is the follow-on that docstring has pointed to since Step 11.

## 2.2 Frontend — newly audited by this step, not covered by Steps 17/19

`frontend/` is the **unmodified Vite + React + TypeScript scaffold** generated by `npm create vite`, never built out:

- `package.json` dependencies: `react`, `react-dom`, `tailwindcss`, `@tailwindcss/vite` — no `react-router` (or any router), no `axios`/`fetch` wrapper, no state-management library, no auth/token library of any kind.
- `src/App.tsx` is the default Vite counter demo (an `<img>` hero, a click counter, links to Vite/React docs) — it makes zero API calls to the FastAPI backend, has no concept of a screen, route, or session.
- No login form, no signup form, no protected-route wrapper, no token-storage code (`localStorage`/cookie), no `Authorization` header attachment anywhere — because there is no HTTP client to attach one to yet.

**Conclusion:** the frontend consequence of this document's backend design is not "retrofit an existing auth UI" — there is no existing UI of any kind to retrofit. This narrows Section 13 considerably: the minimum frontend consequence is additive (new screens, new client code), not a modification of anything that exists today.

## 2.3 `ReflectionSession` — re-confirmed, not re-derived

Re-inspected directly (`app/models/reflection_session.py`) and unchanged from Step 19's Section 3 findings: no expiry, no token, no user reference; strict one-to-one with `Reading` (`Reading.reflection_session_id` is `unique=True`, `nullable=False`); "identity and timestamps only" by its own docstring. Step 19's preserved ambiguity (whether it can become the ownership boundary without changing its meaning) is inherited unchanged into this document — Section 3 below does not re-litigate it, only builds the concrete schema on top of Step 19's Option B recommendation.

## 2.4 Existing retrofit insertion point

Direct inspection of `app/api/interpretation.py` confirms all four existing routes share exactly one resolution helper:

```python
def _get_reading_or_404(session: Session, reading_id: UUID) -> Reading:
    reading = session.get(Reading, reading_id)
    if reading is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_READING_NOT_FOUND)
    return reading
```

Every route (`interpret_reading_route`, `get_current_interpretation_route`, `list_interpretations_route`, `get_narrative_route`) calls this and only this to resolve `reading_id`. This is the single, already-existing choke point Section 8 designs the retrofit against — not a new pattern this document invents.

---

# 3. Ownership Architecture

## 3.1 Re-evaluating Step 19's recommendation against the full authentication design

Step 19 recommended:

```text
User
  └── ReflectionSession (owner_id)
        └── Reading
              ├── CardDraw
              ├── Interpretation
              └── NarrativeModel (derived)
```

Nothing found in this step's wider audit (frontend, migration tooling, `docs/ROADMAP.md`'s M1/M3 sequencing) weakens that recommendation — if anything, ADR-0003's "modular and extensible" rationale is reinforced by the roadmap's own M1→M3 ordering, since Authentication (M1) is explicitly platform-wide infrastructure that Reading History (M3) merely consumes, not something Raidian Wise owns or should special-case. **This document reaffirms Option B (ownership on `ReflectionSession`), Option A (`Reading.owner_id`) as the valid, simpler fallback, and does not reopen Section 3's preserved `ReflectionSession`-semantics ambiguity from Step 19.**

## 3.2 Should `User` be the identity/account entity?

**Yes — no alternative was found.** No existing table or concept in this schema (`Deck`, `Spread`, `ReflectionSession`, `Reading`) is a plausible account entity; all are either shared reference data or already-analyzed domain entities (Step 19 Section 2.4's Option C conclusion, reconfirmed). A new `User` table is the only viable identity anchor.

## 3.3 Child-table ownership columns

**None required**, unchanged from Step 19 Section 6: `CardDraw`, `Interpretation`, and `NarrativeModel` (never persisted) all inherit ownership transitively through `Reading` → `ReflectionSession` → `User`. Adding a duplicate `owner_id` to any of them would violate this project's own repeatedly-applied "derive, don't store-and-risk-drift" precedent (`Spread.position_count`, `Reading.is_spread_complete`) for zero benefit.

## 3.4 Foreign-key behavior and deletion semantics

- `ReflectionSession.owner_id -> User.id`: recommend `ForeignKey("users.id", ondelete="CASCADE")`. Rationale: `docs/PRINCIPLES.md`'s "Privacy By Design" ("users should retain ownership and control of their personal reflections") argues for user-controlled deletion — if a `User` row is ever deleted, their reflections should not become orphaned rows silently owned by no one; cascading delete is the schema-level enforcement of "control" including the right to erase. This mirrors the existing `Reading.reflection_session_id` (`ondelete="CASCADE"`) and `Interpretation.reading_id`/`CardDraw.reading_id` (`ondelete="CASCADE"`) pattern already used consistently throughout this schema — not a new technique.
- **Not designed here:** whether user deletion is actually exposed as a product feature, and whether "delete" should instead mean "deactivate" (Section 15).

## 3.5 Uniqueness constraints

- `User.email` (or whichever identity field Section 4 settles on): unique, case-normalized (Section 5.1).
- `ReflectionSession.owner_id`: **not unique** — one `User` legitimately owns many `ReflectionSession` rows (every Reading a user ever starts creates one, per the existing strict 1:1 with `Reading`). This is a plain many-to-one FK, no new constraint shape needed.

## 3.6 Indexing

- `User.email`: unique index (also serves as the login lookup index).
- `ReflectionSession.owner_id`: a plain index, to make Reading History's future `WHERE reflection_sessions.owner_id = :user_id` filter (Step 19 Section 7.1) efficient — the same reasoning already applied to `Interpretation.sequence`'s uniqueness index.

## 3.7 Nullable during migration, or mandatory immediately?

**Nullable during a transitional phase, `NOT NULL` once backfilled — exactly the pattern `74ffb042dc2d` (`Interpretation.sequence`) already established and proved safe in this repository.** Elaborated in Section 11.

## 3.8 Existing rows

Addressed in Section 11 — this repository has no production deployment and no real user data (Step 19 Section 6, reconfirmed: "this audit found no production deployment and no real user data anywhere in this repository").

---

# 4. Authentication Mechanism

Re-evaluating Step 19 Section 5's two options against concrete repository/project criteria, per this task's explicit list.

## 4.1 Option A — Application-managed credentials + JWT

| Criterion | Evaluation |
|---|---|
| Compatibility with the decided stack | Full — FastAPI's own documented reference pattern (`OAuth2PasswordBearer` + a JWT-issuing login route) targets exactly this stack; ADR-0004 names no obstruction. |
| Dependency footprint | One password-hashing library (Section 5) + one JWT library — both small, single-purpose, widely used, no service dependency. |
| Deployment model | Fits Render/PostgreSQL with no new infrastructure category — a stateless signed token needs no server-side session store. |
| Local development | Fully offline — no external account, no sandbox credentials, no network dependency for `pytest` or manual testing. |
| Testing | Straightforward — a test can mint a valid token directly (calling the same signing function the login route uses) without a live HTTP round-trip to a third party; consistent with this project's existing `db_session`/`seeded_session`/`client` fixture conventions (no new test infrastructure category, only new fixtures within the existing pattern). |
| Database requirements | One new, genuinely sensitive `users` table (Section 5). |
| Secret management | Raidian must generate, store, and rotate its own signing key — a real, novel operational responsibility this repository has never had before (Section 14). |
| Password security responsibility | Fully internal — hashing, breach response, rate-limiting are all Raidian's to build and own. |
| Token lifecycle | Fully controlled internally — expiry, revocation-on-logout semantics are Raidian's own design choice (Section 6). |
| Logout/revocation | Requires deliberate design (Section 6.10) — a stateless JWT has no built-in server-side revocation; needs either short expiries, a denylist, or acceptance of "logout is client-side only." |
| Future frontend integration | A same-origin token — no redirect flow, no callback URL, simplest possible client integration (attach a header). |
| Future non-Tarot reflective activities | Mechanism-agnostic — works identically for any future `ReflectionSession`-owning activity, no rework needed as ADR-0003's roadmap unfolds. |
| Operational complexity | Entirely within the team's own control — highest risk surface for a small team, but no external dependency to negotiate, price, or monitor for uptime. |

## 4.2 Option B — External OIDC provider

| Criterion | Evaluation |
|---|---|
| Compatibility with the decided stack | Compatible, but **ADR-0004 (the decided technology stack) names no identity provider** — adopting one is a new, ADR-0004-unaddressed dependency, not a natural extension of it. |
| Dependency footprint | An OIDC client library, plus a live account with a third-party provider — a new operational relationship, not just a new package. |
| Deployment model | Fine on Render, but couples authentication availability to a third party's uptime and pricing, which this platform has never depended on before. |
| Local development | Real friction — sandbox/test credentials, redirect URI allow-listing, frequently a local tunnel for OAuth callbacks during development. |
| Testing | Harder to fully isolate — either a live sandbox call or a more elaborate mock of the provider's token-verification contract; more test infrastructure than Option A needs. |
| Database requirements | **Not zero** — still needs a local table mapping the provider's subject ID to Raidian's own `ReflectionSession.owner_id` target; different shape, not less schema (Step 19 Section 5.2, reconfirmed). |
| Secret management | Shifts to storing a client secret for the OIDC provider instead of a signing key — a different secret, not the absence of one. |
| Password security responsibility | Shifted to the provider — real operational relief for a small team, the strongest argument in this option's favor. |
| Token lifecycle | Governed by the provider's own token/refresh semantics — less control, less to build. |
| Logout/revocation | Provider-mediated — typically simpler in practice (a provider-side revocation endpoint exists), traded for less direct control. |
| Future frontend integration | A "Sign in with X" redirect flow — a different UX shape than a native form; worth weighing against `docs/PRINCIPLES.md`'s "Simplicity Over Complexity" for a reflection app whose Product Spec never once mentions third-party sign-in. |
| Future non-Tarot reflective activities | Equally mechanism-agnostic once integrated — no disadvantage here versus Option A. |
| Operational complexity | Traded, not reduced: credential-security operations move off-team, but provider selection, pricing, data-residency, and privacy-policy alignment (Section 14) become new, ongoing responsibilities. |

## 4.3 Decision

**No repository or governance evidence newly tips this balance — Step 19's finding stands: this is a genuine, unresolved product/governance decision, not a technical one this document can respectfully settle.** Consistent with `PRODUCT_DECISIONS.md` Q1's own pattern (name the dependency, recommend the smallest compliant path, leave the final call explicit): **this document recommends Option A (application-managed credentials + JWT)** as the smaller, fully self-contained choice that introduces no dependency ADR-0004 did not already implicitly permit (a small Python library, not a new service relationship), and because it best fits a still-tiny, pre-launch, single-team project with no existing operational relationship to any identity provider. **This document does not select Option A as final** — Section 15 records the decision as open.

---

# 5. Account Model

Designed for Option A (Section 4.3's recommendation); the OIDC-minimum representation is named in 5.4 for completeness, per this task's instruction, without being developed further.

## 5.1 Minimum `User` model

```text
User
  id              UUID, primary key            (UUIDPrimaryKeyMixin, consistent with every other model)
  email           string, unique, not null      (normalized lowercase before storage/comparison)
  hashed_password string, not null              (never the plaintext password -- Section 5.2)
  is_active       boolean, not null, default True
  created_at      timestamp                      (TimestampMixin, already used everywhere else)
  updated_at      timestamp                      (TimestampMixin)
```

No speculative fields (display name, avatar, profile bio, preferences) — none is named by any current governance document, and none is required to make ownership work. `Settings` (Product Spec Section 6: "Scripture preference... Bible translation preference... deck preference") is a *future* Reading-preferences concept, not an account field, and is explicitly not designed here.

## 5.2 Is email an authentication identifier, ownership identifier, or both?

**Both, in this design — the same value serves as the unique login credential and, via `User.id`, the ownership anchor.** This is the simplest option and matches this project's own naming precedent (`docs/NAMING_CONVENTIONS.md`'s `/users` route example, `docs/ARCHITECTURE.md`'s undetailed "Authentication Service"). No governance document distinguishes "who logs in" from "who owns" — this document does not invent a distinction that isn't asked for.

## 5.3 Normalized identity uniqueness

Recommend storing email lowercased and trimmed before the uniqueness constraint is checked or enforced — a standard, minimal normalization (not full RFC 5321 canonicalization, which is unnecessary complexity for this project's scale, per `docs/PRINCIPLES.md`'s "Simplicity Over Complexity").

## 5.4 If OIDC is chosen instead

The minimum stable external identity representation would be a `User` row keyed by `(issuer, subject)` from the provider's ID token, with `email` demoted to a denormalized, provider-supplied display field rather than the uniqueness anchor (a provider's `sub` claim, not email, is the stable identifier — a user can change their email at the provider without becoming a different `User` row). Not developed further — Section 4.3 defers this choice.

## 5.5 Future extensibility

The model above is deliberately minimal. Any future field (display name, profile, notification preferences) can be added as an ordinary additive migration later, following the same nullable-then-backfill pattern this document already recommends for `owner_id` (Section 11) — not designed now, per this task's explicit "avoid speculative profile fields" instruction.

---

# 6. Password Security (Option A only)

## 6.1 Storage

**Never plaintext.** Recommend hashing with a modern, purpose-built algorithm — `bcrypt` (via `passlib` or the `bcrypt` package directly) or `argon2` (via `argon2-cffi`) are the two well-established choices for this exact stack; either is an appropriate, standard answer, and this document does not need to adjudicate between them further than naming both as acceptable. **Not added to `requirements.txt` by this document** — named as the required future dependency only.

## 6.2 Verification

A login route accepts `email` + `password`, looks up `User` by normalized email, and verifies the submitted password against `hashed_password` using the chosen library's constant-time comparison — never a manual `==` string comparison (timing-attack-prone) and never a reversible encryption scheme.

## 6.3 Minimum password policy

Recommend a minimum length (e.g. 8–12 characters) and nothing more elaborate — `docs/PRINCIPLES.md`'s "Simplicity Over Complexity" argues against a complex composition-rule policy (mandatory symbols/digits/case-mixing), which security research has increasingly shown to encourage predictable patterns rather than genuinely strengthen passwords. Not designed as a configurable policy engine — a fixed, simple minimum is proportionate to this project's current scale.

## 6.4 Password-change / reset

**Deferred, not in scope for the minimum ownership boundary this document designs.** A "change password while logged in" route is small and could reasonably accompany initial login/register implementation; a "forgot password" email-based reset flow is a materially larger scope addition (requires transactional email delivery, a time-limited reset token, and its own abuse-prevention considerations) and is recommended as an explicitly separate, later decision — named in Section 15, not designed here. Building a complete account-management system (profile editing, email change, account deletion flows) when only the ownership boundary is required would over-scope this step; this document deliberately does not do that.

---

# 7. JWT / Token Architecture (Option A only)

## 7.1 Access-token claims

Minimum viable claim set:

```text
sub   -- the authenticated User.id (UUID, as a string)
exp   -- expiration (unix timestamp)
iat   -- issued-at (unix timestamp)
```

No `iss`/`aud` claims recommended yet — this project has exactly one API audience (its own FastAPI backend) and no multi-service token-sharing scenario anywhere in any governance document; adding issuer/audience validation now would be unused complexity (`docs/PRINCIPLES.md`, again). Named as a natural addition if Raidian ever splits into multiple backend services or a shared platform-wide identity token — not needed today.

## 7.2 Subject identifier

`User.id` (UUID) — not email. Consistent with every other identifier in this schema being a UUID, and avoids a token becoming invalid purely because a user later changes their email (relevant if that feature is ever built).

## 7.3 Expiration

Recommend a short-to-medium access-token lifetime (e.g. 15–60 minutes) as the standard, conservative default for a stateless bearer token with no server-side revocation list. **Refresh tokens are not recommended** (Section 7.9) — see below for why a short-lived access token alone is judged sufficient for this project's current scope.

## 7.4 Signing algorithm

A symmetric algorithm (`HS256`) is sufficient and simplest for a single-backend, non-federated system — there is no second service anywhere in this architecture that would need to verify a token without holding the shared secret, so an asymmetric algorithm (`RS256`) would add key-management complexity with no corresponding benefit today. Named as a future reconsideration only if Raidian ever needs a separate service to verify tokens independently.

## 7.5 Secret/key management

A single signing secret, generated once and supplied via environment variable — following the exact existing convention `app/core/config.py`'s `Settings` class already uses for `database_url` (`RAIDIAN_`-prefixed env var, loaded via `pydantic-settings`, `.env`-file-friendly for local development). **Not added to `config.py` by this document** — named as the required future field (e.g. `RAIDIAN_JWT_SECRET_KEY`) only. Must never be committed to the repository or logged (Section 14).

## 7.6 Issuer/audience

Not justified today (Section 7.1) — no multi-service or multi-tenant scenario exists in this architecture.

## 7.7 Where tokens are accepted

The `Authorization: Bearer <token>` header, on every route that requires an authenticated identity — the standard FastAPI `OAuth2PasswordBearer`/`HTTPBearer` pattern. No cookie-based transport is recommended (no CSRF-mitigation infrastructure exists or is otherwise needed, and a header-based bearer token is simpler for a same-origin SPA + API pair with no server-rendered pages).

## 7.8 FastAPI dependency shape

One new dependency, illustratively `get_current_user(token: str = Depends(oauth2_scheme), session: Session = Depends(get_db)) -> User`, decoding and verifying the JWT, loading the `User` row, and raising `401` if the token is missing, malformed, expired, or names a nonexistent/inactive user. This sits alongside `get_db()` as the second dependency the API layer will ever have — not a replacement for it, and not merged into it (transaction handling and identity resolution remain separate concerns, mirroring how `get_db()` already keeps transaction handling separate from every route's own business logic).

## 7.9 Invalid/expired-token behavior

`401 Unauthorized` for: missing token, malformed token, expired token, invalid signature, or a `sub` that no longer resolves to an existing `User`. A disabled account (`is_active = False`) is also recommended to fail at this same dependency, as `401`, not a later, deeper check — consistent with keeping authentication and authorization cleanly separated (Section 7.10) while still failing fast.

## 7.10 Authentication vs. authorization, stated explicitly

- **Authentication** answers "who is making this request" — resolved once, by `get_current_user`, independent of which resource is being accessed.
- **Authorization** answers "is this specific, already-authenticated user allowed to touch this specific resource" — resolved separately, per-resource, by the ownership dependency Section 8 designs. The two must remain distinct dependencies, not one merged check — a future route that needs "any authenticated user" without a specific resource in scope (unlikely today, but a real distinction) would otherwise have no way to express that.

## 7.11 Refresh tokens

**Not recommended for the current scope.** No repository or product requirement justifies the added complexity (a second token type, refresh-token storage/rotation, a dedicated refresh endpoint) — a short-lived access token, re-obtained via a normal login when it expires, is proportionate to this project's current size. Named as a natural addition once/if a genuinely long-lived-session UX requirement is identified — not before.

## 7.12 Logout semantics

With a stateless JWT and no server-side session store, "logout" is recommended to mean **client-side token discard only** (the frontend deletes its stored token) for the current scope — the access token simply expires on its own short timer regardless. A true server-side revocation mechanism (a denylist table, or moving to opaque server-tracked sessions) is a larger design with its own tradeoffs and is named in Section 15 as a deferred question, not designed here, consistent with this task's instruction not to introduce refresh tokens or extra machinery without repository-grounded justification.

---

# 8. Authorization Boundary

## 8.1 Where the ownership check lives

**One reusable FastAPI dependency, not a route-by-route duplicated check** — the same architectural posture this project already applies consistently (`get_db()` as the single shared transaction dependency). Illustratively:

```text
get_owned_reading(reading_id: UUID,
                   current_user: User = Depends(get_current_user),
                   session: Session = Depends(get_db)) -> Reading
```

This composes `get_current_user` (Section 7.8, authentication) with a `Reading` lookup that also checks ownership (authorization) — replacing, not wrapping, today's `_get_reading_or_404`. It lives in the API layer (illustratively `app/api/dependencies.py` or alongside `app/api/interpretation.py`'s existing helpers) — **not** in `reading_orchestration.py`, preserving the boundary that module's own docstring already states (it combines database access with the Interpretation Engine and Narrative Layer; it has never been responsible for request-level authentication/authorization, and this document does not ask it to start).

## 8.2 Conceptual flow, confirmed against the actual schema

```text
request
  → authenticate user            (get_current_user: verify JWT, load User)
  → obtain current user          (the User row itself)
  → load requested Reading        (session.get(Reading, reading_id))
  → verify ownership              (reading.reflection_session.owner_id == current_user.id)
  → allow operation
```

Under Option B (Section 3), the ownership check is one hop through the already-loaded `reading.reflection_session` relationship — no extra query beyond what a normal ORM `.reflection_session` access already performs; not a separate `JOIN` the developer must remember to write correctly (mitigating exactly the row-duplication/mis-join risk Step 19 Section 7.3 warned about for the *list* case — this is a single-row check, not a list query, so that risk does not apply here regardless).

## 8.3 Expected behavior per case

| Case | Result |
|---|---|
| Unauthenticated request | `401` — `get_current_user` fails before any `Reading` lookup happens at all. |
| Authenticated user accessing their own Reading | Succeeds, proceeds exactly as today. |
| Authenticated user accessing another user's Reading | **`404`**, not `403` (Section 8.4). |
| Nonexistent Reading | `404` — same response as the previous row, deliberately indistinguishable (Section 8.4). |
| Nonexistent ReflectionSession | Not independently reachable — every `Reading` has exactly one, `nullable=False` (Section 2.3); this case cannot occur for any persisted `Reading` row. |
| Malformed/invalid `reading_id` (not a valid UUID) | `422 Unprocessable Entity` — FastAPI's existing, automatic path-parameter validation behavior, already true today and unchanged by this design. |

## 8.4 404 vs. 403 — grounded, not assumed

**Recommend `404` for both "does not exist" and "exists but is not yours," collapsed into one response** — a deliberate choice, not a default. Reasoning, grounded in this project's own governing text rather than general security folklore: `docs/PRINCIPLES.md`'s "Privacy By Design" states "users should retain ownership and control of their personal reflections" — a `403 Forbidden` response would confirm to any caller that a specific, guessed-or-obtained `reading_id` *exists and belongs to someone*, leaking the existence of another user's private reflection even while correctly denying access to its contents. A personal-reflection application, where the very fact that a Reading exists is itself sensitive (it could reveal that a specific person uses the app, or how often), has a stronger-than-usual reason to prefer the resource-enumeration-resistant `404` over the more diagnostically-informative `403`. This also requires zero new response shape: it is exactly `_get_reading_or_404`'s existing `404` behavior, with "not owned" added as a second reason to raise the identical response, at the identical call site.

---

# 9. Existing API Retrofit

## 9.1 Exact retrofit mechanism

Replace each route's `reading = _get_reading_or_404(session, reading_id)` call with `reading = _get_reading_or_404` **replaced by** the new `Depends(get_owned_reading)` dependency (Section 8.1) as a path/function parameter, e.g.:

```text
def interpret_reading_route(
    reading: Reading = Depends(get_owned_reading),
    session: Session = Depends(get_db),
) -> InterpretationSummary:
    ...
```

Every one of the four routes (`POST .../interpret`, `GET .../interpretations/current`, `GET .../interpretations`, `GET .../narrative`) changes identically and mechanically — replace the manual `_get_reading_or_404(session, reading_id)` call with the new dependency, and delete `_get_reading_or_404` once no caller remains. **Not performed by this document.**

## 9.2 Boundary preserved

- `reading_orchestration.py` remains responsible only for orchestration (combining database access with the Interpretation Engine and Narrative Layer) — it gains no new parameter, no new import, no awareness of `User` or authentication of any kind. Confirmed against its current signatures (`interpret_reading(session, reading)`, `get_current_interpretation(session, reading)`, `list_interpretations(session, reading)`, `get_narrative_for_reading(session, reading)`) — every one already takes an already-resolved `Reading`, so the retrofit is entirely upstream of orchestration, at the API layer only.
- The Interpretation Engine (`app/services/interpretation/engine.py`) and Narrative Layer (`app/services/narrative/`) gain zero ownership-awareness — consistent with this task's explicit instruction and with every prior step's finding that these layers operate purely on already-validated domain data, never on caller identity.

## 9.3 Response-shape consequences

`404`'s existing `_READING_NOT_FOUND` detail message now also covers "exists but not yours" (Section 8.4) — no new response schema, no new status code introduced to any of the four existing OpenAPI `responses={}` declarations beyond what already exists, except that a `401` now also becomes reachable on every route (previously impossible, since no authentication existed to fail).

---

# 10. Reading History Dependency

Reconciled directly against `READING_HISTORY_OWNERSHIP_DESIGN.md` — nothing in this document's authentication/token design changes any of Step 19's Section 7 conclusions:

- **Ownership-scoped Reading History becomes possible** the moment `get_current_user` and `User.id` exist — the query Step 19 Section 7.1 already specified (`WHERE reflection_sessions.owner_id = :authenticated_user_id AND reading.status = 'saved'`) needs no revision; `:authenticated_user_id` is now concretely `current_user.id`, resolved by `get_current_user` (Section 7.8).
- **Newest-first ordering** (`updated_at DESC`), **one row per Reading**, and **`SAVED` as the sole history gate** — all unchanged, Step 19 Sections 7.2/7.3 fully reconfirmed; nothing about introducing authentication alters `Reading.updated_at`'s mutation surface or the append-only interpretation history that grounded that conclusion.
- **Empty history behavior** — `200 []`, unchanged (Step 19 Section 7.4); an authenticated user with zero saved Readings is not an error case.
- **Future pagination/filtering/search** — remain deferred, unchanged (Step 19 Section 7.5); nothing in this document's scope changes that calculus.
- **Step 19's explicit conclusion preserved:** Reading History must not be exposed platform-wide without ownership scoping — this document's entire authorization design (Section 8) exists specifically to make that scoping possible; it does not weaken or qualify that conclusion.

**Not implemented here** — the `GET /readings` route itself remains out of this step's scope, exactly as it was out of Step 19's.

---

# 11. Migration Strategy

Design only — no migration file is created by this document.

## 11.1 Sequence

1. **Create `users` table.** A new, standalone `CREATE TABLE` — no interaction with any existing table, no backfill concern of its own (a brand-new table starts empty).
2. **Add `ReflectionSession.owner_id`, nullable, no default.** Following `74ffb042dc2d`'s exact proven technique (Section 11.2) — except this repository's finding (Step 19 Section 6, reconfirmed) that there is **no production deployment and no real user data anywhere**, so unlike `Interpretation.sequence` (which needed a `server_default='0'` specifically to satisfy SQLite's `ADD COLUMN ... NOT NULL` requirement against a non-empty table), this column can plausibly be added as nullable from the start with no default needed at all, since any existing dev/test rows simply have no owner yet and nothing depends on backfilling one retroactively (Section 11.3).
3. **Add the foreign key constraint** (`ForeignKey("users.id", ondelete="CASCADE")`) and the plain index on `owner_id` (Section 3.6) — both safe to add immediately, since a nullable FK column with no rows populated yet violates nothing.
4. **(Deferred, not part of this migration)** Backfill any existing dev/test `ReflectionSession` rows with a real owner, once a first real `User` exists to assign them to — not a migration-time concern, since (per Section 11.3) no such backfill is actually required for correctness today.
5. **(Deferred, not part of this migration)** Transition `owner_id` to `NOT NULL`, only once every `ReflectionSession` row created going forward is guaranteed to have one supplied by the (by-then-existing) authentication-gated creation path — i.e., after Section 9's retrofit and a corresponding update to however `ReflectionSession`/`Reading` creation is triggered (not designed further here, since no `ReflectionSession`-creation API route exists yet to modify).

## 11.2 Why this repository's own precedent applies directly

`74ffb042dc2d` (`Interpretation.sequence`) already demonstrates, in this exact repository, the general technique for adding a column that eventually needs `NOT NULL` + a constraint onto a table with pre-existing rows: temporary nullable/defaulted column → deterministic backfill query → drop default → add constraint, all within one migration, using `op.batch_alter_table` for SQLite compatibility. This document's `owner_id` migration follows the identical shape *if* a backfill turns out to be needed — Section 11.3 explains why it currently is not.

## 11.3 Handling existing rows

**This repository's own state resolves the question, not a hypothetical:** Step 19 (Section 6) and Step 17 (Section 2) both already established that no production deployment and no real user data exist anywhere in this repository — every `ReflectionSession`/`Reading` row that exists today is dev/test fixture data (via `tests/factories.py` and `tests/interpretation_helpers.py::build_reading`), disposable at will. Consequences:

- A production migration strategy that must gracefully backfill millions of real, meaningful rows **cannot be responsibly designed from this repository's current state**, because that state does not exist yet — this document declines to invent one it cannot ground in real data, per this task's own instruction.
- The realistic path: add `owner_id` nullable (step 2 above), ship the authentication feature, and either (a) simply delete/reset any leftover dev/test `ReflectionSession` rows with no owner once a local `User` exists to test against (the same disposable-fixture posture this project's own test suite already treats all `Reading` data with), or (b) leave `owner_id` nullable indefinitely in non-production environments and only enforce `NOT NULL` in whichever environment first carries real user data. Both are equally valid given today's actual data; **this document does not choose between them**, since the choice has zero consequence until real user data exists (Section 15).

## 11.4 Rollback implications

Standard Alembic `downgrade()` symmetry — drop the constraint/index, drop the column, drop the table — no data-loss concern beyond whatever `owner_id` values existed being discarded, which (per Section 11.3) is inconsequential given the current absence of real user data.

---

# 12. Testing Strategy

Defined, not implemented — no test file is created or modified by this document. All tests below would follow this project's existing, established fixture conventions (`db_session`/`seeded_session` from `tests/conftest.py`, `tests/factories.py`'s minimal builders, and the self-contained `client`/`api_seeded_session` fixture pattern each API test file already duplicates for its own `get_db` override).

## Authentication

- Valid credentials → login succeeds, returns a token.
- Invalid credentials (wrong password, nonexistent email) → login fails, `401`, no information disclosure about which of the two was wrong.
- Disabled account (`is_active = False`) → login fails, `401` (or, per Section 7.9, fails at `get_current_user` if a token was somehow already issued before deactivation — both paths must be covered).
- Malformed token → `401` at `get_current_user`.
- Expired token → `401` at `get_current_user`.
- Missing token → `401` at `get_current_user`, before any route body executes.

## Ownership

- Owner can access their own Reading via `get_owned_reading`.
- A different, authenticated user cannot access it (`404`, not `403` — Section 8.4).
- A nonexistent `reading_id` produces the identical `404` as the "not owned" case (indistinguishable by design).
- Ownership resolves correctly through `ReflectionSession` (Option B) — a test constructing a `Reading` via its `ReflectionSession.owner_id`, not a shortcut that bypasses that relationship.
- No ownership leakage through child resources — accessing `Interpretation`/`NarrativeModel`/`CardDraw` content for a Reading the caller does not own must be blocked at the same `get_owned_reading` gate (i.e., before orchestration ever runs), not discoverable through some other, unguarded path.

## Existing API (all four retrofitted routes)

For each of `POST .../interpret`, `GET .../interpretations/current`, `GET .../interpretations`, `GET .../narrative`:
- Authenticated owner access → existing success behavior, unchanged (response shape, status codes).
- Unauthenticated request → `401`, rejected before `_get_reading_or_404`'s replacement even queries the database.
- Authenticated non-owner request → `404`.
- **Regression requirement, explicit:** every existing passing test in `test_api_interpretation.py` (23 tests, Step 11) must be updated to supply a valid token for an owning user rather than deleted or weakened — the retrofit must not silently drop coverage of the already-approved success paths.

## Lifecycle (confirmed unaffected, per Section 9.2/10)

- Interpretation history (`sequence` ordering, append-only accumulation) is unaffected by authentication/ownership — a test reinterpreting an owned Reading multiple times should show identical `sequence` behavior to today's unauthenticated tests.
- `SAVED` status preservation across reinterpretation (`test_reinterpretation_after_mark_saved_preserves_saved_and_creates_new_interpretation`, Step 18) is unaffected — ownership is checked upstream of `mark_saved()`/`interpret_reading()`, neither of which this document modifies.
- Narrative on-demand generation (never cached, recomputed every call) is unaffected — the retrofit changes only how `Reading` is resolved, not what happens once it is.

---

# 13. Frontend Boundary

## 13.1 Current state (Section 2.2, restated for this section's completeness)

Nothing exists: no login, no signup, no token storage, no authentication state, no protected routes, no API client of any kind — `frontend/` is the unbuilt Vite scaffold.

## 13.2 Minimum frontend consequences of this backend design

Named, not designed in full (per this task's explicit instruction not to design a complete frontend authentication experience unless product documentation requires it — and `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6's screen inventory, re-confirmed by this step, still names no Login/Signup screen at all):

- An HTTP client capable of attaching an `Authorization: Bearer <token>` header does not exist yet and would need to be introduced before any screen could call the backend at all — true independent of authentication (today's frontend calls no API of any kind), but authentication makes the header-attachment step a hard requirement from the first real API call onward, not an optional enhancement.
- Some form of token storage (most simply `localStorage`, accepting its well-known XSS-exposure tradeoff, or a more defensive in-memory-plus-refresh pattern) must be chosen before login can persist across a page reload — not decided here.
- A minimal "am I logged in" state and a redirect-when-unauthenticated behavior would be needed before any screen that calls an owned-resource route (which, per Section 9, is now all four existing routes) could function correctly.

## 13.3 What this document does not do

Does not design specific screens, specific component structure, specific state-management choice, or specific UX copy for login/signup — Product Spec Section 6 gives this document nothing to build against (Section 10.1 of Step 19, reconfirmed), and inventing a full UX here would exceed this task's scope of naming *consequences*, not designing a *feature*.

---

# 14. Security / Privacy Analysis

Reconciled against `docs/PRINCIPLES.md`'s "Privacy By Design": *"Users should retain ownership and control of their personal reflections."*

## 14.1 Concrete risks created by the current unauthenticated API — stated plainly, not sensationalized

| Risk | Concrete mechanism | Current status |
|---|---|---|
| Horizontal access between users | Any caller who obtains or guesses a `reading_id` (a UUID — not guessable in practice, but obtainable via e.g. a shared link, browser history, or a server log) can call any of the four existing routes against it — read its Interpretation, its Narrative, or trigger a new Interpretation — with no ownership check at all. | **Live today.** Zero mitigation exists; this document's Section 9 retrofit is the fix, not yet applied. |
| Resource enumeration | Not currently exploitable in a *meaningful* sense — UUIDs are not sequentially guessable — but the `404`-only response today already gives no signal either way about ownership, since ownership doesn't exist yet to leak. Becomes a live concern only once ownership exists (Section 8.4's `404`-collapsing design is the mitigation for that future state, not a fix for a present problem). | **Not yet applicable**, correctly anticipated by Section 8.4. |
| Token leakage | Not yet applicable — no token exists yet. Once JWTs exist, standard exposure surfaces apply: must never be logged (application logs, error-tracking payloads), must be transmitted only over HTTPS in any real deployment, and `localStorage` storage (Section 13.2) carries a known XSS-exposure tradeoff that should be weighed, not ignored, when the frontend is actually built. | **Named for the future implementation, not yet applicable.** |
| Password credential exposure | Not yet applicable — no password storage exists yet. Section 6.1's hashing requirement is the mitigation; must never be logged, and `hashed_password` must never appear in any API response schema (a discipline this project's existing schemas — `InterpretationSummary`, `InterpretationHistoryEntry` — already exercise correctly by only ever exposing intentionally-designed fields, never raw ORM attributes by accident, per `INTERPRETATION_API_DESIGN.md`'s own schema-boundary discipline). | **Named for the future implementation.** |
| Logging of sensitive data | No logging infrastructure of any kind exists yet in this repository (a repository-wide search confirms no logging library or configuration) — a real gap to close *when* logging is eventually added, not a problem today since nothing is logged at all yet. | **Not yet applicable; named for future logging work.** |
| Secret handling | `app/core/config.py` already has the correct pattern (env-var-sourced, `.env`-file-friendly, never hardcoded) for `database_url`; the future JWT signing secret (Section 7.5) should follow the identical pattern — not a new discipline to invent, an existing one to extend. | **Pattern already established; extension only.** |
| Child-resource access through Reading IDs | Confirmed by Section 9.2: `Interpretation`/`NarrativeModel`/`CardDraw` content is only ever reachable by first resolving a `Reading` — there is no separate, unguarded route that fetches an `Interpretation` or `CardDraw` directly by its own ID. Once the Section 8 dependency guards `Reading` resolution, every child resource is correctly guarded by construction, with no separate check needed per child type. | **Structurally sound already — confirmed, not assumed, by re-reading `app/api/interpretation.py` and finding no such direct route exists.** |

## 14.2 The governing-principle gap, restated precisely

Step 19 already established the headline finding: `docs/PRINCIPLES.md` treats per-user ownership as a settled, highest-tier principle while zero implementation exists. This document's contribution is narrower and more concrete: it shows *exactly* what closing that gap requires (Sections 3–11) and *exactly* what remains exposed until it is closed (Section 14.1's table) — turning a principle-level gap into an enumerated, actionable list.

---

# 15. Open Decisions / Governance Questions

Precise list of decisions that cannot responsibly be made from the existing repository/specification — none silently resolved by this document.

- **App-managed JWT (Option A) vs. OIDC (Option B)** — recommended (A), not decided (Section 4.3).
- **Exact `User`/account semantics beyond the minimum model** (Section 5) — e.g., whether a display name or any profile field is ever needed — not asked by any current document.
- **Whether email verification is required before an account is usable** — no governance document addresses this; a real product decision (verification adds friction and requires transactional email delivery, which does not exist in this repository in any form) that this document does not make.
- **Password reset requirements** (Section 6.4) — named as a larger, separate scope addition, not designed.
- **Frontend authentication UX** (Section 13) — Product Spec Section 6 gives no screen to build against; whether/how to amend the Product Spec's own screen inventory to add one is a documentation/product action outside this document's authority, mirroring Step 19's identical finding about the same gap.
- **Ownership migration treatment for existing development data** (Section 11.3) — this document names two equally-valid options and does not choose, since the choice has no consequence until real user data exists.
- **Whether unsaved Readings are accessible after authentication** — **yes, by this document's design**, stated explicitly so it is not mistaken for an open question: ownership (Section 8) gates access by *owner*, not by `status`; `SAVED` only gates Reading *History* visibility (Step 19 Section 7, unchanged). An authenticated owner can still fetch their own `DRAFTING`/`SPREAD_COMPLETE`/`INTERPRETED` Reading's interpretation/narrative via the four existing (retrofitted) routes — this was already true, unauthenticated, before this document, and ownership does not narrow it, only correctly scope it to the actual owner.
- **Whether `ReflectionSession` is permanently established as the ownership boundary** — Step 19's ambiguity (Section 2.3 here) is explicitly still not resolved by this document; nothing in the authentication design forces a resolution either way, since Option A's fallback placement (`Reading.owner_id`) would compose identically with every authentication/authorization mechanism this document designs.
- **User account deletion/deactivation semantics and their effect on owned Readings** (Section 3.4) — cascade-delete is recommended as the schema-level default; whether the product actually wants hard deletion versus a soft "deactivate and retain" is not decided.
- **Server-side token revocation (a denylist, or moving off pure stateless JWTs)** (Section 7.12) — named as a deferred question, not designed.

---

# 16. Implementation Boundary

## 16.1 What could safely be built next, once Section 15's decisions are approved

Evaluated sequence, mirroring this series' own established practice (a dedicated design step before implementation, exactly as Engine/Narrative/Orchestration/API/Lifecycle/Save/Ownership each received) — reordered slightly from Step 19's Section 12 sketch now that this document has designed the concrete pieces:

1. **Account model + migration** (Sections 5, 11) — the `User` table and the nullable `owner_id` column can be built and migrated independently of any authentication mechanism being finalized; both are needed regardless of the final Section 4/15 decision.
2. **Credential/token infrastructure** (Sections 6–7) — password hashing, JWT issuance/verification, login/register routes — the largest single body of new work, and entirely gated on Section 4/15's mechanism decision.
3. **Authentication dependency** (`get_current_user`, Section 7.8) — small, once step 2 exists.
4. **Ownership relationship wiring** (`ReflectionSession.owner_id` populated at creation time, Section 6 of Step 19) — requires step 1 and a resolved authentication dependency to know *whose* `ReflectionSession` is being created; not designable further until whatever currently-nonexistent route creates a `Reading`/`ReflectionSession` is itself designed (a gap this document surfaces but does not resolve — no such route exists anywhere yet, even unauthenticated).
5. **Ownership authorization dependency** (`get_owned_reading`, Section 8) — small, once steps 3–4 exist.
6. **Retrofit the four existing interpretation/narrative routes** (Section 9) — mechanical, once step 5 exists; required before any of this work is considered complete for real deployment, not optional.
7. **Save Reading API** (`POST /readings/{id}/save`, per `SAVE_READING_DESIGN.md`) — can follow immediately once step 6's pattern is established, applying the identical `get_owned_reading` dependency.
8. **Reading History API** (`GET /readings`, per Step 19 Section 7–8) — last, since it is the feature this entire chain of dependencies exists to unblock.

## 16.2 What must remain deferred regardless

- Password reset / email verification (Section 15).
- Any frontend screen or UX design (Section 13).
- OIDC integration, unless Section 4's decision selects it instead of Option A.
- Server-side token revocation infrastructure (Section 7.12).
- Any production migration backfill strategy for real user data, since none exists yet to design against (Section 11.3).

**No step in Section 16.1 is authorized by this document.**

---

# 17. Conclusion

This audit confirms, with the widest sweep yet in this series (frontend included), that Raidian Wise's authentication and ownership gap is exactly as total as Step 19 found, and shows precisely what closing it requires: one new `User` table, one new `owner_id` column on `ReflectionSession` (Option B, reaffirmed), a small, self-contained JWT-based authentication mechanism (Option A, recommended but not decided), one new authentication dependency and one new ownership-authorization dependency composing cleanly with the existing `get_db()` pattern, a mechanical retrofit of the four already-shipped interpretation/narrative routes, and a migration strategy this repository's own precedent (`74ffb042dc2d`) already proves is safe to execute once needed. Nothing in this design requires touching the deterministic Interpretation Engine, the Narrative Layer, or any already-approved Reading/Draw lifecycle rule — the entire boundary sits at the API layer, exactly where `app/api/interpretation.py`'s own docstring has pointed since Step 11. The remaining work is substantial (Section 16) but no longer architecturally uncertain; what remains is a product/governance decision (Section 15) and then a sequence of independently reviewable implementation steps, not further open design questions about *where* ownership and authentication belong in this system.

---

## Related Documents

- `READING_HISTORY_OWNERSHIP_DESIGN.md` — Step 19's ownership-placement audit (Options A/B/C), `ReflectionSession` semantics, and Reading History query design, all reaffirmed and extended by this document rather than re-derived.
- `SAVE_READING_DESIGN.md` — Step 17's original ownership-dependency finding for Reading History, and the `mark_saved()`/`Reading.status` lifecycle this document confirms needs no change (Section 10).
- `PRODUCT_DECISIONS.md` — Q1's "name the dependency, recommend the smallest compliant path, leave the final call explicit" pattern, applied identically to Section 4 here.
- `READING_LIFECYCLE_DESIGN.md`, `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` — the already-approved `DRAFTING → SPREAD_COMPLETE → INTERPRETED → SAVED` transition rules, confirmed unaffected by this document (Section 10).
- `INTERPRETATION_API_DESIGN.md` — Sections 4–5's original auth/ownership gap and the `_get_reading_or_404` insertion point this document's Section 8/9 retrofits directly.
- `docs/PRINCIPLES.md` — "Privacy By Design," the governing citation for Section 8.4's 404-over-403 recommendation and Section 14's risk analysis.
- `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (ADR-0003, ADR-0004, ADR-0006), `docs/ROADMAP.md` (M1 Authentication, M3 Reading History), `docs/NAMING_CONVENTIONS.md` — the governance stack this audit checked directly.
- `app/models/reading.py`, `app/models/reflection_session.py`, `app/models/exceptions.py`, `app/api/interpretation.py`, `app/core/config.py`, `app/db/session.py`, `backend/requirements.txt`, `backend/alembic/versions/74ffb042dc2d_add_interpretation_sequence_column.py`, `frontend/` — the actual, current code, configuration, and migration precedent every finding in this document was checked against.
