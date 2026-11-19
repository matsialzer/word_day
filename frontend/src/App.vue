<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Hosts from './components/Hosts.vue'
import Icon from './components/Icon.vue'
import { api } from './lib/api'
import { auth, logout } from './lib/state'

const route = useRoute()
const router = useRouter()
const pending = ref(0)

const nav = [
  { to: '/', label: 'Обзор', icon: 'home' },
  { to: '/words', label: 'Словарь', icon: 'book' },
  { to: '/bonuses', label: 'Бонусы', icon: 'gift', badge: true },
  { to: '/users', label: 'Ученики', icon: 'users' },
  { to: '/settings', label: 'Настройки', icon: 'sliders' },
  { to: '/broadcast', label: 'Рассылка', icon: 'send' },
]

// Счётчик бонусов на проверке в меню
async function loadPending() {
  if (!auth.authed) return
  try {
    pending.value = (await api.get('/bonuses/counts')).pending
  } catch { /* не критично для навигации */ }
}
onMounted(loadPending)
watch(() => route.fullPath, loadPending)

async function doLogout() {
  await logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <RouterView v-if="route.meta.public" />
  <div v-else class="shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark"><Icon name="book" :size="17" /></span>
        <span>WordDay</span>
      </div>
      <nav class="nav" aria-label="Разделы">
        <RouterLink v-for="item in nav" :key="item.to" :to="item.to" :title="item.label">
          <Icon :name="item.icon" />
          <span class="label">{{ item.label }}</span>
          <span v-if="item.badge && pending" class="count">{{ pending }}</span>
        </RouterLink>
      </nav>
      <div class="sidebar-foot">
        <button class="btn btn-sm" style="width: 100%" title="Выйти" @click="doLogout">
          <Icon name="logout" :size="16" /><span class="label">Выйти</span>
        </button>
      </div>
    </aside>
    <main class="main"><RouterView /></main>
  </div>
  <Hosts />
</template>
