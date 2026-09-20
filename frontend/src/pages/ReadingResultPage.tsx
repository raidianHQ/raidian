import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { Link, useLocation, useParams } from 'react-router-dom'
import { generateAiNarrative, getCurrentAiNarrative, type AINarrativeResponse } from '../api/aiNarrative'
import { ApiError } from '../api/client'
import {
  getCurrentInterpretation,
  getNarrative,
  type Citation,
  type InterpretationSummary,
  type InterpretiveModel,
  type NarrativeModel,
  type NarrativeSection,
} from '../api/interpretation'
import { createJournalEntry, listJournalEntries, type JournalEntry } from '../api/journal'
import { getReading, saveReading, type ReadingDetail, type ReadingStatus } from '../api/readings'
import { getScripture, type ScripturalPerspective } from '../api/scripture'
import { useAuth } from '../auth/useAuth'
import { CardArtwork } from '../components/CardArtwork'

/**
 * Reading Result (Step 55; reorganized into a single guided-reflection
 * flow) -- Documentation/READING_RESULT_FLOW_DESIGN.md Sections 4/5/6/9.
 * Renders everything Raidian Wise knows about one Reading, in one linear
 * "what are the cards saying together?" progression: question -> spread
 * -> opening synthesis -> key themes -> each card -> relationships and
 * patterns -> the full deterministic reading -> optional Scripture ->
 * closing reflection and questions -> journal.
 *
 * Two entry modes for the deterministic Interpretation/Narrative, per the
 * design doc Section 7:
 *
 * Mode A (fresh): SpreadReviewPage navigates here with the just-generated
 * `interpretation`/`narrative` already in `location.state` -- used
 * directly, no fetch performed at all.
 *
 * Mode B (revisit/refresh/direct navigation): no router state present.
 * Falls back to GET /interpretations/current + GET /narrative. A 404 from
 * the first call means "not yet interpreted" -- handled explicitly, never
 * treated as an error and never triggers POST /interpret automatically.
 *
 * Three further, independent reads always run regardless of mode (each
 * degrades gracefully on its own if it fails -- none of them can block
 * the deterministic reading above from rendering):
 * - GET /readings/{id} for the spread/cards/artwork.
 * - GET /readings/{id}/ai-narrative/current -- a safe, free, read-only
 *   check for an AI reflection already generated in a prior visit (never
 *   triggers generation itself); a 404 just means "not generated yet."
 * - GET /readings/{id}/journal-entries -- this reading's own private
 *   journal, always available independent of interpretation/AI/Scripture.
 *
 * The Interpretation Engine and Narrative assembler remain fully
 * deterministic and are never modified by this page. AI-generated content
 * (opening summary, key themes when AI is available, closing reflection,
 * reflection questions, and the optional Scriptural weave-in) is always
 * clearly a *synthesis of* the deterministic reading below it, never a
 * replacement for it -- when AI is unavailable or fails, this page falls
 * back to the deterministic Narrative's own "Your Reading"/"Overall
 * Reflection" prose and a small set of reading-grounded reflection
 * prompts, so the guided-reflection experience never goes empty.
 */

interface LocationState {
  interpretation?: InterpretationSummary
  narrative?: NarrativeModel
}

const EVIDENCE_STRENGTH_LABEL: Record<string, string> = {
  strong: 'Strong',
  moderate: 'Moderate',
  weak: 'Weak',
  unresolved: 'Unresolved',
}

// Narrative section ids (backend/app/services/narrative/sections.py) this
// page pulls out individually to serve as deterministic fallbacks/framing
// for specific slots in the flow, rather than rendering the Narrative as
// one undifferentiated block. Every other present section renders in the
// "complete deterministic reading" section, in the Narrative's own order.
const OPENING_SECTION_IDS = ['your_reading', 'central_theme']
const KEY_THEMES_SECTION_ID = 'what_the_spread_shows'
const CLOSING_SECTION_ID = 'overall_reflection'
const FRAMING_SECTION_IDS = new Set([...OPENING_SECTION_IDS, KEY_THEMES_SECTION_ID, CLOSING_SECTION_ID])

/**
 * Step 57 (F-1 fix, Documentation/FRONTEND_MVP_AUDIT.md): renders one
 * Citation using only fields the backend schema actually populates for
 * it (backend/app/schemas/interpretive_model.py::Citation).
 */
