/**
 * Reading API calls, mirroring backend/app/schemas/reading_api.py
 * one-for-one for the fields this frontend slice actually uses
 * (Step 46's history proof; Step 47's creation + detail fetch; Step 49's
 * draw recording). The full Reading experience (interpretation, save UI
 * beyond history) is deliberately not built yet
 * (Documentation/FRONTEND_INTEGRATION_DESIGN.md Section 11).
 */

import { request } from './client'
import type { CardSummary } from './cards'
import type { SpreadSummary } from './spreads'

export type ReadingStatus = 'drafting' | 'spread_complete' | 'interpreted' | 'saved'
export type Orientation = 'upright' | 'reversed'
export type DrawMethod = 'physical' | 'digital'

export interface ReadingSummary {
  id: string
  status: ReadingStatus
  question: string
  question_domain: string | null
  created_at: string
  updated_at: string
}

export interface ReadingCardDrawSummary {
  id: string
  position: SpreadSummary['positions'][number]
  card: CardSummary
  orientation: Orientation
  draw_order: number
  created_at: string
}

export interface ReadingDetail extends ReadingSummary {
  draw_method: DrawMethod
  spread_id: string
  spread: SpreadSummary
  deck_id: string
  card_draws: ReadingCardDrawSummary[]
}

/** Response of POST /readings/{reading_id}/draws -- the just-recorded draw. */
export interface CardDrawSummary {
  id: string
  position_id: string
  card_id: string
  orientation: Orientation
  draw_order: number
  created_at: string
  reading_status: ReadingStatus
}

/** GET /readings -- the authenticated caller's saved Reading history. */
export function listSavedReadings(token: string): Promise<ReadingSummary[]> {
  return request<ReadingSummary[]>('/readings', { token })
}

/**
 * POST /readings -- `question_domain`/`deck_id` both have server-side
 * defaults this slice never overrides. `draw_method` defaults to
 * 'physical' here too (unchanged for every existing caller), but is now
 * sent explicitly so NewReadingPage's Use My Deck / Digital Draw choice
 * reaches the backend (Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md
 * Section 8.2).
 */
export function createReading(
  token: string,
  spreadId: string,
  question: string,
  drawMethod: DrawMethod = 'physical',
): Promise<ReadingSummary> {
  return request<ReadingSummary>('/readings', {
    method: 'POST',
    token,
    body: { spread_id: spreadId, question, draw_method: drawMethod },
  })
}

/** GET /readings/{reading_id} -- full current state of one Reading. */
export function getReading(token: string, readingId: string): Promise<ReadingDetail> {
  return request<ReadingDetail>(`/readings/${readingId}`, { token })
}

/**
 * POST /readings/{reading_id}/draws -- records exactly one CardDraw.
 * Sends only the three client-supplied fields the backend accepts;
 * draw_order/ownership/lifecycle status are all server-computed
 * (Documentation/CARDDRAW_API_DESIGN.md Section 4.1/4.3) and must never
 * be sent from here.
 */
export function recordCardDraw(
  token: string,
  readingId: string,
  positionId: string,
  cardId: string,
  orientation: Orientation,
): Promise<CardDrawSummary> {
  return request<CardDrawSummary>(`/readings/${readingId}/draws`, {
    method: 'POST',
    token,
    body: { position_id: positionId, card_id: cardId, orientation },
  })
}

/**
 * POST /readings/{reading_id}/draws/digital -- draws every position of a
 * draw_method='digital', DRAFTING, not-yet-drawn Reading at once. Takes
 * no request body (which cards are drawn is never client-influenced) and
 * returns one CardDrawSummary per position, the same shape
 * recordCardDraw() above returns for a single manual draw.
 */
export function performDigitalDraw(token: string, readingId: string): Promise<CardDrawSummary[]> {
  return request<CardDrawSummary[]>(`/readings/${readingId}/draws/digital`, {
    method: 'POST',
    token,
  })
}

/**
 * POST /readings/{reading_id}/save -- idempotent (a no-op, still 200, if
 * already saved). Independent of interpretation/narrative: allowed from
 * spread_complete or interpreted, never requires narrative to exist first
 * (Documentation/READING_RESULT_FLOW_DESIGN.md Section 7).
 */
export function saveReading(token: string, readingId: string): Promise<ReadingSummary> {
  return request<ReadingSummary>(`/readings/${readingId}/save`, {
    method: 'POST',
    token,
  })
}
