import { createContext } from 'react'

export interface AuthContextValue {
  token: string | null
  isAuthenticated: boolean
  setToken: (token: string) => void
  clearToken: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)
