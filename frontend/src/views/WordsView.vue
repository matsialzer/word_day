<script setup>
import { onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import Icon from '../components/Icon.vue'
import ImportModal from '../components/ImportModal.vue'
import Pager from '../components/Pager.vue'
import WordForm from '../components/WordForm.vue'
import { api } from '../lib/api'
import { notify, notifyError } from '../lib/state'

const filters = reactive({ q: '', level: '', theme: '', active: '' })
const page = ref(1)
const size = 25
const data = ref({ items: [], total: 0 })
const meta = ref({ levels: [], themes: [] })
const loading = ref(true)
const form = ref(null) // { word } | null
const importing = ref(false)
const audioInput = ref(null)
let audioTarget = null
let timer = null
let player = null

async function load() {
  loading.value = true
  try {
    data.value = await api.get('/words', { ...filters, page: page.value, size })
  } catch (e) {
    notifyError(e)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  try {
    meta.value = await api.get('/words/meta')
  } catch (e) {
    notifyError(e)
  }
  load()
})
onBeforeUnmount(() => { clearTimeout(timer); player?.pause() })

// Поиск с задержкой, остальные фильтры - сразу; любой фильтр возвращает на 1-ю страницу
watch(() => filters.q, () => { clearTimeout(timer); timer = setTimeout(() => { page.value = 1; load() }, 300) })
watch(() => [filters.level, filters.theme, filters.active], () => { page.value = 1; load() })

function goto(p) { page.value = p; load() }

async function toggle(w) {
  try {
    const r = await api.post(`/words/${w.id}/toggle`)
    Object.assign(w, r)
    notify(r.is_active ? 'Слово возвращено в подачу' : 'Слово скрыто из подачи')
  } catch (e) { notifyError(e) }
}

function pickAudio(w) { audioTarget = w; audioInput.value.click() }
async function uploadAudio(e) {
  const file = e.target.files[0]
  e.target.value = ''
  if (!file || !audioTarget) return
  try {
    Object.assign(audioTarget, await api.upload(`/words/${audioTarget.id}/audio`, file))
    notify('Озвучка сохранена')
  } catch (err) { notifyError(err) }
}
function play(w) {
  player?.pause()
  player = new Audio(`/api/words/${w.id}/audio`)
  player.play().catch(() => notify('Не удалось воспроизвести файл', 'error'))
}

function saved() { form.value = null; load(); api.get('/words/meta').then((m) => (meta.value = m)) }
</script>

<template>
  <div class="page-head">
    <div>
      <h1>Словарь</h1>
      <p>Новые слова встают в конец своего уровня, если место не указано</p>
    </div>
    <div class="actions">
      <button class="btn" @click="importing = true"><Icon name="upload" :size="16" /> Импорт CSV</button>
      <button class="btn btn-primary" @click="form = { word: null }"><Icon name="plus" :size="16" /> Добавить слово</button>
    </div>
  </div>

  <div class="toolbar">
    <input v-model="filters.q" class="grow" type="search" placeholder="Поиск по слову или переводу" aria-label="Поиск" />
    <select v-model="filters.level" aria-label="Уровень">
      <option value="">Все уровни</option>
      <option v-for="l in meta.levels" :key="l" :value="l">{{ l }}</option>
    </select>
    <select v-model="filters.theme" aria-label="Тема">
      <option value="">Все темы</option>
      <option v-for="t in meta.themes" :key="t" :value="t">{{ t }}</option>
    </select>
    <select v-model="filters.active" aria-label="Статус">
      <option value="">Любой статус</option>
      <option value="true">В подаче</option>
      <option value="false">Скрытые</option>
    </select>
  </div>

  <div class="card">
    <div class="table-wrap">
      <table>
        <thead>
          <tr><th>Слово</th><th>Перевод</th><th>Уровень</th><th>Тема</th><th>№</th><th>Озвучка</th><th /></tr>
        </thead>
        <tbody>
          <tr v-for="w in data.items" :key="w.id" :class="{ 'is-off': !w.is_active }">
            <td>
              <strong>{{ w.word }}</strong>
              <span class="muted mono" style="margin-left: 6px">{{ w.transcription }}</span>
              <div class="muted small">{{ w.example }}</div>
            </td>
            <td>
              {{ w.translation_ru }}
              <div class="muted small">{{ w.translation_uz || '—' }}</div>
            </td>
            <td><span class="badge badge-accent">{{ w.level }}</span></td>
            <td>{{ w.theme }}</td>
            <td class="muted">{{ w.freq_rank }}</td>
            <td>
              <div class="row" style="gap: 6px; flex-wrap: nowrap">
                <button v-if="w.has_audio" class="btn btn-icon btn-sm" title="Прослушать" aria-label="Прослушать" @click="play(w)"><Icon name="play" :size="14" /></button>
                <button class="btn btn-icon btn-sm" :title="w.has_audio ? 'Заменить озвучку' : 'Загрузить озвучку (mp3)'" aria-label="Загрузить озвучку" @click="pickAudio(w)"><Icon name="mic" :size="14" /></button>
              </div>
            </td>
            <td>
              <div class="cell-actions">
                <span v-if="!w.is_active" class="badge">скрыто</span>
                <button class="btn btn-icon btn-sm" title="Редактировать" aria-label="Редактировать" @click="form = { word: w }"><Icon name="edit" :size="14" /></button>
                <button class="btn btn-icon btn-sm" :title="w.is_active ? 'Скрыть из подачи' : 'Вернуть в подачу'" :aria-label="w.is_active ? 'Скрыть' : 'Вернуть'" @click="toggle(w)">
                  <Icon :name="w.is_active ? 'eyeoff' : 'eye'" :size="14" />
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div v-if="loading && !data.items.length" class="loading"><span class="spin" /></div>
    <div v-else-if="!data.items.length" class="empty">
      Слов не найдено. Измените фильтры или <a href="#" @click.prevent="form = { word: null }">добавьте слово</a>.
    </div>
    <Pager v-if="data.total > size" :page="page" :size="size" :total="data.total" @change="goto" />
  </div>

  <input ref="audioInput" type="file" accept=".mp3,audio/mpeg" hidden @change="uploadAudio" />
  <WordForm v-if="form" :word="form.word" :levels="meta.levels" :themes="meta.themes" @close="form = null" @saved="saved" />
  <ImportModal v-if="importing" @close="importing = false" @done="importing = false; load()" />
</template>
