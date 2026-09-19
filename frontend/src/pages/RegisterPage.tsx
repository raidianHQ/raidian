import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { register } from '../api/auth'

/**
 * POST /auth/register does not authenticate the caller (Step 46,
 * Documentation/FRONTEND_INTEGRATION_DESIGN.md "Register / Login"
 * data-flow section) -- successful registration navigates to /login
 * with the email pre-filled, rather than silently auto-logging in, to
 * keep Register and Login as the two distinct actions the backend
 * contract itself treats them as.
 */
export function RegisterPage() {
  const navigate = useNavigate()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setIsSubmitting(true)
    try {
      await register(email, password)
      navigate('/login', { replace: true, state: { registeredEmail: email } })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-sm">
      <h1 className="mb-6 text-2xl font-medium text-ink">Register</h1>
      <form onSubmit={(event) => void handleSubmit(event)} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm text-ink-soft">
          Email
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="rounded-md border border-border bg-paper px-3 py-2 text-ink"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-ink-soft">
          Password
          <input
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="rounded-md border border-border bg-paper px-3 py-2 text-ink"
          />
        </label>
        {error && (
          <p role="alert" className="rounded-md bg-error-soft px-3 py-2 text-sm text-error">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-md bg-accent px-3 py-2 text-paper hover:opacity-90 disabled:opacity-60"
        >
          {isSubmitting ? 'Creating account…' : 'Create account'}
        </button>
      </form>
      <p className="mt-4 text-sm text-ink-soft">
        Already have an account?{' '}
        <Link to="/login" className="text-accent">
          Log in
        </Link>
      </p>
    </div>
  )
}
