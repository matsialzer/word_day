<script setup>
// Глобальные слои: уведомления и диалог подтверждения
import Modal from './Modal.vue'
import { answerConfirm, confirmState, toasts } from '../lib/state'
</script>

<template>
  <div class="toasts" aria-live="polite">
    <div v-for="t in toasts" :key="t.id" class="toast" :class="{ error: t.kind === 'error' }">{{ t.message }}</div>
  </div>

  <Modal v-if="confirmState.open" :title="confirmState.title" width="440px" @close="answerConfirm(false)">
    <p v-if="confirmState.text">{{ confirmState.text }}</p>
    <template #footer>
      <button class="btn" @click="answerConfirm(false)">Отмена</button>
      <button class="btn" :class="confirmState.danger ? 'btn-danger' : 'btn-primary'" @click="answerConfirm(true)">
        {{ confirmState.action }}
      </button>
    </template>
  </Modal>
</template>
