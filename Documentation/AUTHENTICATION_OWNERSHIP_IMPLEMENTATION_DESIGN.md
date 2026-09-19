# Raidian Wise — Authentication & Ownership Implementation Readiness Design/Audit (Step 21)

# Document Information

Version: 1.0 (Draft for Review — Not Yet Approved)
Status: Proposed — Implementation-Readiness Audit and Design Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Determines whether `AUTHENTICATION_OWNERSHIP_DESIGN.md` (Step 20) is sufficiently specified to implement safely, by translating its architecture into implementation-ready contracts (exact fields, types, routes, request/response shapes, migration steps, test list) and by re-verifying every relevant repository fact directly rather than assuming Step 20's findings still hold. This document implements nothing and makes no new product decision.

Audience:
Whoever implements authentication and ownership next, and whoever must approve the remaining product/governance decisions this document identifies as still open before that implementation begins.

Authority:
Operationalizes `AUTHENTICATION_OWNERSHIP_DESIGN.md` (Step 20) without reopening any of its recommendations or Step 19's (`READING_HISTORY_OWNERSHIP_DESIGN.md`) — this document narrows "what should we build" (Step 20) into "exactly what would we type" (this document), and stops short of deciding anything Step 20 itself left open (Section 13 restates the boundary explicitly). Does not override `docs/PRINCIPLES.md`, `docs/ARCHITECTURE.md`, or `docs/DECISIONS.md`, per ADR-0006.

---

# 0. Scope

Read-only implementation-readiness audit and design only. No application code, schema, migration, dependency, frontend code, or test file is created or modified. Where Step 20 left a decision open (the JWT-vs-OIDC choice, password reset, email verification, etc.), this document does not resolve it — it states plainly whether that open item blocks implementation or not, and why.

---

# 1. Executive Summary

Every fact this document re-checked from Step 20 (models, dependencies, session/config conventions, API router structure, test fixtures, frontend state) is **unchanged** — no repository drift occurred between Step 20 and this step (confirmed via `git log`/`git status`: no commits landed in between). This document's contribution is narrower and more concrete: it turns Step 20's architecture into field-level, route-level, migration-level, and test-level detail that a future implementation step could follow directly, and it identifies exactly one blocking condition (Section 15): **the authentication mechanism itself (app-managed JWT vs. OIDC) remains a Step-20-flagged, not-yet-approved product/governance decision** — everything else in this document is judged implementation-ready *conditional on* that decision resolving in favor of app-managed JWT, which is Step 20's recommendation but not (per Step 20's own Section 4.3 and Section 15) an approved decision. If that decision is approved as recommended, this document finds **no other stop condition** — the ownership model, migration sequence, authorization boundary, and route retrofit are all fully specifiable from the current repository state with no invented placeholder and no unresolved schema question.

---

# 2. Current-State Verification

Direct re-inspection, not assumed carried-over from Step 20. `git log -3 --oneline` confirms the most recent commit is still `e2facae` (Step 18) and `git status` shows the identical five untracked Documentation files plus the same 94-line `README.md` diff Step 20 last observed — **no code changed between Step 20 and this step.**

| Area | Verified finding |
|---|---|
| Models | `app/models/__init__.py` exports exactly: `Base`, `Card`, `CardCorrespondence`, `CardDraw`, `Deck`, `Arcana`, `DrawMethod`, `Orientation`, `ReadingStatus`, `SemanticRole`, `Suit`, `DuplicateCardError`, `Interpretation`, `Reading`, `ReflectionSession`, `Spread`, `SpreadPosition`. No `User`, no ownership field, unchanged from Step 20. |
| Mixins (`app/db/base.py`) | `UUIDPrimaryKeyMixin` (`id: Mapped[uuid.UUID]`, `Uuid` column, `default=uuid.uuid4`), `TimestampMixin` (`created_at`/`updated_at`, both `DateTime(timezone=True)`, `server_default=func.now()`, `updated_at` also `onupdate=func.now()`), and `str_enum_type()` (a portable, `native_enum=False` VARCHAR+CHECK enum column, storing `.value` not `.name`) — every future `User` field and enum should reuse these exact three primitives, not invent new ones. |
| Database/session config | `app/db/session.py`'s `get_db()` (commit-on-success/rollback-on-exception) is unchanged and is the only session-scoping mechanism; no second dependency of any kind exists yet. |
| Configuration/secrets | `app/core/config.py`'s `Settings` class has exactly one field, `database_url`, `RAIDIAN_`-prefixed via `pydantic-settings`, `.env`-file-friendly. No secret-key field, no auth-related setting. |
| Requirements/dependencies | `backend/requirements.txt` unchanged (reproduced in Section 12). **Newly verified this step, not merely re-stated:** `pip list` against the actual `backend/.venv` finds **zero** installed packages matching `jwt`, `bcrypt`, `passlib`, `argon`, `crypto`, `jose`, `itsdangerous`, or `email` (case-insensitive) — confirming the absence is real at the installed-environment level, not merely a `requirements.txt` omission that some already-installed transitive dependency might paper over. |
| FastAPI dependency patterns | `get_db()` remains the only dependency used anywhere (`app/api/interpretation.py`); no `Depends(...)`-based auth pattern exists to extend. |
| API router structure | `app/main.py` registers exactly one router (`interpretation_router`) and no middleware (no CORS, no auth, nothing) — confirmed by direct re-read. `app/api/interpretation.py`'s router is `APIRouter(prefix="/readings/{reading_id}", tags=["interpretation"])`; a future account router would need its own, differently-prefixed `APIRouter` (Section 7). |
| Existing error handling | Exactly two HTTP error mappings exist anywhere: `404` (`_get_reading_or_404`, `_READING_NOT_FOUND`/`_NEVER_INTERPRETED` constants) and `409` (`ReadingNotReadyForInterpretationError`). No `401`/`403`/`422`-for-business-rules precedent exists yet — `422` for a malformed UUID path parameter is FastAPI's own automatic behavior, not application code. |
| Existing test fixtures | Two independent, non-shared patterns confirmed by direct re-read: (a) `tests/conftest.py`'s `db_session`/`seeded_session` — a raw SQLAlchemy `Session` against an in-memory `StaticPool` SQLite engine with `PRAGMA foreign_keys=ON` enabled per-connection; (b) `test_api_interpretation.py`'s self-contained `api_engine`/`client` fixtures — a second, independently-defined `StaticPool` engine plus a `get_db` dependency override wired into `app.main.app`'s `TestClient`, kept deliberately separate from (a) because an HTTP-layer test needs a `get_db` override while a direct-session test does not. Any future authentication test file will need the identical self-contained `client`-fixture pattern (b), not a shared one, consistent with this project's existing precedent of duplicating it per API test file rather than centralizing it in `conftest.py`. |
| `tests/factories.py` | `make_reading()` constructs a bare `ReflectionSession()` with no owner field and flushes it — confirming directly (not inferring) that every existing reading-construction helper will need a new, owner-aware counterpart once `owner_id` exists (Section 4.5), and that today's helper cannot silently keep working unchanged for any future owned-Reading test. |
| Frontend structure | `frontend/src/App.tsx` is still the unmodified Vite demo (hero image + click counter); `package.json` still lists only `react`, `react-dom`, `tailwindcss`, `@tailwindcss/vite`, plus devDependencies — no router, no HTTP client, no auth library. Re-confirmed unchanged. |
| Existing API communication patterns | None exist — the frontend makes zero calls to the FastAPI backend today, confirmed by the absence of any `fetch`/`axios`/API-client code anywhere in `frontend/src/`. |
| Environment-variable conventions | Exactly one precedent: `RAIDIAN_DATABASE_URL` (via `RAIDIAN_` prefix + `database_url` field). Any new secret (Section 9.2) should follow this identical naming shape, e.g. `RAIDIAN_JWT_SECRET_KEY`. |

