# Raidian Wise — Product Decision Resolution (Step 14)

# Document Information

Version: 1.0 (Recommended Decisions — Pending Formal Governance Sign-off)
Status: Proposed Resolution — Design Only, No Implementation
Owner: RaidianHQ
Last Updated: September 2026

Purpose:
Resolves the six product-level decisions `READING_LIFECYCLE_DESIGN.md` (Step 13, Section 16) identified as open, at baseline `6757f50`. For each, this document names the current documented requirement, the current implementation, the precise conflict, the options considered, a clearly labeled recommendation, and that recommendation's consequences — reasoned from `RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, `RAIDIAN_WISE_ARCHITECTURE_V1.md`, and `docs/DECISIONS.md`'s governance hierarchy, not from what is easiest to keep unchanged in the existing code. Where a recommendation would leave the Product Spec's own text inaccurate, this document says so explicitly and names the follow-on governance action (an ADR or a Product Spec revision) required to make the recommendation binding — this document's own authority stops at *recommending*, per `docs/DECISIONS.md` ADR-0006's governance hierarchy (Architecture and Decisions rank above a Documentation-series design note; nothing here amends either).

Audience:
Whoever holds product/governance authority over Raidian Wise (to accept, amend, or reject each recommendation) and the engineers who will implement whatever is accepted.

Authority:
This document does not outrank `RAIDIAN_WISE_PRODUCT_SPEC_V1.md`, `docs/ARCHITECTURE.md`, or `docs/DECISIONS.md` — per ADR-0006's governance hierarchy (Project Charter → Vision → Principles → Architecture → Decisions → Agents → Roadmap), a Documentation-series design note has no formal standing to override any of them. Every recommendation below is exactly that — a recommendation — and Section 7's Authoritative Decision Summary is offered as a *convenience reference* for implementation, not a substitute for the actual governance action (an ADR, or a Product Spec revision) each recommendation implies.

---

# 0. Scope

Resolves exactly the six questions `READING_LIFECYCLE_DESIGN.md` Section 16 (Q1–Q5) and Section 11/Q6-equivalent raised. Does not:

- Modify any code, schema, migration, reference data, or API route.
- Implement any AI/LLM logic or Reflection Engine integration — Q1 recommends *when* that work should happen, not how to build it.
- Change any interpretation rule.
- Make any frontend change.
- Amend `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` or any other governance document directly — Section 8 names which document(s) a follow-up governance action should amend, but does not edit them here.

---

# 1. Q1 — Narrative MVP: Deterministic, or AI/Reflection Engine?

