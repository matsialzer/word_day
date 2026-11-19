export const num = (n) => Number(n ?? 0).toLocaleString('ru-RU')

// 5000 -> «5 000 сум»
export const sum = (n) => `${num(n)} сум`

export function date(value, withTime = false) {
  if (!value) return '—'
  const d = new Date(value)
  return d.toLocaleString('ru-RU', withTime
    ? { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' }
    : { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export const shortDay = (iso) => {
  const [, m, d] = iso.split('-')
  return `${d}.${m}`
}

export const REASONS = {
  top_week: 'Топ недели',
  streak_30: 'Серия 30 дней',
  words_100: '100 выученных слов',
}

export const FLAGS = {
  too_fast: 'Много слишком быстрых ответов',
  uniform_timing: 'Одинаковое время ответов (похоже на скрипт)',
  fast_median: 'Подозрительно быстрые ответы',
  perfect_accuracy: '100% точность на большом числе ответов',
}

export const LANGS = { ru: 'Русский', uz: "O'zbekcha" }