---

# 3. User Model — Implementation Contract

Translating Step 20 Section 5's minimal `User` into field-level detail, using this project's exact existing conventions (Section 2's mixins).

```python
class User(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    reflection_sessions: Mapped[list["ReflectionSession"]] = relationship(back_populates="owner")
```

| Field | Type | Nullable | Unique | Index | Default | Notes |
|---|---|---|---|---|---|---|
| `id` | `Uuid` (via `UUIDPrimaryKeyMixin`) | No | Yes (PK) | Yes (PK) | `uuid.uuid4` | Identical to every other model's primary key — no deviation. |
| `email` | `String(320)` | No | **Yes** | Yes | none | `320` is the RFC 5321 maximum mailbox-address length — a defensible, standard bound, not an arbitrary one. Stored lowercased/trimmed by application code before insert/query (Step 20 Section 5.3) — **not** a database-level `CHECK`/`LOWER()` constraint, since SQLite/PostgreSQL portability for a functional unique index adds complexity this project's "Simplicity Over Complexity" principle does not justify yet; normalization happens once, at the service boundary (Section 6.6), not enforced redundantly at the schema layer. |
| `hashed_password` | `String(255)` | No | No | No | none | `255` comfortably exceeds any bcrypt (60 chars) or argon2 (~97 chars typical) encoded-hash length, with headroom (Section 9.1's algorithm choice does not need to be finalized to size this column safely). |
| `is_active` | `Boolean` | No | No | No | `True` | Section 3.1 below. |
| `created_at` / `updated_at` | `DateTime(timezone=True)` (via `TimestampMixin`) | No | No | No | `func.now()` | Identical to every other model — no deviation. |

## 3.1 Active/inactive semantics

`is_active = False` blocks authentication (Section 9.4's failure-mode design: `get_current_user` must reject a token resolving to an inactive user, and — per that same section — the login endpoint must also reject credentials for an inactive user, at whichever of the two layers is exercised first for a given request). **What sets `is_active = False` is explicitly out of scope** — no admin/moderation feature exists or is proposed anywhere in this project's governance documents; the column is included because Step 20 Section 5.1 already named it as part of the minimum model (an account state that can plausibly need disabling is a reasonable minimum, even before any mechanism to disable one is built), not because a deactivation feature is being designed here.

## 3.2 Password storage requirement

`hashed_password` must **never** hold a plaintext value at any point after the registration/login boundary — enforced by code discipline (Section 6, Section 9.1), not a schema-level constraint (no portable way to enforce "looks like a hash" at the database layer, and none is warranted).

## 3.3 Deliberately excluded fields

Per this task's explicit instruction and Step 20 Section 5.1/5.5 (unchanged): no display name, no profile/avatar fields, no role/permission field, no email-verification flag, no password-reset token field, no refresh-token field. None is named by any current governance document (re-verified: `docs/ROADMAP.md`, `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6's screen inventory, and `docs/NAMING_CONVENTIONS.md`'s `/users` mention all remain silent on any of these, exactly as Step 20 found).

## 3.4 Relationship direction

`User.reflection_sessions` (one-to-many, back-populating `ReflectionSession.owner`) — the natural direction given `ReflectionSession.owner_id` is the FK-bearing side (Section 5). No `back_populates` cycle risk, consistent with every existing one-to-many relationship in this schema (e.g. `Spread.readings`, `Deck.readings`).

---

# 4. Ownership Model — Implementation Contract

## 4.1 Relationship shape, confirmed against the actual current model

`ReflectionSession` (`app/models/reflection_session.py`) currently has exactly two mapped attributes: the inherited `id`/`created_at`/`updated_at` and a single `reading` relationship (`uselist=False`, `cascade="all, delete-orphan"`, back-populating `Reading.reflection_session`). **Adding `owner_id` requires no restructuring** — it is a plain new column and a plain new relationship on an otherwise-unchanged model; nothing about `ReflectionSession`'s current shape conflicts with or complicates this addition. This directly answers this task's Section 4 verification requirement: **yes, the current `ReflectionSession` model and relationship structure supports this cleanly**, with zero structural obstacle found.

## 4.2 Exact column

```python
owner_id: Mapped[uuid.UUID] = mapped_column(
    ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
)
owner: Mapped["User"] = relationship(back_populates="reflection_sessions")
```

| Property | Value | Rationale |
|---|---|---|
| FK type | `Uuid` (matching `User.id`'s type exactly — every PK/FK pair in this schema is `Uuid`, no exception anywhere to deviate from) | Consistency with `UUIDPrimaryKeyMixin`. |
| Nullable | **`True` initially** (Section 4.4/8), transitioning to `False` once every code path that creates a `ReflectionSession` is guaranteed to supply an owner | Step 20 Section 3.7/11.1, reaffirmed after re-verifying no such creation path yet exists to make `False` immediately safe (Section 4.5). |
| `ondelete` | `CASCADE` | Step 20 Section 3.4's `PRINCIPLES.md`-grounded reasoning, reaffirmed — matches every other cascade in this schema. |
| Index | Plain (non-unique) B-tree index | Supports the future Reading History filter (`WHERE reflection_sessions.owner_id = :user_id`) — Step 19 Section 7.1, unchanged. |
| Uniqueness | **None** | One `User` legitimately owns many `ReflectionSession` rows (Step 20 Section 3.5, reaffirmed — no change). |

## 4.3 Whether existing readings require a migration/backfill

**No** — re-verified directly, not assumed: this repository's only `Reading`/`ReflectionSession` rows are transient, in-memory, per-test SQLite rows created by `tests/factories.py::make_reading` and `tests/interpretation_helpers.py::build_reading`, both instantiated fresh inside each test's isolated `:memory:` database and discarded at test teardown (`db_session`'s `finally: session.close(); engine.dispose()`). There is no persistent development database file checked into or referenced by this repository requiring a real backfill pass. This reaffirms Step 20 Section 11.3's finding after directly re-confirming its premise (no persistent dev data) rather than merely repeating the conclusion.

## 4.4 Nullable vs. mandatory, and why "initially nullable" is not a compromise here

A `ReflectionSession`-creating code path does not exist yet at all — `make_reading()` (test-only) and the (non-existent) production creation path are the only two ways a `ReflectionSession` could ever come into being, and the production path has never been built (no API route creates a `Reading`/`ReflectionSession` today — every existing route only ever reads an already-existing one, per `app/api/interpretation.py`'s four routes, re-confirmed). Consequently: `owner_id` must start nullable simply because **the column would otherwise be impossible to populate correctly today, independent of any migration-safety concern** — there is no code yet that could supply a value at insert time. Once the (not-yet-existing) `Reading`/`ReflectionSession`-creation path is built as part of this same authentication/ownership initiative (Section 14, step 6), that path should always supply `owner_id`, and `NOT NULL` becomes both safe and correct to enforce from that point forward.

## 4.5 How newly created readings receive ownership

**Not designable in further detail here, and this document does not invent a mechanism** — per this task's explicit instruction not to invent a temporary owner mechanism. The concrete answer depends on a production `Reading`/`ReflectionSession`-creation route that does not exist yet anywhere in this codebase (confirmed by Section 2's router-structure re-verification: all four existing routes only resolve an already-existing `reading_id`). This document names the dependency precisely rather than routing around it: **whatever future step builds Reading creation must accept an authenticated `current_user` (via `get_current_user`, Section 5) and set `ReflectionSession(owner=current_user)` at construction time** — the mechanism is exactly as simple as that sentence, but the route itself is out of this document's and Step 20's scope alike, and is not retroactively designed here just to make this section feel more complete than the repository currently supports.

---

# 5. Authentication Contract

Conditional on Section 15's blocking decision resolving in favor of Step 20's recommendation (app-managed JWT) — if it resolves otherwise (OIDC), this entire section would need to be redesigned, not merely adjusted (Section 15 states this explicitly, not as an afterthought).

## 5.1 Registration endpoint

```text
POST /auth/register
```
Request body:
```json
{ "email": "user@example.com", "password": "a-plaintext-password" }
```
Response (201 Created):
```json
{ "id": "uuid", "email": "user@example.com", "created_at": "iso-8601" }
```
Never echoes `hashed_password`. `409 Conflict` if the normalized email already exists (mirrors this project's existing precedent of a specific, named 4xx for a specific business-rule violation — `ReadingNotReadyForInterpretationError` → `409`, re-used here for "email already registered" rather than inventing a new status code for the same *kind* of conflict). `422` for a request body that fails Pydantic validation (e.g. malformed email, too-short password per Section 6.3) — FastAPI's own automatic behavior, not new application code.

## 5.2 Login endpoint

```text
POST /auth/login
```
Request body:
```json
{ "email": "user@example.com", "password": "a-plaintext-password" }
```
Response (200 OK):
```json
{ "access_token": "eyJ...", "token_type": "bearer" }
```
`401 Unauthorized` for: nonexistent email, wrong password, or `is_active = False` — **collapsed into one identical response and message** ("Incorrect email or password"), deliberately not distinguishing "wrong password" from "no such account," for the same resource-enumeration-avoidance reasoning Step 20 Section 8.4 already applied to Reading ownership (`PRINCIPLES.md`'s "Privacy By Design" — confirming an account's *existence* is itself information a caller without the correct password should not receive). This is a direct, newly-drawn implication of Step 20's own 404-vs-403 reasoning, applied here to a different boundary (login, not Reading access) for the identical underlying reason.

## 5.3 Token claims (unchanged from Step 20 Section 7.1)

```text
sub  -- User.id (string-encoded UUID)
exp  -- expiration, unix timestamp
iat  -- issued-at, unix timestamp
```

## 5.4 Token lifetime

Short-to-medium (e.g. 30–60 minutes), per Step 20 Section 7.3 — an exact number is an implementation/configuration detail, not a product decision, and is not pinned down further here (Section 13 classifies it accordingly).

## 5.5 Signing configuration

`HS256`, secret sourced from a new `RAIDIAN_JWT_SECRET_KEY` environment variable added to `app/core/config.py`'s `Settings` class, following the exact existing `database_url` pattern (Section 2's environment-variable-convention finding) — no new configuration *mechanism*, only a new field within the mechanism that already exists.

## 5.6 Password hashing requirement

Section 9.1 — not finalized to a single named library here (bcrypt vs. argon2, both acceptable, per Step 20 Section 6.1, reaffirmed), but the contract is fixed regardless of which: `register` hashes before storing, `login` verifies via the chosen library's constant-time comparison, never a manual `==`.

## 5.7 Inactive-user behavior

Section 3.1 — `401` at both `login` (checked explicitly, since a freshly-submitted password might otherwise successfully verify against a disabled account) and `get_current_user` (checked again, since a token issued before deactivation could otherwise remain valid for its full unexpired lifetime) — **both checks are required**, not redundant: they close two different windows (before a token exists, and after one already does).

## 5.8 Authentication failure behavior

Uniform `401` with a generic detail message across every failure mode named in 5.2/5.7 and in Section 9.4 (missing/malformed/expired/invalid-signature token) — no response varies its message or status code based on *which* condition failed, per the same enumeration-avoidance reasoning.

## 5.9 Logout semantics

Client-side token discard only (Step 20 Section 7.12, reaffirmed, not redesigned here) — no server-side endpoint, no revocation list. If a `POST /auth/logout` route is ever added purely for symmetry/discoverability, it would be a no-op success response with no server-side state change — **not designed further, named only because this task asks the contract to address logout explicitly.**

## 5.10 Dependency boundary

`get_current_user` (Section 6) is the only consumer of the issued token going forward — `register`/`login` themselves require no authentication dependency (a caller is, by definition, not yet authenticated when calling either).

---

# 6. Authorization Boundary — Implementation Contract

## 6.1 `get_current_user`

```python
def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_db),
) -> User:
    ...
```
- Decodes and verifies the JWT (signature + `exp`) using the configured secret/algorithm (Section 5.5).
- On any decode/verification failure (malformed, expired, bad signature) → `401`.
- Loads `User` by `sub`; if no such row exists → `401` (not `404` — an authentication-layer failure, distinct from Section 6.2's resource-authorization `404`).
- If `user.is_active` is `False` → `401` (Section 5.7).
- Returns the resolved `User` on success.

## 6.2 `get_owned_reading`

```python
def get_owned_reading(
    reading_id: UUID,
    current_user: User = Depends(get_current_user),
    session: Session = Depends(get_db),
) -> Reading:
    reading = session.get(Reading, reading_id)
    if reading is None or reading.reflection_session.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail=_READING_NOT_FOUND)
    return reading
```
Replaces `_get_reading_or_404` at its exact existing call sites (Section 7). `reading.reflection_session` is a plain relationship attribute access (one implicit `SELECT`, or none if already loaded) — not a hand-written `JOIN` the implementer could get wrong, directly addressing this task's "one ownership enforcement boundary, not duplicated checks" goal: every route depends on this single function, and this single function performs the entire check exactly once, in one place.

## 6.3 Behavior verification, restated against this exact code shape

| Case | Result | Where in the code above |
|---|---|---|
| Unauthenticated request | `401` | `get_current_user` raises before `get_owned_reading`'s body ever runs — FastAPI resolves `Depends` arguments before the route body, and `get_owned_reading` itself depends on `get_current_user`, so the chain fails at the earliest point. |
| Nonexistent Reading | `404` | `reading is None` branch. |
| Reading owned by another user | `404` | `reading.reflection_session.owner_id != current_user.id` branch — identical response to the row above, by design (Step 20 Section 8.4). |
| Same-user (owner) access | Succeeds, `reading` returned | Neither branch triggers. |
| Authorization happens before orchestration? | **Yes, always** | `get_owned_reading` is a FastAPI dependency, resolved before the route function body (which is the only place orchestration functions are ever called) executes at all. |
| Engine/narrative layers remain ownership-agnostic? | **Yes, confirmed unchanged** | `interpret_reading(session, reading)`, `get_current_interpretation(session, reading)`, `list_interpretations(session, reading)`, `get_narrative_for_reading(session, reading)` all already take an already-resolved `Reading` as their second argument (re-verified against `app/services/reading_orchestration.py`'s current signatures) — none needs a new parameter, since ownership is fully resolved upstream, at the API layer, before any of them is ever invoked. |

---

# 7. Existing API Retrofit Plan

Exact, mechanical, per-route change — **not implemented by this document.**

| Route | Current signature (verified) | Retrofitted signature |
|---|---|---|
| `POST /readings/{reading_id}/interpret` | `interpret_reading_route(reading_id: UUID, session: Session = Depends(get_db))` then `reading = _get_reading_or_404(session, reading_id)` | `interpret_reading_route(reading: Reading = Depends(get_owned_reading), session: Session = Depends(get_db))` — the manual `_get_reading_or_404` call is deleted from the function body. |
| `GET /readings/{reading_id}/interpretations/current` | Same shape | Same change. |
| `GET /readings/{reading_id}/interpretations` | Same shape | Same change. |
| `GET /readings/{reading_id}/narrative` | Same shape | Same change. |

`_get_reading_or_404` itself is deleted once no route calls it — confirmed by direct re-read that it has exactly four call sites, one per route, and no other caller anywhere in the codebase.

**Confirmed, not merely asserted:** `reading_orchestration.py`'s four functions require zero signature change (Section 6.3's table) — the retrofit is entirely contained within `app/api/interpretation.py`, touching no other file's function signatures. New OpenAPI-documented response: `401` added to every route's `responses={}` declaration (currently only `404`/`409` appear); `404`'s existing description (`_READING_NOT_FOUND`) now also covers "not owned," with no new response body shape.

---

# 8. Migration Plan

Design only — no migration file created. Two independent migrations, following this repository's existing Alembic conventions (four prior migrations, most directly `74ffb042dc2d`, already inspected in Step 20 Section 11.2 and re-confirmed here by direct re-read of that file).

## 8.1 Migration 1 — create `users`

```python
def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
```
Standalone `CREATE TABLE` — no interaction with any existing table, no backfill (a new table starts empty), no SQLite/PostgreSQL divergence (every type used — `Uuid`, `String`, `Boolean`, `DateTime(timezone=True)` — is already used identically across this schema's existing migrations and proven portable by them).

## 8.2 Migration 2 — add `ReflectionSession.owner_id`

```python
def upgrade() -> None:
    op.add_column(
        "reflection_sessions",
        sa.Column("owner_id", sa.Uuid(), nullable=True),
    )
    op.create_index("ix_reflection_sessions_owner_id", "reflection_sessions", ["owner_id"])
    with op.batch_alter_table("reflection_sessions") as batch_op:
        batch_op.create_foreign_key(
            "fk_reflection_sessions_owner_id_users",
            "users", ["owner_id"], ["id"], ondelete="CASCADE",
        )

def downgrade() -> None:
    with op.batch_alter_table("reflection_sessions") as batch_op:
        batch_op.drop_constraint("fk_reflection_sessions_owner_id_users", type_="foreignkey")
    op.drop_index("ix_reflection_sessions_owner_id", table_name="reflection_sessions")
    op.drop_column("reflection_sessions", "owner_id")
```
`op.batch_alter_table` used for the FK addition specifically because SQLite cannot add a foreign-key constraint to an existing table via a plain `ALTER TABLE` — the exact same reason `74ffb042dc2d` already uses `batch_alter_table` for its own constraint addition; this is a **repeated, already-proven technique in this repository**, not a new one. No `server_default` is needed on `owner_id` (unlike `Interpretation.sequence`'s `server_default='0'`) because, per Section 4.3, no pre-existing row needs to satisfy a `NOT NULL` requirement — the column is added nullable and stays nullable in this migration; **no third migration transitioning it to `NOT NULL` is designed here**, since Section 4.4 already establishes that transition is not yet safe to schedule (it depends on a not-yet-built Reading-creation route).

## 8.3 SQLite / PostgreSQL compatibility

Both migrations use only types and operations already proven across this repository's four existing migrations against both dialects (`Uuid`, `String`, `Boolean`, `DateTime(timezone=True)`, `batch_alter_table` for constraint changes) — no new portability question is introduced.

## 8.4 Downgrade behavior

Both migrations downgrade cleanly and symmetrically (drop FK/index/column, or drop index/table) — no data-loss concern beyond discarding `users`/`owner_id` values, which (per Section 4.3) are inconsequential today given the absence of persistent data outside test runs.

---

# 9. Security Requirements

Implementation-level requirements that must be preserved during coding — separated into what is already a live gap versus what is a future-implementation risk to guard against while building.

## 9.1 Already a live gap (exists today, independent of this initiative)

- **Horizontal access**: any caller can already read/mutate any Reading via its four routes with zero ownership check (Step 20 Section 14.1, re-confirmed unchanged — this document's entire Sections 6–7 exist to close this).

## 9.2 Must be satisfied by the implementation itself (not yet applicable today, but load-bearing once built)

- **Password hashing**: bcrypt or argon2 only (Section 5.6) — never a fast general-purpose hash (SHA-256/MD5), never plaintext, never reversible encryption.
- **JWT secret configuration**: sourced from `RAIDIAN_JWT_SECRET_KEY` (Section 5.5), never hardcoded, never logged, never committed to the repository (must be added to `.gitignore`-covered `.env` handling exactly as `RAIDIAN_DATABASE_URL` already is).
- **Token expiration**: enforced by `get_current_user`'s decode step (Section 6.1) — an unexpired-check bypass would be a critical defect, so this must be a library-verified check (the JWT library's own `exp` validation), never a manually-reimplemented comparison.
- **Algorithm enforcement**: the decode call must pin the expected algorithm (`HS256`) explicitly rather than trusting the token's own `alg` header — a well-known JWT library footgun (an attacker-supplied `alg: none` or algorithm-confusion attack) that the implementation must not reproduce, named here specifically so the eventual implementer does not have to rediscover it.
- **Credential leakage**: `hashed_password` must never appear in any response schema (Section 3.2) or be interpolated into any log line, error message, or exception string.
- **User enumeration**: collapsed error responses at both the login boundary (Section 5.2) and the Reading-ownership boundary (Section 6.2/Step 20 Section 8.4) — both already specified above, restated here as the security requirement they jointly satisfy.
- **Authorization bypass**: the single-dependency design (Section 6) exists specifically so no route can accidentally omit the check by hand-rolling its own — a future code-review requirement, not an automated one, since nothing in this stack currently enforces "every route touching `Reading` must depend on `get_owned_reading`" mechanically; named as a residual manual-review risk, not eliminated by architecture alone.
- **Inactive accounts**: checked at both `login` and `get_current_user` (Section 5.7) — a single-point check would leave one of the two windows open.
- **Error-message leakage**: no stack trace, internal exception text, or SQL error should ever reach a response body — not a new requirement this document introduces, but worth naming since a new `users` table and password-verification code path is new surface area where an unhandled exception could otherwise leak internals for the first time in this project's history.

## 9.3 CORS implications

**Not yet addressed anywhere in this repository** — `app/main.py` registers no CORS middleware at all (confirmed, Section 2). This is currently a non-issue only because the frontend makes no cross-origin (or same-origin) calls at all yet; the moment a real frontend origin needs to call this API with an `Authorization` header attached, CORS configuration becomes mandatory (a bearer-token header is not automatically exempted from CORS preflight the way a same-origin cookie might be). **Named as a required addition once the frontend integration (Section 11) actually begins — not designed further here**, since no deployment origin is named in any governance document to configure against.

## 9.4 `localStorage`/token handling in the frontend

Restated from Step 20 Section 13.2/14.1, not redesigned: `localStorage` is the simplest option and carries a known XSS-exposure tradeoff; a more defensive in-memory-plus-silent-refresh pattern is an alternative with its own cost (Section 7.11's "no refresh tokens" recommendation makes a pure in-memory approach awkward, since losing memory on every page reload would force a full re-login far more often). **Not decided here** — named as a frontend-implementation-time choice, not a blocking one.

## 9.5 Development vs. production configuration

The only environment-conditional behavior this design introduces is the JWT secret itself (Section 5.5) — it must differ between local development and any real deployment, exactly as `database_url` already does today (SQLite locally, PostgreSQL in production, per ADR-0004). No other environment-specific security behavior is proposed (e.g. this document does not recommend relaxing any check in development — `is_active`/expiration/signature checks apply identically in every environment).

---

# 10. Test Plan

Design only — no test file created. Every test below follows the exact fixture conventions Section 2 re-verified (`db_session`/`seeded_session` for direct-session tests; a new, self-contained `client`-style fixture, mirroring `test_api_interpretation.py`'s existing pattern, for any HTTP-layer auth test file).

## 10.1 `User` model / password (direct-session tests, `db_session`)

- Creating a `User` with a valid email/hashed password succeeds and is retrievable.
- Duplicate email (case-insensitive) raises `IntegrityError` at the database layer — mirrors this project's existing precedent (`test_reflection_session_reading_is_one_to_one`'s `IntegrityError`-on-uniqueness-violation pattern, applied here to `User.email`).
- Password hashing produces a value distinct from the plaintext input; verifying the correct plaintext against the stored hash succeeds; verifying an incorrect plaintext fails.

## 10.2 Registration/login (HTTP-layer tests, new `client` fixture)

- `POST /auth/register` with a new email → `201`, response omits `hashed_password`.
- `POST /auth/register` with an already-registered (or case-variant) email → `409`.
- `POST /auth/register` with an invalid email or too-short password → `422`.
- `POST /auth/login` with correct credentials → `200`, a well-formed JWT.
- `POST /auth/login` with wrong password → `401`, identical message to "no such account."
- `POST /auth/login` with a nonexistent email → `401`, identical message.
- `POST /auth/login` against an `is_active = False` account → `401`.

## 10.3 Token validation (`get_current_user`)

- Missing `Authorization` header → `401`.
- Malformed token (not a valid JWT structure) → `401`.
- Expired token → `401`.
- Token with an invalid signature (signed with a different secret) → `401`.
- Token whose `sub` resolves to a since-deleted `User` → `401`.
- Token whose `sub` resolves to an `is_active = False` `User` → `401`.
- Valid, unexpired token for an active user → `get_current_user` returns the correct `User`.

## 10.4 Ownership (`get_owned_reading`)

- Owner requesting their own Reading → the `Reading` is returned.
- **A second, distinct user requesting the first user's Reading → `404`** — this is this task's specifically emphasized proof requirement ("one user's Reading can never be accessed or interpreted by another user"): a dedicated test constructing two `User` rows, two independent `ReflectionSession`/`Reading` pairs (one owned by each), and asserting the second user's authenticated request against the first user's `reading_id` returns `404` with no data disclosed.
- Nonexistent `reading_id` (valid UUID, no matching row) → `404`, identical response shape to the cross-user case.
- Ownership resolves correctly through the `ReflectionSession` relationship specifically — a test that constructs a `Reading` via `ReflectionSession(owner=user)` (not a shortcut bypassing that relationship) and confirms `get_owned_reading` succeeds only for that exact owner.

## 10.5 All four existing routes, per route (×4)

For each of `POST .../interpret`, `GET .../interpretations/current`, `GET .../interpretations`, `GET .../narrative`:
- Authenticated owner → existing success response, unchanged in shape.
- No `Authorization` header → `401`.
- Authenticated, non-owning user → `404`.
- **Regression requirement, explicit and non-negotiable per this task's instruction:** every one of `test_api_interpretation.py`'s existing 23 tests (Step 11) must continue passing, updated only to supply a valid owning-user token — none deleted, none weakened, none silently skipped.

## 10.6 Orchestration-not-bypassed checks

- A direct call to `reading_orchestration.interpret_reading(session, reading)` (bypassing the API layer entirely, as existing orchestration-layer tests already do) continues to succeed with no `User`/ownership argument of any kind — proving the retrofit did not leak an ownership dependency into a layer that must remain ownership-agnostic (Section 6.3's table, proven by a passing test rather than only by code inspection).

## 10.7 Full-suite regression

The existing **277-test suite** (Steps 1–18, all currently passing, re-confirmed by this step's own test run — Section "Final Report" below) must remain fully passing, unmodified in behavior, after every addition above — this document's test plan is strictly additive.

---

# 11. Frontend Boundary

Restated and lightly sharpened from Step 20 Section 13 — not redesigned, since nothing about the frontend changed between Step 20 and this step (Section 2, re-confirmed).

- **API client location/pattern**: a minimal `fetch`-based (or a small wrapper) client module would need to exist before any screen could call `POST /auth/login` or any owned-Reading route — none exists today to extend; this is new code, not a modification.
- **Login/register screens**: not designed here — `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6's screen inventory still names neither (re-verified unchanged from Step 20 Section 2.2/4).
- **Token handling**: Section 9.4 — not decided between `localStorage` and an in-memory pattern.
- **Authenticated request handling**: every future API call touching a Reading must attach `Authorization: Bearer <token>`; a client-side wrapper is the natural place to centralize this once built, mirroring the backend's own "one boundary, not per-call duplication" principle (Section 6), though this document does not mandate a specific frontend architecture to achieve it.
- **Logout**: clears the client-stored token (Section 5.9) — no server call required.
- **Route protection**: a minimal "redirect to login if no valid token" gate would be needed before any authenticated screen renders — not designed in detail (no router is even installed yet, Section 2).
- **Ownership-aware Reading History integration later**: Section 10 of Step 19/Section 10 of Step 20, unchanged — `GET /readings` remains out of scope for both this document and the eventual first authentication implementation pass; named here only so the frontend boundary is understood to extend to it eventually, not implemented against it now.

**Not designed**: a complete frontend UX, specific component structure, or specific state-management library choice — none is necessary for backend implementation correctness, and this task's own instruction limits this section to the boundary, not the full experience.

---

# 12. Dependency Analysis

`backend/requirements.txt`, current, verified byte-for-byte unchanged from Step 20:
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

**Newly verified this step**: `pip list` against the actual installed `backend/.venv` environment returns zero matches for any auth-adjacent package name (Section 2) — confirming there is no already-installed, merely-unlisted dependency to quietly rely on. Any implementation genuinely needs new packages, not just a `requirements.txt` entry for something already present.

**Smallest appropriate additions, named for a future implementation step, not installed here:**
- **Password hashing**: one of `bcrypt` (small, C-extension-backed, minimal API surface, no additional transitive dependencies of note) or `passlib[bcrypt]` (a thin, slightly higher-level wrapper around the same primitive). Recommend the plain `bcrypt` package directly — smaller dependency footprint than pulling in `passlib`'s broader multi-algorithm framework for a single-algorithm need, consistent with `docs/PRINCIPLES.md`'s "Simplicity Over Complexity."
- **JWT**: `PyJWT` — a small, single-purpose, widely-used library with no heavier alternative-dependency chain; `python-jose` is a reasonable alternative but pulls in a broader cryptographic-suite surface than this project's single-algorithm (`HS256`) need justifies.
- **No OIDC/OAuth client library** is named, since Section 15's decision has not resolved in that direction.

**Not added to `requirements.txt` by this document** — every package above is a recommendation for the eventual implementation step, per this task's explicit instruction.

---

# 13. Product/Governance Boundary

| Item | Status |
|---|---|
| Ownership placement on `ReflectionSession` (Option B) | **Already recommended (Step 19/20)** — an engineering architecture conclusion, grounded in ADR-0003, not itself requiring further product sign-off beyond what Step 19/20 already documented; treated as settled input by this document. |
| `User → ReflectionSession → Reading` ownership chain, `CASCADE` deletion, no child-table ownership columns | **Already recommended (Step 20)**, implementation contract only refined here — not a new decision. |
| `404` (not `403`) for unauthorized Reading access | **Already recommended (Step 20 Section 8.4)**, grounded directly in `docs/PRINCIPLES.md` — carried forward unchanged. |
| **App-managed JWT vs. OIDC** | **Still an open product/governance decision, explicitly not converted into a settled fact by this document.** Step 20 Section 4.3 recommended Option A but did not select it; Section 15 below restates this as the one blocking item. |
| Exact token lifetime, exact password-hashing library choice (bcrypt vs. argon2), exact JWT library choice | **Implementation details**, not product decisions — any reasonable choice within Section 9's named constraints is acceptable without further governance sign-off, per this task's own instruction not to convert an engineering preference into a product decision by treating trivial implementation choices as blocking ones. |
| Password reset, email verification, MFA, roles/admin, OAuth/social login | **Not requested by any governance document** (re-verified, Section 3.3/7) — correctly out of scope, not a deferred-but-implied requirement. |
| Whether `ReflectionSession` is *permanently* the ownership boundary (vs. `Reading` directly) | **Still an open, explicitly preserved ambiguity** (Step 19 Section 3, Step 20 Section 15) — this document's Section 4 contract is written to compose identically with either placement if that ambiguity is ever resolved differently, and does not treat the current recommendation as irreversible. |

---

# 14. Implementation Sequence

Refined from Step 20 Section 16.1 with this document's added detail, reordered where this step's findings justify it (notably: Reading-creation, Section 4.5's named gap, must be sequenced explicitly rather than assumed away).

1. **Dependencies/configuration**: add `bcrypt`, `PyJWT` to `requirements.txt`; add `jwt_secret_key` (and, if a non-default lifetime is wanted, a token-lifetime setting) to `app/core/config.py`'s `Settings`, following the existing `RAIDIAN_`-prefix convention.
2. **`User` model + Migration 1** (Section 3, Section 8.1).
3. **Password/auth service functions** (hash, verify, token issue/decode) — a small, dedicated module (e.g. `app/services/auth.py` or `app/core/security.py`), not folded into the model or the API layer, mirroring this project's existing service/API separation.
4. **`POST /auth/register` / `POST /auth/login`** (Section 5) — a new `app/api/auth.py` router, registered in `app/main.py` alongside `interpretation_router`.
5. **`get_current_user` dependency** (Section 6.1).
6. **Ownership migration** (`ReflectionSession.owner_id`, Migration 2, Section 8.2).
7. **The still-missing Reading/ReflectionSession-creation path** (Section 4.5) — **explicitly surfaced here as a prerequisite this sequence cannot skip**: `get_owned_reading` and the route retrofit (steps 8–9) are meaningless for any *newly created* Reading until something authenticated actually creates one with an owner attached. Whether this is an entirely new route (Reading creation has never been exposed via any API in this project's history) or an extension of an existing internal helper is not designed here — named as a real, load-bearing gap in the sequence, not assumed solved by steps 1–6 alone.
8. **`get_owned_reading` dependency** (Section 6.2).
9. **API retrofit** of the four existing routes (Section 7).
10. **Backend security/ownership tests** (Section 10.1–10.6).
11. **Full regression validation** (Section 10.7 — the existing 277-test suite, plus everything added in step 10).
12. **Frontend integration** (Section 11) — deliberately last, consistent with this project's own established practice of a working, tested backend preceding any frontend build-out (Steps 1–18's entire history has followed this order).
13. **Save Reading API / Reading History API** (`SAVE_READING_DESIGN.md`, `READING_HISTORY_OWNERSHIP_DESIGN.md`) — deferred beyond even this sequence, exactly as Step 20 Section 16.1 already concluded; restated here only for completeness, not re-designed.

**No step above is authorized by this document.**

---

# 15. Stop Conditions

Conditions that would require stopping implementation rather than guessing — evaluated against this document's own findings, not hypothetically.

1. **Unresolved authentication mechanism choice — CURRENTLY BLOCKING.** Step 20 Section 4.3 recommended app-managed JWT but explicitly did not select it, and this document (Section 13) confirms nothing has changed that would allow silently treating it as decided. **This is the one active stop condition this audit found.** Sections 3, 5, 6, 7, 8, 9, 10 of this document are all written *as if* that decision resolves in favor of Option A (per Step 20's recommendation) — if it instead resolves toward OIDC, those sections require rework, not adjustment.
2. **Ownership relationship requiring an unapproved semantic change** — **not triggered.** Section 4.1 confirms `ReflectionSession` supports the addition cleanly, with no structural obstacle and no reinterpretation of its existing meaning required.
3. **Existing API behavior conflicting with the approved architecture** — **not triggered.** Section 7's retrofit is purely additive (a new dependency swapped in for an existing one at the same call sites); no existing successful-path behavior changes for an authenticated owner.
4. **A migration requiring a data backfill not covered by the design** — **not triggered.** Section 4.3/8.2 confirm no backfill is needed given the repository's current, verified absence of persistent data.
5. **Frontend/backend contract conflict** — **not triggered, but not yet exercisable either**: no frontend contract exists yet to conflict with (Section 11); this is a non-issue only because there is nothing to conflict against, not because compatibility was verified.
6. **A security requirement that cannot be satisfied by the proposed mechanism** — **not triggered.** Every requirement in Section 9 is satisfiable by Option A (app-managed JWT) using only well-established, small dependencies (Section 12); nothing in this repository's constraints (SQLite/PostgreSQL dual support, FastAPI's dependency-injection model, the existing test-fixture conventions) conflicts with any of them.

**Net finding: exactly one stop condition is active (#1), and it is the same one Step 20 already flagged — this document narrows what implementation would look like once it clears, without finding any new blocker of its own.**

---

# 16. Final Readiness Assessment

**Conditionally ready.** If Section 15's stop condition (#1, the JWT-vs-OIDC product/governance decision) resolves in favor of Step 20's recommendation, this document finds the resulting implementation **fully specifiable** with no invented placeholder, no unresolved schema question, and no conflict with any already-approved lifecycle, orchestration, or API behavior — Sections 3–10 and 14 constitute a implementation-ready contract an engineer could follow directly. If that decision instead resolves toward OIDC, Sections 5–10 (everything downstream of the authentication mechanism itself) would need to be redesigned against that different mechanism — this document does not attempt to hedge by designing both in parallel, since Step 20 Section 4.2's own comparison already shows the two are not minor variations of one design but materially different account-model and token-handling shapes.

---

## Related Documents

- `AUTHENTICATION_OWNERSHIP_DESIGN.md` (Step 20) — the architecture this document operationalizes into field/route/migration-level detail without reopening any of its recommendations.
- `READING_HISTORY_OWNERSHIP_DESIGN.md` (Step 19) — the original ownership-placement audit and the preserved `ReflectionSession`-semantics ambiguity this document's Section 13 explicitly does not resolve.
- `SAVE_READING_DESIGN.md`, `READING_LIFECYCLE_DESIGN.md`, `READING_DRAW_LIFECYCLE_IMPLEMENTATION_DESIGN.md` — the already-approved lifecycle this document confirms (Section 6.3, Section 15 item 3) needs no change.
- `INTERPRETATION_API_DESIGN.md` — the original `_get_reading_or_404` insertion point this document's Section 7 retrofits directly.
- `PRODUCT_DECISIONS.md` — the "name the dependency, recommend the smallest compliant path, leave the final call explicit" pattern this document's Section 13 applies identically to the authentication-mechanism decision.
- `docs/PRINCIPLES.md` — "Privacy By Design," the governing citation for Section 5.2's login-enumeration design and Section 6's 404-based ownership check.
- `docs/DECISIONS.md` (ADR-0003, ADR-0004, ADR-0006), `docs/ROADMAP.md`, `docs/NAMING_CONVENTIONS.md` — the governance stack re-checked, not re-derived, in Section 2.
- `app/models/reflection_session.py`, `app/models/reading.py`, `app/db/base.py`, `app/db/session.py`, `app/core/config.py`, `app/api/interpretation.py`, `app/services/reading_orchestration.py`, `backend/requirements.txt`, `backend/alembic/versions/74ffb042dc2d_add_interpretation_sequence_column.py`, `tests/conftest.py`, `tests/factories.py`, `tests/test_api_interpretation.py`, `frontend/` — the actual, current code, configuration, and test infrastructure every finding and contract in this document was checked directly against.
