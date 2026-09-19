import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { createReading, type ReadingSummary } from '../api/readings'
import { listSpreads, type SpreadSummary } from '../api/spreads'
import { useAuth } from '../auth/useAuth'

/**
 * New Reading -- Spread Selection + Question entry (Step 47).
 *
 * ---------------------------------------------------------------------
 * POST /readings sequencing decision (explicitly determined, not a
 * convenience default):
 *
 * The backend's ReadingCreateRequest (backend/app/schemas/reading_api.py)
 * requires exactly two fields with no server-side default: `spread_id`
 * and `question`. `question_domain` and `deck_id` are optional, and
 * `draw_method` already defaults to PHYSICAL -- the only path this slice
 * builds (Digital Draw is explicitly out of scope, per this step's own
 * boundaries and the enum's own docstring, backend/app/models/enums.py).
 *
 * Documentation/FRONTEND_INTEGRATION_DESIGN.md Section 6 already
 * considered this question once, at the *Question vs. Draw Method*
 * boundary, and left the exact firing point as "a frontend flow
 * decision, not resolved" pending a Draw Method screen this slice does
 * not build. Re-examined here, narrowed to what this step actually
 * ships: with no Draw Method screen in scope, there is no later point
 * in the flow where *more* required information becomes available --
 * `spread_id` and `question` together are both the earliest and the
 * only point at which the request is satisfiable. Creating the Reading
 * any earlier (e.g., on Spread selection alone) is impossible, since
 * the backend rejects a blank/missing `question` (`Reading.question`'s
 * own `@validates` guard, defense-in-depth behind the schema's own
 * validator); creating it any later would require inventing an
 * additional screen this step does not build.
 *
 * Decision: **one combined Spread-selection-and-Question form**, firing
 * `POST /readings` on submit, once both a Spread is selected and a
 * non-blank Question is entered. This is the minimum
 * implementation-safe choice for this slice -- not a claim that a
 * multi-screen wizard (Layout Selection -> Question -> Draw Method, per
 * the Product Spec's own literal screen sequence) is rejected for the
 * eventual, full experience. That remains open for whichever future
 * step actually builds Draw Method/Digital Draw.
 * ---------------------------------------------------------------------
 */
export function NewReadingPage() {
  const { token } = useAuth()
  const navigate = useNavigate()

  const [spreads, setSpreads] = useState<SpreadSummary[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedSpreadId, setSelectedSpreadId] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    let cancelled = false
    listSpreads()
      .then((result) => {
        if (!cancelled) {
          setSpreads(result)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setLoadError(err instanceof ApiError ? err.message : 'Could not load spreads.')
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function handleSubmit() {
    if (!token || !selectedSpreadId || !question.trim()) {
      return
    }
    setSubmitError(null)
    setIsSubmitting(true)
    try {
      const reading: ReadingSummary = await createReading(token, selectedSpreadId, question.trim())
      navigate(`/readings/${reading.id}/draw`, { replace: true })
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : 'Could not create the reading. Please try again.')
      setIsSubmitting(false)
    }
  }

  const canSubmit = selectedSpreadId !== null && question.trim().length > 0 && !isSubmitting

  return (
    <div className="mx-auto w-full max-w-2xl">
      <h1 className="mb-2 text-2xl font-medium text-ink">New Reading</h1>
      <p className="mb-8 text-sm text-ink-soft">Choose a layout, then enter your question.</p>

      {loadError && (
        <p role="alert" className="mb-6 rounded-md bg-error-soft px-3 py-2 text-sm text-error">
          {loadError}
        </p>
      )}

      {!loadError && spreads === null && <p className="text-sm text-ink-soft">Loading spreads…</p>}

      {spreads !== null && (
        <>
          <fieldset className="mb-8 flex flex-col gap-3">
            <legend className="mb-2 text-sm font-medium text-ink">Layout</legend>
            {spreads.map((spread) => {
              const isSelected = spread.id === selectedSpreadId
              return (
                <button
                  key={spread.id}
                  type="button"
                  onClick={() => setSelectedSpreadId(spread.id)}
                  aria-pressed={isSelected}
                  className={`rounded-lg border px-4 py-3 text-left transition-colors ${
                    isSelected
                      ? 'border-accent bg-accent-soft'
                      : 'border-border bg-paper hover:bg-paper-muted'
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-4">
                    <span className="font-medium text-ink">{spread.name}</span>
                    <span className="whitespace-nowrap text-xs text-ink-soft">
                      {spread.position_count} position{spread.position_count === 1 ? '' : 's'}
                    </span>
                  </div>
                  {spread.description && <p className="mt-1 text-sm text-ink-soft">{spread.description}</p>}
                  <p className="mt-2 text-xs text-ink-soft">
                    {spread.positions.map((position) => position.name).join(' · ')}
                  </p>
                </button>
              )
            })}
          </fieldset>

          <label className="mb-6 flex flex-col gap-1 text-sm text-ink-soft">
            Your question
            <textarea
              required
              rows={3}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What should I focus on right now?"
              className="rounded-md border border-border bg-paper px-3 py-2 text-ink"
            />
          </label>

          {submitError && (
            <p role="alert" className="mb-4 rounded-md bg-error-soft px-3 py-2 text-sm text-error">
              {submitError}
            </p>
          )}

          <button
            type="button"
            disabled={!canSubmit}
            onClick={() => void handleSubmit()}
            className="rounded-md bg-accent px-4 py-2 text-paper hover:opacity-90 disabled:opacity-50"
          >
            {isSubmitting ? 'Creating reading…' : 'Begin reading'}
          </button>
        </>
      )}
    </div>
  )
}
