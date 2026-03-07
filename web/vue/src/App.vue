<template>
  <v-app>
    <v-snackbar v-model="snackbar" color="error" timeout="4000">
      {{ errorMessage }}
    </v-snackbar>
    <router-view />
  </v-app>
</template>

<script setup lang="ts">
import { snackbar, errorMessage } from '@/lib/api'
</script>
