import { Link } from 'react-router-dom'

/**
 * Home (Step 47; updated Step 52) -- a calm welcome plus the two
 * meaningful next actions: starting a new reading, or reviewing saved
 * history (frontend/src/pages/ReadingHistoryPage.tsx, Step 52). Kept
 * deliberately minimal -- not a dashboard, no reading data fetched or
 * summarized here.
 */
export function HomePage() {
  return (
    <div className="mx-auto flex w-full max-w-lg flex-1 flex-col items-start justify-center gap-4">
      <h1 className="text-2xl font-medium text-ink">Welcome</h1>
      <p className="text-ink-soft">
        Raidian is a space for reflection -- a place to ask a question and sit with what the cards
        bring to mind, not a prediction of what will happen.
      </p>
      <div className="flex items-center gap-4">
        <Link
          to="/readings/new"
          className="rounded-md bg-accent px-4 py-2 text-paper no-underline hover:opacity-90"
        >
          Start a new reading
        </Link>
        <Link to="/readings" className="text-sm text-accent underline">
          View reading history
        </Link>
      </div>
    </div>
  )
}
