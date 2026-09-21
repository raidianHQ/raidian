/**
 * Optional Scriptural Reflection API calls, mirroring
 * backend/app/schemas/scripture_model.py field-for-field.
 *
 * Deliberately its own module, separate from api/interpretation.ts --
 * mirrors the backend's own architectural separation between tarot
 * interpretation and Scripture (Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md
 * Section 15: "conceptually and architecturally separate from tarot
 * interpretation"). Deterministic, never AI-generated -- no LLM call is
 * involved in producing a ScripturalPerspective.
 *
 * Scripture is optional by construction: getScripture() is a separate,
 * opt-in fetch a caller makes only if it wants a reflection --
 * getCurrentInterpretation()/getNarrative() (api/interpretation.ts) are
 * entirely unaffected by whether this is ever called.
 */

import { request } from './client'
import type { Citation } from './interpretation'

export interface ScriptureReflection {
  theme: string
  book: string
  chapter: number
  verse_start: number
  verse_end: number | null
  reference_display: string
  translation: string
  context_note: string
  reflection_connection: string
  theme_citations: Citation[]
}

export interface ScripturalPerspective {
  schema_version: string
  generated_at: string
  source_schema_version: string
  disclaimer: string
  reflections: ScriptureReflection[]
}

/**
 * GET /readings/{reading_id}/scripture -- the first call for a given
 * interpretation selects and, if it finds at least one approved
 * reference, persists a snapshot; every later call for that same
 * interpretation returns the persisted snapshot as-is, without
 * re-querying the (mutable) Scripture reference dataset. `reflections`
 * may legitimately be empty when none of the reading's own established
 * themes have an approved mapping yet -- not an error, and never
 * persisted (so a later addition to the approved dataset can still be
 * found on this reading's next request).
 */
export function getScripture(token: string, readingId: string): Promise<ScripturalPerspective> {
  return request<ScripturalPerspective>(`/readings/${readingId}/scripture`, { token })
}

/**
 * GET /readings/{reading_id}/scripture/current -- never selects,
 * computes, or persists anything; 404 means no Scriptural Reflection
 * snapshot has been created yet for this reading's current
 * interpretation (either GET /scripture was never called, or it was
 * called but found no approved match). Mirrors
 * api/aiNarrative.ts::getCurrentAiNarrative()'s own "safe, read-only
 * check" contract.
 */
export function getCurrentScripture(token: string, readingId: string): Promise<ScripturalPerspective> {
  return request<ScripturalPerspective>(`/readings/${readingId}/scripture/current`, { token })
}
