// Тонкая обёртка над fetch: единые заголовки, разбор ошибок, реакция на выход из сессии.

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

let onUnauthorized = () => {}
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn
}

// FastAPI отдаёт detail строкой или списком ошибок валидации
function formatDetail(detail) {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail
      .map((e) => {
        const field = (e.loc || []).slice(1).join('.')
        const msg = String(e.msg || '').replace(/^Value error, /, '')
        return field ? `${field}: ${msg}` : msg
      })
      .join('; ')
  }
  return 'Не удалось выполнить запрос'
}

async function request(method, path, { body, form, params } = {}) {
  const url = new URL('/api' + path, window.location.origin)
  for (const [key, value] of Object.entries(params || {})) {
    if (value !== null && value !== undefined && value !== '') url.searchParams.set(key, value)
  }

  // Этот заголовок серверу нужен для всех запросов на изменение (защита от CSRF)
  const headers = { 'X-Requested-With': 'wordday' }
  let payload
  if (form) {
    payload = form
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json'
    payload = JSON.stringify(body)
  }

  let res
  try {
    res = await fetch(url, { method, headers, body: payload, credentials: 'same-origin' })
  } catch {
    throw new ApiError(0, 'Нет связи с сервером')
  }

  const isJson = (res.headers.get('content-type') || '').includes('json')
  const data = isJson ? await res.json() : null
  if (res.status === 401 && path !== '/login') onUnauthorized()
  if (!res.ok) throw new ApiError(res.status, formatDetail(data?.detail))
  return data
}

export const api = {
  get: (path, params) => request('GET', path, { params }),
  post: (path, body) => request('POST', path, { body: body ?? {} }),
  put: (path, body) => request('PUT', path, { body }),
  upload: (path, file) => {
    const form = new FormData()
    form.append('file', file)
    return request('POST', path, { form })
  },
}
