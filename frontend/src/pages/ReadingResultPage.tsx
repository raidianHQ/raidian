import { useEffect, useState } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import {
  getCurrentInterpretation,
  getNarrative,
  type Citation,
  type InterpretationSummary,
  type NarrativeModel,
} from '../api/interpretation'
import { saveReading, type ReadingStatus } from '../api/readings'
import { useAuth } from '../auth/useAuth'

/**
 * Reading Result (Step 55) -- Documentation/READING_RESULT_FLOW_DESIGN.md
 * Sections 4/5/6/9. Renders the deterministic InterpretiveModel and
 * NarrativeModel for one Reading; also serves as the interpretation half
 * of the Product Spec's "Reading Detail" when revisited later (Section 5
 * of the design doc).
 *
 * Two entry modes, per the design doc Section 7:
 *
 * Mode A (fresh): SpreadReviewPage navigates here with the just-generated
 * `interpretation`/`narrative` already in `location.state` -- used
 * directly, no fetch performed at all.
 *
 * Mode B (revisit/refresh/direct navigation): no router state present
 * (this is exactly what a page refresh produces -- in-memory router
 * state does not survive a reload). Falls back to
 * GET /interpretations/current + GET /narrative. A 404 from the first
 * call means "not yet interpreted" -- handled explicitly (Section 8 of
 * the design doc), never treated as an error and never triggers
 * POST /interpret automatically.
 *
 * Both the Interpretation Engine and Narrative assembler are
 * deterministic -- nothing on this page is described as AI-generated.
 */

interface LocationState {
  interpretation?: InterpretationSummary
  narrative?: NarrativeModel
}

const EVIDENCE_STRENGTH_LABEL: Record<string, string> = {
  strong: 'Strong',
  moderate: 'Moderate',
  weak: 'Weak',
  unresolved: 'Unresolved',
}

/**
 * Step 57 (F-1 fix, Documentation/FRONTEND_MVP_AUDIT.md): renders one
 * Citation using only fields the backend schema actually populates for
 * it (backend/app/schemas/interpretive_model.py::Citation) -- verified
 * live against a real interpretation before implementing this. A
 * citation is exactly one of two mutually exclusive shapes:
 * - source_type "card_draw": card_name/position_name are the
 *   user-meaningful fields; contributing_theme is present on some but
 *   not all card_draw citations. card_draw_id is an internal UUID,
 *   never shown.
 * - source_type "compound_rule"/"structural_rule": rule_id/rule_tier
 *   are the user-meaningful fields (no live example of this shape
 *   appeared in verification, so this branch follows the schema's own
 *   docstring exactly rather than an observed sample).
 */
function citationLabel(citation: Citation): string {
  if (citation.source_type === 'card_draw') {
    const base = citation.position_name
      ? `${citation.card_name ?? 'A card'} — ${citation.position_name}`
      : (citation.card_name ?? 'A drawn card')
    return citation.contributing_theme ? `${base} (${citation.contributing_theme})` : base
  }
  const ruleName = citation.rule_id ? citation.rule_id.replace(/_/g, ' ') : 'a pattern in the spread'
  return citation.rule_tier ? `${ruleName} (${citation.rule_tier})` : ruleName
}

function Citations({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) {
    return null
  }
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-ink-soft">Sources:</span>
      {citations.map((citation, index) => (
        <span
          key={index}
          className="rounded-full border border-border bg-paper-muted px-2 py-0.5 text-xs text-ink-soft"
        >
          {citationLabel(citation)}
        </span>
      ))}
    </div>
  )
}

type SaveState =
  | { phase: 'idle' }
  | { phase: 'saving' }
  | { phase: 'saved'; status: ReadingStatus }
  | { phase: 'error'; error: string }

