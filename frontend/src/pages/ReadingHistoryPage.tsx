import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../api/client'
import { listSavedReadings, type ReadingStatus, type ReadingSummary } from '../api/readings'
import { useAuth } from '../auth/useAuth'
import { Panel } from '../components/Panel'

/**
 * Reading History (Step 52; restyled for the cosmic redesign) -- GET
 * /readings, reused verbatim from the existing API layer (no new HTTP
 * mechanism). Saved Readings only, by the backend's own already-
 * established, unmodified design (READING_HISTORY_OWNERSHIP_DESIGN.md
 * Section 7) -- this page does not attempt to surface drafts/in-progress
 * Readings and adds no second endpoint to do so.
 *
 * Known, deliberate contract gap, not fabricated here: ReadingSummary
 * (backend/app/schemas/reading_api.py) has no spread_id/spread field --
 * its own docstring already says why ("no current consumer... needs
 * them"). This page therefore cannot display a spread name without an
 * extra GET /readings/{id} call per row, which was not authorized by
 * this step and is not added speculatively. Each entry is distinguished
 * by its question, status, and last-updated time instead -- see the
 * Step 52 report for this finding.
 */

const STATUS_LABEL: Record<ReadingStatus, string> = {
  drafting: 'Drafting',
  spread_complete: 'Spread complete',
  interpreted: 'Interpreted',
  saved: 'Saved',
}

/**
 * Step 52 finding, confirmed by live comparison against the backend's
 * own clock (not assumed): `created_at`/`updated_at` are timezone-aware
 * columns (`DateTime(timezone=True)`), and their *values* are
 * genuinely UTC -- but the JSON serialization carries no timezone
 * designator at all (e.g. "2026-09-19T16:14:00", not "...Z" or
 * "...+00:00"). Per the ECMAScript date-time string grammar, a
 * date-time with no offset parses as LOCAL time, not UTC -- passing
 * the raw string to `Date` would silently show the wrong clock time,
 * off by the viewer's own UTC offset. Appending "Z" when no designator
 * is present is not a reinterpretation of the value; it is the
 * confirmed-correct reading of a value already known to be UTC. See
 * the Step 52 report for the live evidence and the corresponding
 * backend-serialization follow-up this suggests.
 */
function toAbsoluteDate(iso: string): Date {
  const hasDesignator = /Z$|[+-]\d{2}:\d{2}$/.test(iso)
  return new Date(hasDesignator ? iso : `${iso}Z`)
}

function formatDateTime(iso: string): string {
  return toAbsoluteDate(iso).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

export function ReadingHistoryPage() {
  const { token, clearToken } = useAuth()

  const [readings, setReadings] = useState<ReadingSummary[] | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    if (!token) {
      return
    }
    let cancelled = false
    listSavedReadings(token)
      .then((result) => {
        if (!cancelled) {
          setReadings(result)
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
        setLoadError(err instanceof ApiError ? err.message : 'Could not load your reading history.')
      })
    return () => {
      cancelled = true
    }
  }, [token, clearToken])

  if (loadError) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <p role="alert" className="rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
          {loadError}
        </p>
      </div>
    )
  }

  if (!readings) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <p className="text-sm text-ink-soft">Loading…</p>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full max-w-2xl">
      <div className="mb-8 text-center">
        <h1 className="font-serif text-3xl text-ink sm:text-4xl">Reading History</h1>
        <p className="mt-2 text-sm text-ink-soft">Your saved readings, newest first.</p>
      </div>

      {readings.length === 0 ? (
        <Panel className="text-center">
          <p className="text-sm text-ink-soft">You haven't saved any readings yet.</p>
          <Link
            to="/readings/new"
            className="mt-4 inline-block rounded-full bg-accent px-4 py-2 text-sm text-paper hover:opacity-90"
          >
            Start a new reading
          </Link>
        </Panel>
      ) : (
        <ul className="flex flex-col gap-3">
          {readings.map((reading) => (
            <Panel key={reading.id} as="li" className="p-4 sm:p-5">
              <div className="flex items-start justify-between gap-4">
                {/* min-w-0 lets this text shrink/wrap inside the flex row instead
                    of resisting its intrinsic content width (Step 57 fix for the
                    Step 56 audit's F-2 finding, Documentation/FRONTEND_MVP_AUDIT.md
                    Section 14) -- a long, unbroken question could otherwise push
                    the row wider than its container on a narrow screen. */}
                <p className="min-w-0 flex-1 text-ink">{reading.question}</p>
                <span className="rounded-full border border-border px-2 py-0.5 text-xs tracking-wide whitespace-nowrap text-accent uppercase">
                  {STATUS_LABEL[reading.status]}
                </span>
              </div>
              <p className="mt-1 text-xs text-ink-soft">Updated {formatDateTime(reading.updated_at)}</p>

              {/* Step 59: two separate, explicit actions rather than one
                  whole-card link -- preserves the existing Spread Review
                  destination while adding a direct path to Reading Result
                  (Documentation/READING_RESULT_FLOW_DESIGN.md Section 5,
                  Documentation/STEP58_REMAINING_MVP_DECISIONS_AUDIT.md
                  Section 14). No router state is passed on the Result
                  link -- ReadingResultPage's own existing Mode B
                  (GET /interpretations/current + GET /narrative) handles
                  this navigation exactly as it already handles a direct
                  visit or a refresh; nothing about that logic is
                  duplicated or re-implemented here. */}
              <div className="mt-3 flex items-center gap-4">
                <Link to={`/readings/${reading.id}`} className="text-sm text-accent underline">
                  View Spread Review
                </Link>
                <Link to={`/readings/${reading.id}/result`} className="text-sm text-accent underline">
                  View Result
                </Link>
              </div>
            </Panel>
          ))}
        </ul>
      )}
    </div>
  )
}
