# Raidian Wise — Reading History & Ownership Architecture Design/Audit (Step 19)

# Document Information

Version: 1.0 (Draft for Review — Not Yet Approved)
Status: Proposed — Audit and Design Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Audits the actual current repository (post Step 18, baseline `e2facae`) and the full governance stack (`docs/PRINCIPLES.md`, `docs/ARCHITECTURE.md`, `docs/DECISIONS.md`, `docs/NAMING_CONVENTIONS.md`) to determine the minimum viable identity/ownership architecture required to make "Reading History = the authenticated user's saved Readings" implementable — without inventing infrastructure, without silently deciding the questions this task asks to be preserved as open, and without disturbing the deterministic Interpretation/Narrative architecture. This document implements nothing.

Audience:
Whoever eventually designs and implements authentication and Reading History, and anyone auditing whether that future work matches this project's own governance documents rather than inventing a scheme unmoored from them.

Authority:
Extends `INTERPRETATION_API_DESIGN.md` Sections 4–5's original auth/ownership finding and `SAVE_READING_DESIGN.md` Section 9's sharpened version of it, into a full architectural comparison. Does not override `PRODUCT_DECISIONS.md` Q3/Q6, `docs/PRINCIPLES.md`, `docs/ARCHITECTURE.md`, or `docs/DECISIONS.md` — per ADR-0006's governance hierarchy (Charter → Vision → **Principles** → **Architecture** → **Decisions** → Agents → Roadmap), this document's own recommendations rank below all four and are offered as input to a future, higher-authority decision, not a substitute for one.

---

# 0. Scope

Read-only audit and architecture/design pass only. No code, schema, migration, API route, or test file is touched. Where a question is genuinely ambiguous given the actual repository (Section 3), this document preserves that ambiguity rather than resolving it. Where a decision requires product/governance judgment (Section 5's auth mechanism, Section 2's ownership placement), this document recommends but does not decide.

---

# 1. Repository Identity & Ownership Audit

Direct, repository-wide search — not inferred from any prior report.

| Searched for | Found? | Where |
|---|---|---|
| `class User` / any user model | **No** | Zero matches anywhere in `app/` |
| `user_id` | **No** | Zero matches in any model, schema, or migration |
| `owner` / `owner_id` | **No** | Zero matches in application code (only unrelated tarot-content matches for the word "security" in reference-data YAML — noise, not signal) |
| `account` | **No** | Zero matches |
| `identity` | Only in prose | `ReflectionSession`'s own docstring ("intentionally minimal: identity and timestamps only") and `docs/PRINCIPLES.md`'s Purpose statement — neither is a data model or mechanism |
| `auth` / `authentication` / `authorization` | Only as documentation of absence | `app/api/interpretation.py`'s own docstring: "No authentication or authorization exists anywhere in this codebase yet" |
| `token`, `jwt`, `oauth`, `password` | **No** | Zero matches anywhere in `app/` or `backend/requirements.txt` |
| middleware | **No** | `app/main.py` registers no middleware of any kind |
| identity-related FastAPI dependency (e.g. a `get_current_user`) | **No** | `get_db()` (`app/db/session.py`) remains the only dependency anywhere in the API layer |
| Password hashing / session library in `requirements.txt` | **No** | Confirmed by direct inspection: `fastapi`, `uvicorn`, `SQLAlchemy`, `alembic`, `pydantic`, `pydantic-settings`, `psycopg2-binary`, `python-dotenv`, `PyYAML`, `pytest`, `httpx2` — no auth-adjacent package of any kind |

**Findings, stated directly:**
- **No identity model exists.** Not partially, not as a stub — zero code.
- **No authentication library is installed.**
- **No authorization mechanism exists.**
- **`ReflectionSession` does not represent an authentication session.** It has no expiry, no token, no user reference — it is a domain entity ("the overall reflective experience"), not an HTTP/auth session, despite the word "session" in its name (Section 3 examines this in full).
- **Whether `ReflectionSession` can safely be treated as an ownership boundary** is a real architectural question, not a settled fact — addressed in Section 2/3, not decided by this section alone.
- **No existing identifier can safely serve as a temporary owner key.** The only candidate is `ReflectionSession.id` — but see Section 3: because `Reading.reflection_session_id` is unique (a strict one-to-one), using it as a stand-in "owner" would make every single `Reading` its own owner, so a "history of my saved readings" would never contain more than one row. This fails the feature's own purpose, not merely as a stopgap — it is actively wrong, not just temporary.
- **No reusable identity abstraction exists in the API layer.** `get_db()` is the only dependency any route uses; there is nothing to extend.

---

# 2. Data Model Audit — Ownership Placement

