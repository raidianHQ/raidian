# Raidian Wise — Interpretation API Design (Step 10)

# Document Information

Version: 1.0 (Draft for Review — Not Yet Approved)
Status: Proposed — Design Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Defines the HTTP API contract for exposing a completed Reading's deterministic Interpretation and Narrative — triggering interpretation, retrieving the current interpretation, retrieving interpretation history, and retrieving the current narrative — as a thin transport layer strictly downstream of `app/services/reading_orchestration.py` (Step 9, baseline `9708878`). This document does not implement any route, schema, or middleware.

Audience:
Software engineers and AI development agents who will implement this API (a future step, not this one), and anyone auditing what API/auth infrastructure this project actually has versus what this design assumes or defers.

Authority:
Concretizes `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 9 (API Sketch) and `docs/NAMING_CONVENTIONS.md`'s API-route rules against the actual, current implementation (`app/services/reading_orchestration.py`, `app/schemas/interpretive_model.py`, `app/schemas/narrative_model.py`) and the actual, current absence of any API or auth layer. Does not override `INTERPRETATION_ENGINE_DESIGN.md`, `INTERPRETATION_RULES_DESIGN.md`, `NARRATIVE_LAYER_DESIGN.md`, or `READING_INTEGRATION_DESIGN.md` — every decision already made in those documents is treated as settled and is not revisited here.

---

# 0. Scope

This document defines **Step 10 only**: the API contract for exposing interpretation and narrative data. It does **not**:

- Implement any route, Pydantic request/response class, or FastAPI dependency.
- Design authentication or authorization mechanisms — it documents that neither exists and states what would need to be built (Sections 4, 5).
- Design general Reading CRUD or Card Draw entry routes (`POST /readings`, `PATCH /readings/{id}`, `POST /readings/{id}/draws`, digital draw, save) — these remain `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 9's sketch, unbuilt, and out of scope here; this document only concretizes the four interpretation/narrative-specific endpoints the task requests.
- Add LLM/AI behavior, frontend/UI, new interpretation rules, or activate any deferred rule (`INTERPRETATION_RULES_DESIGN.md` Section 12.3, unchanged).
- Modify `InterpretiveModel`, `NarrativeModel`, or persist `NarrativeModel` (`READING_INTEGRATION_DESIGN.md` Section 9's decision stands, unchanged).

---

# 1. Repository Inspection Summary

## 1.1 What already exists

- **`app/services/reading_orchestration.py`** (Step 9): `interpret_reading(session, reading) -> Interpretation` and `get_narrative_for_reading(session, reading) -> NarrativeModel | None`, both taking an already-loaded `Reading` ORM instance, not an ID. `Reading.is_spread_complete` (derived property). `ReadingNotReadyForInterpretationError` (raised before the engine is ever invoked).
- **`app/schemas/interpretive_model.py`** / **`app/schemas/narrative_model.py`**: `InterpretiveModel` and `NarrativeModel`, both frozen Pydantic models, already fully field-complete and already the exact contracts this API must expose unmodified.
- **`app/db/session.py`**: a `get_db()` FastAPI dependency already exists — `yield`s a `SessionLocal()`, and its `finally` block calls `db.close()`. **It does not commit on success or roll back on exception** — as written today, it only closes the session, which (per SQLAlchemy's default session-closing behavior) discards any uncommitted pending transaction rather than persisting it. This function is real, existing code, but is currently **incomplete for a write-performing endpoint's needs** (Section 14 addresses the concrete gap).
- **`app/main.py`**: a bare `FastAPI()` instance with one root route (`GET /`). No router, no dependency, no schema is wired into it.

## 1.2 What does not exist at all — confirmed by direct repository inspection, not assumed

- **No `app/api/` package** (confirmed by directory search, unchanged since `READING_INTEGRATION_DESIGN.md` Section 1.2's identical finding).
- **`get_db()` has zero callers anywhere in the codebase** (confirmed by a full-repository grep) — it is unused, unwired code, not a proven-working pattern.
- **No authentication of any kind.** No user model, no session/token/cookie handling, no login endpoint, no password or identity storage anywhere in `app/models/` or `app/`.
- **No authorization or ownership concept.** `ReflectionSession` (the parent of every `Reading`, one-to-one) is, by its own docstring, deliberately minimal: "identity and timestamps only." **It has no `user_id` field, and neither does `Reading`.** There is currently no database-level way to answer "which user does this Reading belong to" — confirmed by reading both models directly, not inferred.
- **No platform-wide API error-response convention.** `docs/NAMING_CONVENTIONS.md` specifies route naming (plural nouns) but nothing about error body shape, status-code conventions, or an error envelope.

## 1.3 What the governing docs say about this gap

`docs/ARCHITECTURE.md` names "Authentication Service" as one of the platform's five Core Services (alongside Reflection Engine, Scripture Engine, Journal Engine, Growth Engine) — but, per the same inspection this entire design series has repeated at every step, **naming a service in an architecture document is not the same as it existing**. No ADR in `docs/DECISIONS.md` specifies an authentication mechanism (JWT vs. session cookie vs. OAuth provider), and none is inferable from the current stack (ADR-0004 lists FastAPI/SQLAlchemy/etc. but nothing auth-specific). `docs/NAMING_CONVENTIONS.md` lists `/users` as an example plural-noun route — evidence a user resource is anticipated, not evidence one exists.

**Conclusion, stated plainly per this task's explicit instruction:** authentication and authorization for this API are **missing infrastructure that must be added later**, by a separate, dedicated design effort (likely the actual implementation of the platform's Authentication Service) — not something this document invents a convention for. Sections 4 and 5 state precisely what is missing and what this document assumes as an interim, explicitly-flagged position.

---

# 2. Endpoint Design

Four endpoints, per the task's four requested capabilities. Path prefix `/readings/{reading_id}` follows `docs/NAMING_CONVENTIONS.md`'s plural-noun rule and `RAIDIAN_WISE_ARCHITECTURE_V1.md` Section 9's existing `/readings/{id}/...` sketch — this document adopts that prefix rather than inventing a new one.

| Method | Path | Purpose | Orchestration call |
|---|---|---|---|
| `POST` | `/readings/{reading_id}/interpret` | Trigger interpretation for a completed Reading | `interpret_reading(session, reading)` |
| `GET` | `/readings/{reading_id}/interpretations/current` | Retrieve the current (highest-`sequence`) Interpretation | `get_current_interpretation(session, reading)` *(new, proposed — Section 2.1)* |
| `GET` | `/readings/{reading_id}/interpretations` | Retrieve interpretation history | `list_interpretations(session, reading)` *(new, proposed — Section 2.1)* |
| `GET` | `/readings/{reading_id}/narrative` | Retrieve the current NarrativeModel | `get_narrative_for_reading(session, reading)` |

**Naming rationale:** `/interpretations` (plural) for the trigger and history endpoints, matching `docs/NAMING_CONVENTIONS.md`; `/interpretations/current` (a nested singular alias, a common and well-understood REST pattern — cf. `/me`) rather than inventing a separate singular resource name for "the current one." `/narrative` is deliberately **singular** and has **no** history sub-route — `NarrativeModel` is never persisted (`READING_INTEGRATION_DESIGN.md` Section 9), so unlike interpretations, there is no history concept for it to expose; the naming difference is intentional, not an oversight.

**Explicitly out of scope, not designed here:** a per-interpretation-ID detail fetch (`GET /readings/{reading_id}/interpretations/{interpretation_id}`) is a natural small future addition (e.g. "inspect this specific past interpretation's full content") but was not requested and is not designed in detail — noted only as an obvious extension point.

## 2.1 Two new orchestration functions this design requires — proposed, not implemented

The task's boundary requires the API to never issue its own `Interpretation` queries (Section 3's "must not duplicate orchestration logic" applies here just as much as to write operations) — so this document proposes **two small, read-only additions to `reading_orchestration.py`**, following exactly the same "illustrative signature, not final code" convention every prior design document in this series has used:

```python
# Illustrative signatures -- not implemented by this document.

def get_current_interpretation(session: Session, reading: Reading) -> Interpretation | None:
    """The same highest-sequence lookup get_narrative_for_reading() already
    performs internally, exposed as its own reusable function so the API
    layer never writes this query itself."""
    ...

def list_interpretations(session: Session, reading: Reading) -> list[Interpretation]:
    """All Interpretation rows for `reading`, ordered by sequence
    descending (current first) -- see Section 12 for why this ordering,
    distinct from Reading.interpretations' own ascending relationship
    order (Section 7 of READING_INTEGRATION_DESIGN.md), is chosen
    specifically for this list-endpoint's consumer."""
    ...
```

A natural (not mandated) implementation refinement: `get_narrative_for_reading()` could be rewritten to call `get_current_interpretation()` internally instead of repeating its own query — this document notes the opportunity but does not prescribe it as a requirement.

---

# 3. Request / Response Contracts

## 3.1 Request bodies

**None of the four endpoints take a request body.** `POST /readings/{reading_id}/interpret` triggers interpretation with no parameters beyond the path — matching `interpret_reading()`'s own signature (`session`, `reading` only) and `NARRATIVE_LAYER_DESIGN.md` Section 4's already-established "no tone_profile, no locale parameter" contract for the deterministic layers. There is nothing for a caller to configure.

## 3.2 Response schemas

**`InterpretiveModel` and `NarrativeModel` are returned exactly as-is — never re-shaped, filtered, or wrapped in a way that hides any field.** This is a direct consequence of Section 11 (Provenance/citation exposure) below and of the "must not construct InterpretiveModel/NarrativeModel manually" boundary: the API's job is to serialize what the orchestration layer already produced, not to decide what part of it a caller is allowed to see.

**New response envelope, proposed (not implemented) — `InterpretationSummary`:**

```python
# Illustrative shape, not final code.
class InterpretationSummary(BaseModel):
    id: UUID
    reading_id: UUID
    sequence: int
    engine_version: str
    reference_data_version: str
    created_at: datetime
    interpretive_model: InterpretiveModel   # embedded verbatim, unmodified
```

This wraps `Interpretation`'s own row-level fields (`id`, `sequence`, `created_at` — none of which live inside `InterpretiveModel` itself, since the engine has no concept of its own database row) around the untouched `InterpretiveModel`. Building this wrapper from an already-persisted `Interpretation` row via `InterpretiveModel.model_validate(row.interpretive_model)` is **not** "constructing `InterpretiveModel` manually" in the sense the task's boundary prohibits — that phrase means the API must never *fabricate or hand-assemble interpretation content*; deserializing an already-engine-produced, already-validated JSON blob through the schema's own `model_validate` is the identical, already-proven-safe operation `get_narrative_for_reading()` itself already performs (`READING_INTEGRATION_DESIGN.md` Section 8, "reuses an already-tested round-trip"). This document treats that distinction as settled, not ambiguous.

| Endpoint | Response body | Response model |
|---|---|---|
| `POST /readings/{id}/interpret` | The newly-created interpretation | `InterpretationSummary` (full, including nested `interpretive_model`) |
| `GET /readings/{id}/interpretations/current` | The current interpretation | `InterpretationSummary` (full) |
| `GET /readings/{id}/interpretations` | The full history | `list[InterpretationHistoryEntry]` — see Section 12 for why this is a **lighter** shape than `InterpretationSummary` |
| `GET /readings/{id}/narrative` | The current narrative | `NarrativeModel` (returned directly, no envelope — it already carries `source_engine_version`/`source_reference_data_version`/etc. as its own fields, so wrapping it would only duplicate information) |

---

# 4. Authentication Requirements

**None exist. None are designed here.** Per Section 1.2/1.3's inspection, there is no authentication mechanism anywhere in this codebase to build against, and no ADR specifies one. This document takes the position that:

- Every route sketched in Section 2 **would**, if implemented today exactly as designed, be **fully unauthenticated** — any caller who can reach the API can call any of these four endpoints for any `reading_id`.
- This is **acceptable only as an explicitly-flagged interim state**, consistent with this project's early, pre-launch stage (no real user data, no deployed instance with real Readings) — it is **not** acceptable for any real deployment, and this document says so explicitly rather than silently leaving the gap implicit.
- Designing an authentication mechanism (token format, session handling, login flow) is **out of scope for this document** — it belongs to whoever eventually implements the platform's Authentication Service (`docs/ARCHITECTURE.md`'s Core Services list), a cross-cutting concern affecting every Raidian Wise route, not something specific to interpretation/narrative endpoints that should be invented in isolation here.

