// Небольшое общее состояние: сессия, уведомления, диалог подтверждения.
import { reactive } from 'vue'
import { api } from './api'

// ---- сессия ----
export const auth = reactive({ checked: false, authed: false })

export async function checkSession() {
  try {
    await api.get('/me')
    auth.authed = true
  } catch {
    auth.authed = false
  }
  auth.checked = true
  return auth.authed
}

export async function login(password) {
  await api.post('/login', { password })
  auth.authed = true
}

export async function logout() {
  try {
    await api.post('/logout')
  } finally {
    auth.authed = false
  }
}

// ---- уведомления ----
export const toasts = reactive([])
let toastId = 0

export function notify(message, kind = 'ok', ms = 4000) {
  const id = ++toastId
  toasts.push({ id, message, kind })
  setTimeout(() => {
    const i = toasts.findIndex((t) => t.id === id)
    if (i >= 0) toasts.splice(i, 1)
  }, ms)
}

export const notifyError = (e) => notify(e?.message || 'Произошла ошибка', 'error', 6000)

// ---- подтверждение опасных действий ----
export const confirmState = reactive({ open: false, title: '', text: '', action: '', danger: false })
let resolver = null

export function askConfirm({ title, text = '', action = 'Подтвердить', danger = false }) {
  Object.assign(confirmState, { open: true, title, text, action, danger })
  return new Promise((resolve) => (resolver = resolve))
}

export function answerConfirm(value) {
  confirmState.open = false
  resolver?.(value)
  resolver = null
}
