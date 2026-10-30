import { useEffect, useState } from 'react'

// In production set VITE_API_URL (e.g. https://your-app.onrender.com). Locally it talks to Flask on :5000.
const BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:5000'

export async function get(path, params = {}) {
  const sp = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === '') return
    if (Array.isArray(v)) v.forEach((x) => sp.append(k, x))
    else sp.append(k, v)
  })
  const qs = sp.toString()
  const res = await fetch(`${BASE}/api${path}${qs ? `?${qs}` : ''}`)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`)
  return body
}

/** useApi('/city/Pune', {profile:'balanced'}) -> { data, error, loading }. Pass path=null to skip. */
export function useApi(path, params) {
  const key = path ? path + JSON.stringify(params || {}) : null
  const [state, setState] = useState({ data: null, error: null, loading: Boolean(path) })

  useEffect(() => {
    if (!path) {
      setState({ data: null, error: null, loading: false })
      return undefined
    }
    let alive = true
    setState((s) => ({ ...s, loading: true, error: null }))
    get(path, params)
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((e) => alive && setState({ data: null, error: e.message, loading: false }))
    return () => {
      alive = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key])

  return state
}

export function useDebounced(value, ms = 350) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}