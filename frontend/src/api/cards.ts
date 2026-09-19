/**
 * Reference-data API calls for Cards, mirroring
 * backend/app/schemas/reference_data_api.py::CardSummary one-for-one
 * (Step 49). Public endpoint -- no token needed
 * (Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 5).
 *
 * `image_ref` is carried through for type-completeness only -- Card
 * Entry does not render or resolve it into a URL
 * (Documentation/CARD_IMAGE_ASSET_DESIGN.md Section 9: Card Entry is a
 * text-based searchable/filterable selector, and the Product Spec
 * explicitly defers visual card browsing beyond it).
 */

import { request } from './client'

export type Arcana = 'major' | 'minor'
export type Suit = 'wands' | 'cups' | 'swords' | 'pentacles'

export interface CardSummary {
  id: string
  name: string
  arcana: Arcana
  suit: Suit | null
  rank: string | null
  image_ref: string | null
  keywords: string[]
}

/** GET /cards -- all 78 seeded cards, Major Arcana then Minor by suit/rank. */
export function listCards(): Promise<CardSummary[]> {
  return request<CardSummary[]>('/cards')
}
