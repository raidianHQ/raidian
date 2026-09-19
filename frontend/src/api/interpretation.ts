/**
 * Interpretation/Narrative API calls (Step 55), mirroring
 * backend/app/schemas/interpretive_model.py, narrative_model.py, and
 * interpretation_api.py field-for-field. Reuses the existing
 * request()/ApiError machinery (api/client.ts) -- no second HTTP
 * mechanism.
 *
 * Both the Interpretation Engine and the Narrative assembler are
 * deterministic (Documentation/READING_RESULT_FLOW_DESIGN.md Section 11)
 * -- nothing in this module calls, or is a client for, an AI provider.
 */

import { request } from './client'

export type EvidenceStrength = 'strong' | 'moderate' | 'weak' | 'unresolved'
export type SourceType = 'card_draw' | 'compound_rule' | 'structural_rule'
export type RuleTier = 'core' | 'conditional' | 'emergent'

export interface Citation {
  source_type: SourceType
  card_draw_id: string | null
  card_name: string | null
  position_name: string | null
  position_semantic_role: string | null
  contributing_theme: string | null
  rule_id: string | null
  rule_tier: RuleTier | null
}

export interface Explained<T> {
  value: T
  citations: Citation[]
}

export interface Tension {
  pole_a: string
  pole_b: string
  label: string
}

export interface TrajectoryStep {
  position_name: string
  semantic_role: string
  card_name: string
  orientation: 'upright' | 'reversed'
}

export interface Trajectory {
  arc: TrajectoryStep[]
}

export interface Contradiction {
  description: string
  sources: Citation[]
}

export interface InterpretiveModel {
  schema_version: string
  engine_version: string
  reference_data_version: string
  generated_at: string
  central_question: string
  central_issue: Explained<string>
  primary_tension: Explained<Tension> | null
  supporting_themes: Explained<string>[]
  trajectory: Explained<Trajectory> | null
  blocker: Explained<string> | null
  uncertainty: string[]
  advice: Explained<string> | null
  clarification: Explained<string> | null
  contradictions: Contradiction[]
  evidence_strength: EvidenceStrength
}

export interface InterpretationSummary {
  id: string
  reading_id: string
  sequence: number
  engine_version: string
  reference_data_version: string
  created_at: string
  interpretive_model: InterpretiveModel
}

export interface NarrativeStatement {
  text: string
  citations: Citation[]
}

export interface NarrativeSection {
  id: string
  title: string
  source_field: string | null
  present: boolean
  statements: NarrativeStatement[]
}

export interface NarrativeModel {
  schema_version: string
  narrative_template_version: string
  source_schema_version: string
  source_engine_version: string
  source_reference_data_version: string
  generated_at: string
  sections: NarrativeSection[]
}

/**
 * POST /readings/{reading_id}/interpret -- not idempotent; every call
 * creates a new Interpretation row (Documentation/READING_RESULT_FLOW_DESIGN.md
 * Section 3). Must only ever be called from an explicit user action, never
 * from a page load/refresh/effect.
 */
export function interpretReading(token: string, readingId: string): Promise<InterpretationSummary> {
  return request<InterpretationSummary>(`/readings/${readingId}/interpret`, {
    method: 'POST',
    token,
  })
}

/**
 * GET /readings/{reading_id}/interpretations/current -- 404 means "not
 * yet interpreted," the presence-detection mechanism this project's
 * design settled on (Documentation/READING_RESULT_FLOW_DESIGN.md Section 6)
 * rather than a new backend field. Safe to call on every page load/refresh
 * -- read-only, never generates anything.
 */
export function getCurrentInterpretation(token: string, readingId: string): Promise<InterpretationSummary> {
  return request<InterpretationSummary>(`/readings/${readingId}/interpretations/current`, { token })
}

/**
 * GET /readings/{reading_id}/narrative -- always recomputed fresh from
 * the current Interpretation, never cached/persisted. Safe to retry on
 * its own without re-triggering interpretation.
 */
export function getNarrative(token: string, readingId: string): Promise<NarrativeModel> {
  return request<NarrativeModel>(`/readings/${readingId}/narrative`, { token })
}
