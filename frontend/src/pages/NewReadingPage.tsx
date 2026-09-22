import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { createReading, performDigitalDraw, type DrawMethod, type ReadingSummary } from '../api/readings'
import { listSpreads, type SpreadSummary } from '../api/spreads'
import { useAuth } from '../auth/useAuth'
import { Panel } from '../components/Panel'

/**
 * New Reading -- Spread Selection + Question entry + Draw Method choice
 * (Step 47; Draw Method choice added for Digital Draw; restyled for the
 * cosmic redesign).
 *
 * ---------------------------------------------------------------------
 * POST /readings sequencing decision (explicitly determined, not a
 * convenience default):
 *
 * The backend's ReadingCreateRequest (backend/app/schemas/reading_api.py)
 * requires exactly two fields with no server-side default: `spread_id`
 * and `question`. `question_domain` and `deck_id` remain optional and
 * unset by this slice; `draw_method` is now chosen explicitly below
 * (Use My Deck / Digital Draw) instead of always relying on the
 * backend's own PHYSICAL default.
 *
 * Decision (unchanged from Step 47): **one combined Spread-selection,
 * Question, and Draw-Method form**, firing `POST /readings` on submit,
 * once a Spread is selected and a non-blank Question is entered --
 * still the minimum implementation-safe choice for this slice, not a
 * claim that a multi-screen wizard (per the Product Spec's own literal
 * screen sequence) is rejected for the eventual, full experience.
 *
 * Digital Draw sequencing: for a `digital` choice, `POST
 * /readings/{id}/draws/digital` fires immediately after `POST /readings`
 * succeeds, in the same submit handler -- the user never sees Card
 * Entry at all, going straight to Spread Review once both calls
 * succeed. A `physical` choice is unchanged: straight to Card Entry.
 * ---------------------------------------------------------------------
 */

const DRAW_METHODS: { value: DrawMethod; label: string; description: string }[] = [
  { value: 'physical', label: 'Use My Deck', description: 'Draw your own physical cards and enter them here.' },
  { value: 'digital', label: 'Digital Draw', description: 'Let Raidian Reflection draw the cards for you.' },
]

export function NewReadingPage() {
  const { token, clearToken } = useAuth()
  const navigate = useNavigate()

  const [spreads, setSpreads] = useState<SpreadSummary[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [selectedSpreadId, setSelectedSpreadId] = useState<string | null>(null)
  const [question, setQuestion] = useState('')
  const [drawMethod, setDrawMethod] = useState<DrawMethod>('physical')
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
      const reading: ReadingSummary = await createReading(token, selectedSpreadId, question.trim(), drawMethod)
      if (drawMethod === 'digital') {
        await performDigitalDraw(token, reading.id)
        navigate(`/readings/${reading.id}`, { replace: true })
      } else {
        navigate(`/readings/${reading.id}/draw`, { replace: true })
      }
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken()
        return
      }
      setSubmitError(err instanceof ApiError ? err.message : 'Could not create the reading. Please try again.')
      setIsSubmitting(false)
    }
  }

  const canSubmit = selectedSpreadId !== null && question.trim().length > 0 && !isSubmitting

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="mb-8 text-center">
        <h1 className="font-serif text-3xl text-ink sm:text-4xl">New Reading</h1>
        <p className="mt-2 text-sm text-ink-soft">Choose a layout, then enter your question.</p>
      </div>

      {loadError && (
        <p role="alert" className="mb-6 rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
          {loadError}
        </p>
      )}

      {!loadError && spreads === null && <p className="text-sm text-ink-soft">Loading spreads…</p>}

      {spreads !== null && (
        <Panel className="flex flex-col gap-8">
          <fieldset className="flex flex-col gap-3">
            <legend className="mb-2 text-xs font-medium tracking-[0.2em] text-accent uppercase">Layout</legend>
            {spreads.map((spread) => {
              const isSelected = spread.id === selectedSpreadId
              return (
                <button
                  key={spread.id}
                  type="button"
                  onClick={() => setSelectedSpreadId(spread.id)}
                  aria-pressed={isSelected}
                  className={`rounded-2xl border px-4 py-3 text-left transition-colors ${
                    isSelected
                      ? 'border-accent bg-accent-soft'
                      : 'border-border bg-paper-muted hover:bg-paper'
                  }`}
                >
                  <div className="flex items-baseline justify-between gap-4">
                    <span className="font-serif text-lg text-ink">{spread.name}</span>
                    <span className="text-xs whitespace-nowrap text-ink-soft">
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

          <label className="flex flex-col gap-1 text-sm text-ink-soft">
            <span className="text-xs font-medium tracking-[0.2em] text-accent uppercase">Your question</span>
            <textarea
              required
              rows={3}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="What should I focus on right now?"
              className="rounded-xl border border-border bg-paper px-3 py-2 text-ink placeholder:text-ink-soft/70"
            />
          </label>

          <fieldset className="flex flex-col gap-3">
            <legend className="mb-2 text-xs font-medium tracking-[0.2em] text-accent uppercase">
              How will you draw?
            </legend>
            {DRAW_METHODS.map((method) => {
              const isSelected = method.value === drawMethod
              return (
                <button
                  key={method.value}
                  type="button"
                  onClick={() => setDrawMethod(method.value)}
                  aria-pressed={isSelected}
                  className={`rounded-2xl border px-4 py-3 text-left transition-colors ${
                    isSelected
                      ? 'border-accent bg-accent-soft'
                      : 'border-border bg-paper-muted hover:bg-paper'
                  }`}
                >
                  <span className="font-serif text-lg text-ink">{method.label}</span>
                  <p className="mt-1 text-sm text-ink-soft">{method.description}</p>
                </button>
              )
            })}
          </fieldset>

          {submitError && (
            <p role="alert" className="rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
              {submitError}
            </p>
          )}

          <button
            type="button"
            disabled={!canSubmit}
            onClick={() => void handleSubmit()}
            className="self-start rounded-full bg-accent px-5 py-2.5 text-paper hover:opacity-90 disabled:opacity-50"
          >
            {isSubmitting
              ? drawMethod === 'digital'
                ? 'Drawing your cards…'
                : 'Creating reading…'
              : 'Begin reading'}
          </button>
        </Panel>
      )}
    </div>
  )
}