---

# 5. Authorization / Resource Ownership Requirements

**Cannot be designed against real infrastructure, because none exists (Section 1.2).** `Reading` has no owning-user reference at all — there is no `user_id` column on `Reading` or `ReflectionSession` to check against. Concretely, this means:

- **This document does not propose adding a `user_id` field now.** Doing so would be exactly the kind of unrequested schema change and invented convention the task's boundaries caution against — ownership modeling is a decision for whoever designs the Authentication Service, informed by how users/accounts actually end up modeled (a decision this document has no basis to make).
- **What this document does state as a hard requirement for whenever authorization is added:** every one of these four endpoints resolves a `reading_id` to a specific `Reading` row: the future authorization check belongs exactly at that resolution point (Section 6's "resolve `reading_id` -> `Reading`, or 404" step) — verify the authenticated caller owns (or is otherwise entitled to) that specific `Reading` before proceeding to any orchestration call. This is named here as the **insertion point** for a future check, not as a designed check itself.
- **Until that exists, this API must not be exposed on any deployment with real user data.** This document is not the place to build a stopgap (e.g., a shared API key) — that would itself be an invented, undocumented convention, exactly what the task says not to assume.

---

# 6. HTTP Status Codes and Error Responses

No platform-wide error-envelope convention exists (Section 1.2), so this document adopts FastAPI's own default `HTTPException` shape (`{"detail": "..."}`) rather than inventing a custom one — the smallest-footprint choice available, and trivially replaceable later if/when a platform-wide convention is established elsewhere.

| Status | When | Applies to |
|---|---|---|
| `200 OK` | Successful `GET` | All three `GET` endpoints |
| `201 Created` | A new `Interpretation` row was created | `POST /interpret` only — every successful call creates a genuinely new resource (Section 13), never a "nothing changed" `200`/`304` |
| `404 Not Found` | `reading_id` does not resolve to an existing `Reading` | All four endpoints |
| `404 Not Found` | The Reading exists but has never been interpreted | `GET .../interpretations/current`, `GET .../narrative` (Section 7) |
| `409 Conflict` | `reading.is_spread_complete` is `False` (`ReadingNotReadyForInterpretationError`) | `POST /interpret` only |
| `500 Internal Server Error` | An unexpected exception from `engine.interpret()`, `assemble_narrative()`, or any other unanticipated failure | Any endpoint |

**Why `409`, not `400` or `422`, for an incomplete spread:** the request itself is syntactically and semantically valid (a real `reading_id`, no body expected) — what's wrong is the **current state of the resource** it targets, which is exactly what `409 Conflict` means. `400 Bad Request` would misleadingly suggest the request itself was malformed; `422 Unprocessable Entity` is conventionally reserved for request-body validation failures, and this endpoint has no body to validate.

---

# 7. Behavior for Each Named Scenario

| Scenario | Endpoint(s) affected | Behavior |
|---|---|---|
| **Reading does not exist** | All four | `404 Not Found` before any orchestration call — the API layer's own `reading_id -> Reading` lookup (Section 3's only permitted direct query) fails first. No orchestration function is ever invoked. |
| **Reading is incomplete** (`is_spread_complete` is `False`) | `POST /interpret` | `409 Conflict`. `ReadingNotReadyForInterpretationError` (already raised by `interpret_reading()`, before the engine is invoked — Step 9's own tested guarantee) is caught by the route handler and translated to `409`. No `Interpretation` row is created; `reading.status` is untouched (already proven at the orchestration level, `test_incomplete_reading_is_rejected_before_the_engine_is_invoked`). |
| **No Interpretation exists yet** | `GET .../interpretations/current`, `GET .../narrative` | `404 Not Found` — `get_current_interpretation()`/`get_narrative_for_reading()` both return `None` for a never-interpreted Reading (the latter already proven, `test_get_narrative_for_reading_returns_none_when_never_interpreted`); the route handler translates `None` to `404`. |
| **No Interpretation exists yet** | `GET .../interpretations` (history) | `200 OK` with an empty list `[]` — a list endpoint returning "no items yet" is not a `404` in ordinary REST practice, unlike a singular "current" resource that genuinely does not exist. |
| **Interpretation fails** (an unexpected exception inside `engine.interpret()`) | `POST /interpret` | `500 Internal Server Error`. Because `interpret_reading()` never commits internally (Step 9), and the exception propagates before `save_interpretation()` is ever reached, no partial `Interpretation` row exists to worry about — the API layer's transaction wrapper (Section 14) rolls back the session on any exception, which in this case has nothing to undo. |
| **NarrativeModel assembly fails** (an unexpected exception inside `assemble_narrative()`) | `GET .../narrative` | `500 Internal Server Error`. Already proven at the orchestration level that this cannot affect an already-persisted `Interpretation` (`test_narrative_assembly_failure_does_not_alter_the_persisted_interpretation`) — and since this is a `GET` (read-only) request, there is nothing for the API's transaction wrapper to roll back in the first place; the rollback-on-exception behavior is safe here precisely because it is a no-op. |

---

# 8. Synchronous or Asynchronous?

**Synchronous.** Every deterministic layer this API exposes — `engine.interpret()` (Step 2, no I/O beyond a handful of already-fast reference-data reads) and `assemble_narrative()` (Step 7, proven to touch no database at all) — is local, CPU-bound, and fast: the entire 220-test backend suite, which calls `interpret()` and `assemble_narrative()` dozens of times each, runs in well under a minute total, meaning each individual call is on the order of milliseconds. There is no network call, no AI provider round-trip, and no long-running computation anywhere in this request path. A background job queue, polling endpoint, or webhook mechanism would add real infrastructure and complexity with no corresponding benefit today.

**This conclusion is scoped to the deterministic layers only.** If a future optional AI-assisted wording pass (`NARRATIVE_LAYER_DESIGN.md` Section 13's `[A']`, explicitly not designed here) is ever built, it would call the Reflection Engine over a network — a genuinely slow, potentially-failing operation that **might** justify async handling. That is a separate future design question for whoever builds `[A']`, not something this document decides or needs to anticipate structurally (the endpoints designed here would be unaffected either way, since `[A']` output, if it ever exists, would be a different, not-yet-designed response shape, not a modification to `GET .../narrative` as specified here).

---

# 9. Does the API Expose Raw `InterpretiveModel`, `NarrativeModel`, or Both?

**Both, via separate endpoints — never merged into one combined response.** `NARRATIVE_LAYER_DESIGN.md` Section 3 deliberately separates the deterministic `InterpretiveModel` (structured evidence + conclusions) from the `NarrativeModel` (assembled prose sections) as two different consumer-facing artifacts, each independently useful (a future custom UI or Explainability panel wants the former; rendered narrative text wants the latter) — collapsing them into a single "reading detail" response would blur a boundary this project has deliberately maintained since Step 6, purely for API-layer convenience. A future convenience aggregate endpoint (e.g. a `GET /readings/{id}` that bundles evidence + current interpretation + current narrative for a single frontend page load) is a plausible later addition, but would simply **compose** the same underlying calls this document already defines — it would add no new orchestration logic, and is not designed in detail here.

---

# 10. Version Fields That Must Be Exposed

Already present, unmodified, on the schemas this API returns verbatim — this section is a checklist confirming none are ever stripped, not a proposal for new fields:

- `InterpretiveModel.schema_version`, `.engine_version`, `.reference_data_version` — already on every `InterpretationSummary.interpretive_model`.
- `NarrativeModel.schema_version`, `.narrative_template_version`, `.source_schema_version`, `.source_engine_version`, `.source_reference_data_version` — already on every `GET .../narrative` response.
- `InterpretationSummary.sequence` and `.created_at` — the row-level provenance fields that live outside `InterpretiveModel` itself (Section 3.2) but are equally necessary for a caller to know *which* interpretation, in what order, it is looking at.

---

# 11. Provenance / Citation Exposure

**Full exposure, always — no filtering, redaction, or "lite" response variant.** Every `Citation` inside every `Explained[T]` field of `InterpretiveModel`, and every `NarrativeStatement.citations` inside `NarrativeModel`, is serialized exactly as stored — this is a direct consequence of Section 3.2's "returned exactly as-is" rule and is required by `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 13 (Explainability): the API is the last hop before a future frontend's "how did Raidian Wise arrive at this?" panel, and citation data that is stripped here can never be reconstructed later from the response alone (the same reasoning `INTERPRETATION_ENGINE_DESIGN.md` Section 4.2 already applied to why citations must be captured at generation time, extended here to why they must not be discarded at serving time).

---

# 12. Interpretation History Semantics and Ordering

**`GET /readings/{id}/interpretations` returns entries newest-first (descending `sequence`) — the current interpretation is always list index `0`.** This is a deliberate API-level choice, decoupled from `Reading.interpretations`' own internal SQLAlchemy relationship ordering (ascending, `READING_INTEGRATION_DESIGN.md` Section 7) — that internal ordering exists for the ORM's own convenience (e.g. `[-1]` meaning "current" inside orchestration code); an API history list is a different consumer with a different natural expectation (most-recent-first is the conventional shape for a "history" view).

**Proposed lighter response shape for this endpoint specifically — `InterpretationHistoryEntry`:**

```python
# Illustrative shape, not final code.
class InterpretationHistoryEntry(BaseModel):
    id: UUID
    sequence: int
    engine_version: str
    reference_data_version: str
    created_at: datetime
    # Deliberately NOT the full nested interpretive_model -- see rationale below.
```

**Rationale for omitting the full `InterpretiveModel` from the list endpoint:** as reinterpretation history accumulates for a Reading (an intentionally unbounded, ever-growing collection per `READING_INTEGRATION_DESIGN.md` Section 6/7 — nothing ever prunes it), a history list returning every past interpretation's *complete* structured content (potentially dozens of cited themes, trajectory steps, etc. each) would grow the response size roughly linearly with reinterpretation count for no benefit a history *list* view actually needs. `GET .../interpretations/current` (and, if ever added, a per-ID detail fetch — Section 2's noted extension point) remain the place to retrieve full content. This is a considered API-shape decision, not a data-loss concern: nothing is deleted or degraded — the full `InterpretiveModel` for any historical row remains fully retrievable, just not by this particular list endpoint.

