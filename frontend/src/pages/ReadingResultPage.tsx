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
import { getCurrentScripture, getScripture, type ScripturalPerspective } from '../api/scripture'
import { useAuth } from '../auth/useAuth'
import { CardArtwork } from '../components/CardArtwork'
import { GoldDivider } from '../components/GoldDivider'
import { BookIcon, ConstellationIcon, ReflectionIcon, SpreadIcon } from '../components/icons'
import { SectionPanel } from '../components/Panel'

/**
 * Reading Result (Step 55; reorganized into a single guided-reflection
 * flow; restyled Step -- cosmic redesign) -- Documentation/
 * READING_RESULT_FLOW_DESIGN.md Sections 4/5/6/9. Renders everything
 * Raidian Wise knows about one Reading, in one linear "what are the
 * cards saying together?" progression: question -> spread -> opening
 * synthesis -> key themes -> each card -> relationships and patterns ->
 * the full deterministic reading -> optional Scripture -> closing
 * reflection and questions -> journal.
 *
 * The redesign groups this same, unchanged flow into three visually
 * distinct zones -- a hero (question/spread), "The Reading" panel
 * (everything the Interpretation Engine and Narrative/AI produced), and
 * "Your Reflection" panel (the closing prompt + this reading's own
 * Journal) -- separated by GoldDivider, per the design brief ("do not
 * place both sections into one large undifferentiated card"). This is a
 * presentation/grouping change only: no section here was added, removed,
 * or given new data-fetching/mutation behavior.
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
 * Four further, independent reads always run regardless of mode (each
 * degrades gracefully on its own if it fails -- none of them can block
 * the deterministic reading above from rendering):
 * - GET /readings/{id} for the spread/cards/artwork.
 * - GET /readings/{id}/ai-narrative/current -- a safe, free, read-only
 *   check for an AI reflection already generated in a prior visit (never
 *   triggers generation itself); a 404 just means "not generated yet."
 *   AiNarrativeState starts at 'checking', not 'idle', specifically so
 *   the "Generate AI Reflection" action cannot render -- and be clicked,
 *   firing a needless/possibly-failing new Anthropic request -- before
 *   this check has actually resolved.
 * - GET /readings/{id}/scripture/current -- the same safe, read-only
 *   check, one layer over, for a Scriptural Reflection snapshot already
 *   persisted in a prior visit; mirrors the AI Narrative check exactly,
 *   including its own 'checking' initial phase (ScriptureState).
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
    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
      <span className="text-sm text-ink-soft">Sources:</span>
      {citations.map((citation, index) => (
        <span
          key={index}
          className="rounded-full border border-border bg-paper-muted px-2 py-0.5 text-sm text-ink-soft"
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
      <h3 className="mb-1.5 text-sm font-medium tracking-wide text-accent uppercase sm:text-base">
        {section.title}
      </h3>
      {section.statements.map((statement, index) => (
        <p key={index} className="text-lg leading-relaxed text-ink sm:text-xl">
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
 * *Generating a new* Scripture selection is opt-in, never auto-triggered
 * (Documentation/RAIDIAN_WISE_PRODUCT_SPEC_V1.md Section 15.2 --
 * "Scripture Off" is the state where this simply stays 'idle' forever):
 * the user must explicitly click "Show Scriptural Reflection" before GET
 * /scripture is ever called. A persisted per-Reading/per-User preference
 * (Section 15.2's three-state setting) is future work -- this local,
 * request-scoped toggle is the minimal UI this foundation adds.
 *
 * Loading an *already-persisted* snapshot (GET .../scripture/current)
 * *is* automatic (a free, safe, read-only check on mount, mirroring
 * AiNarrativeState's own 'checking' phase above exactly) -- a
 * saved/reopened reading whose Scriptural Reflection was already shown
 * once displays it immediately, without the user re-clicking "Show
 * Scriptural Reflection". 'checking' is the true initial state; 'idle'
 * means "checked, no snapshot exists yet", offering the normal
 * click-to-select action.
 */
