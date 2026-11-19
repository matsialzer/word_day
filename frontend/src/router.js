import { createRouter, createWebHistory } from 'vue-router'
import { auth, checkSession } from './lib/state'

const routes = [
  { path: '/login', name: 'login', component: () => import('./views/LoginView.vue'), meta: { public: true, title: 'Вход' } },
  { path: '/', name: 'dashboard', component: () => import('./views/DashboardView.vue'), meta: { title: 'Обзор' } },
  { path: '/words', name: 'words', component: () => import('./views/WordsView.vue'), meta: { title: 'Словарь' } },
  { path: '/bonuses', name: 'bonuses', component: () => import('./views/BonusesView.vue'), meta: { title: 'Бонусы' } },
  { path: '/users', name: 'users', component: () => import('./views/UsersView.vue'), meta: { title: 'Ученики' } },
  { path: '/settings', name: 'settings', component: () => import('./views/SettingsView.vue'), meta: { title: 'Настройки' } },
  { path: '/broadcast', name: 'broadcast', component: () => import('./views/BroadcastView.vue'), meta: { title: 'Рассылка' } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  if (!auth.checked) await checkSession()
  if (to.meta.public) return auth.authed ? { name: 'dashboard' } : true
  return auth.authed ? true : { name: 'login' }
})

router.afterEach((to) => {
  document.title = `${to.meta.title} · WordDay`
})

export default router
