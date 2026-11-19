<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import Icon from '../components/Icon.vue'
import { api } from '../lib/api'
import { num } from '../lib/format'
import { askConfirm, notify, notifyError } from '../lib/state'

const MAX = 3500
const text = ref('')
const status = ref(null)
const busy = ref(false)
let poll = null

async function refresh() {
  try {
    status.value = await api.get('/broadcast')
    if (!status.value.running) stopPolling()
  } catch (e) {
    stopPolling()
    notifyError(e)
  }
}
function startPolling() { stopPolling(); poll = setInterval(refresh, 1000) }
function stopPolling() { clearInterval(poll); poll = null }

onMounted(async () => {
  await refresh()
  if (status.value?.running) startPolling()
})
onBeforeUnmount(stopPolling)

const done = computed(() => (status.value ? status.value.sent + status.value.blocked + status.value.failed : 0))
const percent = computed(() => (status.value?.total ? Math.round((100 * done.value) / status.value.total) : 0))
const finished = computed(() => status.value && !status.value.running && status.value.finished_at)

async function send() {
  const ok = await askConfirm({
    title: 'Отправить рассылку?',
    text: `Сообщение получат ${num(status.value.audience)} учеников. Отменить отправку после старта нельзя.`,
    action: 'Отправить',
  })
  if (!ok) return
  busy.value = true
  try {
    await api.post('/broadcast', { text: text.value })
    notify('Рассылка запущена')
    text.value = ''
    await refresh()
    startPolling()
  } catch (e) {
    notifyError(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Рассылка</h1>
      <p>Одно сообщение всем активным ученикам в Telegram</p>
    </div>
  </div>

  <div v-if="!status" class="loading"><span class="spin" /></div>
  <div v-else class="stack" style="max-width: 720px">
    <section class="card card-pad stack">
      <label class="field">
        Текст сообщения
        <textarea v-model="text" :maxlength="MAX" rows="7" placeholder="Например: завтра добавим новые слова уровня B1!" :disabled="status.running" />
        <span class="hint" style="align-self: flex-end">{{ text.length }} / {{ MAX }}</span>
      </label>
      <div class="row" style="justify-content: space-between">
        <span class="muted small">Получателей: <b>{{ num(status.audience) }}</b> (заблокированные не включены). Текст отправляется как обычный, без разметки.</span>
        <button class="btn btn-primary" :disabled="busy || status.running || !text.trim() || !status.audience" @click="send">
          <Icon name="send" :size="16" /> Отправить
        </button>
      </div>
    </section>

    <section v-if="status.running || finished" class="card card-pad stack" style="gap: 10px" aria-live="polite">
      <div class="row" style="justify-content: space-between">
        <h2>{{ status.running ? 'Идёт отправка…' : 'Последняя рассылка завершена' }}</h2>
        <span class="muted small">{{ done }} из {{ status.total }}</span>
      </div>
      <div class="bar"><span :style="{ width: percent + '%' }" /></div>
      <div class="row">
        <span class="badge badge-ok">доставлено {{ status.sent }}</span>
        <span class="badge">заблокировали бота {{ status.blocked }}</span>
        <span class="badge" :class="status.failed ? 'badge-danger' : ''">ошибок {{ status.failed }}</span>
      </div>
    </section>
  </div>
</template>
