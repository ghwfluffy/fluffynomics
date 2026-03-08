<template>
  <router-view />
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
</template>

<script setup lang="ts">
import { snackbar, errorMessage } from '@/lib/api'
</script>

<style scoped>
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