function citationLabel(citation: Citation): string {
  if (citation.source_type === 'card_draw') {
    const base = citation.position_name
      ? `${citation.card_name ?? 'A card'} — ${citation.position_name}`
      : (citation.card_name ?? 'A drawn card')
    return citation.contributing_theme ? `${base} (${citation.contributing_theme})` : base
  }
  const ruleName = citation.rule_id ? citation.rule_id.replace(/_/g, ' ') : 'a pattern in the spread'
  return citation.rule_tier ? `${ruleName} (${citation.rule_tier})` : ruleName
}

function Citations({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) {
    return null
  }
  return (
    <div className="mt-1 flex flex-wrap items-center gap-1.5">
      <span className="text-xs text-ink-soft">Sources:</span>
      {citations.map((citation, index) => (
        <span
          key={index}
          className="rounded-full border border-border bg-paper-muted px-2 py-0.5 text-xs text-ink-soft"
        >
          {citationLabel(citation)}
        </span>
      ))}
    </div>
  )
}

function NarrativeSectionBlock({ section }: { section: NarrativeSection }) {
  return (
    <div>
      <h3 className="mb-1 text-sm font-medium uppercase tracking-wide text-ink-soft">{section.title}</h3>
      {section.statements.map((statement, index) => (
        <p key={index} className="text-ink">
          {statement.text}
        </p>
      ))}
    </div>
  )
}

function findSection(narrative: NarrativeModel | null, id: string): NarrativeSection | undefined {
  return narrative?.sections.find((section) => section.id === id && section.present)
}

/**
 * Deterministic reflection prompts, grounded only in fields the
 * Interpretation Engine already produced -- the fallback for "Reflection
 * Questions" when no AI reflection has been generated. A natural
 * post-MVP concept already named in docs/NAMING_CONVENTIONS.md
 * ("Reflection Question... Questions should never attempt to lead users
 * toward predetermined conclusions"); this is plain client-side text
 * assembly, not a new interpretation rule.
 */
function fallbackReflectionQuestions(model: InterpretiveModel): string[] {
  const questions: string[] = [
    `What comes up for you when you sit with "${model.central_issue.value}"?`,
  ]
  if (model.uncertainty.length > 0) {
    // model.uncertainty entries are full sentences (e.g. "This spread
    // does not include an Advice position..."), not short phrases, so
    // this is stated plainly rather than quoted inline like the two
    // shorter, phrase-shaped fields below.
    questions.push(
      `This reading also names something it doesn't resolve: ${model.uncertainty[0]} What would help you feel clearer about that?`,
    )
  }
  if (model.advice) {
    questions.push(`How might "${model.advice.value}" apply to your actual situation right now?`)
  }
  return questions
}

type SaveState =
  | { phase: 'idle' }
  | { phase: 'saving' }
  | { phase: 'saved'; status: ReadingStatus }
  | { phase: 'error'; error: string }

/**
 * Scripture is opt-in, never auto-fetched (Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md
 * Section 15.2 -- "Scripture Off" is the state where this simply stays
 * 'idle' forever): the user must explicitly click "Show Scriptural
 * Reflection" before GET /scripture is ever called. A persisted per-
 * Reading/per-User preference (Section 15.2's three-state setting) is
 * future work -- this local, request-scoped toggle is the minimal UI
 * this foundation adds.
 */
type ScriptureState =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'loaded'; perspective: ScripturalPerspective }
  | { phase: 'error'; error: string }

/**
 * Generating a NEW AI narrative is opt-in and never idempotent -- nothing
 * calls POST /ai-narrative automatically. Loading a previously-generated
 * one (GET .../current) *is* automatic (a free, safe, read-only check on
 * mount), so a saved/reopened reading shows its prior AI reflection
 * immediately rather than making the user regenerate it -- see this
 * page's own module docstring.
 */
type AiNarrativeState =
  | { phase: 'idle' }
  | { phase: 'loading' }
  | { phase: 'loaded'; result: AINarrativeResponse }
  | { phase: 'error'; error: string }

