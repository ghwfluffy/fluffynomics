<template>
  <div class="landing">
    <div class="hero">
      <p class="eyebrow">Fluffynomics - Wealth Tracker</p>
      <h1>Budgeting and money planning software for real life.</h1>
      <p>
        Track checking, savings, debt, stocks, and crypto accounts in one secure workspace.
        Your data is private to your user account and protected by signed, encrypted sessions.
      </p>
    </div>

    <v-card class="auth-card" elevation="8">
      <v-tabs v-model="mode" color="primary" grow>
        <v-tab value="login">Login</v-tab>
        <v-tab value="register">Register</v-tab>
      </v-tabs>

      <v-card-text>
        <v-form v-if="mode === 'login'" @submit.prevent="submitLogin">
          <v-text-field v-model="loginForm.username" label="Username" required />
          <v-text-field
            v-model="loginForm.password"
            label="Password"
            type="password"
            required
          />
          <v-btn type="submit" block color="primary" class="mt-2">Sign In</v-btn>
        </v-form>

        <v-form v-else @submit.prevent="submitRegister">
          <v-text-field v-model="registerForm.username" label="Username" required />
          <v-text-field
            v-model="registerForm.password"
            label="Password"
            type="password"
            required
          />
          <v-btn type="submit" block color="primary" class="mt-2">Create Account</v-btn>
        </v-form>
      </v-card-text>
    </v-card>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login, register } from '@/lib/auth'

const router = useRouter()
const mode = ref<'login' | 'register'>('login')

const loginForm = ref({
  username: '',
  password: '',
})

const registerForm = ref({
  username: '',
  password: '',
})

const submitLogin = async () => {
  await login(loginForm.value.username, loginForm.value.password)
  await router.push('/app')
}

const submitRegister = async () => {
  await register(registerForm.value.username, registerForm.value.password)
  mode.value = 'login'
  loginForm.value.username = registerForm.value.username
  registerForm.value.password = ''
}
</script>

<style scoped>
.landing {
  min-height: 100vh;
  display: grid;
  grid-template-columns: 1.15fr 1fr;
  gap: 24px;
  padding: 32px;
  background:
    radial-gradient(circle at 8% 10%, #fde68a 0%, #fde68a00 35%),
    radial-gradient(circle at 90% 12%, #a7f3d0 0%, #a7f3d000 36%),
    linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
}

.hero {
  align-self: center;
  padding: 24px;
}

.hero h1 {
  font-size: clamp(2rem, 4vw, 3.2rem);
  line-height: 1.1;
  max-width: 20ch;
  margin: 0 0 12px;
}

.hero p {
  max-width: 56ch;
  color: #334155;
}

.eyebrow {
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
  color: #0f766e;
}

.auth-card {
  align-self: center;
  max-width: 460px;
  width: 100%;
  margin-inline: auto;
}

@media (max-width: 960px) {
  .landing {
    grid-template-columns: 1fr;
    padding: 18px;
  }
}
</style>
