import { Link, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

/**
 * Minimal application shell -- header/nav only. Grows as the Reading
 * experience does (New Reading added Step 47; History/Settings remain
 * for a later slice, Documentation/FRONTEND_INTEGRATION_DESIGN.md
 * Section 11).
 */
export function AppShell() {
  const { isAuthenticated, clearToken } = useAuth()

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex items-center justify-between border-b border-border px-6 py-4">
        <Link to="/" className="text-lg font-medium text-ink no-underline">
          Raidian
        </Link>
        <nav className="flex items-center gap-4 text-sm">
          {isAuthenticated ? (
            <>
              <Link to="/readings" className="text-ink-soft hover:text-ink">
                History
              </Link>
              <Link to="/readings/new" className="text-ink-soft hover:text-ink">
                New Reading
              </Link>
              <button
                type="button"
                onClick={clearToken}
                className="rounded-md border border-border px-3 py-1.5 text-ink-soft hover:bg-paper-muted"
              >
                Log out
              </button>
            </>
          ) : (
            <>
              <Link to="/login" className="text-ink-soft hover:text-ink">
                Log in
              </Link>
              <Link
                to="/register"
                className="rounded-md bg-accent px-3 py-1.5 text-paper no-underline hover:opacity-90"
              >
                Register
              </Link>
            </>
          )}
        </nav>
      </header>
      <main className="flex flex-1 flex-col px-6 py-8">
        <Outlet />
      </main>
    </div>
  )
}
