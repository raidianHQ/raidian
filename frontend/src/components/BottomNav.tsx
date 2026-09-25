import { NavLink } from 'react-router-dom'
import { HomeIcon, NewReadingIcon, ReadingsIcon } from './icons'

/**
 * Global primary navigation -- the reference design's elegant bottom-nav
 * treatment, now the one consistent nav surface across every viewport
 * (see AppShell), not just mobile. Built only from routes this app
 * actually has (App.tsx): Home ("/"), Reading History ("/readings",
 * labeled "Readings" to match the reference's naming), and New Reading
 * ("/readings/new"). No Journal/Explore/Resources items -- those aren't
 * routes here (Journal is per-Reading, inline on ReadingResultPage, not
 * its own destination) and this does not invent new pages to fill out
 * the reference mockup's full five-item set.
 */
const ITEMS: { to: string; label: string; icon: typeof HomeIcon; end?: boolean }[] = [
  { to: '/', label: 'Home', icon: HomeIcon, end: true },
  { to: '/readings', label: 'Readings', icon: ReadingsIcon },
  { to: '/readings/new', label: 'New Reading', icon: NewReadingIcon },
]

export function BottomNav() {
  return (
    <nav
      aria-label="Primary"
      className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-[var(--color-bg-deep)]/95 px-2 pt-2 backdrop-blur-md"
      style={{ paddingBottom: 'max(env(safe-area-inset-bottom, 0px), 0.5rem)' }}
    >
      <ul className="mx-auto flex max-w-md items-center justify-around">
        {ITEMS.map(({ to, label, icon: Icon, end }) => (
          <li key={to}>
            <NavLink
              to={to}
              end={end}
              className={({ isActive }) =>
                `flex flex-col items-center gap-1 rounded-xl px-4 py-1.5 text-[0.62rem] tracking-wide uppercase no-underline transition-colors ${
                  isActive ? 'text-accent' : 'text-ink-soft'
                }`
              }
            >
              <Icon className="h-5 w-5" />
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  )
}
