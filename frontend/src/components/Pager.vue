<script setup>
import { computed } from 'vue'
import { num } from '../lib/format'

const props = defineProps({ page: Number, size: Number, total: Number })
const emit = defineEmits(['change'])
const pages = computed(() => Math.max(1, Math.ceil(props.total / props.size)))
</script>

<template>
  <div class="pager">
    <span class="muted small">Всего: {{ num(total) }}</span>
    <div class="row">
      <button class="btn btn-sm" :disabled="page <= 1" @click="emit('change', page - 1)">← Назад</button>
      <span class="small">{{ page }} / {{ pages }}</span>
      <button class="btn btn-sm" :disabled="page >= pages" @click="emit('change', page + 1)">Вперёд →</button>
    </div>
  </div>
</template>
