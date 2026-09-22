import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { getNarrative, interpretReading, type InterpretationSummary, type NarrativeModel } from '../api/interpretation'
import { getReading, type ReadingDetail, type ReadingStatus } from '../api/readings'
import { useAuth } from '../auth/useAuth'
import { CardArtwork } from '../components/CardArtwork'
import { Panel } from '../components/Panel'

/**
 * Spread Review / Reading Detail (Step 50; restyled for the cosmic
 * redesign) -- the Product Spec's "full visual layout of all positions,
 * cards, and orientations" screen (RAIDIAN_WISE_PRODUCT_SPEC_V1.md
 * Section 6), built directly against the existing, already-audited GET
 * /readings/{reading_id} contract (Documentation/READING_DETAIL_API_DESIGN.md)
 * -- no new backend behavior, no new fields, no new endpoint.
 *
 * Card presentation (Step 75; extracted to ../components/CardArtwork.tsx
 * so ReadingResultPage's own card-by-card presentation can reuse the
 * exact same artwork resolution/fallback logic rather than a second,
 * possibly-diverging copy). See that module's own docstring for the
 * OD-1/OD-2/OD-3 background.
 *
 * Status handling: `reading.status` is rendered and branched on
 * verbatim -- this page never counts draws or positions to infer
 * completion itself. The one derived value used for the undrawn-count
 * summary line is a plain display aggregation (list which of the
 * already-known positions have no matching card_draws entry), not a
 * recomputation of the backend's own DRAFTING/SPREAD_COMPLETE decision.
 */

const STATUS_LABEL: Record<ReadingStatus, string> = {
  drafting: 'Drafting',
  spread_complete: 'Spread complete',
  interpreted: 'Interpreted',
  saved: 'Saved',
}


/**
 * Local state machine for the explicit "Interpret My Reading" action
 * (Step 55, Documentation/READING_RESULT_FLOW_DESIGN.md Section 4). The
 * "Interpreting" transient state the Product Spec names lives here, as
 * an in-place render state of this page -- not a separate route -- and
 * the sequence (enter interpreting -> POST /interpret -> GET /narrative
 * -> navigate to /readings/:id/result carrying both results as router
 * state) only ever advances from an explicit button click, never from
 * an effect, so it cannot be triggered by a render, a remount, or a
 * refresh. A narrative-only failure keeps the already-successful
 * `interpretation` in state so retrying calls GET /narrative alone --
 * POST /interpret is never re-issued for a narrative failure.
 */
type InterpretFlowState =
  | { phase: 'idle' }
  | { phase: 'interpreting' }
  | { phase: 'interpret-failed'; error: string }
  | { phase: 'narrating'; interpretation: InterpretationSummary }
  | { phase: 'narrative-failed'; interpretation: InterpretationSummary; error: string }