---

# 13. Idempotency / Reinterpretation Behavior

**Not idempotent, by design — re-affirms `READING_INTEGRATION_DESIGN.md` Section 11 (Resolved Q3) rather than re-deciding it.** Every `POST /interpret` call creates a genuinely new `Interpretation` row and returns `201 Created`, even if called twice in a row against unchanged evidence — there is no request-level deduplication, no `If-None-Match`/conditional-request handling, and no "nothing changed, here's the same resource" `200` response. This is not an oversight this document is introducing; it is the same explicit, already-approved non-goal `READING_INTEGRATION_DESIGN.md` established, restated here only because the task asks this document to address it directly at the API layer too.

---

# 14. Transaction Boundaries Between the API and Orchestration Service

This is the one place this document identifies a **concrete, existing code gap**, not just an unbuilt future piece: `app/db/session.py`'s `get_db()` (Section 1.1) already exists but does not commit on success. Per `READING_INTEGRATION_DESIGN.md` Section 14, `interpret_reading()` and `save_interpretation()` never commit internally — commit is always the caller's responsibility. **The API layer is that caller**, and `get_db()` as currently written does not fulfill that responsibility.

**Proposed (not implemented) fix, illustrative only:**

```python
# Illustrative revision to app/db/session.py's get_db() -- not implemented
# by this document.
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
```

