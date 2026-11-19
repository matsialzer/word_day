<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login } from '../lib/state'

const router = useRouter()
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await login(password.value)
    router.push({ name: 'dashboard' })
  } catch (e) {
    error.value = e.message
    password.value = ''
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <form class="card card-pad login-card stack" @submit.prevent="submit">
      <div class="brand" style="padding: 0">
        <span class="brand-mark">W</span>
        <span>WordDay</span>
      </div>
      <div>
        <h1>Вход в админ-панель</h1>
        <p class="muted small" style="margin-top: 4px">Пароль задан в настройках сервера (WEB_ADMIN_PASSWORD).</p>
      </div>
      <label class="field">
        Пароль
        <input v-model="password" type="password" autocomplete="current-password" required autofocus />
      </label>
      <div v-if="error" class="alert" role="alert">{{ error }}</div>
      <button class="btn btn-primary" :disabled="busy || !password">
        <span v-if="busy" class="spin" /> Войти
      </button>
    </form>
  </div>
</template>

<style scoped>
.login-page { min-height: 100vh; display: grid; place-items: center; padding: 20px; }
.login-card { width: min(400px, 100%); gap: 18px; }
</style>
