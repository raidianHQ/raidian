/**
 * Reference-data API calls for Spreads, mirroring
 * backend/app/schemas/reference_data_api.py one-for-one (Step 47).
 * Public endpoint -- no token needed
 * (Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 5).
 */

import { request } from './client'

export interface SpreadPositionSummary {
  id: string
  name: string
  description: string | null
  position_order: number
  semantic_role: string
  required: boolean
}

export interface SpreadSummary {
  id: string
  name: string
  description: string | null
  position_count: number
  allow_duplicate_cards: boolean
  positions: SpreadPositionSummary[]
}

/** GET /spreads -- every seeded Spread, positions embedded and ordered. */
export function listSpreads(): Promise<SpreadSummary[]> {
  return request<SpreadSummary[]>('/spreads')
}
