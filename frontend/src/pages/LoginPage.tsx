import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { login } from '../api/auth'
import { useAuth } from '../auth/useAuth'
import { Panel } from '../components/Panel'
import { PasswordInput } from '../components/PasswordInput'

export function LoginPage() {
  const { setToken } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const navigationState = location.state as { from?: string; registeredEmail?: string } | null

  const [email, setEmail] = useState(navigationState?.registeredEmail ?? '')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      const { access_token: accessToken } = await login(email, password)
      setToken(accessToken)
      navigate(navigationState?.from ?? '/', { replace: true })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center">
      <Panel>
        <h1 className="mb-6 text-center font-serif text-3xl text-ink">Log in</h1>
        {navigationState?.registeredEmail && (
          <p className="mb-4 rounded-xl bg-accent-soft px-3 py-2 text-sm text-accent">
            Account created. Log in to continue.
          </p>
        )}
        <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1 text-sm text-ink-soft">
            Email
            <input
              type="email"
              required
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="rounded-xl border border-border bg-paper px-3 py-2 text-ink"
            />
          </label>
          <div className="flex flex-col gap-1 text-sm text-ink-soft">
            <label htmlFor="login-password">Password</label>
            <PasswordInput
              id="login-password"
              required
              autoComplete="current-password"
              value={password}
              onChange={setPassword}
            />
          </div>
          {error && (
            <p role="alert" className="rounded-xl bg-error-soft px-3 py-2 text-sm text-error">
              {error}
            </p>
          )}
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-full bg-accent px-3 py-2 text-paper hover:opacity-90 disabled:opacity-60"
          >
            {isSubmitting ? 'Logging in…' : 'Log in'}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-ink-soft">
          Don&apos;t have an account?{' '}
          <Link to="/register" className="text-accent">
            Register
          </Link>
        </p>
      </Panel>
    </div>
  )
}
