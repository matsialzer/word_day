<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import Icon from '../components/Icon.vue'
import Pager from '../components/Pager.vue'
import { api } from '../lib/api'
import { LANGS, date, num } from '../lib/format'
import { askConfirm, notify, notifyError } from '../lib/state'

const filters = reactive({ q: '', blocked: '' })
const page = ref(1)
const size = 25
const data = ref({ items: [], total: 0 })
const loading = ref(true)
let timer = null

async function load() {
  loading.value = true
  try {
    data.value = await api.get('/users', { ...filters, page: page.value, size })
  } catch (e) {
    notifyError(e)
  } finally {
    loading.value = false
  }
}
onMounted(load)
onBeforeUnmount(() => clearTimeout(timer))
watch(() => filters.q, () => { clearTimeout(timer); timer = setTimeout(() => { page.value = 1; load() }, 300) })
watch(() => filters.blocked, () => { page.value = 1; load() })

const who = (u) => (u.username ? `@${u.username}` : `id ${u.telegram_id}`)

async function setBlocked(u, blocked) {
  const ok = await askConfirm({
    title: blocked ? 'Заблокировать ученика?' : 'Разблокировать ученика?',
    text: blocked
      ? `${who(u)} перестанет получать слова, рассылки и не попадёт в бонусы.`
      : `${who(u)} снова сможет учиться и участвовать в бонусах.`,
    action: blocked ? 'Заблокировать' : 'Разблокировать',
    danger: blocked,
  })
  if (!ok) return
  try {
    Object.assign(u, await api.post(`/users/${u.id}/block`, { blocked }))
    notify(blocked ? 'Ученик заблокирован' : 'Ученик разблокирован')
  } catch (e) { notifyError(e) }
}
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Ученики</h1>
      <p>Блокировка — для тех, кого поймали на накрутке</p>
    </div>
  </div>

  <div class="toolbar">
    <input v-model="filters.q" class="grow" type="search" placeholder="Поиск: @username, телефон или Telegram ID" aria-label="Поиск" />
    <select v-model="filters.blocked" aria-label="Статус">
      <option value="">Все</option>
      <option value="false">Активные</option>
      <option value="true">Заблокированные</option>
    </select>
  </div>

  <div class="card">
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Ученик</th><th>Телефон</th><th>Язык</th><th>Уровень</th><th>XP</th><th>Серия</th><th>С нами с</th><th /></tr>
        </thead>
        <tbody>
          <tr v-for="u in data.items" :key="u.id" :class="{ 'is-off': u.is_blocked }">
            <td>
              <a v-if="u.username" :href="`https://t.me/${u.username}`" target="_blank" rel="noopener">@{{ u.username }}</a>
              <span v-else class="mono">id {{ u.telegram_id }}</span>
              <div v-if="!u.is_onboarded" class="muted small">не завершил настройку</div>
            </td>
            <td class="mono">{{ u.phone || '—' }}</td>
            <td>{{ LANGS[u.language] }}</td>
            <td><span class="badge badge-accent">{{ u.level }}</span></td>
            <td>{{ num(u.xp) }}</td>
            <td>{{ u.streak }} дн.</td>
            <td class="muted">{{ date(u.created_at) }}</td>
            <td>
              <div class="cell-actions">
                <span v-if="u.is_blocked" class="badge badge-danger">заблокирован</span>
                <button v-if="!u.is_blocked" class="btn btn-sm btn-danger" @click="setBlocked(u, true)"><Icon name="ban" :size="14" /> Заблокировать</button>
                <button v-else class="btn btn-sm" @click="setBlocked(u, false)">Разблокировать</button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="loading && !data.items.length" class="loading"><span class="spin" /></div>
    <div v-else-if="!data.items.length" class="empty">Никого не найдено</div>
    <Pager v-if="data.total > size" :page="page" :size="size" :total="data.total" @change="(p) => { page = p; load() }" />
  </div>
</template>
