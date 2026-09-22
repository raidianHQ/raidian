import { useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import type { Arcana, CardSummary, Suit } from '../api/cards'
import { listCards } from '../api/cards'
import { getReading, recordCardDraw, type Orientation, type ReadingDetail } from '../api/readings'
import { useAuth } from '../auth/useAuth'
import { Panel } from '../components/Panel'

/**
 * Card Entry (Step 49; restyled for the cosmic redesign) -- the real
 * physical-draw workflow, replacing Step 47's placeholder. Per
 * Documentation/CARD_IMAGE_ASSET_DESIGN.md Section 9: the Product Spec
 * specifies Card Entry as a text-based searchable/filterable selector,
 * and explicitly defers visual card browsing beyond it -- so this page
 * never renders, loads, or resolves `image_ref` into a URL; a card is
 * identified by its CardSummary fields (name, arcana, suit, rank) alone.
 *
 * The backend is authoritative for everything this page cannot
 * determine on its own: draw_order, ownership, and lifecycle status
 * (DRAFTING -> SPREAD_COMPLETE). This page never computes completion
 * itself -- it always re-fetches GET /readings/{id} after a successful
 * draw and renders whatever status comes back.
 */

type ArcanaFilter = 'all' | Arcana
type SuitFilter = 'all' | Suit

const ORIENTATIONS: { value: Orientation; label: string }[] = [
  { value: 'upright', label: 'Upright' },
  { value: 'reversed', label: 'Reversed' },
]

const SUITS: Suit[] = ['wands', 'cups', 'swords', 'pentacles']

/**
 * Step 67: Roman-numeral and Arabic-numeral rank aliases for the
 * free-text card search below. Card names already spell ranks out in
 * full ("Four of Wands"), so typing "IV" (or "IV of Wands", or "4")
 * would otherwise search for those literal characters instead of the
 * rank they denote -- the exact MVP-testing gap this step addresses.
 * Whole-token only (never a partial match inside a longer word), so
 * ordinary text search is otherwise completely unaffected.
 *
 * A few of these tokens (i, v, vi, ix, x, iv) already happen to appear
 * as raw substrings inside unrelated existing card names today, purely
 * by coincidence -- e.g. "v" inside "The Lovers"/"The Devil", "vi"
 * inside "The Devil", "ix"/"x" inside "Six", "iv" inside "Five". That
 * is not a feature anyone is relying on (nobody searches "iv" hoping to
 * find "Five of Wands"); this table intentionally supersedes those
 * accidental matches with the numeral's real, meaningful rank. Digit
 * tokens ("1".."10") carry no such coincidence at all -- no card name
 * contains a digit character -- so they are unambiguous additions.
 */
const RANK_SEARCH_ALIASES: Record<string, string> = {
  i: 'ace', ii: 'two', iii: 'three', iv: 'four', v: 'five',
  vi: 'six', vii: 'seven', viii: 'eight', ix: 'nine', x: 'ten',
  '1': 'ace', '2': 'two', '3': 'three', '4': 'four', '5': 'five',
  '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine', '10': 'ten',
}

function normalizeCardSearch(rawQuery: string): string {
  const trimmed = rawQuery.trim().toLowerCase()
  if (!trimmed) {
    return trimmed
  }
  return trimmed
    .split(/\s+/)
    .map((token) => RANK_SEARCH_ALIASES[token] ?? token)
    .join(' ')
}

export function CardEntryPage() {
  const { readingId } = useParams<{ readingId: string }>()
  const { token, clearToken } = useAuth()

  const [reading, setReading] = useState<ReadingDetail | null>(null)
  const [cards, setCards] = useState<CardSummary[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  const [selectedPositionId, setSelectedPositionId] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [arcanaFilter, setArcanaFilter] = useState<ArcanaFilter>('all')
  const [suitFilter, setSuitFilter] = useState<SuitFilter>('all')
  const [selectedCardId, setSelectedCardId] = useState<string | null>(null)
  const [selectedOrientation, setSelectedOrientation] = useState<Orientation | null>(null)

  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)

  async function loadReading(readingIdToLoad: string, authToken: string) {
    try {
      const result = await getReading(authToken, readingIdToLoad)
      setReading(result)
    } catch (err) {
      handleLoadError(err)
    }
  }

  function handleLoadError(err: unknown) {
    if (err instanceof ApiError && err.status === 401) {
      clearToken()
      return
    }
    setLoadError(err instanceof ApiError ? err.message : 'Could not load this reading.')
  }

  useEffect(() => {
    if (!token || !readingId) {
      return
    }
    let cancelled = false

    Promise.all([getReading(token, readingId), listCards()])
      .then(([readingResult, cardsResult]) => {
        if (!cancelled) {
          setReading(readingResult)
          setCards(cardsResult)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          handleLoadError(err)
        }
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

  const filteredCards = useMemo(() => {
    if (!cards) {
      return []
    }
    const query = normalizeCardSearch(search)
    return cards.filter((card) => {
      if (query && !card.name.toLowerCase().includes(query)) {
        return false
      }
      if (arcanaFilter !== 'all' && card.arcana !== arcanaFilter) {
        return false
      }
      if (suitFilter !== 'all' && card.suit !== suitFilter) {
        return false
      }
      return true
    })
  }, [cards, search, arcanaFilter, suitFilter])

  const selectedCard = cards?.find((card) => card.id === selectedCardId) ?? null

  function selectPosition(positionId: string) {
    setSelectedPositionId(positionId)
    setSelectedCardId(null)
    setSelectedOrientation(null)
    setSubmitError(null)
    // A leftover search query from a previous position silently combines
    // with the arcana/suit filters with no visual indication -- clearing
    // it here is the fix for the Step 49 follow-up "missing Wands cards"
    // defect (stale text filter, not a suit/rank/backend issue).
    setSearch('')
  }

  async function handleSubmit() {
    if (!token || !readingId || !selectedPositionId || !selectedCardId || !selectedOrientation || isSubmitting) {
      return
    }
    setIsSubmitting(true)
    setSubmitError(null)
    try {
      await recordCardDraw(token, readingId, selectedPositionId, selectedCardId, selectedOrientation)
      await loadReading(readingId, token)
      setSelectedPositionId(null)
      setSelectedCardId(null)
      setSelectedOrientation(null)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken()
        return
      }
      setSubmitError(err instanceof ApiError ? err.message : 'Could not record this draw. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <p role="alert" className="rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
          {loadError}
        </p>
      </div>
    )
  }

  if (!reading || !cards) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <p className="text-sm text-ink-soft">Loading…</p>
      </div>
    )
  }

  const canDraw = reading.status === 'drafting'
  const positions = reading.spread.positions

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="mb-8 text-center">
        <h1 className="font-serif text-3xl text-ink sm:text-4xl">Card Entry</h1>
        <p className="mt-3 text-sm text-ink-soft">
          <span className="font-medium text-ink">Question: </span>
          {reading.question}
        </p>
        <p className="text-sm text-ink-soft">
          <span className="font-medium text-ink">Layout: </span>
          {reading.spread.name}
        </p>
      </div>

      {!canDraw && (
        // Step 50 navigation decision: a dedicated link, not automatic
        // navigation. Auto-redirecting away from Card Entry the instant
        // the backend reports completion would fire mid-render with no
        // user action behind it -- the same "don't invent a surprising
        // automatic transition" principle Step 49 already applied to
        // draw submission (no auto-advance to the next position).
        // Spread Review is offered as the clear next step instead.
        <Panel className="mb-8">
          <p className="font-serif text-xl text-ink">This spread is complete.</p>
          <p className="mt-1 text-sm text-ink-soft">
            Every required position has been drawn. Interpreting this reading is not available yet.
          </p>
          <div className="mt-3 flex items-center gap-4">
            <Link
              to={`/readings/${reading.id}`}
              className="rounded-full bg-accent px-3 py-1.5 text-sm text-paper hover:opacity-90"
            >
              View spread review
            </Link>
            <Link to="/" className="text-sm text-accent underline">
              Back to home
            </Link>
          </div>
        </Panel>
      )}

      <section className="mb-8">
        <h2 className="mb-2 text-xs font-medium tracking-[0.2em] text-accent uppercase">Positions</h2>
        <ul className="flex flex-col gap-2">
          {positions.map((position) => {
            const draw = drawnByPositionId.get(position.id)
            const isSelected = selectedPositionId === position.id
            const isAvailable = canDraw && !draw

            return (
              <li key={position.id}>
                <button
                  type="button"
                  disabled={!isAvailable}
                  onClick={() => selectPosition(position.id)}
                  className={`w-full rounded-2xl border px-4 py-3 text-left transition-colors ${
                    isSelected ? 'border-accent bg-accent-soft' : 'border-border bg-paper-muted'
                  } ${isAvailable ? 'hover:bg-paper' : ''} ${!isAvailable && !draw ? 'opacity-60' : ''}`}
                >
                  <div className="flex items-center justify-between gap-4">
                    <span className="font-medium text-ink">{position.name}</span>
                    {draw ? (
                      <span className="text-xs text-ink-soft">
                        {draw.card.name} · {draw.orientation}
                      </span>
                    ) : (
                      <span className="text-xs text-ink-soft">
                        {isAvailable ? 'not yet drawn' : 'unavailable'}
                      </span>
                    )}
                  </div>
                  {position.description && (
                    <p className="mt-1 text-sm text-ink-soft">{position.description}</p>
                  )}
                </button>
              </li>
            )
          })}
        </ul>
      </section>

      {canDraw && selectedPositionId && (
        <Panel as="section" className="mb-8 flex flex-col gap-4">
          <p className="text-sm text-ink-soft">
            Drawing for{' '}
            <span className="font-medium text-ink">
              {positions.find((position) => position.id === selectedPositionId)?.name}
            </span>
          </p>

          <div className="flex flex-col gap-2">
            <label className="flex flex-col gap-1 text-sm text-ink-soft">
              Search cards
              <input
                type="text"
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Card name…"
                className="rounded-xl border border-border bg-paper px-3 py-2 text-ink placeholder:text-ink-soft/70"
              />
            </label>

            <div className="flex gap-3">
              <label className="flex flex-1 flex-col gap-1 text-sm text-ink-soft">
                Arcana
                <select
                  value={arcanaFilter}
                  onChange={(event) => {
                    const next = event.target.value as ArcanaFilter
                    setArcanaFilter(next)
                    if (next !== 'minor') {
                      setSuitFilter('all')
                    }
                  }}
                  className="rounded-xl border border-border bg-paper px-3 py-2 text-ink"
                >
                  <option value="all">All</option>
                  <option value="major">Major Arcana</option>
                  <option value="minor">Minor Arcana</option>
                </select>
              </label>

              <label className="flex flex-1 flex-col gap-1 text-sm text-ink-soft">
                Suit
                <select
                  value={suitFilter}
                  disabled={arcanaFilter === 'major'}
                  onChange={(event) => setSuitFilter(event.target.value as SuitFilter)}
                  className="rounded-xl border border-border bg-paper px-3 py-2 text-ink disabled:opacity-50"
                >
                  <option value="all">All</option>
                  {SUITS.map((suit) => (
                    <option key={suit} value={suit}>
                      {suit.charAt(0).toUpperCase() + suit.slice(1)}
                    </option>
                  ))}
                </select>
              </label>
            </div>
          </div>

          <ul className="flex max-h-64 flex-col gap-1 overflow-y-auto rounded-xl border border-border p-1">
            {filteredCards.length === 0 && (
              <li className="px-3 py-2 text-sm text-ink-soft">No cards match this search.</li>
            )}
            {filteredCards.map((card) => {
              const isSelected = card.id === selectedCardId
              return (
                <li key={card.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedCardId(card.id)}
                    aria-pressed={isSelected}
                    className={`w-full rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                      isSelected ? 'bg-accent-soft text-accent' : 'text-ink hover:bg-paper-muted'
                    }`}
                  >
                    {card.name}
                    <span className="ml-2 text-xs text-ink-soft">
                      {card.arcana === 'major' ? 'Major Arcana' : card.suit}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>

          <div>
            <p className="mb-2 text-sm text-ink-soft">Orientation</p>
            <div className="flex gap-2">
              {ORIENTATIONS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setSelectedOrientation(option.value)}
                  aria-pressed={selectedOrientation === option.value}
                  className={`rounded-full border px-4 py-2 text-sm transition-colors ${
                    selectedOrientation === option.value
                      ? 'border-accent bg-accent-soft text-accent'
                      : 'border-border bg-paper-muted text-ink hover:bg-paper'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
          </div>

          {selectedCard && selectedOrientation && (
            <p className="text-sm text-ink-soft">
              Selected: <span className="font-medium text-ink">{selectedCard.name}</span> ({selectedOrientation})
            </p>
          )}

          {submitError && (
            <p role="alert" className="rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
              {submitError}
            </p>
          )}

          <button
            type="button"
            disabled={!selectedCardId || !selectedOrientation || isSubmitting}
            onClick={() => void handleSubmit()}
            className="self-start rounded-full bg-accent px-4 py-2 text-paper hover:opacity-90 disabled:opacity-50"
          >
            {isSubmitting ? 'Recording…' : 'Record draw'}
          </button>
        </Panel>
      )}
    </div>
  )
}