This is the standard FastAPI + SQLAlchemy request-scoped-session pattern: the route handler calls into `reading_orchestration` (which only ever flushes), and the dependency itself commits once the handler returns successfully, or rolls back if anything — the handler's own logic, or a `404`/`409` translation, or a genuine unexpected exception — raises. **Every `GET` endpoint's request also flows through this same commit-on-success path**, but since none of them writes anything (Section 6/7's "narrative failure has nothing to roll back" note applies equally to interpretation retrieval), the `commit()` call on those paths is a harmless no-op, not a risk.

---

# 15. OpenAPI Documentation Expectations

Not implemented here, but expected of whoever builds these routes, since FastAPI generates OpenAPI/Swagger directly from route decorators and Pydantic response models:

- Every route needs an explicit `response_model` set to the real schema (`InterpretationSummary`, `list[InterpretationHistoryEntry]`, `NarrativeModel`) — never a bare `dict` or untyped return, so the generated schema is accurate enough for a future frontend to codegen against.
- Every route needs a `summary` and a `description` that references the specific section of this document (or `READING_INTEGRATION_DESIGN.md`) it implements, continuing this project's established practice of keeping code traceable back to its governing design document.
- Every non-`200`/`201` status this document specifies (`404`, `409`, `500`) should be declared via FastAPI's `responses={...}` parameter so it appears in the generated OpenAPI spec, not left implicit.
- No authentication scheme can be documented in the OpenAPI spec (`securitySchemes`) until Section 4's missing infrastructure exists — this is expected to be a visible gap in the generated spec for now, not something to paper over with a placeholder.

---

# 16. Architectural Boundaries — Restated and Checked Against This Design

Every rule the task stated was checked against the design above, not just repeated:

- **No interpretation or narrative rules implemented here.** Every endpoint's entire content comes from `engine.interpret()` / `assemble_narrative()`, called unmodified. Confirmed: this document adds zero new business logic — Section 2.1's two new functions are pure lookups (an `ORDER BY`/`WHERE`), not rule evaluation.
- **No reference-data access.** No endpoint or proposed function reads `Card`, `Spread`, `CardCorrespondence`, or `theme_vocabulary` — every response is built entirely from `Reading` (the path-resolved resource), `Interpretation` rows, and the orchestration layer's own already-existing calls.
- **No manual construction of `InterpretiveModel`/`NarrativeModel`.** Section 3.2 draws the precise line: deserializing an already-engine-produced JSON blob via `model_validate` (proven safe, reused from Step 8/9) is not "construction" in the prohibited sense; nothing in this design fabricates a field value.
- **No duplicated orchestration logic.** Confirmed via Section 2.1: rather than letting the API write its own `Interpretation` queries, this document proposes moving that logic *into* `reading_orchestration.py`, preserving the single-source-of-truth property Step 9 established.
- **`API → Reading Orchestration → Engine/Persistence` and `API → Reading Orchestration → Narrative Assembly` — never bypassed.** Every row in Section 2's table names an orchestration-layer call as its only path to data; no endpoint is designed to import `app/services/interpretation/` or `app/services/narrative/` directly.
- **No LLM/AI, no frontend/UI, no new/activated interpretation rules, no `NarrativeModel` persistence** — none appear anywhere in this document; Section 9 explicitly re-affirms the no-persistence decision rather than silently assuming it.

---

# 17. Unresolved Questions

Recorded, not decided — each requires infrastructure or a decision this document has no basis to make on its own authority:

**Q1 — What authentication mechanism will Raidian Wise actually use?** (Section 4) Entirely unspecified anywhere in the repository. Blocks real deployment of every route this document designs.

**Q2 — How will resource ownership be modeled once authentication exists** (a `user_id` on `ReflectionSession`? A separate membership/grant table?) **and should reinterpreting or viewing a Reading ever be shareable beyond its original owner?** (Section 5) Not answerable without Q1 being resolved first.

**Q3 — Should the `InterpretationHistoryEntry` list ever gain pagination?** (Section 12) Not designed here — plausible if reinterpretation history grows large for a single Reading in practice, but nothing in this project's current scale (a personal reflection app) suggests it is needed yet; recorded as a deferred idea only, matching this series' established discipline of not building ahead of demonstrated need.

**Q4 — Should a per-interpretation-ID detail route be added** (Section 2's noted extension point)? Not requested by this task; recorded as a natural future addition, not decided.

---

## Related Documents

- `READING_INTEGRATION_DESIGN.md` — the orchestration layer (`interpret_reading`, `get_narrative_for_reading`, the `sequence`-based "current" rule, the transition-aware status logic, the transaction-boundary/caller-commits convention) this API sits strictly downstream of and does not redesign.
- `NARRATIVE_LAYER_DESIGN.md` — Section 3's `[A]`/`[B]`/`[A']` split, referenced in Section 8/9 above for why this API stays synchronous and keeps `InterpretiveModel`/`NarrativeModel` as separate response shapes.
- `INTERPRETATION_ENGINE_DESIGN.md` — Section 4.2/13 (Explainability), the citation-preservation requirement Section 11 above enforces at the API boundary.
- `RAIDIAN_WISE_ARCHITECTURE_V1.md` — Section 9 (API Sketch), the `/readings/{id}/interpret` naming this document adopts, and Section 2's still-unbuilt `reading_service.py`/`draw_service.py` sketch this document does not re-design.
- `docs/ARCHITECTURE.md` — the Authentication Service named as a Core Service but not yet built, the basis for Section 4/5's "missing infrastructure" conclusion.
- `docs/NAMING_CONVENTIONS.md` — the plural-noun API route rule this document's path design follows.
- `app/services/reading_orchestration.py`, `app/db/session.py` — the actual, current code this document integrates with and, in `get_db()`'s case, identifies a concrete gap in (Section 14).