type ScriptureState =
  | { phase: 'checking' }
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
 *
 * 'checking' is the true initial state (not 'idle') and is what the
 * existence-check effect below starts in and stays in until GET
 * .../ai-narrative/current actually resolves -- 'idle' means "checked,
 * confirmed none exists yet", not "haven't looked". Collapsing those two
 * into one 'idle' state previously let the "Generate AI Reflection" CTA
 * render (and be clickable) during the initial check itself: on a slow
 * connection/cold backend, a user could click it and trigger a brand new
 * (and possibly failing) AI generation request even though a narrative
 * from a prior visit already existed and was about to load.
 */
type AiNarrativeState =
  | { phase: 'checking' }
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
  const [scriptureState, setScriptureState] = useState<ScriptureState>({ phase: 'checking' })
  const [aiNarrativeState, setAiNarrativeState] = useState<AiNarrativeState>({ phase: 'checking' })
  const [includeScriptureInAiNarrative, setIncludeScriptureInAiNarrative] = useState(false)

  /**
   * Save This Reading (Raidian Reading Lifecycle improvements): whether
   * there is currently anything new/changed for the user to persist by
   * clicking Save. Starts `false` and is set `true` only by an actual
   * change this visit -- a freshly-added journal entry, a freshly
   * *generated* AI Narrative, or a freshly *generated* Scriptural
   * Perspective (never by merely loading an already-persisted one of
   * either on mount, and never by viewing the interpretation or using
   * PDF/print, none of which touch this state at all). Also seeded
   * `true` once `readingDetail` first loads if this reading has never
   * been saved at all (`status !== 'saved'`) -- that first Save is
   * itself a legitimate pending action, since it is what makes the
   * reading appear in Reading History at all. Reset to `false` after a
   * successful Save (see handleSave), returning to the clean/disabled
   * state until another change occurs.
   */
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false)

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
        if (cancelled) return
        setReadingDetail(detail)
        // Save button dirty-tracking: a reading that has never been
        // saved has a genuine, legitimate pending action the instant it
        // loads (see hasUnsavedChanges's own docstring) -- checked here,
        // once, against the server's own persisted status, never
        // inferred from local session state.
        if (detail.status !== 'saved') {
          setHasUnsavedChanges(true)
        }
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
          return
        }
        // 404 ("not generated yet") or any other failure checking for an
        // existing narrative: move to 'idle', offering the "Generate AI
        // Reflection" action below -- never surfaced as an error the user
        // didn't cause. Explicit (rather than leaving the prior state)
        // so the CTA cannot render before this check has actually
        // resolved -- see AiNarrativeState's own docstring.
        setAiNarrativeState({ phase: 'idle' })
      })
    return () => {
      cancelled = true
    }
  }, [token, readingId, clearToken])

  // A previously-persisted Scriptural Reflection snapshot, if one
  // exists -- a free, read-only check, never a selection trigger. 404
  // ("no snapshot yet") is the ordinary, expected case and moves this to
  // 'idle', offering the normal "Show Scriptural Reflection" action.
  // Mirrors the AI Narrative existence-check effect above exactly.
  useEffect(() => {
    if (!token || !readingId) {
      return
    }
    let cancelled = false
    getCurrentScripture(token, readingId)
      .then((perspective) => {
        if (!cancelled) setScriptureState({ phase: 'loaded', perspective })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        if (err instanceof ApiError && err.status === 401) {
          clearToken()
          return
        }
        setScriptureState({ phase: 'idle' })
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
      setHasUnsavedChanges(false)
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
      setHasUnsavedChanges(true)
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
      setHasUnsavedChanges(true)
      // AI Narrative + Scriptural Reflection integration: when the user
      // opted in, the backend (generate_ai_narrative_for_reading) has
      // already selected -- and, if any approved reference was found,
      // persisted -- the Scriptural Perspective as part of this same
      // request. Surface it here too, so the separate Scriptural
      // Reflection section reflects it immediately and the user is never
      // required to click "Show Scriptural Reflection" a second time for
      // what they already asked for. A free, read-only check (never a
      // second selection call) -- mirrors the mount-time existence check
      // below exactly, including its own silent, no-error fallback: a
      // 404 here just means this reading's themes had no approved
      // match, which is a normal outcome, not something to surface as a
      // failure of an AI generation that otherwise succeeded.
      if (includeScriptureInAiNarrative) {
        void getCurrentScripture(token, readingId)
          .then((perspective) => setScriptureState({ phase: 'loaded', perspective }))
          .catch((scriptureErr: unknown) => {
            if (scriptureErr instanceof ApiError && scriptureErr.status === 401) {
              clearToken()
            }
          })
      }
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
      setHasUnsavedChanges(true)
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
      <div className="mx-auto w-full max-w-275">
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
      <div className="mx-auto w-full max-w-275">
        <h1 className="mb-2 font-serif text-3xl text-ink">Reading Result</h1>
        <div className="rounded-3xl border border-border bg-paper/80 px-4 py-6 text-center backdrop-blur-sm">
          <p className="text-sm text-ink-soft">This reading hasn't been interpreted yet.</p>
          <Link
            to={`/readings/${readingId}`}
            className="mt-4 inline-block rounded-full bg-accent px-4 py-2 text-sm text-paper hover:opacity-90"
          >
            Back to Spread Review
          </Link>
        </div>
      </div>
    )
  }

  if (!interpretation) {
    return (
      <div className="mx-auto w-full max-w-275">
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
    <div id="reading-print-area" className="-mt-12 mx-auto flex w-full max-w-275 flex-col">
      {/* 1 + 2. Hero -- "Your Reading" heading area, and the spread
          subtitle/question beneath it. Stays unboxed, directly on the
          cosmic background, matching the mockup -- the large gold
          divider below it is the first of the major-section transitions,
          not the hero's own closing rule.
          `-mt-12` here cancels AppShell's `<main>` own `pt-6` for this page
          specifically, plus one further small increment into the header's
          own bottom padding (empty space, no content sits there), pulling
          the whole reading content block -- heading, spread label,
          question, and everything below -- up together as one group,
          without touching AppShell's shared `<main>` padding used by every
          other page. */}
      <div className="mb-2 flex flex-col items-center gap-3 text-center">
        <h1 className="font-serif text-4xl text-ink sm:text-5xl">Your Reading</h1>
        {readingDetail && (
          <p className="text-xs font-medium tracking-[0.3em] text-accent uppercase">
            {readingDetail.spread.name}
            {positions.length > 0 && ` · ${positions.length}-Card Spread`}
          </p>
        )}
        <p className="max-w-2xl text-xl text-ink italic sm:text-2xl">&ldquo;{model.central_question}&rdquo;</p>
      </div>
      <GoldDivider size="lg" />

      {/* 3. The card spread -- its own major SectionPanel, distinct from
          "The Reading" below it (not a subsection sharing that panel).
          Individual cards have no bordered/filled box of their own (the
          "box around the box" the mockup doesn't have) -- only the card
          artwork's own frame (aspect-2/3, bg-paper) remains, plus the
          position label, name, and orientation badge as plain stacked
          text. */}
      {positions.length > 0 && (
        <SectionPanel
          title="Your Spread"
          icon={<SpreadIcon className="h-8 w-8 text-accent" />}
          className="print-break-before"
        >
          <div className="print-spread-grid grid grid-cols-2 gap-5 sm:grid-cols-3 sm:gap-7">
            {positions.map((position) => {
              const draw = drawByPositionName.get(position.name)
              if (!draw) return null
              return (
                <div
                  key={position.id}
                  className="print-spread-cell flex flex-col items-center gap-2 text-center break-inside-avoid"
                >
                  <span className="text-sm font-medium text-ink-soft sm:text-base">{position.name}</span>
                  <div className="print-card-frame aspect-2/3 w-full overflow-hidden rounded-xl bg-paper p-2 sm:p-3">
                    <CardArtwork card={draw.card} orientation={draw.orientation} />
                  </div>
                  <span className="font-serif text-base text-ink sm:text-lg">{draw.card.name}</span>
                  <span
                    className={`rounded-full px-2 py-0.5 text-sm ${
                      draw.orientation === 'reversed' ? 'bg-error-soft text-error' : 'bg-accent-soft text-accent'
                    }`}
                  >
                    {draw.orientation === 'reversed' ? '↓ Reversed' : '↑ Upright'}
                  </span>
                </div>
              )
            })}
          </div>
        </SectionPanel>
      )}

      <GoldDivider size="lg" />

      {/* 5 + 6. "The Reading" -- opening synthesis, key themes, card-by-
          card, relationships/patterns, and Scriptural Reflection. Its own
          major SectionPanel; the sub-parts within it (Key Themes, Card by
          Card, ...) use plain typography/dividers, never their own
          SectionPanel, so that treatment stays reserved for genuinely
          major sections. */}
      <SectionPanel title="The Reading" icon={<BookIcon className="h-8 w-8 text-accent" />}>
        {/* Opening synthesis -- AI's opening_summary/overall_narrative
            when available, else the deterministic Narrative's own
            opening prose. Either way, this is a synthesis OF the
            reading below it, never a replacement for it. */}
        <div className="flex flex-col gap-3">
          {aiLoaded ? (
            <>
              <p className="text-lg leading-relaxed text-ink sm:text-xl">{aiLoaded.opening_summary}</p>
              <p className="text-lg leading-relaxed text-ink sm:text-xl">{aiLoaded.overall_narrative}</p>
            </>
          ) : (
            <>
              {narrativeError && (
                <div className="no-print rounded-xl bg-error-soft px-3 py-2">
                  <p role="alert" className="text-sm text-error">
                    {narrativeError}
                  </p>
                  <button
                    type="button"
                    onClick={() => void handleRetryNarrative()}
                    className="mt-2 rounded-full bg-accent px-3 py-1.5 text-sm text-paper hover:opacity-90"
                  >
                    Try loading the reflection again
                  </button>
                </div>
              )}
              {!narrative && !narrativeError && (
                <p className="no-print text-sm text-ink-soft">Loading reflection…</p>
              )}
              {openingSections.map((section) => (
                <NarrativeSectionBlock key={section.id} section={section} />
              ))}
            </>
          )}

          {aiNarrativeState.phase === 'checking' && (
            <p className="no-print text-sm text-ink-soft">Checking for a previously generated AI reflection…</p>
          )}

          {/* AI generation entry point lives here, at the top of the flow it
              opens -- see AiNarrativeState's own docstring for why this is
              opt-in/not automatic. */}
          {aiNarrativeState.phase === 'idle' && (
            <div className="no-print rounded-2xl border border-dashed border-border bg-paper-muted p-3">
              <p className="mb-2 text-sm text-ink-soft">
                Generate an AI-written reflection woven through this reading -- optional, and always secondary to
                the structured analysis below.
              </p>
              <label className="mb-2 flex items-center gap-2 text-sm text-ink-soft">
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
                className="rounded-full bg-accent px-4 py-2 text-sm text-paper hover:opacity-90"
              >
                Generate AI Reflection
              </button>
            </div>
          )}
          {aiNarrativeState.phase === 'loading' && (
            <p className="no-print text-sm text-ink-soft">Generating your AI reflection…</p>
          )}
          {aiNarrativeState.phase === 'error' && (
            <div className="no-print rounded-xl bg-error-soft px-3 py-2">
              <p role="alert" className="text-sm text-error">
                {aiNarrativeState.error}
              </p>
              <p className="mt-1 text-sm text-ink-soft">
                Your reading is still complete without it -- see the structured reading below.
              </p>
              <button
                type="button"
                onClick={() => void handleGenerateAiNarrative()}
                className="mt-2 rounded-full bg-accent px-3 py-1.5 text-sm text-paper hover:opacity-90"
              >
                Try again
              </button>
            </div>
          )}
        </div>

        {/* Key themes. */}
        {keyThemes.length > 0 && (
          <div>
            <h2 className="mb-3 text-sm font-medium tracking-wide text-ink-soft uppercase sm:text-base">
              Key Themes
            </h2>
            <ul className="flex flex-wrap gap-2">
              {keyThemes.map((theme, index) => (
                <li key={index} className="rounded-full bg-accent-soft px-3 py-1 text-sm text-accent">
                  {theme}
                </li>
              ))}
            </ul>
            {!aiLoaded && !keyThemesSection && (
              <p className="mt-2 text-sm text-ink-soft">Themes carried by more than one card in this reading.</p>
            )}
          </div>
        )}

        {/* Individual card interpretations -- spacing/a thumbnail as the
            visual anchor for each entry, not a bordered box per card. */}
        <div>
          <h2 className="mb-4 text-sm font-medium tracking-wide text-ink-soft uppercase sm:text-base">
            Card by Card
          </h2>
          <div className="flex flex-col gap-8">
            {model.card_interpretations.map((card, index) => {
              const draw = drawByPositionName.get(card.position_name)
              return (
                <div key={index} className="flex gap-4 break-inside-avoid">
                  {draw && (
                    <div className="print-card-frame aspect-2/3 w-16 shrink-0 overflow-hidden rounded-lg bg-paper-muted sm:w-24">
                      <CardArtwork card={draw.card} orientation={card.orientation} />
                    </div>
                  )}
                  <div className="flex flex-col gap-2">
                    <p className="font-serif text-lg text-ink sm:text-xl">
                      {card.card_name}{' '}
                      <span className="font-sans text-sm text-ink-soft sm:text-base">— {card.position_name}</span>
                    </p>
                    <span
                      className={`self-start rounded-full px-2 py-0.5 text-sm ${
                        card.orientation === 'reversed' ? 'bg-error-soft text-error' : 'bg-accent-soft text-accent'
                      }`}
                    >
                      {card.orientation === 'reversed' ? '↓ Reversed' : '↑ Upright'}
                    </span>
                    <p className="text-lg leading-relaxed text-ink sm:text-xl">{card.meaning_text}</p>
                    <Citations citations={[card.citation]} />
                  </div>
                </div>
              )
            })}
          </div>
        </div>

        {/* Card relationships and patterns. */}
        <div>
          <h2 className="mb-3 text-sm font-medium tracking-wide text-ink-soft uppercase sm:text-base">
            How the Cards Connect
          </h2>
          <ul className="flex flex-col gap-3">
            {model.relationships.same_suit_clusters.map((cluster, index) => (
              <li key={`suit-${index}`} className="text-lg leading-relaxed text-ink sm:text-xl">
                The {cluster.suit} cards reinforce one another: {cluster.card_names.join(', ')}.
                <Citations citations={cluster.citations} />
              </li>
            ))}
            {totalCards > 1 && (
              <li className="text-lg leading-relaxed text-ink sm:text-xl">
                This reading draws {model.relationships.major_arcana_count} Major Arcana and{' '}
                {model.relationships.minor_arcana_count} Minor Arcana card
                {model.relationships.minor_arcana_count === 1 ? '' : 's'}.
              </li>
            )}
            {model.relationships.same_suit_clusters.length === 0 && totalCards <= 1 && (
              <li className="text-base text-ink-soft">Not enough cards in this reading to form a pattern.</li>
            )}
            {aiLoaded?.card_relationships.map((relationship, index) => (
              <li key={`ai-${index}`} className="text-lg leading-relaxed text-ink sm:text-xl">
                {relationship}
              </li>
            ))}
          </ul>
        </div>

        {/* Scriptural Reflection -- optional, opt-in (see ScriptureState's
            own docstring above). Deterministic theme -> Scripture reference
            mapping, never AI-generated, never presented as this reading's
            conclusion -- see the fixed disclaimer rendered with every
            result. Moved here (was after Structured Reading) now that
            Structured Reading is its own major SectionPanel below --
            this keeps it as the closing subsection of "The Reading"
            instead of being orphaned between two major panels. */}
        <div className="flex flex-col gap-4 border-t border-border pt-6">
          <h2 className="text-sm font-medium tracking-wide text-ink-soft uppercase sm:text-base">
            Scriptural Reflection (Optional)
          </h2>

          {scriptureState.phase === 'checking' && (
            <p className="no-print text-sm text-ink-soft">Checking for a previously shown Scriptural Reflection…</p>
          )}

          {scriptureState.phase === 'idle' && (
            <div className="no-print flex flex-col items-start gap-3">
              <p className="text-sm text-ink-soft">
                See whether any Scripture references connect to this reading's own established themes.
              </p>
              <button
                type="button"
                onClick={() => void handleShowScripture()}
                className="self-start rounded-full bg-accent px-4 py-2 text-sm text-paper hover:opacity-90"
              >
                Show Scriptural Reflection
              </button>
            </div>
          )}

          {scriptureState.phase === 'loading' && <p className="no-print text-sm text-ink-soft">Loading…</p>}

          {scriptureState.phase === 'error' && (
            <div className="no-print">
              <p role="alert" className="mb-2 rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
                {scriptureState.error}
              </p>
              <button
                type="button"
                onClick={() => void handleShowScripture()}
                className="rounded-full bg-accent px-3 py-1.5 text-sm text-paper hover:opacity-90"
              >
                Try again
              </button>
            </div>
          )}

          {scriptureState.phase === 'loaded' && (
            <>
              <p className="text-sm text-ink-soft italic">{scriptureState.perspective.disclaimer}</p>
              {scriptureState.perspective.reflections.length === 0 ? (
                <p className="text-base text-ink-soft">
                  None of this reading's themes have an approved Scripture reference yet.
                </p>
              ) : (
                <ul className="flex flex-col gap-5">
                  {scriptureState.perspective.reflections.map((reflection, index) => (
                    <li key={index} className="rounded-xl border border-border bg-paper-muted p-3 break-inside-avoid">
                      <p className="font-serif text-lg text-ink">
                        {reflection.reference_display} ({reflection.translation})
                      </p>
                      <p className="mt-1 text-sm tracking-wide text-ink-soft uppercase">Theme: {reflection.theme}</p>
                      <p className="mt-2 text-base leading-relaxed text-ink sm:text-lg">{reflection.context_note}</p>
                      <p className="mt-2 text-base text-ink-soft">{reflection.reflection_connection}</p>
                      <Citations citations={reflection.theme_citations} />
                    </li>
                  ))}
                </ul>
              )}
            </>
          )}
        </div>
      </SectionPanel>

      <GoldDivider size="lg" />

      {/* 7. The deterministic synthesis / supporting interpretation --
          what the engine concluded, and (collapsed by default) the full
          evidence behind it. Its own major SectionPanel now (was a
          divider-only subsection of "The Reading"), per the redesign's
          explicit call for a distinct "Structured Reading" section. */}
      <SectionPanel title="Structured Reading" icon={<ConstellationIcon className="h-8 w-8 text-accent" />}>
        <div className="flex flex-col gap-4">
          <p className="text-sm text-ink-soft">
            A structured analysis of your cards and positions -- no AI is used to produce this reading.
          </p>

          <p className="text-lg leading-relaxed text-ink sm:text-xl">{model.deterministic_synthesis.value}</p>
          <Citations citations={model.deterministic_synthesis.citations} />

          {remainingSections.map((section) => (
            <NarrativeSectionBlock key={section.id} section={section} />
          ))}

          <details className="rounded-xl border border-border">
            <summary className="cursor-pointer px-3 py-2 text-sm font-medium text-ink-soft select-none">
              See the supporting evidence
            </summary>
            <div className="flex flex-col gap-4 border-t border-border p-3">
              <div>
                <p className="text-sm font-medium tracking-wide text-ink-soft uppercase">Evidence strength</p>
                <p className="text-base text-ink sm:text-lg">
                  {EVIDENCE_STRENGTH_LABEL[model.evidence_strength] ?? model.evidence_strength}
                </p>
              </div>

              <div>
                <p className="text-sm font-medium tracking-wide text-ink-soft uppercase">Central issue</p>
                <p className="text-base leading-relaxed text-ink sm:text-lg">{model.central_issue.value}</p>
                <Citations citations={model.central_issue.citations} />
              </div>

              {model.primary_tension && (
                <div>
                  <p className="text-sm font-medium tracking-wide text-ink-soft uppercase">Primary tension</p>
                  <p className="text-base leading-relaxed text-ink sm:text-lg">
                    {model.primary_tension.value.pole_a} ↔ {model.primary_tension.value.pole_b} —{' '}
                    {model.primary_tension.value.label}
                  </p>
                  <Citations citations={model.primary_tension.citations} />
                </div>
              )}

              {model.supporting_themes.length > 0 && (
                <div>
                  <p className="text-sm font-medium tracking-wide text-ink-soft uppercase">Supporting themes</p>
                  <ul className="list-inside list-disc text-base leading-relaxed text-ink sm:text-lg">
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
                  <p className="text-sm font-medium tracking-wide text-ink-soft uppercase">Trajectory</p>
                  <ol className="list-inside list-decimal text-base leading-relaxed text-ink sm:text-lg">
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
                  <p className="text-sm font-medium tracking-wide text-ink-soft uppercase">Blocker</p>
                  <p className="text-base leading-relaxed text-ink sm:text-lg">{model.blocker.value}</p>
                  <Citations citations={model.blocker.citations} />
                </div>
              )}

              {model.advice && (
                <div>
                  <p className="text-sm font-medium tracking-wide text-ink-soft uppercase">Advice</p>
                  <p className="text-base leading-relaxed text-ink sm:text-lg">{model.advice.value}</p>
                  <Citations citations={model.advice.citations} />
                </div>
              )}

              {model.clarification && (
                <div>
                  <p className="text-sm font-medium tracking-wide text-ink-soft uppercase">Clarification</p>
                  <p className="text-base leading-relaxed text-ink sm:text-lg">{model.clarification.value}</p>
                  <Citations citations={model.clarification.citations} />
                </div>
              )}

              {model.uncertainty.length > 0 && (
                <div>
                  <p className="text-sm font-medium tracking-wide text-ink-soft uppercase">What remains unclear</p>
                  <ul className="list-inside list-disc text-base leading-relaxed text-ink sm:text-lg">
                    {model.uncertainty.map((item, index) => (
                      <li key={index}>{item}</li>
                    ))}
                  </ul>
                </div>
              )}

              {model.contradictions.length > 0 && (
                <div>
                  <p className="text-sm font-medium tracking-wide text-ink-soft uppercase">Contradictions</p>
                  <ul className="list-inside list-disc text-base leading-relaxed text-ink sm:text-lg">
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
        </div>
      </SectionPanel>

      <GoldDivider size="lg" fromLabel="Reading" toLabel="Reflection" />

      {/* 8 + 9. "Your Reflection" -- the closing reflection/reflection-
          questions prompt, leading into this reading's own Journal
          (create + list). Save-this-reading lives at the very end, as
          the natural closing action once reflecting is done. */}
      <SectionPanel title="Your Reflection" icon={<ReflectionIcon className="h-8 w-8 text-accent" />}>
        {/* Closing reflection -- AI's own when available, else the
            deterministic Narrative's "Overall Reflection" plus
            reading-grounded prompts. */}
        <div className="flex flex-col gap-4">
          <p className="text-lg leading-relaxed text-ink sm:text-xl">{closingReflectionText}</p>
          {aiLoaded?.scriptural_reflection && (
            <div>
              <p className="mb-1 text-sm font-medium tracking-wide text-ink-soft uppercase">Scriptural Perspective</p>
              <p className="text-lg leading-relaxed text-ink sm:text-xl">{aiLoaded.scriptural_reflection}</p>
            </div>
          )}
          <div>
            <p className="mb-1 text-sm font-medium tracking-wide text-ink-soft uppercase">Questions to sit with</p>
            <ul className="list-inside list-disc text-lg leading-relaxed text-ink sm:text-xl">
              {reflectionQuestions.map((question, index) => (
                <li key={index}>{question}</li>
              ))}
            </ul>
          </div>
        </div>

        {/* Journal -- always available, independent of AI/Scripture. Not
            included in the printed/PDF output by default (Journal is a
            private space, not "reading result" content). */}
        <div className="no-print flex flex-col gap-3 border-t border-border pt-6">
          <p className="text-sm text-ink-soft sm:text-base">
            A private space for your own response to this reading. Your journal entries belong to you.
          </p>

          {journalEntries.length > 0 && (
            <ul className="flex flex-col gap-3">
              {journalEntries.map((entry) => (
                <li key={entry.id} className="rounded-xl bg-paper-muted p-3">
                  <p className="text-base whitespace-pre-wrap text-ink">{entry.content}</p>
                  <p className="mt-1 text-sm text-ink-soft">{new Date(entry.created_at).toLocaleString()}</p>
                </li>
              ))}
            </ul>
          )}

          <form onSubmit={(event) => void handleAddJournalEntry(event)} className="flex flex-col gap-2">
            <label htmlFor="journal-entry" className="text-sm font-medium tracking-wide text-ink-soft uppercase">
              What stands out to you about this reading?
            </label>
            <textarea
              id="journal-entry"
              value={journalDraft}
              onChange={(event) => setJournalDraft(event.target.value)}
              rows={5}
              className="rounded-2xl border border-border bg-paper px-3 py-2.5 text-ink placeholder:text-ink-soft/70"
              placeholder="Write your own reflection here…"
            />
            {journalError && (
              <p role="alert" className="rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
                {journalError}
              </p>
            )}
            <button
              type="submit"
              disabled={journalSaving || !journalDraft.trim()}
              className="self-start rounded-full bg-accent px-4 py-2 text-sm text-paper hover:opacity-90 disabled:opacity-50"
            >
              {journalSaving ? 'Saving…' : 'Save to journal'}
            </button>
          </form>
        </div>

        {/* Save. mark_saved() is idempotent, so this action was previously
            offered unconditionally; it is now gated on hasUnsavedChanges
            (see that state's own docstring) so the button is only active
            when there is actually something new to persist -- a freshly
            added journal entry, a freshly generated AI Narrative or
            Scriptural Perspective, or a reading that has never been
            saved at all. Merely viewing/opening an already-saved reading,
            or viewing already-persisted interpretation/AI Narrative/
            Scripture loaded from a prior visit, leaves this disabled.
            The button itself is always rendered (never swapped out for
            static text) so it can re-activate the moment another change
            occurs, without needing a page reload. */}
        <div className="no-print border-t border-border pt-6">
          {saveState.phase === 'error' && (
            <p role="alert" className="mb-2 rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
              {saveState.error}
            </p>
          )}
          <button
            type="button"
            disabled={!hasUnsavedChanges || saveState.phase === 'saving'}
            onClick={() => void handleSave()}
            className="rounded-full bg-accent px-4 py-2 text-sm text-paper hover:opacity-90 disabled:opacity-50"
          >
            {saveState.phase === 'saving' ? 'Saving…' : hasUnsavedChanges ? 'Save this reading' : 'Saved'}
          </button>
        </div>
      </SectionPanel>

      <div className="no-print mt-8 flex flex-wrap items-center justify-center gap-3">
        <Link
          to={`/readings/${readingId}`}
          className="rounded-full border border-accent px-4 py-2 text-sm text-accent no-underline transition-colors hover:bg-accent hover:text-paper"
        >
          Back to Spread Review
        </Link>
        <button
          type="button"
          onClick={() => window.print()}
          className="rounded-full border border-accent px-4 py-2 text-sm text-accent transition-colors hover:bg-accent hover:text-paper"
        >
          Share / Save PDF
        </button>
      </div>
    </div>
  )
}
