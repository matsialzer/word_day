<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { api } from '../lib/api'
import { sum } from '../lib/format'
import { notify, notifyError } from '../lib/state'

const server = ref(null)
const form = reactive({ words_per_day: 10, top_n: 3, weekly_budget: 0, monthly_budget: 0 })
const busy = ref(false)
const error = ref('')

function apply(s) {
  server.value = s
  for (const k of Object.keys(form)) form[k] = s[k]
}
onMounted(async () => {
  try { apply(await api.get('/settings')) } catch (e) { notifyError(e) }
})

const dirty = computed(() => server.value && Object.keys(form).some((k) => form[k] !== server.value[k]))

// Сколько максимум может уйти за неделю при заданном топе (верхняя граница суммы)
const maxTop = computed(() => (server.value ? form.top_n * server.value.amount_range[1] : 0))
const overBudget = computed(() => server.value && maxTop.value > form.weekly_budget)
const monthLessWeek = computed(() => form.monthly_budget < form.weekly_budget)

async function save() {
  error.value = ''
  busy.value = true
  try {
    const body = Object.fromEntries(Object.keys(form).map((k) => [k, Number(form[k])]))
    apply(await api.put('/settings', body))
    notify('Настройки сохранены')
  } catch (e) {
    error.value = e.message
    notifyError(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Настройки</h1>
      <p>Изменения применяются без перезапуска бота</p>
    </div>
  </div>

  <div v-if="!server" class="loading"><span class="spin" /></div>
  <form v-else class="stack" style="max-width: 720px" @submit.prevent="save">
    <section class="card card-pad stack">
      <h2>Обучение</h2>
      <label class="field">
        Новых слов в день
        <input v-model.number="form.words_per_day" type="number" :min="server.limits.words_per_day[0]" :max="server.limits.words_per_day[1]" required />
        <span class="hint">От {{ server.limits.words_per_day[0] }} до {{ server.limits.words_per_day[1] }}. Действует со следующей выдачи; уже выданные наборы не меняются.</span>
      </label>
    </section>

    <section class="card card-pad stack">
      <h2>Бонусы</h2>
      <div class="form-grid">
        <label class="field">
          Победителей в «топе недели»
          <input v-model.number="form.top_n" type="number" :min="server.limits.top_n[0]" :max="server.limits.top_n[1]" required />
          <span class="hint">Суммы от {{ sum(server.amount_range[1]) }} (1-е место) до {{ sum(server.amount_range[0]) }}</span>
        </label>
        <span />
        <label class="field">
          Бюджет на неделю, сум
          <input v-model.number="form.weekly_budget" type="number" min="0" step="1000" required />
          <span class="hint">Уже начислено: {{ sum(server.used_week) }}</span>
        </label>
        <label class="field">
          Бюджет на месяц, сум
          <input v-model.number="form.monthly_budget" type="number" min="0" step="1000" required />
          <span class="hint">Уже начислено: {{ sum(server.used_month) }}</span>
        </label>
      </div>
      <div v-if="overBudget" class="alert warn">
        Топ из {{ form.top_n }} может стоить до {{ sum(maxTop) }} — больше недельного бюджета. Нижние места останутся без бонуса.
      </div>
      <div v-if="monthLessWeek" class="alert warn">Месячный бюджет меньше недельного — недельный лимит не будет достигнут.</div>
      <p class="muted small">Бот никогда не создаст бонус сверх этих лимитов. Новые значения учитываются при следующем расчёте (понедельник).</p>
    </section>

    <div v-if="error" class="alert" role="alert">{{ error }}</div>
    <div class="actions">
      <button class="btn btn-primary" :disabled="busy || !dirty"><span v-if="busy" class="spin" /> Сохранить</button>
      <button v-if="dirty" class="btn" type="button" @click="apply(server)">Сбросить</button>
    </div>
  </form>
</template>
