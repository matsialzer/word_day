<script setup>
import { computed, onMounted, ref } from 'vue'
import BarChart from '../components/BarChart.vue'
import { api } from '../lib/api'
import { num, sum } from '../lib/format'
import { notifyError } from '../lib/state'

const data = ref(null)
const settings = ref(null)

onMounted(async () => {
  try {
    ;[data.value, settings.value] = await Promise.all([api.get('/dashboard'), api.get('/settings')])
  } catch (e) {
    notifyError(e)
  }
})

const o = computed(() => data.value?.overview)
const pct = (used, limit) => (limit > 0 ? Math.min(100, Math.round((100 * used) / limit)) : 0)
const barClass = (p) => (p >= 100 ? 'danger' : p >= 80 ? 'warn' : '')
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Обзор</h1>
      <p>Что происходит в боте за последние дни</p>
    </div>
  </div>

  <div v-if="!data" class="loading"><span class="spin" /></div>
  <div v-else class="stack" style="gap: 16px">
    <div class="grid stats">
      <div class="card stat">
        <div class="label">Ученики</div>
        <div class="value">{{ num(o.users) }}</div>
        <div class="hint">настроили бота: {{ num(o.onboarded) }} · заблокировано: {{ num(o.blocked) }}</div>
      </div>
      <div class="card stat">
        <div class="label">Активны за сутки</div>
        <div class="value">{{ num(o.active_1d) }}</div>
        <div class="hint">за 7 дней: {{ num(o.active_7d) }} · новых: {{ num(o.new_7d) }}</div>
      </div>
      <div class="card stat">
        <div class="label">Ответов за 7 дней</div>
        <div class="value">{{ num(o.answers_7d) }}</div>
        <div class="hint">верных: {{ o.accuracy_7d }}%</div>
      </div>
      <div class="card stat">
        <div class="label">Слов в словаре</div>
        <div class="value">{{ num(o.words_total) }}</div>
        <div class="hint">в подаче: {{ num(o.words_active) }}</div>
      </div>
      <div class="card stat">
        <div class="label">Выучено слов</div>
        <div class="value">{{ num(o.words_learned) }}</div>
        <div class="hint">выдано ученикам: {{ num(o.words_given) }}</div>
      </div>
      <RouterLink to="/bonuses" class="card stat" style="color: inherit; text-decoration: none">
        <div class="label">Бонусы на проверке</div>
        <div class="value">{{ num(o.bonuses_pending) }}</div>
        <div class="hint">выплачено: {{ num(o.bonuses_paid_count) }} на {{ sum(o.bonuses_paid_sum) }}</div>
      </RouterLink>
    </div>

    <div class="card">
      <div class="card-head">
        <h2>Ответы по дням</h2>
        <span class="muted small">за 14 дней · тёмным — верные</span>
      </div>
      <div class="card-pad"><BarChart :data="data.activity" /></div>
    </div>

    <div class="grid cols-2">
      <div class="card">
        <div class="card-head"><h2>Словарь по уровням</h2></div>
        <div class="card-pad stack" style="gap: 12px">
          <div v-for="l in data.levels" :key="l.level">
            <div class="row" style="justify-content: space-between">
              <strong>{{ l.level }}</strong>
              <span class="muted small">{{ num(l.active) }} в подаче из {{ num(l.total) }}</span>
            </div>
            <div class="bar" style="margin-top: 5px"><span :style="{ width: pct(l.active, Math.max(...data.levels.map((x) => x.total), 1)) + '%' }" /></div>
          </div>
        </div>
      </div>

      <div v-if="settings" class="card">
        <div class="card-head">
          <h2>Бюджет бонусов</h2>
          <RouterLink to="/settings" class="small">Изменить</RouterLink>
        </div>
        <div class="card-pad stack" style="gap: 16px">
          <div v-for="b in [
            { label: 'Эта неделя', used: data.budget_used.week, limit: settings.weekly_budget },
            { label: 'Этот месяц', used: data.budget_used.month, limit: settings.monthly_budget },
          ]" :key="b.label">
            <div class="row" style="justify-content: space-between">
              <strong>{{ b.label }}</strong>
              <span class="small">{{ sum(b.used) }} <span class="muted">из {{ sum(b.limit) }}</span></span>
            </div>
            <div class="bar" :class="barClass(pct(b.used, b.limit))" style="margin-top: 5px">
              <span :style="{ width: pct(b.used, b.limit) + '%' }" />
            </div>
          </div>
          <p class="muted small">Бот не создаст бонус сверх этих лимитов.</p>
        </div>
      </div>
    </div>
  </div>
</template>
