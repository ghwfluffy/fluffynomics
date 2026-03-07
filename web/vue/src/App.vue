<template>
  <v-app>
    <router-view />
    <v-snackbar v-model="snackbar" color="error" timeout="4500">
      {{ errorMessage }}
    </v-snackbar>
  </v-app>
</template>

<script setup lang="ts">
import { snackbar, errorMessage } from '@/lib/api'
</script>
