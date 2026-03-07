<template>
  <v-app>
    <v-app-bar color="white" density="comfortable" elevation="1">
      <v-app-bar-title class="brand-title">
        <img src="/cat_small.png" alt="Fluffynomics cat" class="brand-cat" />
        Fluffynomics - Wealth Tracker
      </v-app-bar-title>
      <div class="mr-4">{{ currentUser?.username }}</div>
      <v-btn variant="outlined" color="primary" @click="signOut">Logout</v-btn>
    </v-app-bar>

    <v-main>
      <router-view />
    </v-main>

    <v-snackbar v-model="snackbar" color="error" timeout="4500">
      {{ errorMessage }}
    </v-snackbar>
  </v-app>
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
.brand-title {
  display: flex;
  align-items: center;
  gap: 10px;
}

.brand-cat {
  width: 30px;
  height: 30px;
}
</style>
