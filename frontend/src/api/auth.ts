/**
 * Auth API calls, mirroring backend/app/schemas/auth.py one-for-one
 * (Step 46, Documentation/FRONTEND_INTEGRATION_DESIGN.md Section 5).
 */

import { request } from './client'

export interface UserResponse {
  id: string
  email: string
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
}

/**
 * POST /auth/register -- does NOT authenticate the caller (no token in
 * the response, confirmed by the live backend contract, Step 39/44).
 * Callers must separately call `login` afterward.
 */
export function register(email: string, password: string): Promise<UserResponse> {
  return request<UserResponse>('/auth/register', {
    method: 'POST',
    body: { email, password },
  })
}

export function login(email: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>('/auth/login', {
    method: 'POST',
    body: { email, password },
  })
}
