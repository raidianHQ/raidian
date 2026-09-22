import { useId, useState } from 'react'
import { EyeIcon, EyeOffIcon } from './icons'

/**
 * Password field with a show/hide toggle, shared by LoginPage and
 * RegisterPage. Visibility is purely a local render toggle (`type`
 * flips between "password"/"text") -- the value itself is never
 * touched, logged, or sent anywhere by this component, only read via
 * the caller's own `value`/`onChange`, exactly like a plain
 * `<input type="password">` would be.
 */
export function PasswordInput({
  id,
  value,
  onChange,
  autoComplete,
  required,
  minLength,
}: {
  id?: string
  value: string
  onChange: (value: string) => void
  autoComplete: string
  required?: boolean
  minLength?: number
}) {
  const [visible, setVisible] = useState(false)
  const generatedId = useId()
  const inputId = id ?? generatedId

  return (
    <div className="relative">
      <input
        id={inputId}
        type={visible ? 'text' : 'password'}
        required={required}
        minLength={minLength}
        autoComplete={autoComplete}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-xl border border-border bg-paper px-3 py-2 pr-10 text-ink"
      />
      <button
        type="button"
        onClick={() => setVisible((prev) => !prev)}
        aria-label={visible ? 'Hide password' : 'Show password'}
        className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-ink-soft transition-colors hover:text-accent"
      >
        {visible ? <EyeOffIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
      </button>
    </div>
  )
}
