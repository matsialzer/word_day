<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

defineProps({ title: String, width: { type: String, default: '640px' } })
const emit = defineEmits(['close'])
const root = ref(null)

function onKey(e) {
  if (e.key === 'Escape') emit('close')
}
onMounted(() => {
  document.addEventListener('keydown', onKey)
  document.body.style.overflow = 'hidden'
  root.value?.querySelector('input, select, textarea, button')?.focus()
})
onUnmounted(() => {
  document.removeEventListener('keydown', onKey)
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="overlay" @mousedown.self="emit('close')">
    <div ref="root" class="modal" role="dialog" aria-modal="true" :aria-label="title" :style="{ width: `min(${width}, 100%)` }">
      <div class="modal-head">
        <h2>{{ title }}</h2>
        <button class="btn btn-icon" type="button" aria-label="Закрыть" @click="emit('close')">✕</button>
      </div>
      <div class="modal-body"><slot /></div>
      <div v-if="$slots.footer" class="modal-foot"><slot name="footer" /></div>
    </div>
  </div>
</template>
