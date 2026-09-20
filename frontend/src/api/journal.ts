/**
 * Journal API calls, mirroring backend/app/schemas/journal.py
 * field-for-field. A Journal entry is a private, user-written reflection
 * attached to a Reading -- entirely independent of
 * interpretation/AI/Scripture (docs/NAMING_CONVENTIONS.md's "Journal").
 */

import { request } from './client'

export interface JournalEntry {
  id: string
  reading_id: string
  sequence: number
  content: string
  created_at: string
}

/** POST /readings/{reading_id}/journal-entries */
export function createJournalEntry(token: string, readingId: string, content: string): Promise<JournalEntry> {
  return request<JournalEntry>(`/readings/${readingId}/journal-entries`, {
    method: 'POST',
    token,
    body: { content },
  })
}

/** GET /readings/{reading_id}/journal-entries -- oldest first. */
export function listJournalEntries(token: string, readingId: string): Promise<JournalEntry[]> {
  return request<JournalEntry[]>(`/readings/${readingId}/journal-entries`, { token })
}