## 2.1 Relevant current schema (direct inspection, unchanged through Step 18)

`Reading.reflection_session_id` — `ForeignKey("reflection_sessions.id", ondelete="CASCADE")`, `nullable=False`, **`unique=True`**. `ReflectionSession.reading` — `relationship(..., uselist=False, cascade="all, delete-orphan")`. Together these enforce a **strict one-to-one** between `ReflectionSession` and `Reading` today — confirmed by `test_reflection_session_reading_is_one_to_one` raising `IntegrityError` on a second `Reading` for the same session. `Interpretation.reading_id` and `CardDraw.reading_id` both FK to `Reading` with `ondelete="CASCADE"`; neither has any independent identity concept. No indexes beyond primary keys and the uniqueness constraints already named in prior audits (`READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` Section 2.3). No migration references ownership in any form.

## 2.2 Option A — ownership on `Reading`

```text
User
 └── Reading (owner_id)
      ├── CardDraw
      └── Interpretation
```

| Criterion | Evaluation |
|---|---|
| Data integrity | A single new FK column, `NOT NULL`-able once populated; straightforward. |
| Query simplicity | **Best.** Reading History becomes a single-table filter: `WHERE Reading.owner_id = :user_id AND Reading.status = 'saved'` — no join at all. |
| Lifecycle consistency | Ownership set once at creation, never revisited — consistent with `Reading`'s own "evidence, immutable" philosophy (Product Spec Section 17), treating "who this event belongs to" as another immutable evidence-adjacent fact. |
| Compatibility with existing schema | Clean addition; `ReflectionSession` stays exactly as minimal as its own docstring insists it should ("not a dumping ground for fields that belong to Reading") — though ownership arguably isn't a *Reading* fact either (Section 2.4). |
| Migration impact | One column + backfill, following the exact pattern already proven safe in this project (`74ffb042dc2d`'s `Interpretation.sequence` migration: temporary default, backfill, drop default) — not a new migration technique. |
| Future Reading History queries | Optimal — single indexed column. |
| Compatibility with future auth | Mechanism-agnostic — works identically whichever of Section 5's options is chosen. |
| Could a Reading move between owners? | No textual basis anywhere for a "transfer" or "share" feature — recommend immutable once set. |
| Historical interpretations inherit ownership automatically? | **Yes, for free** — `Interpretation.reading_id` already FKs to `Reading`; an authorization check joins through `reading.owner_id` with zero new column on `Interpretation` itself. |

## 2.3 Option B — ownership on `ReflectionSession`

```text
User
 └── ReflectionSession (owner_id)
      └── Reading
           ├── CardDraw
           └── Interpretation
```

| Criterion | Evaluation |
|---|---|
| Data integrity | Identical mechanics, one FK column, on a different (currently smaller) table. |
| Query simplicity | One extra join versus Option A: `JOIN reflection_sessions ON reading.reflection_session_id = reflection_sessions.id WHERE reflection_sessions.owner_id = :user_id AND reading.status = 'saved'`. Given today's strict 1:1 cardinality (Section 2.1), this join can never multiply `Reading` rows — no risk of the row-duplication pitfall Section 7 warns about, regardless of whether `ReflectionSession` ever becomes 1:many in the future (a future fan-out would only be a risk querying *downward* from one `ReflectionSession` to many `Reading`s, not *upward* from `Reading` to its one parent, which is what Reading History actually needs). |
| Lifecycle consistency | Matches `ReflectionSession`'s own stated aspiration ("may in the future wrap other reflective activities... alongside tarot") — ownership placed here would automatically apply to any future activity type (journaling, Scripture study) without duplicating an `owner_id` column onto each one individually. |
| Compatibility with existing schema | Also clean — and arguably *more* consistent with `ReflectionSession`'s "identity and timestamps only" self-description than adding a non-identity fact to `Reading`, since ownership is an identity fact. |
| Migration impact | Identical mechanics to Option A. |
| Future Reading History queries | One extra join; negligible at this project's scale, and no existing precedent either way (no multi-table `Reading` query exists today to compare against — Section 2.1). |
| Compatibility with future auth | Same as Option A. |
| Could ownership move? | Same answer — no basis, recommend immutable. |
| Historical interpretations inherit ownership automatically? | Yes, for free, one join further removed (`Interpretation` → `Reading` → `ReflectionSession` → owner) — still no new column needed anywhere else. |

## 2.4 Option C — another existing entity

**No genuine basis found for a third option.** `Deck` and `Spread` are shared reference data, used identically across every user — neither is a remotely plausible ownership anchor, and neither the Product Spec nor any architecture document suggests otherwise. Per this task's own instruction ("only include another option if the repository provides a genuine basis for it"), Option C is not developed further.

## 2.5 Comparative recommendation

**This document recommends Option B (`ReflectionSession`), with Option A named as a fully valid, simpler fallback** — not because of aesthetic preference, but because of one specific, governance-grounded reason: **ADR-0003 ("Platform Identity") explicitly commits Raidian to adding further reflective activity types (journaling, Scripture, dream reflection) "without requiring fundamental rebranding," and states "architecture should remain modular and extensible."** Placing ownership at the `ReflectionSession` level means every future activity type inherits the same ownership pattern automatically, without redesigning ownership per feature — a real, ADR-grounded future-proofing argument, not a stylistic one. The cost of choosing Option B over Option A is a single extra join, which is negligible at this project's scale and carries zero present-day complexity difference in migration mechanics. Option A remains the correct fallback if Section 3's preserved ambiguity is ever resolved against `ReflectionSession` continuing to generalize beyond tarot.

---

# 3. `ReflectionSession` Semantics

Direct inspection of `app/models/reflection_session.py`, `app/models/reading.py`, and `test_reflection_session_and_reading.py` — answered precisely, with genuine ambiguity preserved where it exists.

| Question | Answer |
|---|---|
| Is it a user/account session? | **No.** No expiry, no token, no user reference of any kind — an HTTP/auth "session" and this domain entity share a name, not a mechanism. |
| Is it a logical container for one or more Readings? | **Not today.** Its own docstring aspires to eventually wrap "other reflective activities... alongside tarot," but the *enforced* cardinality right now is a strict one-to-one with `Reading` (Section 2.1). |
| Can multiple Readings belong to one `ReflectionSession`? | **No — actively prevented** by `Reading.reflection_session_id`'s `unique=True` constraint, database-enforced, not merely a convention. |
| Can a Reading exist without one? | **No** — `reflection_session_id` is `nullable=False`; every `Reading` requires exactly one. |
| Is the relationship currently mandatory? | **Yes, both directions** — `Reading` requires exactly one `ReflectionSession`; cascade `delete-orphan` on `ReflectionSession.reading` (`uselist=False`) means the pairing is enforced, not incidental. |
| Does its existing identifier have user-facing meaning? | **No** — an opaque UUID, never exposed by any API route (none references it at all today), no display name. |
| **Could it become the ownership boundary without changing its meaning?** | **Genuinely ambiguous — preserved, not resolved here.** Its docstring's *aspiration* (generalizing across future activity types) argues yes; its *current, enforced* cardinality (strict 1:1 with one `Reading`) means there is zero practical difference today between anchoring ownership here versus on `Reading` itself, which argues the question doesn't yet have a forced answer. |
| Would this create undesirable coupling between authentication and reflection-session lifecycle? | **A real dependency worth naming, not dismissing.** If `ReflectionSession` becomes the owner-bearing entity, then every `ReflectionSession` creation (today, automatic and implicit whenever a `Reading` is created — see `tests/interpretation_helpers.py::build_reading`) would require a resolved, authenticated identity to already be available at that exact moment. This is plausibly correct (starting a Reading should require being logged in), but it is a coupling this document names explicitly rather than assumes is free. |

---

# 4. Product Spec / Governance Audit

Every identity/ownership/authentication-relevant statement found across the full governance stack — not the Product Spec alone, per this task's explicit inclusion of "any ADRs relevant to identity, authentication, ReflectionSession, or persistence."

| Requirement | Current implementation | Design implication |
|---|---|---|
| **`docs/PRINCIPLES.md`, "Privacy By Design":** "Users should retain ownership and control of their personal reflections." (A governance-tier document — ranked above Architecture/Decisions/Roadmap per ADR-0006 — Status: Active.) | No ownership concept exists anywhere. | The single highest-authority textual statement in this entire project that per-user ownership is not optional polish — it is an accepted governing principle current code does not yet honor at all. |
| **Product Spec Section 6:** "Reading History — list of **saved** Readings, searchable/filterable." | No history query, route, or schema exists (`SAVE_READING_DESIGN.md` Section 2). | Confirms Q3's approved framing; gives no ownership-scoping detail of its own. |
| **Product Spec Section 6, screen inventory:** lists Home, New Reading (4 sub-screens), Spread Review, Interpreting, Reading Result, Reading History, Reading Detail, Settings, Disclaimer/About — **no Login, Signup, or Account screen appears anywhere.** | No auth UI exists (consistent — nothing to build against). | **A genuine Product Spec gap, not previously named this precisely:** the spec assumes "Reading History" as a screen without ever specifying how a user's identity would be established to view it. Authentication is not merely an unbuilt engineering concern here — it is an *unaddressed product* one. |
| **`docs/ARCHITECTURE.md`, Core Services:** "Authentication Service" listed as one of five, with zero further detail — no mechanism, no data model, no route sketch. | Nothing built (`INTERPRETATION_API_DESIGN.md` Sections 4–5, re-confirmed here). | Naming a service is not designing one — already established, reconfirmed directly. |
| **`docs/ROADMAP.md`, M1:** "Authentication" listed alongside "AI service architecture" and "Reflection Engine" as Core Architecture milestones. | Nothing built. | A whole-platform, cross-cutting milestone — not something Raidian Wise's Reading History feature should build in isolation (the same reasoning `PRODUCT_DECISIONS.md` Q1 already applied to the Reflection Engine). |
| **`docs/DECISIONS.md`, ADR-0004 (Technology Stack):** names the entire decided stack (React/Vite/TS, Tailwind, FastAPI, SQLAlchemy, Alembic, Pydantic, SQLite/PostgreSQL, GitHub Pages, Render) — **no authentication library or identity provider is named anywhere in it.** | N/A | Confirms the auth mechanism is a genuinely open architectural decision, not merely unbuilt — even the stack ADR is silent on it. |
| **`docs/DECISIONS.md`, ADR-0003 (Platform Identity):** "Tarot is the first reflective experience implemented within the platform rather than the platform's sole identity... Architecture should remain modular and extensible." | N/A | Direct governance basis for Section 2.5's Option B recommendation — future activity types should share one ownership pattern. **Note:** this ADR's title, "Platform Identity," is about product/brand identity, not user identity — a naming coincidence worth flagging so it is not mistaken for an auth-relevant ADR on a skim. |
| **`docs/NAMING_CONVENTIONS.md`:** "/users" listed as a sibling example alongside "/readings" and "/journals" under API route naming conventions; separately, "Journal entries belong to the user and remain under their control." | No `User` resource, no Journal feature. | Evidence a `User` resource and per-user ownership are anticipated platform-wide (not just for tarot), consistent with Section 2.5's reasoning — not evidence either exists. |

**No contradiction was found where the Product Spec claims something already works** — every statement above is prospective ("Reading History," "the user's ownership") rather than descriptive of current behavior, so there is nothing to silently rewrite. The one genuine gap worth naming as such: the Product Spec's screen inventory (Section 6) assumes identity-scoped features (History) while never sketching how identity itself is established — recorded, not resolved, here.

---

# 5. Authentication Options Audit

## 5.1 Option 1 — Application-managed username/password + JWT or session tokens

| Dimension | Evaluation |
|---|---|
| Implementation complexity | Medium — password hashing (e.g. `passlib`/`bcrypt`), token issuance/verification, login/register/logout routes, eventual password-reset flow. Well-trodden FastAPI path (FastAPI's own documentation walks through exactly this with `OAuth2PasswordBearer`). |
| Operational burden | Entirely Raidian's own — credential storage, breach liability, rate-limiting login attempts, password-reset email delivery. |
| Security responsibility | Fully internal — highest risk surface for a small team, but fully within the team's control. |
| Database impact | One new, genuinely sensitive `users` table (email, hashed password, timestamps). |
| FastAPI integration | Excellent — this is the framework's own documented reference pattern. |
| Frontend implications | A real login/register UI must be designed (not currently in Product Spec Section 6's screen inventory — Section 4's named gap) and token storage/refresh handled client-side. |
| Local dev/testing | Straightforward, fully offline, no external dependency. |
| Future deployment | Fits the already-decided stack (Render, PostgreSQL) with no new infrastructure category. |
| Ownership support | Clean — `users.id` becomes the FK target Section 2 designs against. |
| Unnecessary infra for current MVP? | A real, non-trivial new responsibility (credential security) for a personal-reflection MVP — a genuine cost, not free, but entirely within the already-decided stack. |

## 5.2 Option 2 — External identity provider / OIDC

| Dimension | Evaluation |
|---|---|
| Implementation complexity | Lower application-side complexity (no password storage/hashing code), but adds a **new third-party dependency ADR-0004 never named.** |
| Operational burden | Shifted to the provider (password resets, breach response, MFA) — traded for a new operational dependency (provider uptime, pricing, data-residency questions). |
| Security responsibility | Shared — the provider handles credential security; Raidian must still correctly verify tokens. |
| Database impact | **Not zero** — still needs a local table mapping the provider's subject ID to Raidian's own ownership records; different shape, not less schema. |
| FastAPI integration | Fine, standard OIDC client patterns, but more moving parts (redirect flows, callback URLs) than a same-origin token. |
| Frontend implications | Typically a "Sign in with X" redirect flow — a different UX than a native form, needs evaluation against `docs/PRINCIPLES.md`'s "Simplicity Over Complexity." |
| Local dev/testing | Real added friction — sandbox credentials, callback URL configuration, often a tunneling tool for local OAuth callbacks. |
| Future deployment | Fine on Render, but couples platform identity to a third party's continued existence and pricing. |
| Ownership support | Clean, same mechanics, keyed on the provider's subject ID instead of a local password. |
| Unnecessary infra for current MVP? | Trades one kind of complexity for another; **directly touches `docs/PRINCIPLES.md`'s "Privacy By Design"** — a third-party identity provider necessarily learns who a user is (at minimum, an email address), a privacy-relevant architectural choice worth flagging explicitly against that governing principle, not necessarily disqualifying it. |

## 5.3 Another mechanism?

No concrete basis was found anywhere in the repository or Product Spec for any other approach (magic links, device-only pseudo-identity, etc.). One candidate — an anonymous, device-scoped identifier with no real login — was considered and set aside: it would not satisfy this task's own framing ("the *authenticated* user's saved Readings"), would not survive a cleared cookie or a new device, and has zero textual grounding in any governing document. Not developed further, per this task's instruction to name another option only with a genuine basis.

## 5.4 What this audit recommends, and what it explicitly does not decide

**Recommendation, not a decision:** Option 1 (application-managed credentials) is the smaller, fully self-contained choice — it introduces no dependency beyond what ADR-0004 already committed to, and it is the standard, well-documented path for this exact stack (FastAPI + SQLAlchemy + PostgreSQL). Option 2 remains a completely legitimate alternative if the product owner prefers to offload credential-security operations to a specialist provider — that tradeoff (Section 5.2) is real and worth an explicit, informed choice, not a default. **This document does not select one** — the actual mechanism is exactly the kind of decision `PRODUCT_DECISIONS.md` Q1 already modeled: name the dependency, recommend the smallest compliant path, leave the final call to whoever holds product/governance authority.

---

# 6. Minimum Ownership Model

Direct answers, per this task's explicit list, assuming Section 2.5's Option B recommendation (ownership on `ReflectionSession`) — each answer is stated so it transfers cleanly to Option A if that fallback is chosen instead.

- **What entity represents an authenticated user?** A new, minimal `User` (or `Account`) table — email/credential fields per whichever Section 5 mechanism is eventually chosen, plus the standard `UUIDPrimaryKeyMixin`/`TimestampMixin` this project already uses everywhere else.
- **What identifier is used?** The new `User.id` (a UUID, consistent with every other primary key in this schema — no reason to deviate).
- **Where is that identifier stored?** A new `owner_id` FK column on `ReflectionSession` (Option B) or on `Reading` (Option A fallback).
- **Mandatory or nullable?** Recommend `nullable=False` once the User model exists — a `ReflectionSession`/`Reading` with no owner has no coherent meaning under this task's own framing ("the authenticated user's saved Readings"). A migration would need a backfill strategy for any pre-existing rows (Section 10), exactly as `Interpretation.sequence`'s own migration already handled the same shape of problem.
- **Immutable?** Yes, recommended — no textual basis anywhere for reassigning a Reading/session to a different owner (Sections 2.2/2.3).
- **How are new Readings assigned an owner?** At `ReflectionSession` creation time, from whatever identity the (future) authentication dependency resolves for the request — not designed further here, since no API layer exists yet to attach it to.
- **How are existing pre-ownership Readings handled?** Not a present concern — this audit found no production deployment and no real user data anywhere in this repository; a future migration's backfill question is theoretical today, not a live data-migration problem (contrast with `Interpretation.sequence`, which did need to handle real pre-existing rows in dev/test databases).
- **Can ownership ever be transferred?** No — recommend disallowing outright, consistent with the immutability answer above.
- **What happens when an owner is deleted/deactivated?** Not designed here — depends entirely on which Section 5 mechanism is chosen and what "deactivation" means under it; named as a Section 14 deferred question, not decided.
- **Does `Interpretation` need an owner column?** **No.** It already FKs to `Reading`, which (transitively, through whichever of Sections 2.2/2.3 is chosen) already resolves to an owner — duplicating the column would violate this project's own repeatedly-applied "derive, don't store-and-risk-drift" precedent (`Spread.position_count`, `Reading.is_spread_complete`) for no benefit.
- **Does `NarrativeModel` need ownership information?** **No.** `NarrativeModel` is never persisted (`PRODUCT_DECISIONS.md` Q1/Q5, unchanged) — it is recomputed on demand from an already-authorized `Interpretation`; there is no row to own.
- **Does `CardDraw` need ownership information?** **No.** Same reasoning as `Interpretation` — it already FKs to `Reading` and inherits ownership transitively; a duplicate column would be pure, unjustified redundancy.

---

# 7. Reading History Query Design

## 7.1 Filter

Under the recommended Option B:

```text
SELECT reading.*
FROM readings AS reading
JOIN reflection_sessions ON reading.reflection_session_id = reflection_sessions.id
WHERE reflection_sessions.owner_id = :authenticated_user_id
  AND reading.status = 'saved'
```

(Under the Option A fallback, the join collapses away: `WHERE reading.owner_id = :authenticated_user_id AND reading.status = 'saved'`.)

## 7.2 Cardinality

Exactly one row per `Reading`, guaranteed by never joining against `Interpretation` for this listing (Section 2.3's explicit pitfall warning, restated from `SAVE_READING_DESIGN.md` Section 7 and re-verified here against the actual current schema — nothing has changed that would alter this conclusion).

## 7.3 Ordering — re-evaluated against the actual current model, not merely restated

`SAVE_READING_DESIGN.md` Section 7.2 named `updated_at` as a coincidentally-workable approximation for "recently saved," given that (at the time) nothing else mutated a `Reading` row after creation besides its own lifecycle transitions. **Re-checked directly against the schema as it exists today, post-Step-18: this conclusion still holds, unchanged.** `Reading.updated_at` (`TimestampMixin`, `onupdate=func.now()`) still only ever advances in response to a status transition (`DRAFTING`→`SPREAD_COMPLETE` via `add_card_draw()`, →`INTERPRETED` via `save_interpretation()`, →`SAVED` via `mark_saved()`) — no Reading-editing feature exists to introduce an unrelated `updated_at` bump. This document distinguishes the three timestamps this task asks to be kept separate, precisely:

- **"Newest Reading"** = `Reading.created_at`, descending. Answers "which Reading did I start most recently" — irrelevant to History's actual purpose.
- **"Most recently saved Reading"** = the property History actually wants. No dedicated field exists for it. `Reading.updated_at` is presently a correct proxy *only because* `SAVED` is very likely (though not certain) to be the last status transition a Reading ever undergoes — a Reading that reinterprets *after* being saved does **not** bump `Reading.updated_at` at all (reinterpretation only touches the `interpretations` table and, per `PRODUCT_DECISIONS.md`, deliberately never regresses or re-touches `Reading.status` once already `SAVED` — confirmed directly against `persistence.py`'s guard). So `updated_at` for an already-`SAVED` Reading is frozen at the moment it was saved, exactly the value History wants — **this is a stronger, more precisely-verified conclusion than Step 17's original, which had not yet checked reinterpretation's specific effect on `updated_at`.**
- **"Most recently interpreted Reading"** = the current highest-`sequence` `Interpretation.created_at` — a completely different field on a completely different table, and per Section 7.2, must never be allowed to influence History's ordering or cardinality.

**Recommendation, re-confirmed rather than merely repeated: order by `Reading.updated_at DESCENDING`. Do not introduce a `saved_at` column** — this audit found no case where `updated_at` would give an incorrect answer for a `SAVED` Reading under the currently-implemented lifecycle, because saving is (today) always either the terminal status transition or immediately followed by no further `Reading`-row mutation. The only scenario that would break this proxy — a future Reading-*editing* feature that touches `Reading.updated_at` for reasons unrelated to saving — does not exist and is not proposed by any current document; if it is ever built, `saved_at` becomes justified at that time, not before.

## 7.4 Empty result

`200 []`, never `404` — applying the same platform convention `INTERPRETATION_API_DESIGN.md` Section 7 already established for the interpretation-history list, re-applied here rather than re-derived.

## 7.5 Pagination

Remains deferred. This audit found nothing — no data volume concern, no Product Spec requirement, no new information beyond what `INTERPRETATION_API_DESIGN.md`'s own Q3 already concluded — that would make pagination necessary now.

---

# 8. API Boundary

**`GET /readings`, not `GET /readings/history`.** `docs/NAMING_CONVENTIONS.md`'s own plural-noun example list names `/readings` directly (alongside `/users`, `/journals`) — no sub-resource path is suggested anywhere, and `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 9's own illustrative sketch already used exactly `GET /readings` for "list/search Reading history." A query parameter (e.g. `?status=saved`, or simply "this route only ever returns saved Readings for the authenticated caller" as its whole contract) is a smaller, more consistent choice than inventing a new path segment.

A future `POST /readings/{reading_id}/save` (mirroring `POST /readings/{reading_id}/interpret`'s already-established shape exactly) is the natural API boundary for `Reading.mark_saved()`, whenever an API layer for it is built.

**Neither route is designed further here** (both are out of this task's scope), but this audit determines the shape each would need once authentication exists:

- **Authentication dependency:** both routes would require a resolved, authenticated identity — `GET /readings` cannot function at all without one (Section 5); `POST .../save` could theoretically remain callable without one today (exactly as the four existing routes are), but would need the same ownership check as every other mutation once ownership exists.
- **Ownership authorization:** `POST .../save` would need "does the authenticated caller own this `reading_id`" — not merely "does this `reading_id` exist" (today's only check, `_get_reading_or_404`).
- **Response schema:** `GET /readings` would need a `Reading`-shaped summary schema — none exists today (`app/schemas/` has no Reading-facing schema of any kind); not designed further here.
- **Empty result:** `200 []` (Section 7.4).
- **`404` for a Reading that exists but does not belong to the caller:** recommend **collapsing "not found" and "not authorized" into the same `404`** response — the standard, deliberate practice of not revealing *that* a resource exists to a caller who isn't entitled to see it. This is consistent with, not a deviation from, this project's existing `_get_reading_or_404` naming and behavior once ownership is added to that same check.
- **Do the current interpretation/narrative endpoints require ownership enforcement once authentication exists?** **Yes — all four existing routes** (`POST .../interpret`, `GET .../interpretations/current`, `GET .../interpretations`, `GET .../narrative`) resolve a caller-supplied `reading_id` with zero ownership check today; every one of them would need the identical "does the authenticated caller own this Reading" gate `POST .../save` and `GET /readings` need. This is not new work invented by this document — `INTERPRETATION_API_DESIGN.md` Section 5 already named this exact insertion point ("every one of these four endpoints resolves a `reading_id` to a specific `Reading` row: the future authorization check belongs exactly at that resolution point") — this audit reconfirms it applies identically to the two new routes this document considers.

---

# 9. Security / Authorization Boundary

The future rule, stated once, applying identically everywhere: **an authenticated user may access or mutate only Readings they own** (transitively, through whichever of Section 2's options is chosen).

| Surface | Ownership check needed once auth exists? |
|---|---|
| Save Reading | Yes — mutation against a specific `reading_id`. |
| Reading History | Yes — the entire query is scoped by ownership (Section 7.1); without it, the feature is not merely insecure, it does not do what it is named for (`SAVE_READING_DESIGN.md` Section 8's identical finding, reconfirmed here). |
| Current Interpretation | Yes — read access to another user's Interpretive Model. |
| Interpretation History | Yes — same reasoning. |
| Narrative | Yes — same reasoning, even though `NarrativeModel` itself carries no ownership (Section 6) — the check happens at `Reading` resolution, upstream of narrative assembly, exactly as it already does for every other field. |
| Future Reading Detail | Yes, by the same rule, whenever built. |
| Future Reading editing | Yes, by the same rule, whenever built. |

**Does the current unauthenticated interpretation API become a security problem once ownership exists?** **Yes, directly** — the moment a `User`/ownership model exists at all, every one of the four already-shipped routes becomes a real information-disclosure and unauthorized-mutation surface (any caller could interpret, or read the interpretation/narrative of, any other user's Reading by guessing or otherwise obtaining its UUID). This is not a new problem this document invents — `INTERPRETATION_API_DESIGN.md` Sections 4–5 already flagged the *absence* of ownership as the reason those routes are "acceptable only as an explicitly-flagged interim state... not acceptable for any real deployment." This document's contribution is confirming that the trigger condition for that acceptability window closing is specifically "ownership infrastructure exists" — once Section 6's `User`/`owner_id` model is built, retrofitting the ownership check onto these four existing routes becomes a required, not optional, follow-on step, not a separate future nice-to-have. **This document does not implement that retrofit** — it is named here as a direct, load-bearing consequence of the very ownership work this document is designing around, for whoever plans that future step to act on with full context.

---

# 10. Contradictions / Gaps

1. **The Product Spec's screen inventory never sketches a Login/Signup/Account screen** (Section 4) — the single most concrete, previously-unstated gap this audit surfaces: authentication is an unaddressed *product* question, not merely an unbuilt *engineering* one.
2. **`docs/PRINCIPLES.md`'s "Privacy By Design" already mandates per-user ownership** ("Users should retain ownership and control of their personal reflections") at the highest governance tier this project has, while zero ownership code exists anywhere — the gap between an accepted principle and the implementation is total, not partial.
3. **ADR-0004 (the decided technology stack) is silent on authentication** — confirming the mechanism is a genuinely open decision even at the level of "what libraries/services are we allowed to use," not merely "what have we built so far."
4. **Once ownership exists, all four already-shipped interpretation/narrative routes require a retrofit** (Section 9) — a real, identified follow-on cost of this work, not a new defect in those routes as they stand today (they were built and approved with this exact interim posture explicitly flagged).

No contradiction was found where the Product Spec or any governance document claims an ownership/auth mechanism *already* exists — every relevant statement is prospective, so nothing here required silently rewriting any source document.

---

# 11. Deferred Questions

- **Which Section 5 authentication mechanism is actually chosen** — this document recommends the smaller, self-contained option (5.4) but does not decide it.
- **Whether Option A or Option B (Section 2) is the final ownership placement** — recommended (B), not decided; Section 3's underlying `ReflectionSession`-cardinality ambiguity is explicitly preserved, not resolved.
- **What "deactivating" or deleting an owner means for their Readings** (cascade-delete? soft-deactivate-and-retain? Section 6) — not designed.
- **The retrofit of ownership checks onto the four existing interpretation/narrative routes** (Section 9) — named as required, not scheduled or designed in detail.
- **Whether a Login/Signup screen's design should be added to the Product Spec's own screen inventory** (Section 10, item 1) — a documentation/product action outside this document's authority to perform.
- **How `docs/PRINCIPLES.md`'s "Privacy By Design" principle should shape the *specific* choice between Section 5's two options** (an external provider necessarily shares some identity data with a third party) — named in Section 5.2, not adjudicated.

---

# 12. Recommended Implementation Sequence

Sequenced so each step is independently reviewable, mirroring this series' own established practice (a dedicated design step before implementation, exactly as Engine/Narrative/Orchestration/API/Lifecycle/Save each received):

1. **A dedicated product/governance decision** resolving Section 5 (which authentication mechanism) and Section 2 (Option A vs. B) — this document's recommendations are input to that decision, not a substitute for it, per ADR-0006.
2. Once decided: a focused schema design step for the `User` model and the `owner_id` column (Section 6), including its migration strategy (Section 2's backfill note) — not designed in implementation detail here.
3. The authentication mechanism's own implementation (login/register/token issuance, or the external-provider integration) — a substantial, separate body of work, out of this document's scope entirely.
4. **Retrofit ownership checks onto the four existing interpretation/narrative routes** (Section 9) — required before any of this work is considered complete for real deployment, not an optional follow-on.
5. Only then: implement `GET /readings` (Reading History) and `POST /readings/{id}/save`, following Sections 7–8's semantics.

No step in this sequence is authorized by this document.

---

# 13. Conclusion

This audit confirms, more precisely than any prior step, exactly what was already suspected and now directly verified: **zero identity or ownership infrastructure exists anywhere in this codebase or in the decided technology stack**, while the project's own highest-tier governance document (`docs/PRINCIPLES.md`) already treats per-user ownership as a settled principle. The minimum viable ownership model is small — one new `User` table, one new `owner_id` column (recommended on `ReflectionSession`, for reasons grounded in ADR-0003, not aesthetics), and no changes anywhere to `Interpretation`, `NarrativeModel`, or `CardDraw`, all of which correctly inherit ownership transitively rather than duplicating it. The larger, harder-to-shortcut piece is the authentication mechanism itself (Section 5) and the mandatory retrofit of ownership checks onto every route this project has already shipped (Section 9) — both are real, substantial, and correctly out of this document's scope to implement, exactly as Step 17 already concluded before this deeper audit began.

---

## Related Documents

- `PRODUCT_DECISIONS.md` — Q1's "name the dependency, recommend the smallest compliant path, leave the final call explicit" pattern, applied identically to Section 5 here.
- `SAVE_READING_DESIGN.md` — Section 9's original, sharpened ownership-dependency finding for Reading History specifically; Section 7's ordering-approximation finding, re-verified (not merely restated) in this document's Section 7.3.
- `INTERPRETATION_API_DESIGN.md` — Sections 4–5's original auth/ownership gap and Section 5's authorization-insertion-point finding, both reconfirmed and extended to two new routes (Section 8) and a mandatory retrofit (Section 9).
- `READING_LIFECYCLE_DESIGN.md`, `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` — the "derive, don't store-and-risk-drift" precedent this document applies in Section 6 to conclude `Interpretation`/`CardDraw`/`NarrativeModel` need no ownership column of their own.
- `docs/PRINCIPLES.md` — "Privacy By Design," the highest-authority citation this document relies on (Section 4).
- `docs/ARCHITECTURE.md`, `docs/DECISIONS.md` (ADR-0003, ADR-0004, ADR-0006), `docs/ROADMAP.md`, `docs/NAMING_CONVENTIONS.md` — the remaining governance stack this audit checked directly rather than assumed.
- `app/models/reading.py`, `app/models/reflection_session.py`, `app/models/enums.py`, `app/api/interpretation.py`, `backend/requirements.txt` — the actual, current code and dependencies every finding in this document was checked against.
