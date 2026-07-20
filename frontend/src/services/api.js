import { supabase } from '@/lib/supabase'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/**
 * Fetch wrapper for the TrackAI backend: injects the current Supabase access
 * token, JSON-encodes bodies, and throws on non-2xx with the server's detail.
 */
export async function api(path, { method = 'GET', body } = {}) {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token

  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail ?? detail
    } catch {
      /* non-JSON error body */
    }
    const err = new Error(detail)
    err.status = res.status
    throw err
  }
  return res.status === 204 ? null : res.json()
}
