<template>
  <div class="app-shell">
    <header class="shell-header cds--header">
      <div class="shell-brand">
        <img src="/cat_small.png" alt="Fluffynomics cat" class="brand-cat" />
        <span>Fluffynomics - Wealth Tracker</span>
      </div>
      <div class="shell-actions">
        <span class="shell-user">{{ currentUser?.username }}</span>
        <button class="cds--btn cds--btn--secondary" type="button" @click="signOut">Logout</button>
      </div>
    </header>

    <main class="shell-main">
      <router-view />
    </main>

    <div v-if="snackbar" class="toast-wrap">
      <div class="cds--inline-notification cds--inline-notification--error" role="alert">
        <div class="cds--inline-notification__details">
          <div class="cds--inline-notification__text-wrapper">
            <p class="cds--inline-notification__title">Error</p>
            <p class="cds--inline-notification__subtitle">{{ errorMessage }}</p>
          </div>
        </div>
        <button class="cds--inline-notification__close-button" type="button" @click="snackbar = false">
          Dismiss
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { currentUser, logout } from '@/lib/auth'
import { snackbar, errorMessage } from '@/lib/api'

const router = useRouter()

const signOut = async () => {
  await logout()
  await router.push('/')
}
</script>

<style scoped>
.app-shell {
  min-height: 100vh;
}

.shell-header {
  height: 3rem;
  padding: 0 1rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
}

.shell-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
}

.brand-cat {
  width: 28px;
  height: 28px;
}

.shell-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.shell-user {
  color: var(--cds-text-secondary);
  font-size: 0.9rem;
}

.shell-main {
  padding-top: 0.75rem;
}

.toast-wrap {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 1200;
  max-width: 420px;
}

.cds--inline-notification__close-button {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
}
</style>
