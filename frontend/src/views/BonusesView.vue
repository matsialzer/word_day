<script setup>
import { onMounted, ref, watch } from 'vue'
import Icon from '../components/Icon.vue'
import { api } from '../lib/api'
import { FLAGS, REASONS, date, sum } from '../lib/format'
import { askConfirm, notify, notifyError } from '../lib/state'

const TABS = [
  { key: 'pending', label: 'На проверке' },
  { key: 'paid', label: 'Выплачено' },
  { key: 'rejected', label: 'Отклонено' },
]
const tab = ref('pending')
const items = ref([])
const counts = ref({ pending: 0, paid: 0, rejected: 0 })
const loading = ref(true)
const busyId = ref(null)

async function load() {
  loading.value = true
  try {
    ;[items.value, counts.value] = await Promise.all([
      api.get('/bonuses', { status: tab.value }),
      api.get('/bonuses/counts'),
    ])
  } catch (e) {
    notifyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(tab, load)

async function resolve(b, paid) {
  const ok = await askConfirm({
    title: paid ? 'Отметить как выплаченный?' : 'Отклонить бонус?',
    text: paid
      ? `${sum(b.amount)} — ${who(b)}. Ученик получит сообщение о выплате.`
      : `${sum(b.amount)} — ${who(b)}. Бюджет освободится, повторно бонус не создаётся.`,
    action: paid ? 'Выплачен' : 'Отклонить',
    danger: !paid,
  })
  if (!ok) return
  busyId.value = b.id
  try {
    const r = await api.post(`/bonuses/${b.id}/${paid ? 'pay' : 'reject'}`)
    if (paid && r.notified === false) notify('Отмечено как выплаченное, но ученику сообщение не доставлено', 'error', 7000)
    else notify(paid ? 'Отмечено как выплаченное' : 'Бонус отклонён')
    await load()
  } catch (e) {
    notifyError(e)
    await load()
  } finally {
    busyId.value = null
  }
}

const who = (b) => (b.username ? `@${b.username}` : `id ${b.telegram_id}`)

async function copy(text) {
  try {
    await navigator.clipboard.writeText(text)
    notify('Скопировано')
  } catch {
    notify('Не удалось скопировать', 'error')
  }
}
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Бонусы</h1>
      <p>Бот лишь предлагает победителей. Выплата — вручную после вашей проверки.</p>
    </div>
  </div>

  <div class="tabs" role="tablist">
    <button v-for="t in TABS" :key="t.key" role="tab" :aria-selected="tab === t.key" @click="tab = t.key">
      {{ t.label }} <span class="muted">{{ counts[t.key] }}</span>
    </button>
  </div>

  <div v-if="loading" class="loading"><span class="spin" /></div>
  <div v-else-if="!items.length" class="card empty">
    {{ tab === 'pending' ? 'Бонусов на проверке нет ✅' : 'Здесь пока пусто' }}
  </div>
  <div v-else class="stack">
    <article v-for="b in items" :key="b.id" class="card card-pad stack" style="gap: 12px">
      <div class="row" style="justify-content: space-between; align-items: flex-start">
        <div>
          <div style="font-size: 1.4rem; font-weight: 700">{{ sum(b.amount) }}</div>
          <div class="muted small">{{ REASONS[b.reason] }} · неделя с {{ date(b.week) }}</div>
        </div>
        <div v-if="b.status === 'pending'" class="actions">
          <button class="btn btn-ok" :disabled="busyId === b.id" @click="resolve(b, true)"><Icon name="check" :size="16" /> Выплачен</button>
          <button class="btn btn-danger" :disabled="busyId === b.id" @click="resolve(b, false)"><Icon name="x" :size="16" /> Отклонить</button>
        </div>
        <span v-else class="badge" :class="b.status === 'paid' ? 'badge-ok' : 'badge-danger'">
          {{ b.status === 'paid' ? 'выплачен' : 'отклонён' }} · {{ date(b.resolved_at, true) }}
        </span>
      </div>

      <div class="row" style="gap: 18px">
        <a v-if="b.username" :href="`https://t.me/${b.username}`" target="_blank" rel="noopener">@{{ b.username }}</a>
        <span v-else class="mono">id {{ b.telegram_id }}</span>
        <span class="row" style="gap: 6px">
          <span class="mono">{{ b.phone || '—' }}</span>
          <button v-if="b.phone" class="btn btn-icon btn-sm" title="Скопировать номер" aria-label="Скопировать номер" @click="copy(b.phone)"><Icon name="copy" :size="14" /></button>
        </span>
      </div>

      <div class="row">
        <span class="badge" :class="b.active_days >= 5 ? 'badge-ok' : ''">активных дней {{ b.active_days }}/7</span>
        <span class="badge" :class="b.accuracy >= 70 ? 'badge-ok' : ''">точность {{ b.accuracy }}%</span>
        <span class="badge">ответов {{ b.answers }}</span>
        <span class="badge" :class="b.test_passed ? 'badge-ok' : ''">тест {{ b.test_passed ? 'сдан' : 'не сдан' }}</span>
      </div>

      <div v-if="b.flags_block.length || b.flags_review.length" class="row">
        <span v-for="f in b.flags_block" :key="f" class="badge badge-danger">⚠ {{ FLAGS[f] }}</span>
        <span v-for="f in b.flags_review" :key="f" class="badge badge-warn">⚠ {{ FLAGS[f] }}</span>
      </div>
    </article>
  </div>
</template>