export function ReadingResultPage() {
  const { readingId } = useParams<{ readingId: string }>()
  const { token, clearToken } = useAuth()
  const location = useLocation()

  // Mode A: initialized synchronously from router state (available on the
  // very first render, via a lazy initializer -- not set from inside an
  // effect body, which this project's lint rules correctly forbid).
  const passedState = (location.state as LocationState | null) ?? null
  const hasFreshResult = Boolean(passedState?.interpretation && passedState?.narrative)

  const [interpretation, setInterpretation] = useState<InterpretationSummary | null>(
    () => passedState?.interpretation ?? null,
  )
  const [narrative, setNarrative] = useState<NarrativeModel | null>(() => passedState?.narrative ?? null)
  const [notInterpreted, setNotInterpreted] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [narrativeError, setNarrativeError] = useState<string | null>(null)

  const [readingDetail, setReadingDetail] = useState<ReadingDetail | null>(null)

  const [saveState, setSaveState] = useState<SaveState>({ phase: 'idle' })
  const [scriptureState, setScriptureState] = useState<ScriptureState>({ phase: 'idle' })
  const [aiNarrativeState, setAiNarrativeState] = useState<AiNarrativeState>({ phase: 'idle' })
  const [includeScriptureInAiNarrative, setIncludeScriptureInAiNarrative] = useState(false)

  const [journalEntries, setJournalEntries] = useState<JournalEntry[]>([])
  const [journalDraft, setJournalDraft] = useState('')
  const [journalSaving, setJournalSaving] = useState(false)
  const [journalError, setJournalError] = useState<string | null>(null)

  useEffect(() => {
    if (!token || !readingId || hasFreshResult) {
      // Mode A is already fully satisfied by the lazy initializers above --
      // no fetch needed.
      return
    }
    let cancelled = false

    // Mode B: direct navigation, refresh, or a later revisit.
    async function loadExisting() {
      let current: InterpretationSummary
      try {
        current = await getCurrentInterpretation(token!, readingId!)
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          clearToken()
          return
        }
        if (err instanceof ApiError && err.status === 404) {
          setNotInterpreted(true)
          return
        }
        setLoadError(err instanceof ApiError ? err.message : 'Could not load this reading.')
        return
      }
      if (cancelled) return
      setInterpretation(current)

      try {
        const narrativeResult = await getNarrative(token!, readingId!)
        if (!cancelled) {
          setNarrative(narrativeResult)
        }
      } catch (err) {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          clearToken()
          return
        }
        setNarrativeError(err instanceof ApiError ? err.message : 'Could not load the narrative for this reading.')
      }
    }

    void loadExisting()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, readingId])

  // Spread/cards/artwork -- independent of interpretation load mode,
  // degrades silently (the section simply doesn't render) if it fails.
  useEffect(() => {
    if (!token || !readingId) {
      return
    }
    let cancelled = false
    getReading(token, readingId)
      .then((detail) => {
        if (!cancelled) setReadingDetail(detail)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          clearToken()
        }
        // Any other failure: the spread/card-artwork section is simply
        // omitted below -- the rest of the reading remains fully usable.
      })
    return () => {
      cancelled = true
    }
  }, [token, readingId, clearToken])

  // A previously-generated AI narrative, if one exists -- a free,
  // read-only check, never a generation trigger. 404 ("not generated
  // yet") is the ordinary, expected case and leaves this idle.
  useEffect(() => {
    if (!token || !readingId) {
      return
    }
    let cancelled = false
    getCurrentAiNarrative(token, readingId)
      .then((summary) => {
        if (!cancelled) setAiNarrativeState({ phase: 'loaded', result: summary.ai_narrative })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          clearToken()
        }
        // 404 or any other failure: stays 'idle', offering the "Generate
        // AI Reflection" action below -- never surfaced as an error the
        // user didn't cause.
      })
    return () => {
      cancelled = true
    }
  }, [token, readingId, clearToken])

  // This reading's own Journal, always available regardless of
  // interpretation/AI/Scripture state.
  useEffect(() => {
    if (!token || !readingId) {
      return
    }
    let cancelled = false
    listJournalEntries(token, readingId)
      .then((entries) => {
        if (!cancelled) setJournalEntries(entries)
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          clearToken()
        }
        // Any other failure: the journal simply starts empty -- writing a
        // new entry is still attempted independently below.
      })
    return () => {
      cancelled = true
    }
  }, [token, readingId, clearToken])

  const drawByPositionName = useMemo(() => {
    const map = new Map<string, ReadingDetail['card_draws'][number]>()
    readingDetail?.card_draws.forEach((draw) => map.set(draw.position.name, draw))
    return map
  }, [readingDetail])

  async function handleRetryNarrative() {
    if (!token || !readingId) {
      return
    }
    setNarrativeError(null)
    try {
      const narrativeResult = await getNarrative(token, readingId)
      setNarrative(narrativeResult)
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken()
        return
      }
      setNarrativeError(err instanceof ApiError ? err.message : 'Could not load the narrative for this reading.')
    }
  }

  async function handleSave() {
    if (!token || !readingId || saveState.phase === 'saving') {
      return
    }
    setSaveState({ phase: 'saving' })
    try {
      const result = await saveReading(token, readingId)
      setSaveState({ phase: 'saved', status: result.status })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken()
        return
      }
      setSaveState({
        phase: 'error',
        error: err instanceof ApiError ? err.message : 'Could not save this reading. Please try again.',
      })
    }
  }

  async function handleShowScripture() {
    if (!token || !readingId || scriptureState.phase === 'loading') {
      return
    }
    setScriptureState({ phase: 'loading' })
    try {
      const perspective = await getScripture(token, readingId)
      setScriptureState({ phase: 'loaded', perspective })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken()
        return
      }
      setScriptureState({
        phase: 'error',
        error: err instanceof ApiError ? err.message : 'Could not load the Scriptural Reflection. Please try again.',
      })
    }
  }

  async function handleGenerateAiNarrative() {
    if (!token || !readingId || aiNarrativeState.phase === 'loading') {
      return
    }
    setAiNarrativeState({ phase: 'loading' })
    try {
      const summary = await generateAiNarrative(token, readingId, {
        includeScripture: includeScriptureInAiNarrative,
      })
      setAiNarrativeState({ phase: 'loaded', result: summary.ai_narrative })
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken()
        return
      }
      setAiNarrativeState({
        phase: 'error',
        error: err instanceof ApiError ? err.message : 'Could not generate an AI reflection. Please try again.',
      })
    }
  }

  async function handleAddJournalEntry(event: FormEvent) {
    event.preventDefault()
    const content = journalDraft.trim()
    if (!token || !readingId || !content || journalSaving) {
      return
    }
    setJournalSaving(true)
    setJournalError(null)
    try {
      const entry = await createJournalEntry(token, readingId, content)
      setJournalEntries((prev) => [...prev, entry])
      setJournalDraft('')
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        clearToken()
        return
      }
      setJournalError(err instanceof ApiError ? err.message : 'Could not save your journal entry. Please try again.')
    } finally {
      setJournalSaving(false)
    }
  }

  if (loadError) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <p role="alert" className="rounded-md bg-error-soft px-3 py-2 text-sm text-error">
          {loadError}
        </p>
        <Link to={`/readings/${readingId}`} className="mt-4 inline-block text-sm text-accent underline">
          Back to Spread Review
        </Link>
      </div>
    )
  }

  if (notInterpreted) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <h1 className="mb-2 text-2xl font-medium text-ink">Reading Result</h1>
        <div className="rounded-lg border border-border bg-paper-muted px-4 py-6 text-center">
          <p className="text-sm text-ink-soft">This reading hasn't been interpreted yet.</p>
          <Link
            to={`/readings/${readingId}`}
            className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm text-paper hover:opacity-90"
          >
            Back to Spread Review
          </Link>
        </div>
      </div>
    )
  }

  if (!interpretation) {
    return (
      <div className="mx-auto w-full max-w-3xl">
        <p className="text-sm text-ink-soft">Loading…</p>
      </div>
    )
  }

  const model = interpretation.interpretive_model
  const positions = readingDetail?.spread.positions ?? []

  const openingSections = OPENING_SECTION_IDS.map((id) => findSection(narrative, id)).filter(
    (section): section is NarrativeSection => Boolean(section),
  )
  const keyThemesSection = findSection(narrative, KEY_THEMES_SECTION_ID)
  const closingSection = findSection(narrative, CLOSING_SECTION_ID)
  const remainingSections = (narrative?.sections ?? []).filter(
    (section) => section.present && !FRAMING_SECTION_IDS.has(section.id),
  )

  const aiLoaded = aiNarrativeState.phase === 'loaded' ? aiNarrativeState.result : null
  const keyThemes = aiLoaded?.key_themes.length
    ? aiLoaded.key_themes
    : model.supporting_themes.map((theme) => theme.value)
  const closingReflectionText = aiLoaded
    ? aiLoaded.reflective_synthesis
    : (closingSection?.statements.map((statement) => statement.text).join(' ') ?? model.deterministic_synthesis.value)
  const reflectionQuestions = aiLoaded?.reflection_questions.length
    ? aiLoaded.reflection_questions
    : fallbackReflectionQuestions(model)
  const totalCards = model.card_interpretations.length

  return (
    <div className="mx-auto w-full max-w-3xl">
      {/* 1. Question / intention */}
      <h1 className="mb-2 text-2xl font-medium text-ink">Reading Result</h1>
      <p className="mb-6 text-lg text-ink">{model.central_question}</p>

      {/* 2. Spread and positions -- the whole reading at a glance. */}
      {positions.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-1 text-sm font-medium uppercase tracking-wide text-ink-soft">Your Spread</h2>
          <p className="mb-3 text-xs text-ink-soft">
            {readingDetail?.spread.name}
            {readingDetail?.spread.description && <> — {readingDetail.spread.description}</>}
          </p>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {positions.map((position) => {
              const draw = drawByPositionName.get(position.name)
              if (!draw) return null
              return (
                <div key={position.id} className="flex flex-col items-center gap-2">
                  <span className="text-center text-sm font-medium text-ink">{position.name}</span>
                  <div className="flex w-full flex-col items-center gap-2 rounded-lg border-2 border-accent bg-paper p-2 text-center shadow-sm">
                    <div className="aspect-2/3 w-full overflow-hidden rounded-md bg-paper-muted">
                      <CardArtwork card={draw.card} orientation={draw.orientation} />
                    </div>
                    <span className="text-sm font-medium text-ink">{draw.card.name}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs ${
                        draw.orientation === 'reversed' ? 'bg-error-soft text-error' : 'bg-accent-soft text-ink'
                      }`}
                    >
                      {draw.orientation === 'reversed' ? '↓ Reversed' : '↑ Upright'}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </section>
      )}

      {/* 3. Opening synthesis -- AI's opening_summary/overall_narrative
          when available, else the deterministic Narrative's own opening
          prose. Either way, this is a synthesis OF the reading below it,
          never a replacement for it. */}
      <section className="mb-8 flex flex-col gap-3">
        {aiLoaded ? (
          <>
            <p className="text-ink">{aiLoaded.opening_summary}</p>
            <p className="text-ink">{aiLoaded.overall_narrative}</p>
          </>
        ) : (
          <>
            {narrativeError && (
              <div className="rounded-md bg-error-soft px-3 py-2">
                <p role="alert" className="text-sm text-error">
                  {narrativeError}
                </p>
                <button
                  type="button"
                  onClick={() => void handleRetryNarrative()}
                  className="mt-2 rounded-md bg-accent px-3 py-1.5 text-sm text-paper hover:opacity-90"
                >
                  Try loading the reflection again
                </button>
              </div>
            )}
            {!narrative && !narrativeError && <p className="text-sm text-ink-soft">Loading reflection…</p>}
            {openingSections.map((section) => (
              <NarrativeSectionBlock key={section.id} section={section} />
            ))}
          </>
        )}

        {/* AI generation entry point lives here, at the top of the flow it
            opens -- see AiNarrativeState's own docstring for why this is
            opt-in/not automatic. */}
        {aiNarrativeState.phase === 'idle' && (
          <div className="rounded-lg border border-dashed border-border bg-paper-muted p-3">
            <p className="mb-2 text-xs text-ink-soft">
              Generate an AI-written reflection woven through this reading -- optional, and always secondary to
              the deterministic analysis below.
            </p>
            <label className="mb-2 flex items-center gap-2 text-xs text-ink-soft">
              <input
                type="checkbox"
                checked={includeScriptureInAiNarrative}
                onChange={(event) => setIncludeScriptureInAiNarrative(event.target.checked)}
              />
              Include the Scriptural Perspective, if available
            </label>
            <button
              type="button"
              onClick={() => void handleGenerateAiNarrative()}
              className="rounded-md bg-accent px-4 py-2 text-sm text-paper hover:opacity-90"
            >
              Generate AI Reflection
            </button>
          </div>
        )}
        {aiNarrativeState.phase === 'loading' && (
          <p className="text-sm text-ink-soft">Generating your AI reflection…</p>
        )}
        {aiNarrativeState.phase === 'error' && (
          <div className="rounded-md bg-error-soft px-3 py-2">
            <p role="alert" className="text-sm text-error">
              {aiNarrativeState.error}
            </p>
            <p className="mt-1 text-xs text-ink-soft">
              Your reading is still complete without it -- see the deterministic reading below.
            </p>
            <button
              type="button"
              onClick={() => void handleGenerateAiNarrative()}
              className="mt-2 rounded-md bg-accent px-3 py-1.5 text-sm text-paper hover:opacity-90"
            >
              Try again
            </button>
          </div>
        )}
      </section>

      {/* 4. Key themes. */}
      {keyThemes.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-ink-soft">Key Themes</h2>
          <ul className="flex flex-wrap gap-2">
            {keyThemes.map((theme, index) => (
              <li key={index} className="rounded-full bg-accent-soft px-3 py-1 text-sm text-ink">
                {theme}
              </li>
            ))}
          </ul>
          {!aiLoaded && !keyThemesSection && (
            <p className="mt-2 text-xs text-ink-soft">Themes carried by more than one card in this reading.</p>
          )}
        </section>
      )}

      {/* 5. Individual card interpretations. */}
      <section className="mb-8">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-ink-soft">Card by Card</h2>
        <div className="flex flex-col gap-4">
          {model.card_interpretations.map((card, index) => {
            const draw = drawByPositionName.get(card.position_name)
            return (
              <div key={index} className="flex gap-3 rounded-lg border border-border p-3">
                {draw && (
                  <div className="aspect-2/3 w-16 shrink-0 overflow-hidden rounded-md bg-paper-muted sm:w-20">
                    <CardArtwork card={draw.card} orientation={card.orientation} />
                  </div>
                )}
                <div className="flex flex-col gap-1">
                  <p className="text-sm font-medium text-ink">
                    {card.card_name} <span className="text-ink-soft">— {card.position_name}</span>
                  </p>
                  <span
                    className={`self-start rounded-full px-2 py-0.5 text-xs ${
                      card.orientation === 'reversed' ? 'bg-error-soft text-error' : 'bg-accent-soft text-ink'
                    }`}
                  >
                    {card.orientation === 'reversed' ? '↓ Reversed' : '↑ Upright'}
                  </span>
                  <p className="text-sm text-ink">{card.meaning_text}</p>
                  <Citations citations={[card.citation]} />
                </div>
              </div>
            )
          })}
        </div>
      </section>

      {/* 6. Card relationships and patterns. */}
      <section className="mb-8">
        <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-ink-soft">
          How the Cards Connect
        </h2>
        <ul className="flex flex-col gap-2">
          {model.relationships.same_suit_clusters.map((cluster, index) => (
            <li key={`suit-${index}`} className="text-sm text-ink">
              The {cluster.suit} cards reinforce one another: {cluster.card_names.join(', ')}.
              <Citations citations={cluster.citations} />
            </li>
          ))}
          {totalCards > 1 && (
            <li className="text-sm text-ink">
              This reading draws {model.relationships.major_arcana_count} Major Arcana and{' '}
              {model.relationships.minor_arcana_count} Minor Arcana card
              {model.relationships.minor_arcana_count === 1 ? '' : 's'}.
            </li>
          )}
          {model.relationships.same_suit_clusters.length === 0 && totalCards <= 1 && (
            <li className="text-sm text-ink-soft">Not enough cards in this reading to form a pattern.</li>
          )}
          {aiLoaded?.card_relationships.map((relationship, index) => (
            <li key={`ai-${index}`} className="text-sm text-ink">
              {relationship}
            </li>
          ))}
        </ul>
      </section>

      {/* 7. Deterministic synthesis / supporting interpretation -- what
          the engine concluded, and (collapsed by default) the full
          evidence behind it. */}
      <section className="mb-8 flex flex-col gap-4 rounded-lg border border-border p-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-ink-soft">The Deterministic Reading</h2>
        <p className="text-xs text-ink-soft">
          A deterministic analysis of your cards and positions -- no AI is used to produce this reading.
        </p>

        <p className="text-ink">{model.deterministic_synthesis.value}</p>
        <Citations citations={model.deterministic_synthesis.citations} />

        {remainingSections.map((section) => (
          <NarrativeSectionBlock key={section.id} section={section} />
        ))}

        <details className="rounded-md border border-border">
          <summary className="cursor-pointer select-none px-3 py-2 text-sm font-medium text-ink-soft">
            See the supporting evidence
          </summary>
          <div className="flex flex-col gap-4 border-t border-border p-3">
            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Evidence strength</p>
              <p className="text-ink">
                {EVIDENCE_STRENGTH_LABEL[model.evidence_strength] ?? model.evidence_strength}
              </p>
            </div>

            <div>
              <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Central issue</p>
              <p className="text-ink">{model.central_issue.value}</p>
              <Citations citations={model.central_issue.citations} />
            </div>

            {model.primary_tension && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Primary tension</p>
                <p className="text-ink">
                  {model.primary_tension.value.pole_a} ↔ {model.primary_tension.value.pole_b} —{' '}
                  {model.primary_tension.value.label}
                </p>
                <Citations citations={model.primary_tension.citations} />
              </div>
            )}

            {model.supporting_themes.length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Supporting themes</p>
                <ul className="list-inside list-disc text-ink">
                  {model.supporting_themes.map((theme, index) => (
                    <li key={index}>
                      {theme.value}
                      <Citations citations={theme.citations} />
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {model.trajectory && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Trajectory</p>
                <ol className="list-inside list-decimal text-ink">
                  {model.trajectory.value.arc.map((step, index) => (
                    <li key={index}>
                      {step.position_name}: {step.card_name} ({step.orientation})
                    </li>
                  ))}
                </ol>
                <Citations citations={model.trajectory.citations} />
              </div>
            )}

            {model.blocker && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Blocker</p>
                <p className="text-ink">{model.blocker.value}</p>
                <Citations citations={model.blocker.citations} />
              </div>
            )}

            {model.advice && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Advice</p>
                <p className="text-ink">{model.advice.value}</p>
                <Citations citations={model.advice.citations} />
              </div>
            )}

            {model.clarification && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Clarification</p>
                <p className="text-ink">{model.clarification.value}</p>
                <Citations citations={model.clarification.citations} />
              </div>
            )}

            {model.uncertainty.length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">What remains unclear</p>
                <ul className="list-inside list-disc text-ink">
                  {model.uncertainty.map((item, index) => (
                    <li key={index}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {model.contradictions.length > 0 && (
              <div>
                <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Contradictions</p>
                <ul className="list-inside list-disc text-ink">
                  {model.contradictions.map((item, index) => (
                    <li key={index}>
                      {item.description}
                      <Citations citations={item.sources} />
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </details>
      </section>

      {/* 8. Scriptural Reflection -- optional, opt-in (see ScriptureState's
          own docstring above). Deterministic theme -> Scripture reference
          mapping, never AI-generated, never presented as this reading's
          conclusion -- see the fixed disclaimer rendered with every
          result. */}
      <section className="mb-8 flex flex-col gap-4 rounded-lg border border-border p-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-ink-soft">
          Scriptural Reflection (Optional)
        </h2>

        {scriptureState.phase === 'idle' && (
          <>
            <p className="text-xs text-ink-soft">
              See whether any Scripture references connect to this reading's own established themes.
            </p>
            <button
              type="button"
              onClick={() => void handleShowScripture()}
              className="self-start rounded-md bg-accent px-4 py-2 text-sm text-paper hover:opacity-90"
            >
              Show Scriptural Reflection
            </button>
          </>
        )}

        {scriptureState.phase === 'loading' && <p className="text-sm text-ink-soft">Loading…</p>}

        {scriptureState.phase === 'error' && (
          <div>
            <p role="alert" className="mb-2 rounded-md bg-error-soft px-3 py-2 text-sm text-error">
              {scriptureState.error}
            </p>
            <button
              type="button"
              onClick={() => void handleShowScripture()}
              className="rounded-md bg-accent px-3 py-1.5 text-sm text-paper hover:opacity-90"
            >
              Try again
            </button>
          </div>
        )}

        {scriptureState.phase === 'loaded' && (
          <>
            <p className="text-xs italic text-ink-soft">{scriptureState.perspective.disclaimer}</p>
            {scriptureState.perspective.reflections.length === 0 ? (
              <p className="text-sm text-ink-soft">
                None of this reading's themes have an approved Scripture reference yet.
              </p>
            ) : (
              <ul className="flex flex-col gap-4">
                {scriptureState.perspective.reflections.map((reflection, index) => (
                  <li key={index} className="rounded-md border border-border bg-paper-muted p-3">
                    <p className="text-sm font-medium text-ink">
                      {reflection.reference_display} ({reflection.translation})
                    </p>
                    <p className="mt-1 text-xs uppercase tracking-wide text-ink-soft">
                      Theme: {reflection.theme}
                    </p>
                    <p className="mt-2 text-sm text-ink">{reflection.context_note}</p>
                    <p className="mt-2 text-sm text-ink-soft">{reflection.reflection_connection}</p>
                    <Citations citations={reflection.theme_citations} />
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>

      {/* 9 + 10. Closing reflection and reflection questions -- AI's own
          when available, else the deterministic Narrative's "Overall
          Reflection" plus reading-grounded prompts. Either way, this is
          meant to lead naturally into the journal below. */}
      <section className="mb-8 flex flex-col gap-4 rounded-lg border border-border p-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-ink-soft">Sit With It</h2>
        <p className="text-ink">{closingReflectionText}</p>
        {aiLoaded?.scriptural_reflection && (
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-ink-soft">Scriptural Perspective</p>
            <p className="text-ink">{aiLoaded.scriptural_reflection}</p>
          </div>
        )}
        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wide text-ink-soft">
            Questions to sit with
          </p>
          <ul className="list-inside list-disc text-ink">
            {reflectionQuestions.map((question, index) => (
              <li key={index}>{question}</li>
            ))}
          </ul>
        </div>
      </section>

      {/* 11. Journal -- always available, independent of AI/Scripture. */}
      <section className="mb-8 flex flex-col gap-3 rounded-lg border border-border p-4">
        <h2 className="text-sm font-medium uppercase tracking-wide text-ink-soft">Journal</h2>
        <p className="text-xs text-ink-soft">
          A private space for your own response to this reading. Your journal entries belong to you.
        </p>

        {journalEntries.length > 0 && (
          <ul className="flex flex-col gap-3">
            {journalEntries.map((entry) => (
              <li key={entry.id} className="rounded-md bg-paper-muted p-3">
                <p className="whitespace-pre-wrap text-sm text-ink">{entry.content}</p>
                <p className="mt-1 text-xs text-ink-soft">{new Date(entry.created_at).toLocaleString()}</p>
              </li>
            ))}
          </ul>
        )}

        <form onSubmit={(event) => void handleAddJournalEntry(event)} className="flex flex-col gap-2">
          <label htmlFor="journal-entry" className="text-xs font-medium uppercase tracking-wide text-ink-soft">
            What stands out to you about this reading?
          </label>
          <textarea
            id="journal-entry"
            value={journalDraft}
            onChange={(event) => setJournalDraft(event.target.value)}
            rows={4}
            className="rounded-md border border-border bg-paper px-3 py-2 text-sm text-ink"
            placeholder="Write your own reflection here…"
          />
          {journalError && (
            <p role="alert" className="rounded-md bg-error-soft px-3 py-2 text-sm text-error">
              {journalError}
            </p>
          )}
          <button
            type="submit"
            disabled={journalSaving || !journalDraft.trim()}
            className="self-start rounded-md bg-accent px-4 py-2 text-sm text-paper hover:opacity-90 disabled:opacity-50"
          >
            {journalSaving ? 'Saving…' : 'Save to journal'}
          </button>
        </form>
      </section>

      {/* Save. mark_saved() is idempotent, so this action is offered
          unconditionally rather than fabricating a locally-known saved
          state (Documentation/READING_RESULT_FLOW_DESIGN.md Section 7). */}
      <section className="mb-8">
        {saveState.phase === 'saved' ? (
          <p className="rounded-md bg-accent-soft px-3 py-2 text-sm text-ink">
            This reading has been saved to your history.
          </p>
        ) : (
          <>
            {saveState.phase === 'error' && (
              <p role="alert" className="mb-2 rounded-md bg-error-soft px-3 py-2 text-sm text-error">
                {saveState.error}
              </p>
            )}
            <button
              type="button"
              disabled={saveState.phase === 'saving'}
              onClick={() => void handleSave()}
              className="rounded-md bg-accent px-4 py-2 text-sm text-paper hover:opacity-90 disabled:opacity-50"
            >
              {saveState.phase === 'saving' ? 'Saving…' : 'Save this reading'}
            </button>
          </>
        )}
      </section>

      <Link to={`/readings/${readingId}`} className="text-sm text-accent underline">
        Back to Spread Review
      </Link>
    </div>
  )
}
