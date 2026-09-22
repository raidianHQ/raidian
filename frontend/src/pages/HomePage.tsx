import { Link } from 'react-router-dom'
import { Panel } from '../components/Panel'

/**
 * Home (Step 47; updated Step 52; restyled for the cosmic redesign) -- a
 * calm welcome plus the two meaningful next actions: starting a new
 * reading, or reviewing saved history (frontend/src/pages/
 * ReadingHistoryPage.tsx, Step 52). Kept deliberately minimal -- not a
 * dashboard, no reading data fetched or summarized here.
 */
export function HomePage() {
  return (
    <div className="mx-auto flex w-full max-w-lg flex-1 flex-col justify-center">
      <Panel className="flex flex-col items-center gap-5 text-center">
        <h1 className="font-serif text-3xl text-ink sm:text-4xl">Welcome</h1>
        <p className="text-ink-soft">
          Raidian Reflection is a quiet space to ask a question and sit with what the cards bring to mind,
          not a prediction of what will happen.
        </p>
        <div className="mt-2 flex flex-col items-center gap-3 sm:flex-row">
          <Link
            to="/readings/new"
            className="rounded-full bg-accent px-5 py-2.5 text-paper no-underline hover:opacity-90"
          >
            Start a new reading
          </Link>
          <Link to="/readings" className="text-sm text-accent underline">
            View reading history
          </Link>
        </div>
      </Panel>
    </div>
  )
}