export function ReadingResultPage() {
  const { readingId } = useParams<{ readingId: string }>()
  const { token, clearToken } = useAuth()
  const location = useLocation()

  // Mode A: initialized synchronously from router state (available on the
  // very first render, via a lazy initializer -- not set from inside an
  // effect body, which this project's lint rules correctly forbid).
  const passedState = (location.state as LocationState | null) ?? null
  const hasFreshResult = Boolean(passedState?.interpretation && passedState?.narrative)

  const [interpretation, setInterpretation] = useState<InterpretationSummary | null>(
    () => passedState?.interpretation ?? null,
  )
  const [narrative, setNarrative] = useState<NarrativeModel | null>(() => passedState?.narrative ?? null)
  const [notInterpreted, setNotInterpreted] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [narrativeError, setNarrativeError] = useState<string | null>(null)
  const [saveState, setSaveState] = useState<SaveState>({ phase: 'idle' })

  useEffect(() => {
    if (!token || !readingId || hasFreshResult) {
      // Mode A is already fully satisfied by the lazy initializers above --
      // no fetch needed.
      return
    }
    let cancelled = false

    // Mode B: direct navigation, refresh, or a later revisit.
    async function loadExisting() {
      let current: InterpretationSummary
      try {
        current = await getCurrentInterpretation(token!, readingId!)
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          clearToken()
          return
        }
        if (err instanceof ApiError && err.status === 404) {
          setNotInterpreted(true)
          return
        }
        setLoadError(err instanceof ApiError ? err.message : 'Could not load this reading.')
        return
      }
      if (cancelled) return
      setInterpretation(current)

      try {
        const narrativeResult = await getNarrative(token!, readingId!)
        if (!cancelled) {
          setNarrative(narrativeResult)
        }
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          clearToken()
          return
        }
        setNarrativeError(err instanceof ApiError ? err.message : 'Could not load the narrative for this reading.')
      }
    }

    void loadExisting()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, readingId])

  async function handleRetryNarrative() {
    if (!token || !readingId) {
      return
    }
    setNarrativeError(null)
    try {
      const narrativeResult = await getNarrative(token, readingId)
      setNarrative(narrativeResult)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken()
        return
      }
      setNarrativeError(err instanceof ApiError ? err.message : 'Could not load the narrative for this reading.')
    }
  }

  async function handleSave() {
    if (!token || !readingId || saveState.phase === 'saving') {
      return
    }
    setSaveState({ phase: 'saving' })
    try {
      const result = await saveReading(token, readingId)
      setSaveState({ phase: 'saved', status: result.status })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken()
        return
      }
      setSaveState({
        phase: 'error',
        error: err instanceof ApiError ? err.message : 'Could not save this reading. Please try again.',
      })
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <p role="alert" className="rounded-md bg-error-soft px-3 py-2 text-sm text-error">
          {loadError}
        </p>
        <Link to={`/readings/${readingId}`} className="mt-4 inline-block text-sm text-accent underline">
          Back to Spread Review
        </Link>
      </div>
    )
  }

  if (notInterpreted) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <h1 className="mb-2 text-2xl font-medium text-ink">Reading Result</h1>
        <div className="rounded-lg border border-border bg-paper-muted px-4 py-6 text-center">
          <p className="text-sm text-ink-soft">This reading hasn't been interpreted yet.</p>
          <Link
            to={`/readings/${readingId}`}
            className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm text-paper hover:opacity-90"
          >
            Back to Spread Review
          </Link>
        </div>
      </div>
    )
  }

  if (!interpretation) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <p className="text-sm text-ink-soft">Loading…</p>
      </div>
    )
  }

  const model = interpretation.interpretive_model
  const presentSections = narrative?.sections.filter((section) => section.present) ?? []

  return (
    <div className="mx-auto w-full max-w-3xl">
      <h1 className="mb-2 text-2xl font-medium text-ink">Reading Result</h1>
      <p className="mb-6 text-lg text-ink">{model.central_question}</p>

      {/* Narrative -- the primary, reflective content. Deterministically
          assembled, never AI-generated (see module docstring). */}
      <section className="mb-8 flex flex-col gap-6">
        {narrativeError && (
          <div className="rounded-md bg-error-soft px-3 py-2">
            <p role="alert" className="text-sm text-error">
              {narrativeError}
            </p>
            <button
              type="button"
              onClick={() => void handleRetryNarrative()}
              className="mt-2 rounded-md bg-accent px-3 py-1.5 text-sm text-paper hover:opacity-90"
            >
              Try loading the reflection again
            </button>
          </div>
        )}
        {!narrative && !narrativeError && <p className="text-sm text-ink-soft">Loading reflection…</p>}
        {presentSections.map((section) => (
          <div key={section.id}>
            <h2 className="mb-1 text-sm font-medium uppercase tracking-wide text-ink-soft">{section.title}</h2>
            {section.statements.map((statement, index) => (
              <p key={index} className="text-ink">
                {statement.text}
              </p>
            ))}
          </div>
        ))}
      </section>

      {/* Interpretation / explainability -- "How did Raidian Wise arrive
          at this?" (RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 6), a
          secondary panel distinct from the narrative above. */}
      <section className="mb-8 flex flex-col gap-4 rounded-lg border border-border p-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-ink-soft">
          How did Raidian Wise arrive at this?
        </h2>
        <p className="text-xs text-ink-soft">
          A deterministic analysis of your cards and positions -- no AI is used to produce this reading.
        </p>

        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Evidence strength</p>
          <p className="text-ink">{EVIDENCE_STRENGTH_LABEL[model.evidence_strength] ?? model.evidence_strength}</p>
        </div>

        <div>
          <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Central issue</p>
          <p className="text-ink">{model.central_issue.value}</p>
          <Citations citations={model.central_issue.citations} />
        </div>

        {model.primary_tension && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Primary tension</p>
            <p className="text-ink">
              {model.primary_tension.value.pole_a} ↔ {model.primary_tension.value.pole_b} —{' '}
              {model.primary_tension.value.label}
            </p>
            <Citations citations={model.primary_tension.citations} />
          </div>
        )}

        {model.supporting_themes.length > 0 && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Supporting themes</p>
            <ul className="list-inside list-disc text-ink">
              {model.supporting_themes.map((theme, index) => (
                <li key={index}>
                  {theme.value}
                  <Citations citations={theme.citations} />
                </li>
              ))}
            </ul>
          </div>
        )}

        {model.trajectory && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Trajectory</p>
            <ol className="list-inside list-decimal text-ink">
              {model.trajectory.value.arc.map((step, index) => (
                <li key={index}>
                  {step.position_name}: {step.card_name} ({step.orientation})
                </li>
              ))}
            </ol>
            <Citations citations={model.trajectory.citations} />
          </div>
        )}

        {model.blocker && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Blocker</p>
            <p className="text-ink">{model.blocker.value}</p>
            <Citations citations={model.blocker.citations} />
          </div>
        )}

        {model.advice && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Advice</p>
            <p className="text-ink">{model.advice.value}</p>
            <Citations citations={model.advice.citations} />
          </div>
        )}

        {model.clarification && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Clarification</p>
            <p className="text-ink">{model.clarification.value}</p>
            <Citations citations={model.clarification.citations} />
          </div>
        )}

        {model.uncertainty.length > 0 && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">What remains unclear</p>
            <ul className="list-inside list-disc text-ink">
              {model.uncertainty.map((item, index) => (
                <li key={index}>{item}</li>
              ))}
            </ul>
          </div>
        )}

        {model.contradictions.length > 0 && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Contradictions</p>
            <ul className="list-inside list-disc text-ink">
              {model.contradictions.map((item, index) => (
                <li key={index}>
                  {item.description}
                  <Citations citations={item.sources} />
                </li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* Save. mark_saved() is idempotent, so this action is offered
          unconditionally rather than fabricating a locally-known saved
          state (Documentation/READING_RESULT_FLOW_DESIGN.md Section 7). */}
      <section className="mb-8">
        {saveState.phase === 'saved' ? (
          <p className="rounded-md bg-accent-soft px-3 py-2 text-sm text-ink">
            This reading has been saved to your history.
          </p>
        ) : (
          <>
            {saveState.phase === 'error' && (
              <p role="alert" className="mb-2 rounded-md bg-error-soft px-3 py-2 text-sm text-error">
                {saveState.error}
              </p>
            )}
            <button
              type="button"
              disabled={saveState.phase === 'saving'}
              onClick={() => void handleSave()}
              className="rounded-md bg-accent px-4 py-2 text-sm text-paper hover:opacity-90 disabled:opacity-50"
            >
              {saveState.phase === 'saving' ? 'Saving…' : 'Save this reading'}
            </button>
          </>
        )}
      </section>

      <Link to={`/readings/${readingId}`} className="text-sm text-accent underline">
        Back to Spread Review
      </Link>
    </div>
  )
}
