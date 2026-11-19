<script setup>
import { ref } from 'vue'
import Modal from './Modal.vue'
import { api } from '../lib/api'
import { notify } from '../lib/state'

const emit = defineEmits(['close', 'done'])
const file = ref(null)
const busy = ref(false)
const error = ref('')

const HEADER = 'word,transcription,translation_ru,translation_uz,example,theme,level,freq_rank,audio_file'

async function run() {
  error.value = ''
  busy.value = true
  try {
    const r = await api.upload('/words/import', file.value)
    notify(`Готово: добавлено ${r.new}, обновлено ${r.updated}` + (r.missing_audio ? `, без аудио: ${r.missing_audio}` : ''))
    emit('done')
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Modal title="Импорт слов из CSV" @close="emit('close')">
    <div class="stack">
      <p class="small">
        Файл .csv в кодировке UTF-8, первая строка — заголовок:
      </p>
      <code class="mono card-pad" style="background: var(--surface-2); border-radius: 8px; display: block; word-break: break-all">{{ HEADER }}</code>
      <ul class="small muted" style="margin: 0; padding-left: 18px">
        <li><b>level</b>: A1, A2, B1, B2 или C1; <b>freq_rank</b>: порядок внутри уровня (1 — самое лёгкое)</li>
        <li><b>translation_uz</b> и <b>audio_file</b> можно оставить пустыми</li>
        <li>Существующие слова обновляются по написанию, новые добавляются</li>
        <li>Если в файле есть ошибка, <b>не загрузится ничего</b></li>
      </ul>
      <label class="field">
        Файл
        <input type="file" accept=".csv,text/csv" @change="file = $event.target.files[0]" />
      </label>
      <div v-if="error" class="alert" role="alert">{{ error }}</div>
    </div>
    <template #footer>
      <button class="btn" @click="emit('close')">Отмена</button>
      <button class="btn btn-primary" :disabled="!file || busy" @click="run">
        <span v-if="busy" class="spin" /> Загрузить
      </button>
    </template>
  </Modal>
</template>
