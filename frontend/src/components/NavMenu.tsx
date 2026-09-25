import { useEffect, useId, useRef, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { CloseIcon, MenuIcon } from './icons'

/**
 * Global navigation hamburger menu (AppShell's header, upper-left) --
 * replaces the header's own previously-inline History/New Reading/Logout
 * links with one consistent entry point, matching BottomNav's own "only
 * real routes" discipline (App.tsx): New Reading (/readings/new), Reading
 * History (/readings), and Logout. No Account/Profile/Settings items --
 * neither route/feature exists in this app yet, and this menu does not
 * invent placeholder destinations to fill out a reference mockup.
 *
 * Only rendered while authenticated (see AppShell) -- Login/Register stay
 * as their own header links for a logged-out visitor, unchanged.
 */
export function NavMenu() {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const buttonRef = useRef<HTMLButtonElement>(null)
  const menuId = useId()
  const location = useLocation()
  const { clearToken } = useAuth()

  // Close on navigation -- a menu link's own onClick already closes it
  // before the route change commits, but this also covers any other way
  // the route could change while open (e.g. browser back/forward). A
  // render-time reset (React's own recommended pattern for "adjust state
  // when a prop changes"), not an effect -- setState directly in an
  // effect body triggers an extra, avoidable render pass.
  const [lastPathname, setLastPathname] = useState(location.pathname)
  if (location.pathname !== lastPathname) {
    setLastPathname(location.pathname)
    setOpen(false)
  }

  useEffect(() => {
    if (!open) {
      return
    }

    function handlePointerDown(event: PointerEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setOpen(false)
        buttonRef.current?.focus()
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    document.addEventListener('keydown', handleKeyDown)
    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      document.removeEventListener('keydown', handleKeyDown)
    }
  }, [open])

  const itemClassName =
    'block rounded-xl px-4 py-2.5 text-sm text-ink-soft no-underline transition-colors hover:bg-paper-muted hover:text-accent'

  return (
    <div ref={containerRef} className="relative">
      <button
        ref={buttonRef}
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="true"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={open ? 'Close menu' : 'Open menu'}
        className="flex h-10 w-10 items-center justify-center rounded-full border border-border text-accent transition-colors hover:border-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent"
      >
        {open ? <CloseIcon className="h-5 w-5" /> : <MenuIcon className="h-5 w-5" />}
      </button>

      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label="Main menu"
          className="absolute top-full left-0 z-30 mt-2 w-56 rounded-2xl border border-border bg-bg-deep/95 p-2 shadow-[0_20px_60px_-30px_rgba(0,0,0,0.7)] backdrop-blur-md"
        >
          <Link role="menuitem" to="/readings/new" className={itemClassName} onClick={() => setOpen(false)}>
            New Reading
          </Link>
          <Link role="menuitem" to="/readings" className={itemClassName} onClick={() => setOpen(false)}>
            Reading History
          </Link>
          <button
            role="menuitem"
            type="button"
            onClick={() => {
              setOpen(false)
              clearToken()
            }}
            className={`${itemClassName} w-full text-left`}
          >
            Log out
          </button>
        </div>
      )}
    </div>
  )
}