**Current documented requirement:**
`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 3.3 states, as a deliberate, reasoned architectural decision: "The Narrative Generation layer is the one component permitted to reach an AI provider, and it must do so exclusively through the existing Reflection Engine service (per ADR-0005)... Its system prompt... must constrain it to *rephrase, not reconsider* the model." Section 5, step 11 repeats this as an MVP flow step. Section 20, Phase 4 defines Narrative Generation's entire build plan as authoring Reflection-Engine prompt files and wiring through ADR-0005 — no alternate, deterministic-only phase is described anywhere in the original spec. `docs/DECISIONS.md` ADR-0005 independently mandates: "Artificial intelligence shall be accessed exclusively through the Reflection Engine... components should never communicate directly with AI providers." `docs/ARCHITECTURE.md` and `docs/ROADMAP.md` both list the Reflection Engine as an M1 ("Core Architecture") platform milestone, alongside Authentication — a whole-platform, cross-cutting foundation, not a Raidian-Wise-specific piece.

**Current implementation:**
`app/services/narrative/` (Steps 6–7) is a fully deterministic, template-based prose assembler. It calls no AI provider, contains no Reflection Engine reference, and the four prompt files Section 3.3 names (`prompts/system/reflection_engine.md`, `prompts/system/safety.md`, `prompts/system/tone.md`, `prompts/interpretation.md`) remain exactly as empty (0 lines each) as when the Product Spec was written. Separately and decisively: **no Reflection Engine implementation exists anywhere in this codebase at all** — not a stub, not a partial module, nothing (confirmed by repository-wide search). ADR-0005's mandated sole AI-access path is not merely unused by Narrative Generation specifically; it does not exist for *any* component to use yet.

**Conflict/gap:**
The Product Spec's literal MVP requirement (AI-authored narrative via the Reflection Engine) cannot currently be satisfied by *any* implementation choice, compliant or not — building a one-off AI call for Raidian Wise's narrative alone would itself violate ADR-0005 ("exclusively through the Reflection Engine," not a per-feature AI integration). The requirement has a hard, unmet, platform-level dependency. `NARRATIVE_LAYER_DESIGN.md`'s `[A]`/`[B]`/`[A']` split already anticipated this gap and built `[A]` (deterministic) as a complete, independently-servable narrative, with `[A']` (the actual, spec-described AI rephrase) named as "optional... never a hard dependency" — but that framing was written by an engineering design document, not ratified as a Product Spec amendment.

**Options considered:**
1. **Treat AI/Reflection-Engine narrative as a hard MVP blocker.** Correct to the Product Spec's literal text, but would mean Raidian Wise cannot ship *any* narrative output until an entire separate M1 platform milestone (Reflection Engine) is built by a different, larger initiative — an indefinite, externally-gated delay with no Raidian-Wise-specific work that could shorten it.
2. **Treat the deterministic layer as silently sufficient, no amendment needed.** This is the option the task explicitly warns against choosing "based on implementation convenience" — it would let already-written code quietly redefine what the Product Spec requires, with no governance record of the change.
3. **Treat the deterministic layer as an explicit, temporary MVP substitute, formally recorded as such, with the AI/Reflection-Engine pass reclassified as a scheduled follow-on once its platform dependency ships.**

**Recommended decision: Option 3.** The Product Spec's AI/Reflection-Engine requirement is **not overridden or dismissed** — it is reasoned, principled (Section 4's "Humility over certainty" and Section 13's "Explainability" both plausibly motivated the "rephrase, not reconsider" constraint, not a stylistic afterthought), and independently reinforced by a formal ADR. Recommending against it outright would be exactly the "assume the implementation is authoritative" move this task prohibits. Instead: the deterministic `[A]` layer is recommended as the **MVP narrative for initial release only**, explicitly labeled interim, on the grounds that (a) it is the only option actually buildable today, since its mandated alternative's dependency does not exist, and (b) it independently satisfies the product's transparency/traceability principles at least as well as an AI rephrase would (every sentence is directly citation-backed; an AI rephrase, even a constrained one, introduces a step whose fidelity to the underlying evidence would need its own adversarial test suite — Section 20 Phase 4's own requirement — that does not exist yet either). The AI/Reflection-Engine pass (`[A']`) is recommended to remain the **long-term, still-required target**, formally gated on the Reflection Engine (M1) shipping, not abandoned.

**Consequences:**
- The Product Spec's Section 3.3/5(step 11)/20(Phase 4) text remains, as written, **inaccurate to what will actually ship as "MVP"** unless formally amended. This document recommends — but cannot itself perform — a Product Spec revision or a new ADR recording: "Narrative Generation's MVP implementation is the deterministic Narrative Layer (`[A]`); an AI/Reflection-Engine rephrase pass (`[A']`) remains required for the originally-specified experience and is scheduled once the Reflection Engine (M1) exists, not deferred indefinitely or silently dropped."
- Until that governance action happens, this document's recommendation has no formal standing over the Product Spec's plain text — anyone reading only the Product Spec would still be told AI narrative is an MVP requirement.

**Implementation impact:**
None required by this document itself. If the recommendation is accepted, the only concrete follow-on work is the governance action above (an ADR or Product Spec revision) — no code change follows from Q1 alone. `[A']`'s eventual design remains explicitly out of scope here, as it was in `NARRATIVE_LAYER_DESIGN.md`.

**Deferred items:**
- Designing `[A']` itself (prompt content, Reflection Engine call shape, adversarial testing) — blocked on the Reflection Engine existing at all.
- Deciding whether `[A']`, once built, replaces `[A]`'s output entirely or is offered as a user-toggleable enhancement alongside it — not asked by this task, not decided here.

---

# 2. Q2 — `SPREAD_COMPLETE`: Authoritative Assignment Mechanism

**Current documented requirement:**
`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 5, steps 8–9: "User reviews the completed spread (all positions filled...) before proceeding. User explicitly triggers Interpret My Reading." Section 6 describes "Spread Review" as a screen the user reaches once positions are filled, where "edit-in-place still available here" — it is described as a review screen, not as a distinct status-locking gesture. Section 17: "Original Reading Evidence (immutable once the spread is complete): question, layout, positions, cards, orientation, draw order, draw method, deck."

**Current implementation:**
`ReadingStatus.SPREAD_COMPLETE` exists but is never assigned by any production code (`READING_LIFECYCLE_DESIGN.md` Section 1.2, re-confirmed here). `Reading.is_spread_complete` (a derived, unstored `@property`) is the only mechanism that actually detects evidence completeness, and it is what gates interpretation — deliberately decoupled from `status` (`READING_INTEGRATION_DESIGN.md` Section 3). Card Draw mutability is currently unrestricted at every status value — nothing in the schema or any service enforces Section 17's "immutable once the spread is complete" at all today.

**Conflict/gap:**
Not a Product-Spec-vs-implementation conflict so much as an unfinished implementation: the Product Spec's framing (evidence completeness is a fact the user reviews, not a distinct gesture they perform) does not, on its own text, require a separate explicit "confirm my spread" action distinct from filling the last position. But nothing today converts that fact into the stored `status` column at all, and Section 17's immutability guarantee has no enforcement mechanism to hang off of.

**Options considered (as named in `READING_LIFECYCLE_DESIGN.md` Section 6):**
1. **Automatic/derived** — a future Reading/Draw Service assigns `status = SPREAD_COMPLETE` the moment `is_spread_complete` first becomes `True`.
2. **Explicit, user/UI-driven** — `status` only advances when the user explicitly confirms/leaves the Spread Review screen.
3. **Leave permanently unused** — treat the derived property as sufficient forever; never assign the stored value at all.

**Recommended decision: Option 1 (automatic/derived), persisted, with an explicit paired consequence for Card Draw mutability.** The Product Spec's own text (Section 5 step 8, Section 6's "Spread Review" description) frames spread completeness as an evidence fact the user is shown, not a separate action they perform — there is no textual basis in the spec for inventing a distinct confirmation gesture (Option 2), and Option 3 leaves Section 17's "immutable once the spread is complete" ungrounded (immutable *when*, exactly, if `status` never says so?). Concretely: **a future Reading/Draw Service, whenever it writes a `CardDraw` that causes `reading.is_spread_complete` to newly become `True` while `status == DRAFTING`, must also set `status = ReadingStatus.SPREAD_COMPLETE` and persist it in the same transaction.** This is the exact transition rule requested by this task ("define the exact transition rule and whether it is persisted"): **automatic, evidence-triggered, and persisted** (not merely computed live at read time — the whole point is to give the stored column a real, reachable meaning).

Paired consequence, recommended as part of the same decision rather than a separate one: **once `status` reaches `SPREAD_COMPLETE` (or later), `CardDraw` rows for that Reading become immutable** — no future Reading/Draw Service should permit adding, editing, or removing a `CardDraw` once this transition has occurred. This directly implements Section 17's "immutable once the spread is complete" (previously true in name only) and removes the "two sources of truth can drift" risk Step 13 raised against Option 1: since the evidence that made `is_spread_complete` true can no longer change once `status` reflects it, the stored value cannot go stale.

**Consequences:**
- `is_spread_complete` (the derived property) and `status == SPREAD_COMPLETE` become, in practice, permanently equivalent facts for any Reading past this transition — but the derived property remains the source of truth the orchestration layer checks (`READING_INTEGRATION_DESIGN.md` Section 3's "not a precondition" decision for `status` itself is **not** reversed by this recommendation — see Implementation impact).
- A Reading created and interpreted before this mechanism exists (i.e., every Reading in the system today) will simply never have passed through a real `SPREAD_COMPLETE` transition — this is a data-migration non-issue, not a correctness problem, since nothing depends on having passed through it retroactively.

**Implementation impact:**
Entirely inside a future Reading/Draw Service (`reading_service.py`, still unbuilt) — the CardDraw-write path, not `reading_orchestration.py`. **`interpret_reading()`'s existing precondition check must not change**: it should keep checking the live `is_spread_complete` property directly, exactly as already implemented and tested (Steps 8–12) — not the stored `status` value — so that a Reading somehow reaching `is_spread_complete == True` without `status` having caught up (a data-migration edge case, or simply every Reading that predates this mechanism) remains interpretable. This recommendation adds a *new* responsibility to a not-yet-built service; it does not ask any existing, tested code to change.

**Deferred items:**
- The actual `reading_service.py` implementation (out of scope — no code changes permitted by this task).
- Whether `CardDraw` mutation should be *entirely* forbidden pre-`SPREAD_COMPLETE` too (today it is unrestricted at `DRAFTING`) — not asked by this task, not decided here; this document only pins down the boundary Section 17 already named (immutable *once* spread-complete), not what happens before it.

---

# 3. Q3 — Meaning of `SAVED`

**Current documented requirement:**
`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 6 is decisive here, in language not previously weighed by `READING_LIFECYCLE_DESIGN.md`: "**Reading History** — list of **saved** Readings, searchable/filterable." (emphasis added to the spec's own wording). This is a stronger signal than a generic "bookmark" framing — it says Reading History, as a screen, shows *only* saved Readings. Section 5 step 13 ("User can save the Reading") and step 14 (what the saved record "preserves") frame saving as the action that makes a Reading a durable, retrievable-later record from the user's point of view.

**Current implementation:**
Every `Interpretation` is already durably persisted the instant it is created, regardless of `status` (Section 1.1's related-table decision, unconditional). `SAVED` is never assigned by any code (Section 1.2). There is no concept anywhere of a Reading being "discarded" or "not kept" — every `Reading` row, saved or not, persists identically in the database once created.

**Conflict/gap:**
Product Spec Section 6 implies saved-vs-not is a meaningful, user-visible partition (only saved Readings appear in history), but the underlying data model no longer has an "unsaved data is at risk of being lost" concept to justify that partition the way it might have when Section 7.5 modeled `interpretive_model`/`narrative` as save-triggered columns on `Reading` itself. The distinction Section 6 wants (saved vs. not, for history-listing purposes) is still meaningful — it has just become a pure *curation/retention* signal rather than a *data-durability* one.

**Options considered (from `READING_LIFECYCLE_DESIGN.md` Section 7):**
1. Pure user-curation bookmark (zero effect on persistence or reinterpretation).
2. Snapshot-pinning action (freezes which Interpretation is "the saved one" — see Q4).
3. Ordering-only terminal marker (no curation meaning beyond lifecycle position).

**Recommended decision: Option 1, sharpened by Section 6's own text into a specific, concrete rule: `SAVED` is the sole gate for whether a Reading appears in Reading History.** Explicitly distinguishing the four things this task asks to separate:
- **Reading lifecycle state:** `SAVED` is a terminal (but not locking — Section 6/Q6) status value on `Reading.status`, assigned only by an explicit, not-yet-built "Save Reading" user action.
- **Interpretation history:** entirely unaffected. `Interpretation` rows accumulate identically whether or not the parent `Reading` is ever saved, and continue accumulating after saving (already implemented, tested — Steps 9/11/12). `SAVED` gates *Reading visibility in history*, not *Interpretation creation or retention*.
- **Narrative generation:** entirely unaffected. Narrative remains always-on-demand, recomputed from the current `Interpretation` regardless of save state (Section 4 below, consistent with Q1).
- **Snapshot/version semantics:** explicitly **none** — see Q4's dedicated resolution.

**Consequences:**
- A Reading that is merely `DRAFTING`/`SPREAD_COMPLETE`/`INTERPRETED` (never saved) is, per this recommendation, correctly excluded from a future "Reading History" list view, even though its data is fully durable in the database — "not in history" and "not persisted" are now different things, and any future frontend/UI copy should not conflate them (e.g., should not warn a user their in-progress Reading will be "lost" if they navigate away — it won't be, it just won't appear in History until saved).
- This creates a mild, worth-naming asymmetry: a Reading can be fully `INTERPRETED`, with real, retrievable content, yet be invisible to the user in the one screen (History) meant to list their past Readings, unless/until they take the separate "Save" action. Whether that is the intended product experience (a deliberate "you must confirm you want to keep this" step) or a UX gap (interpreted-but-unsaved Readings should perhaps also be reachable somehow, e.g. via a distinct "Recent/In Progress" list) is not settled by Section 6's text alone — recorded as a Deferred item below, not decided.

**Implementation impact:**
None from this document directly. Implies a future "Save Reading" API route/service function (not built here) and a future Reading History query that filters on `status == SAVED` (not built here, no frontend exists).

**Deferred items:**
- Whether unsaved-but-interpreted Readings should be reachable through any UI at all before being saved (e.g., a "Recent" list distinct from "History") — not decided; Section 6 only specifies what History itself shows.
- Whether a Reading can be "un-saved" — addressed in Q6, recommended: no.

---

# 4. Q4 — Does Saving Pin a Specific Interpretation?

**Current documented requirement:**
`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 5 step 14: "The saved record preserves: cards, positions, question, orientation, layout, deck, draw method, and interpretation engine version — permanently." Read in isolation, this suggests a single frozen `interpretation_engine_version` (and, implicitly, its accompanying content) as part of "the saved record." Section 17 (Versioning), however, explicitly already anticipates the alternative: "A future 'Reinterpret with current engine' action should be able to overwrite/append a new `interpretive_model` + `narrative` + `interpretation_engine_version`... MVP does not need to build the reinterpretation UI, but the schema must not make it structurally impossible later." Section 17 names *both* "overwrite" and "append" as acceptable readings of its own principle — it does not itself decide between them.

**Current implementation:**
`READING_INTEGRATION_DESIGN.md` Section 5 (already implemented and tested, Steps 9/11/12, and explicitly **not** reopened by this document — it is a settled decision from an earlier, approved step) chose "append": reinterpretation is allowed from every status including `SAVED`, always creates a new `Interpretation` row, and never regresses `status`. "Current interpretation" is always defined as the highest-`sequence` row — a live, moving definition with no pinning mechanism anywhere in the schema.

**Conflict/gap:**
Section 5 step 14's literal, singular "preserves... interpretation engine version" phrasing is in mild tension with a system that can have arbitrarily many `Interpretation` rows, with no field recording which one (if any) corresponds to "the one that was true when the user saved." This is not a contradiction Section 17 itself created (it explicitly left "overwrite vs. append" open) — it is a gap that only becomes visible once append-based history actually exists and accumulates past a single row, which it now does.

**Options considered:**
1. **Yes, pin** — add a mechanism (e.g., a `saved_interpretation_id` column on `Reading`, or an analogous approach) recording which `Interpretation` was current at save time.
2. **No, no pinning** — "current" continues to mean "highest sequence," unconditionally, exactly as already implemented; saving records no interpretation-specific information at all.

**Recommended decision: Option 2 — no pinning.** Reasons, addressing this task's explicit requirement to "document why a saved Reading remains associated with a moving 'current' Interpretation" if the answer is no:
- Section 17 itself treats interpretation as inherently *replaceable* evidence-derived output, not part of the permanent record's evidentiary core (which is explicitly limited to "cards, positions, question, orientation, layout, deck, draw method" — the *evidence* fields, all of which are already correctly immutable/preserved regardless of interpretation history). Section 5 step 14's inclusion of "interpretation engine version" in the same sentence as the evidence fields is the one place the spec blurs this distinction; Section 17's own, more carefully-reasoned framing does not.
- `READING_INTEGRATION_DESIGN.md` Section 5's decision (reinterpretation allowed after `SAVED`, never regressing status) was already made and approved in an earlier step of this exact series; a "yes, pin" answer here would sit awkwardly against it — a user who reinterprets a saved Reading almost certainly wants the *new* interpretation to be what they see next, not a frozen old one silently shown instead while a newer one exists unseen beside it.
- No schema field exists today to record a pin, and this task explicitly forbids schema changes — recommending "yes, pin" here would produce a decision this document cannot itself make actionable, whereas "no pinning" requires zero new code and matches exactly what is already built, tested at three layers (orchestration/API/end-to-end), and never found problematic in Step 12's validation pass.

**What happens when a saved Reading is reinterpreted, stated explicitly:** a new `Interpretation` row is created (as always); `status` remains `SAVED` (as already implemented); the Reading's "current interpretation," wherever displayed (a future Reading Detail view), is simply whichever row now has the highest `sequence` — the newly-created one. No prior "the saved version" concept exists to update or invalidate, because none is recommended to exist.

**Consequences:**
- A saved Reading's displayed content can change after saving, purely as a result of the user choosing to reinterpret it — this is a deliberate, accepted consequence of Option 2, not an oversight. A future frontend should make this legible (e.g., always show which `Interpretation` — by recency, not by `sequence`'s raw value per `READING_WORKFLOW_VALIDATION.md` Section 3.3 — is currently being displayed) rather than implying "saved" means "frozen."

**Implementation impact:**
None. This recommendation asks for no new field, migration, or service change — it is a decision to keep the current, already-implemented behavior as the intended, permanent design, not merely its provisional default.

**Deferred items:**
- If future product feedback shows users expect "saved" to mean "frozen," a pinning mechanism (Option 1) remains buildable later without breaking anything recommended here — recorded as a possible future revisit, not designed now.

---

# 5. Q5 — Should `POST /interpret` Return Narrative Too?

**Current documented requirement:**
`RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 5 steps 10–11 describe interpretation and narrative generation as one continuous flow: "The Interpretation Engine analyzes the Reading and produces... the Interpretive Model. The Narrative Generation layer converts the Interpretive Model into natural-language prose." No API shape is specified by the Product Spec at this level of detail — this is read as a *user-experience* continuity requirement, not a literal single-HTTP-call requirement.

**Current implementation:**
`POST /readings/{id}/interpret` returns `InterpretationSummary` only (no narrative field). A separate `GET /readings/{id}/narrative` call is always required to obtain prose. `INTERPRETATION_API_DESIGN.md` Section 9 already reasons through why: `InterpretiveModel` and `NarrativeModel` are "two different consumer-facing artifacts, each independently useful," and merging them would blur a boundary deliberately maintained since Step 6.

**Conflict/gap:**
None at the requirement level — the Product Spec describes a user-experience sequence, not an HTTP contract, so a two-call implementation satisfies it exactly as well as a one-call implementation would, provided the frontend chains the calls without a visible gap.

**Options considered:**
1. Keep separate (current behavior) — frontend issues `POST /interpret` then immediately `GET /narrative`.
2. Merge — extend `InterpretationSummary` to embed the current `NarrativeModel`.

**Recommended decision: Option 1 — keep separate, unchanged, consistent with Q1.** Two reinforcing reasons: first, `INTERPRETATION_API_DESIGN.md` Section 9's existing rationale (independent artifacts, independent consumers — a future Explainability panel wants the raw model, rendered UI wants narrative) stands on its own regardless of Q1's outcome. Second, and more specifically tied to "keep the decision consistent with the narrative MVP decision" as this task requires: Q1 recommends today's deterministic narrative is an **interim** MVP substitute for an eventual AI/Reflection-Engine pass (`[A']`). An AI-backed narrative call is far more likely to eventually need asynchronous handling (a real network round-trip to an AI provider, per `INTERPRETATION_API_DESIGN.md` Section 8's own reasoning about what *would* justify async handling) than today's sub-millisecond deterministic assembly does. Keeping narrative retrieval on its own endpoint, today, costs nothing and means that whenever `[A']` eventually lands, only `GET /readings/{id}/narrative`'s internals (and possibly its response latency characteristics) need to change — `POST /interpret`'s contract is entirely insulated from that future change. Merging them now would create exactly the coupling that later change would have to undo.

**Consequences:**
A frontend must always make two sequential calls to go from "user clicks Interpret" to "narrative is displayed." This is a minor, already-anticipated implementation detail (`READING_LIFECYCLE_DESIGN.md` Section 13's call sequence already documents exactly this), not a new cost introduced by this recommendation.

**Implementation impact:**
None — this recommendation preserves the current API contract exactly as implemented and approved in Step 11.

**Deferred items:**
None beyond Q1's own (whether `[A']`, once built, changes narrative's performance characteristics enough to warrant async handling — a question for whoever eventually designs `[A']`, not this document).

---

# 6. Q6 — Lifecycle Reversibility: the Complete Transition Rule Set

Synthesizing Q2–Q4's resolutions into one explicit rule set, as this task requires:

| Transition | Allowed? | Trigger | Direction |
|---|---|---|---|
| *(none)* → `DRAFTING` | Yes | Reading created | Forward (initial) |
| `DRAFTING` → `SPREAD_COMPLETE` | Yes | Automatic/derived, the moment `is_spread_complete` first becomes `True` (Q2) | Forward only |
| `SPREAD_COMPLETE` → `INTERPRETED` | Yes | Explicit user action, `POST /interpret` (unchanged, already implemented) | Forward only |
| `DRAFTING` → `INTERPRETED` (bypassing a real `SPREAD_COMPLETE` transition) | Yes, permitted as a defensive allowance | Same `POST /interpret` call, gated on the live `is_spread_complete` property, not on `status` (unchanged, already implemented — Q2's recommendation does not remove this) | Forward only |
| `INTERPRETED` → `INTERPRETED` | Yes | Reinterpretation (unchanged, already implemented, idempotent on `status`) | N/A (no status change) |
| `INTERPRETED` → `SAVED` | Yes | Explicit user action, "Save Reading" (not yet implemented — Q3) | Forward only |
| `SAVED` → `SAVED` | Yes | Reinterpretation (unchanged, already implemented and tested — Q4 confirms no pinning changes this) | N/A (no status change) |
| `SAVED` → any earlier value | **No** | No such action recommended | N/A |
| `SPREAD_COMPLETE`/`INTERPRETED`/`SAVED` → `DRAFTING` | **No** | No such action recommended; `CardDraw` becomes immutable once `SPREAD_COMPLETE` is reached (Q2) | N/A |

**Explicit statement, as this task requires: no transition may move backward, anywhere in this lifecycle.** The recommended rationale, stated once here rather than repeated per-row: Product Spec Section 17 already frames evidence as immutable "once the spread is complete," and this document's Q2 recommendation gives that principle real teeth (Card Draw immutability keyed to a real `status` transition). A product that wants "start over" is recommended to mean "create a new Reading," not "roll an existing one backward" — consistent with Section 17's own immutability principle applied consistently, not just to Card Draw specifically. No prior design document in this series has ever proposed a backward transition, and this document, having now looked for a textual basis for one in the Product Spec and finding none, recommends against inventing one.

---

# 7. Authoritative Decision Summary

For use as the source-of-truth reference for subsequent implementation steps, pending the governance actions Section 8 names:

| # | Decision | Recommended Answer | New Code Required? |
|---|---|---|---|
| Q1 | Narrative MVP | Deterministic (`[A]`) is the **interim** MVP narrative; AI/Reflection-Engine (`[A']`) remains the **long-term required** target, gated on the Reflection Engine (M1) shipping | No (governance action only — Section 8) |
| Q2 | `SPREAD_COMPLETE` mechanism | Automatic/derived: assigned by a future Reading/Draw Service the instant `is_spread_complete` first becomes `True`; persisted (stored, not just live-computed); pairs with Card Draw becoming immutable from that point on | Yes — future Reading/Draw Service only; `reading_orchestration.py`'s existing precondition logic is unchanged |
| Q3 | Meaning of `SAVED` | Pure user-curation/retention marker; the sole gate for Reading History visibility; no effect on Interpretation creation/history or Narrative generation | Yes — future "Save Reading" route/service and History query only |
| Q4 | Saved Interpretation pinning | No pinning. "Current interpretation" always means highest-`sequence`, regardless of save state — unchanged from what is already implemented and tested | None |
| Q5 | `POST /interpret` response shape | Keep Interpretation-only; narrative stays a separate `GET` call — unchanged from what is already implemented | None |
| Q6 | Reversibility | No transition ever moves backward; Card Draw becomes immutable once `SPREAD_COMPLETE` is reached | Covered by Q2's implementation impact |

**Net implementation impact of this entire document: zero code changes to anything that exists today.** Every "Yes" in the table above names work inside a component that does not exist yet (`reading_service.py`/Reading-Draw Service, a "Save Reading" route) — nothing recommended here asks any already-implemented, already-tested code (`engine.py`, `assemble_narrative()`, `reading_orchestration.py`, `app/api/interpretation.py`, `persistence.py`) to change.

---

# 8. Required Follow-On Governance Actions

Recommended, not performed by this document (per ADR-0006, this document has no authority to enact them):

1. **An ADR or a `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` revision recording Q1's staged narrative decision** — the single most consequential item here, since it is the one place this document's recommendation would otherwise leave the Product Spec's plain text actively inaccurate about what MVP delivers.
2. **A `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` Section 7.5 correction** (already flagged, unresolved, by `READING_INTEGRATION_DESIGN.md` Section 1.3 and `READING_LIFECYCLE_DESIGN.md` Section 15.1) — this document adds no new finding here but notes it remains outstanding and is a natural companion edit to action 1.
3. No ADR or spec change is judged necessary for Q2–Q6 — each is recommended as a clarification/extension of already-consistent principles (Section 17's immutability language, Section 6's History framing) rather than a correction of a stated requirement, so ordinary design-doc-then-implementation practice (as this exact series has followed for Steps 3, 6, 8, 10) is recommended to suffice when a future "Reading/Draw Service" or "Save Reading" design step is undertaken.

---

## Related Documents

- `RAIDIAN_WISE_PRODUCT_SPEC_V1.md` — Sections 3.3, 4, 5, 6, 7.5, 13, 17, 18, 20 — the requirements every recommendation above is reasoned from.
- `RAIDIAN_WISE_ARCHITECTURE_V1.md` — the Reflection Engine's placement as a Core Service, cited in Q1.
- `docs/DECISIONS.md` — ADR-0005 (Reflection Engine exclusivity, Q1) and ADR-0006 (governance hierarchy, this document's own stated authority limit).
- `docs/ROADMAP.md` — M1's placement of the Reflection Engine as a cross-cutting platform milestone, cited in Q1.
- `NARRATIVE_LAYER_DESIGN.md` — the `[A]`/`[B]`/`[A']` split Q1's recommendation formally ratifies as an MVP staging decision, which it had proposed but could not itself decide.
- `READING_INTEGRATION_DESIGN.md` — Section 5's reinterpretation-after-`SAVED` decision, treated here (Q4) as settled and not reopened.
- `INTERPRETATION_API_DESIGN.md` — Section 9's separate-endpoints rationale, reaffirmed by Q5.
- `READING_LIFECYCLE_DESIGN.md` — Section 16's Q1–Q5 and Section 11's reversibility question, all resolved by this document; Section 15's contradiction findings, addressed (Q1, Q3/Q4) or left as identified-but-out-of-scope (Section 15.1, Section 8 above).
- `READING_WORKFLOW_VALIDATION.md` — Section 3.3's global-`sequence` finding, cited in Q4's consequences.
