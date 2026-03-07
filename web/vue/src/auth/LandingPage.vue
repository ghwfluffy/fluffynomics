<template>
  <div class="landing">
    <div class="hero">
      <img src="/banner.png" alt="Fluffynomics banner" class="hero-banner" />
      <h1>Budgeting and money planning software for real life.</h1>
      <p>
        Fluffynomics brings your accounts and investments together so you can
        track your wealth and plan ahead.
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
          <label class="example-checkbox">
            <input v-model="registerForm.addExampleData" type="checkbox" />
            <span>Add example data</span>
          </label>
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
  addExampleData: false,
})

const submitLogin = async () => {
  await login(loginForm.value.username, loginForm.value.password)
  await router.push('/app')
}

const submitRegister = async () => {
  const username = registerForm.value.username
  const password = registerForm.value.password
  await register(
    username,
    password,
    registerForm.value.addExampleData,
  )
  await login(username, password)
  await router.push('/app')
  mode.value = 'login'
  loginForm.value.username = username
  registerForm.value.addExampleData = false
  registerForm.value.password = ''
}
</script>

<style scoped>
.landing {
  min-height: 100vh;
  display: grid;
  grid-template-columns: minmax(560px, 760px) minmax(360px, 460px);
  gap: 24px;
  padding: 32px clamp(18px, 6vw, 88px);
  justify-content: center;
  background:
    radial-gradient(circle at 8% 10%, #fde68a 0%, #fde68a00 35%),
    radial-gradient(circle at 90% 12%, #a7f3d0 0%, #a7f3d000 36%),
    linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%);
}

.hero {
  align-self: center;
  padding: 24px;
  justify-self: center;
  width: 100%;
  max-width: 680px;
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

.hero-banner {
  width: min(100%, 580px);
  border-radius: 14px;
  margin-bottom: 18px;
  box-shadow: 0 16px 34px -18px rgba(15, 23, 42, 0.45);
}

.auth-card {
  align-self: center;
  max-width: 460px;
  width: 100%;
  margin-inline: auto;
  background-image: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
}

.example-checkbox {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  margin-top: 8px;
  color: #334155;
  font-size: 0.95rem;
}

.example-checkbox input[type='checkbox'] {
  width: 16px;
  height: 16px;
  accent-color: #0f766e;
}

@media (max-width: 960px) {
  .landing {
    grid-template-columns: 1fr;
    justify-content: stretch;
    padding: 18px;
  }
}
</style>
