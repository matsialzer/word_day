<script setup>
// Форма слова: создание (word == null) и редактирование
import { computed, reactive, ref } from 'vue'
import Modal from './Modal.vue'
import { api } from '../lib/api'
import { notify } from '../lib/state'

const props = defineProps({ word: Object, levels: Array, themes: Array })
const emit = defineEmits(['close', 'saved'])

const editing = computed(() => !!props.word)
const form = reactive({
  word: props.word?.word ?? '',
  transcription: props.word?.transcription ?? '',
  translation_ru: props.word?.translation_ru ?? '',
  translation_uz: props.word?.translation_uz ?? '',
  example: props.word?.example ?? '',
  level: props.word?.level ?? 'A1',
  theme: props.word?.theme ?? props.themes[0] ?? 'basic',
  freq_rank: props.word?.freq_rank ?? null,
})
const error = ref('')
const busy = ref(false)

// Подсказка заранее: формат «вставь пропуск» работает, если слово есть в примере в той же форме
const exampleWarn = computed(() => {
  const w = form.word.trim()
  if (!w || !form.example.trim()) return false
  const re = new RegExp(`(?<![\\p{L}\\p{N}_])${w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?![\\p{L}\\p{N}_])`, 'iu')
  return !re.test(form.example)
})

async function save() {
  error.value = ''
  busy.value = true
  const body = {
    ...form,
    translation_uz: form.translation_uz.trim() || null,
    freq_rank: form.freq_rank ? Number(form.freq_rank) : null,
  }
  try {
    const saved = editing.value
      ? await api.put(`/words/${props.word.id}`, body)
      : await api.post('/words', body)
    notify(editing.value ? 'Слово сохранено' : `Слово «${saved.word}» добавлено`)
    emit('saved', saved)
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Modal :title="editing ? 'Редактировать слово' : 'Новое слово'" @close="emit('close')">
    <form id="word-form" class="form-grid" @submit.prevent="save">
      <label class="field">
        Слово (по-английски)
        <input v-model="form.word" maxlength="64" required placeholder="cat" />
      </label>
      <label class="field">
        Транскрипция
        <input v-model="form.transcription" maxlength="64" required placeholder="kæt" />
      </label>
      <label class="field">
        Перевод на русский
        <input v-model="form.translation_ru" maxlength="128" required placeholder="кошка" />
      </label>
      <label class="field">
        Перевод на узбекский <span class="hint">(латиница, можно пусто)</span>
        <input v-model="form.translation_uz" maxlength="128" placeholder="mushuk" />
      </label>
      <label class="field wide">
        Пример предложения
        <input v-model="form.example" maxlength="300" required placeholder="The cat sleeps on the sofa." />
        <span v-if="exampleWarn" class="hint" style="color: var(--warn)">
          Слова нет в примере в той же форме — формат «вставь пропуск» для него использоваться не будет.
        </span>
      </label>
      <label class="field">
        Уровень
        <select v-model="form.level">
          <option v-for="l in levels" :key="l" :value="l">{{ l }}</option>
        </select>
      </label>
      <label class="field">
        Тема
        <input v-model="form.theme" list="theme-list" maxlength="32" required />
        <datalist id="theme-list"><option v-for="t in themes" :key="t" :value="t" /></datalist>
      </label>
      <label class="field">
        Место на уровне <span class="hint">(1 — самое лёгкое; пусто — в конец)</span>
        <input v-model="form.freq_rank" type="number" min="1" :required="editing" />
      </label>
      <div v-if="error" class="alert wide" role="alert">{{ error }}</div>
    </form>
    <template #footer>
      <button class="btn" type="button" @click="emit('close')">Отмена</button>
      <button class="btn btn-primary" type="submit" form="word-form" :disabled="busy">
        <span v-if="busy" class="spin" /> Сохранить
      </button>
    </template>
  </Modal>
</template>
