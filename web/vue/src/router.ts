import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '@/AppShell.vue'
import LandingPage from '@/auth/LandingPage.vue'
import AccountsPage from '@/accounts/AccountsPage.vue'
import { currentUser, refreshSession } from '@/lib/auth'

const routes = [
  { path: '/', name: 'Landing', component: LandingPage, meta: { public: true } },
  {
    path: '/app',
    component: AppShell,
    meta: { requiresAuth: true },
    children: [{ path: '', name: 'Accounts', component: AccountsPage }],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to) => {
  const user = currentUser.value || (await refreshSession())
  const isAuthenticated = Boolean(user)

  if (to.meta.requiresAuth && !isAuthenticated) {
    return '/'
  }
  if (to.path === '/' && isAuthenticated) {
    return '/app'
  }
  return true
})

export default router
