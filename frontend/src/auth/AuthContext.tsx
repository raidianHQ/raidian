/**
 * Authentication state (Step 46,
 * Documentation/FRONTEND_INTEGRATION_DESIGN.md Section 5.1).
 *
 * Token storage: localStorage. Recommended, not silently mandated, by
 * the design document above -- tied directly to the backend's own
 * already-approved "no refresh tokens" decision
 * (AUTHENTICATION_OWNERSHIP_IMPLEMENTATION_DESIGN.md Section 7.11),
 * which makes a pure in-memory token impractical (it would force a
 * full re-login on every page reload, not merely after the 30-minute
 * expiry).
 *
 * The backend gives no distinct signal for "expired" vs. any other
 * invalid-token condition (every failure collapses into an identical
 * 401, unchanged since Step 22) -- `clearToken` is the uniform response
 * to any 401 from an authenticated call, not a token-specific parse.
 *
 * The `useAuth` hook lives in its own file (useAuth.ts), and the
 * context object in its own (authContext.ts), so this file exports only
 * the `AuthProvider` component -- react-refresh's own
 * only-export-components rule requires this split for Fast Refresh to
 * work correctly.
 */

import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { AuthContext, type AuthContextValue } from './context'

const STORAGE_KEY = 'raidian.token'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY))

  const setToken = useCallback((next: string) => {
    localStorage.setItem(STORAGE_KEY, next)
    setTokenState(next)
  }, [])

  const clearToken = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    setTokenState(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({ token, isAuthenticated: token !== null, setToken, clearToken }),
    [token, setToken, clearToken],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
