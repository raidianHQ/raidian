import { Link, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { BottomNav } from './BottomNav'
import { CosmicBackground } from './CosmicBackground'
import { CrescentStarIcon } from './icons'

/**
 * Application shell (Step 47; restyled for the cosmic redesign --
 * Documentation/FRONTEND_INTEGRATION_DESIGN.md Section 11 for the
 * original scope). Still just header/nav/outlet -- routes and auth
 * behavior are unchanged, only the visual treatment: the header now
 * reads as part of the night-sky background (CosmicBackground) rather
 * than sitting inside a heavy solid navbar, per the design brief.
 *
 * Navigation is split by viewport rather than duplicated: "History" and
 * "New Reading" live in the header on sm+ screens, and in BottomNav
 * (mobile's elegant bottom bar, matching the design reference) below
 * that breakpoint. Log in/out/Register always stay in the header --
 * they aren't part of the reference's bottom-nav set.
 *
 * The unauthenticated header also hides whichever of Log in/Register
 * matches the current route -- otherwise the Login page would show a
 * "Log in" link to itself directly above its own login form (and
 * likewise for Register), which reads as a generic, not-quite-finished
 * navbar rather than a screen actually designed for what it's showing.
 */
export function AppShell() {
  const { isAuthenticated, clearToken } = useAuth()
  const location = useLocation()

  return (
    <div className="relative flex min-h-screen flex-col">
      <CosmicBackground />

      <header className="relative z-10 px-4 pt-8 pb-4 sm:px-8 sm:pt-12">
        <div className="mx-auto flex max-w-275 items-center justify-between gap-4">
          <div className="flex min-h-[2rem] items-center gap-4 text-sm tracking-widest uppercase">
            {isAuthenticated && (
              <Link
                to="/readings"
                className="hidden text-ink-soft no-underline transition-colors hover:text-accent sm:inline"
              >
                History
              </Link>
            )}
          </div>
          <div className="flex items-center gap-4 text-sm tracking-widest uppercase">
            {isAuthenticated ? (
              <>
                <Link
                  to="/readings/new"
                  className="hidden text-ink-soft no-underline transition-colors hover:text-accent sm:inline"
                >
                  New Reading
                </Link>
                <button
                  type="button"
                  onClick={clearToken}
                  className="rounded-full border border-border px-3.5 py-1.5 text-ink-soft transition-colors hover:border-accent hover:text-accent"
                >
                  Log out
                </button>
              </>
            ) : (
              <>
                {location.pathname !== '/login' && (
                  <Link to="/login" className="text-ink-soft no-underline transition-colors hover:text-accent">
                    Log in
                  </Link>
                )}
                {location.pathname !== '/register' && (
                  <Link
                    to="/register"
                    className="rounded-full border border-accent px-3.5 py-1.5 text-accent no-underline transition-colors hover:bg-accent hover:text-paper"
                  >
                    Register
                  </Link>
                )}
              </>
            )}
          </div>
        </div>

        {/* Brand hero -- logo mark, app name, main tagline, then the two
            atmospheric taglines (Same sky/New perspective and "A quieter
            mind...") as their own row underneath, in normal document flow
            (no `absolute`/`relative` positioning). Stacking them below the
            central Link, rather than beside it, means they can never
            overlap or share layout width with the wordmark -- that column
            is governed solely by its own content either way.
            The tagline row's own max-width is a `clamp()` built from the
            *same* `4vw + 0.5rem` term as the wordmark's font-size clamp
            above, scaled by a constant (~16, an estimate of the wordmark's
            average rendered width-per-font-size-unit at this
            tracking/letter-spacing) -- so the row's width grows and shrinks
            in lockstep with the wordmark's own clamp rather than against a
            single fixed breakpoint-tuned value, keeping its outer edges
            approximately aligned with the wordmark's own left/right edges
            at any viewport width, not just one tested size. It's centered
            by the outer column's `items-center`, with the two taglines
            spread to its own edges (`justify-between`, no extra inner
            padding) so they sit at that approximate wordmark-width
            boundary; as the viewport narrows, the row's width shrinks with
            the wordmark instead of disappearing or squeezing toward the
            center.
            Everything in the central Link is sized with `clamp()` (font
            size, icon dimensions) rather than a fixed value + breakpoint
            jump, so it shrinks continuously as the viewport narrows
            instead of holding its full desktop size until a breakpoint and
            then wrapping -- the clamp's own upper bound *is* the current
            desktop size (matches text-5xl/h-14/w-96 exactly), so nothing
            here is bigger than before, only more gracefully responsive
            below it. */}
        <div className="mx-auto mt-6 flex max-w-275 flex-col items-center gap-4 sm:mt-8">
          <Link to="/" className="flex flex-col items-center gap-4 text-center no-underline">
            <CrescentStarIcon className="h-[clamp(2rem,5vw,3.5rem)] w-[clamp(10rem,32vw,24rem)] text-accent" />
            <span className="font-serif text-[clamp(1.75rem,4vw+0.5rem,3rem)] tracking-[0.2em] whitespace-nowrap text-accent">
              RAIDIAN REFLECTION
            </span>
            <span className="text-sm font-medium tracking-[0.4em] text-accent uppercase sm:text-base">
              Reflect • Explore • Align
            </span>
          </Link>

          <div className="flex w-full max-w-[clamp(28rem,64vw+8rem,48rem)] items-start justify-between gap-6 sm:gap-10">
            <p className="max-w-40 text-left font-serif text-lg leading-relaxed text-ink-soft italic sm:max-w-48 sm:text-xl">
              Same sky
              <br />
              New perspective
            </p>

            <p className="max-w-40 text-right font-serif text-lg leading-relaxed text-ink-soft italic sm:max-w-48 sm:text-xl">
              &ldquo;A quieter mind
              <br />
              notices more.&rdquo;
            </p>
          </div>
        </div>
      </header>

      <main
        className={`relative z-10 mx-auto flex w-full max-w-275 flex-1 flex-col px-4 pt-6 sm:px-8 ${
          isAuthenticated ? 'pb-24 sm:pb-16' : 'pb-16'
        }`}
      >
        <Outlet />
      </main>

      {isAuthenticated && <BottomNav />}
    </div>
  )
}