export function SpreadReviewPage() {
  const { readingId } = useParams<{ readingId: string }>()
  const { token, clearToken } = useAuth()
  const navigate = useNavigate()

  const [reading, setReading] = useState<ReadingDetail | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [interpretFlow, setInterpretFlow] = useState<InterpretFlowState>({ phase: 'idle' })

  useEffect(() => {
    if (!token || !readingId) {
      return
    }
    let cancelled = false
    getReading(token, readingId)
      .then((result) => {
        if (!cancelled) {
          setReading(result)
        }
      })
      .catch((err: unknown) => {
        if (cancelled) {
          return
        }
        if (err instanceof ApiError && err.status === 401) {
          clearToken()
          return
        }
        setLoadError(err instanceof ApiError ? err.message : 'Could not load this reading.')
      })
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, readingId])

  const drawnByPositionId = useMemo(() => {
    const map = new Map<string, ReadingDetail['card_draws'][number]>()
    if (reading) {
      for (const draw of reading.card_draws) {
        map.set(draw.position.id, draw)
      }
    }
    return map
  }, [reading])

  function goToResult(interpretation: InterpretationSummary, narrative: NarrativeModel) {
    navigate(`/readings/${readingId}/result`, { state: { interpretation, narrative } })
  }

  async function fetchNarrative(interpretation: InterpretationSummary) {
    if (!token || !readingId) {
      return
    }
    setInterpretFlow({ phase: 'narrating', interpretation })
    try {
      const narrative = await getNarrative(token, readingId)
      goToResult(interpretation, narrative)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken()
        return
      }
      setInterpretFlow({
        phase: 'narrative-failed',
        interpretation,
        error: err instanceof ApiError ? err.message : 'Could not load the narrative for this reading.',
      })
    }
  }

  async function handleInterpretClick() {
    if (!token || !readingId) {
      return
    }
    setInterpretFlow({ phase: 'interpreting' })
    try {
      const interpretation = await interpretReading(token, readingId)
      await fetchNarrative(interpretation)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken()
        return
      }
      setInterpretFlow({
        phase: 'interpret-failed',
        error: err instanceof ApiError ? err.message : 'Could not interpret this reading. Please try again.',
      })
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <p role="alert" className="rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
          {loadError}
        </p>
      </div>
    )
  }

  if (!reading) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <p className="text-sm text-ink-soft">Loading…</p>
      </div>
    )
  }

  const positions = reading.spread.positions
  const isComplete = reading.status !== 'drafting'
  const undrawnPositions = positions.filter((position) => !drawnByPositionId.has(position.id))

  return (
    <div className="mx-auto w-full max-w-3xl">
      <div className="mb-8 text-center">
        <span className="mb-2 inline-block rounded-full border border-border px-2.5 py-0.5 text-sm tracking-wide text-accent uppercase">
          {STATUS_LABEL[reading.status]}
        </span>
        <h1 className="font-serif text-3xl text-ink sm:text-4xl">Spread Review</h1>
        <p className="mt-3 text-lg text-ink italic sm:text-xl">&ldquo;{reading.question}&rdquo;</p>
        <p className="mt-2 text-base text-ink-soft sm:text-lg">
          <span className="font-medium text-ink">{reading.spread.name}</span>
          {reading.spread.description && <> — {reading.spread.description}</>}
        </p>
      </div>

      {isComplete ? (
        <Panel className="mb-8">
          <p className="font-serif text-xl text-ink">This spread is complete.</p>
          <p className="mt-1 text-base text-ink-soft">Every required position has been drawn.</p>

          {(interpretFlow.phase === 'idle' || interpretFlow.phase === 'interpret-failed') && (
            <>
              {interpretFlow.phase === 'interpret-failed' && (
                <p role="alert" className="mt-3 rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
                  {interpretFlow.error}
                </p>
              )}
              <button
                type="button"
                onClick={() => void handleInterpretClick()}
                className="mt-3 rounded-full bg-accent px-4 py-2 text-sm text-paper hover:opacity-90"
              >
                Interpret My Reading
              </button>
            </>
          )}

          {(interpretFlow.phase === 'interpreting' || interpretFlow.phase === 'narrating') && (
            <div className="mt-3 flex flex-col gap-1">
              <p className="text-sm text-ink">Interpreting your reading…</p>
              <p className="text-sm text-ink-soft">
                Raidian Reflection is building a structured analysis of your spread -- no AI is involved in this step.
              </p>
            </div>
          )}

          {interpretFlow.phase === 'narrative-failed' && (
            <div className="mt-3 flex flex-col gap-2">
              <p role="alert" className="rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
                {interpretFlow.error}
              </p>
              <p className="text-sm text-ink-soft">
                Your interpretation was recorded. Only the reflection text failed to load -- retrying will not
                create another interpretation.
              </p>
              <button
                type="button"
                onClick={() => void fetchNarrative(interpretFlow.interpretation)}
                className="self-start rounded-full bg-accent px-4 py-2 text-sm text-paper hover:opacity-90"
              >
                Try loading the reflection again
              </button>
            </div>
          )}

          {interpretFlow.phase === 'idle' && (
            <p className="mt-3 text-sm text-ink-soft">
              Already interpreted this reading?{' '}
              <Link to={`/readings/${reading.id}/result`} className="text-accent underline">
                View the result
              </Link>
              .
            </p>
          )}
        </Panel>
      ) : (
        <Panel className="mb-8">
          <p className="font-serif text-xl text-ink">
            {positions.length - undrawnPositions.length} of {positions.length} position
            {positions.length === 1 ? '' : 's'} drawn.
          </p>
          {undrawnPositions.length > 0 && (
            <p className="mt-1 text-base text-ink-soft">
              Still to draw: {undrawnPositions.map((position) => position.name).join(', ')}
            </p>
          )}
          <Link to={`/readings/${reading.id}/draw`} className="mt-3 inline-block text-sm text-accent underline">
            Continue drawing
          </Link>
        </Panel>
      )}

      <Panel as="section" className="mb-8">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          {positions.map((position) => {
            const draw = drawnByPositionId.get(position.id)
            return (
              <div key={position.id} className="flex flex-col items-center gap-2">
                <div className="flex w-full flex-col items-center gap-1">
                  <span className="text-center text-sm font-medium text-ink-soft sm:text-base">{position.name}</span>
                  {!position.required && <span className="text-xs text-ink-soft">(optional)</span>}
                </div>

                {draw ? (
                  <div className="flex w-full flex-col items-center gap-2 rounded-2xl border border-border bg-paper-muted p-2 text-center">
                    <div className="aspect-2/3 w-full overflow-hidden rounded-xl bg-paper">
                      <CardArtwork card={draw.card} orientation={draw.orientation} />
                    </div>
                    <span className="font-serif text-base text-ink sm:text-lg">{draw.card.name}</span>
                    <span className="text-sm text-ink-soft">
                      {draw.card.arcana === 'major' ? 'Major Arcana' : draw.card.suit}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-sm ${
                        draw.orientation === 'reversed' ? 'bg-error-soft text-error' : 'bg-accent-soft text-accent'
                      }`}
                    >
                      {draw.orientation === 'reversed' ? '↓ Reversed' : '↑ Upright'}
                    </span>
                  </div>
                ) : (
                  <div className="flex aspect-2/3 w-full flex-col items-center justify-center gap-1 rounded-2xl border-2 border-dashed border-border px-2 py-3 text-center">
                    <span className="text-xs text-ink-soft">Not yet drawn</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </Panel>

      <Link to="/" className="text-sm text-accent underline">
        Back to home
      </Link>
    </div>
  )
}
