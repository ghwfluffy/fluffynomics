import { createRouter, createWebHistory } from 'vue-router';
import AccountsPage from '@/accounts/AccountsPage.vue';

const routes = [
  { path: '/', name: 'Accounts', component: AccountsPage }
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

export default router;
