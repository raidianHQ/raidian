/**
 * Shared HTTP wrapper around native `fetch` for the Raidian backend API
 * (Step 46, Documentation/FRONTEND_INTEGRATION_DESIGN.md Section 5).
 *
 * No HTTP client library is used -- the backend's contract (plain JSON
 * bodies, a Bearer auth header, and a consistent `{"detail": "..."}`
 * error shape on every non-2xx response, confirmed unchanged across
 * every backend route audited through Step 44) does not need one.
 */

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL

/** Mirrors the backend's own consistent error response shape. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
  }
}

interface RequestOptions {
  method?: 'GET' | 'POST'
  body?: unknown
  token?: string | null
  /** Query parameters appended to the URL; omitted keys/undefined values are skipped. */
  query?: Record<string, string | undefined>
}

function buildUrl(path: string, query?: Record<string, string | undefined>): string {
  const url = new URL(path, API_BASE_URL)
  if (query) {
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined) {
        url.searchParams.set(key, value)
      }
    }
  }
  return url.toString()
}

async function parseErrorDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (
      typeof body === 'object' &&
      body !== null &&
      'detail' in body &&
      typeof (body as { detail: unknown }).detail === 'string'
    ) {
      return (body as { detail: string }).detail
    }
  } catch {
    // Response body wasn't JSON (or had no `detail`) -- fall through to a generic message.
  }
  return `Request failed with status ${response.status}`
}

/**
 * Performs one API request. Attaches `Authorization: Bearer <token>`
 * when `token` is supplied; never attaches one otherwise (the three
 * reference-data routes are public and take no token,
 * Documentation/REFERENCE_DATA_CORS_DESIGN.md Section 5).
 *
 * Throws `ApiError` for any non-2xx response, carrying the backend's
 * own `detail` message -- callers decide how to present it, this layer
 * never swallows or reinterprets it.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {}
  if (options.token) {
    headers.Authorization = `Bearer ${options.token}`
  }
  if (options.body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }

  const response = await fetch(buildUrl(path, options.query), {
    method: options.method ?? 'GET',
    headers,
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  })

  if (!response.ok) {
    throw new ApiError(response.status, await parseErrorDetail(response))
  }

  if (response.status === 204) {
    return undefined as T
  }
  return (await response.json()) as T
}
