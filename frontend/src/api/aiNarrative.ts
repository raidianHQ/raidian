/**
 * AI Narrative Layer API calls, mirroring
 * backend/app/schemas/ai_narrative.py field-for-field. Reuses the
 * existing request()/ApiError machinery (api/client.ts) -- no second HTTP
 * mechanism.
 *
 * Deliberately its own module, separate from api/interpretation.ts and
 * api/scripture.ts -- mirrors those two files' own architectural
 * separation: the AI Narrative Layer only ever reads an already-finished
 * InterpretiveModel (and, optionally, an already-selected
 * ScripturalPerspective); it never calls, replaces, or reinterprets
 * either.
 *
 * generateAiNarrative() is the only AI provider call anywhere in this
 * application, and it is not idempotent -- call it only from an explicit
 * user action (a button), never from a page load/effect, mirroring
 * interpretReading()'s own contract.
 */

import { request } from './client'
import type { Citation } from './interpretation'

export interface AINarrativeResponse {
  schema_version: string
  source_schema_version: string
  generated_at: string
  provider: string
  model: string
  opening_summary: string
  overall_narrative: string
  key_themes: string[]
  card_relationships: string[]
  reflective_synthesis: string
  reflection_questions: string[]
  scriptural_reflection: string | null
}

export interface AINarrativeSummary {
  id: string
  interpretation_id: string
  sequence: number
  created_at: string
  ai_narrative: AINarrativeResponse
}

// Re-exported only so a caller can reference Citation alongside this
// module without a second import -- the AI Narrative Layer itself never
// constructs a Citation (see AINarrativeResponse's own backend docstring:
// AI-generated prose does not carry field-level citations).
export type { Citation }

/**
 * POST /readings/{reading_id}/ai-narrative -- generates and persists a
 * new AI Narrative for the reading's current interpretation. Not
 * idempotent; every call creates a new AINarrative row (history is kept,
 * mirroring interpretReading()). Pass `includeScripture: true` to also
 * weave in the reading's current Scriptural Perspective -- omitted/false
 * means a purely tarot-based narrative, mirroring GET .../scripture's own
 * per-call, never-stored opt-in.
 */
export function generateAiNarrative(
  token: string,
  readingId: string,
  options: { includeScripture?: boolean } = {}
): Promise<AINarrativeSummary> {
  return request<AINarrativeSummary>(`/readings/${readingId}/ai-narrative`, {
    method: 'POST',
    token,
    query: { include_scripture: options.includeScripture ? 'true' : undefined },
  })
}

/**
 * GET /readings/{reading_id}/ai-narrative/current -- never generates;
 * 404 means no AI narrative has been generated for this reading's
 * current interpretation yet.
 */
export function getCurrentAiNarrative(token: string, readingId: string): Promise<AINarrativeSummary> {
  return request<AINarrativeSummary>(`/readings/${readingId}/ai-narrative/current`, { token })
}
