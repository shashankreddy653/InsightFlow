/** Minimal typed fetch wrapper around the InsightFlow API. */

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || ''
).replace(/\/$/, '')

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`

  const res = await fetch(url, {
    headers:
      options.body instanceof FormData
        ? {}
        : { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!res.ok) {
    let detail = `Request failed (${res.status})`

    try {
      const body = await res.json()

      if (typeof body?.detail === 'string') {
        detail = body.detail
      } else if (Array.isArray(body?.detail)) {
        detail = body.detail
          .map((d: { msg?: string }) => d.msg ?? JSON.stringify(d))
          .join('; ')
      }
    } catch {
      // Keep the default message.
    }

    throw new Error(detail)
  }

  return res.json() as Promise<T>
}

export const api = {
  get: <T,>(path: string) => request<T>(path),

  post: <T,>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      body:
        body instanceof FormData
          ? body
          : JSON.stringify(body ?? {}),
    }),

  patch: <T,>(path: string, body: unknown) =>
    request<T>(path, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),
}

export function downloadFile(path: string, filename?: string) {
  const url = `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`

  fetch(url)
    .then((res) => {
      if (!res.ok) {
        throw new Error(`Download failed (${res.status})`)
      }

      return res.blob()
    })
    .then((blob) => {
      const objectUrl = URL.createObjectURL(blob)
      const a = document.createElement('a')

      a.href = objectUrl
      a.download = filename ?? path.split('/').pop() ?? 'download'

      document.body.appendChild(a)
      a.click()
      a.remove()

      URL.revokeObjectURL(objectUrl)
    })
    .catch((err) =>
      alert(err instanceof Error ? err.message : 'Download failed')
    )
}