import { createApp } from 'vue'
import App from './App.vue'
import router from './router'
import { setUnauthorizedHandler } from './lib/api'
import { auth } from './lib/state'
import './styles.css'

// Сессия истекла в середине работы -> на страницу входа
setUnauthorizedHandler(() => {
  auth.authed = false
  if (router.currentRoute.value.name !== 'login') router.push({ name: 'login' })
})

createApp(App).use(router).mount('#app')
