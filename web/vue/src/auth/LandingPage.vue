<template>
  <div class="landing">
    <div class="hero">
      <img :src="assetUrl('banner.png')" alt="Fluffynomics banner" class="hero-banner" />
      <h1>Budgeting and money planning software for real life.</h1>
      <p>
        Fluffynomics brings your accounts and investments together so you can
        track your wealth and plan ahead.
      </p>
    </div>

    <section class="auth-panel cds--tile">
      <div class="tab-row" role="tablist" aria-label="Authentication mode">
        <button
          class="tab-btn"
          :class="{ 'tab-btn--active': mode === 'login' }"
          type="button"
          role="tab"
          :aria-selected="mode === 'login'"
          @click="mode = 'login'"
        >
          Login
        </button>
        <button
          class="tab-btn"
          :class="{ 'tab-btn--active': mode === 'register' }"
          type="button"
          role="tab"
          :aria-selected="mode === 'register'"
          @click="mode = 'register'"
        >
          Register
        </button>
      </div>

      <form v-if="mode === 'login'" class="form-grid" @submit.prevent="submitLogin">
        <div class="cds--form-item">
          <label for="login-username" class="cds--label">Username</label>
          <input id="login-username" v-model="loginForm.username" class="cds--text-input" required />
        </div>
        <div class="cds--form-item">
          <label for="login-password" class="cds--label">Password</label>
          <input id="login-password" v-model="loginForm.password" class="cds--text-input" type="password" required />
        </div>
        <button type="submit" class="cds--btn cds--btn--primary submit-btn">Sign In</button>
      </form>

      <form v-else class="form-grid" @submit.prevent="submitRegister">
        <div class="cds--form-item">
          <label for="register-username" class="cds--label">Username</label>
          <input id="register-username" v-model="registerForm.username" class="cds--text-input" required />
        </div>
        <div class="cds--form-item">
          <label for="register-password" class="cds--label">Password</label>
          <input
            id="register-password"
            v-model="registerForm.password"
            class="cds--text-input"
            type="password"
            required
          />
        </div>
        <div class="cds--form-item">
          <label for="register-code" class="cds--label">Registration Code</label>
          <input
            id="register-code"
            v-model="registerForm.registrationCode"
            class="cds--text-input"
            placeholder="Required after the first account"
          />
        </div>
        <label class="checkbox-row">
          <input v-model="registerForm.addExampleData" class="checkbox-input" type="checkbox" />
          <span>Add example data</span>
        </label>
        <button type="submit" class="cds--btn cds--btn--primary submit-btn">Create Account</button>
      </form>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login, register } from '@/lib/auth'
import { assetUrl } from '@/lib/paths'

const router = useRouter()
const mode = ref<'login' | 'register'>('login')

const loginForm = ref({
  username: '',
  password: '',
})

const registerForm = ref({
  username: '',
  password: '',
  registrationCode: '',
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
    registerForm.value.registrationCode.trim() || undefined,
  )
  await login(username, password)
  await router.push('/app')
  mode.value = 'login'
  loginForm.value.username = username
  registerForm.value.addExampleData = false
  registerForm.value.password = ''
  registerForm.value.registrationCode = ''
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

.auth-panel {
  align-self: center;
  max-width: 460px;
  width: 100%;
  margin-inline: auto;
  padding: 1rem;
}

.tab-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  margin-bottom: 1rem;
  border-bottom: 1px solid var(--cds-border-subtle-01);
}

.tab-btn {
  border: 0;
  background: transparent;
  padding: 0.75rem;
  cursor: pointer;
  color: var(--cds-text-secondary);
}

.tab-btn--active {
  color: var(--cds-text-primary);
  box-shadow: inset 0 -2px 0 var(--cds-link-primary);
  font-weight: 600;
}

.form-grid {
  display: grid;
  gap: 0.85rem;
}

.submit-btn {
  width: 100%;
  justify-content: center;
}

.checkbox-row {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  color: var(--cds-text-secondary);
}

.checkbox-input {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: #0f62fe;
}

@media (max-width: 960px) {
  .landing {
    grid-template-columns: 1fr;
    justify-content: stretch;
    padding: 18px;
  }
}
</style>
