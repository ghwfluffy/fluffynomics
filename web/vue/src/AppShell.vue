<template>
  <div class="app-shell">
    <header class="shell-header cds--header">
      <div class="shell-brand">
        <img src="/cat_small.png" alt="Fluffynomics cat" class="brand-cat" />
        <span>Fluffynomics - Wealth Tracker</span>
      </div>
      <div class="shell-actions">
        <div ref="profileMenuRef" class="profile-menu-wrap">
          <button
            class="profile-trigger"
            type="button"
            :aria-expanded="profileMenuOpen ? 'true' : 'false'"
            aria-haspopup="menu"
            @click="toggleProfileMenu"
          >
            <span class="profile-avatar">{{ avatarInitials }}</span>
            <span class="shell-user">{{ currentUser?.username }}</span>
            <span class="profile-caret" aria-hidden="true">▾</span>
          </button>
          <div v-if="profileMenuOpen" class="profile-menu cds--tile" role="menu">
            <button class="profile-menu-item" type="button" role="menuitem" @click="onProfileExportClick">
              Export Data
            </button>
            <button class="profile-menu-item" type="button" role="menuitem" @click="onProfileImportClick">
              Import Data
            </button>
            <button class="profile-menu-item profile-menu-item--danger" type="button" role="menuitem" @click="onProfileLogoutClick">
              Logout
            </button>
          </div>
        </div>
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

    <div v-if="exportDialogOpen" class="modal-backdrop">
      <section class="modal-card cds--tile">
        <h3>Export Data</h3>
        <p>Create a portable package of your data. Password is optional.</p>
        <div class="modal-form-grid">
          <label class="bank-label" for="export-password">Password (optional)</label>
          <input
            id="export-password"
            v-model="exportPassword"
            class="cds--text-input"
            type="password"
            autocomplete="new-password"
            placeholder="Leave blank for plaintext package"
          />
        </div>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" :disabled="exportBusy" @click="closeExportDialog">
            Cancel
          </button>
          <button class="cds--btn cds--btn--primary" type="button" :disabled="exportBusy" @click="runExport">
            {{ exportBusy ? 'Exporting...' : 'Download Package' }}
          </button>
        </div>
      </section>
    </div>

    <div v-if="importDialogOpen" class="modal-backdrop">
      <section class="modal-card cds--tile">
        <h3>Import Data</h3>
        <p>This replaces your current data with the package contents.</p>
        <div class="modal-form-grid">
          <div class="import-file-row">
            <button class="cds--btn cds--btn--ghost" type="button" @click="openImportFilePicker">Choose Package File</button>
            <span>{{ importFileName || 'No file selected' }}</span>
          </div>
          <input
            ref="importFileInput"
            class="import-file-input"
            type="file"
            accept="application/json,.json"
            @change="onImportFileSelected"
          />
          <label class="bank-label" for="import-password">Password (optional)</label>
          <input
            id="import-password"
            v-model="importPassword"
            class="cds--text-input"
            type="password"
            autocomplete="new-password"
            placeholder="Required only for encrypted packages"
          />
        </div>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" :disabled="importBusy" @click="closeImportDialog">
            Cancel
          </button>
          <button
            class="cds--btn cds--btn--primary"
            type="button"
            :disabled="importBusy || !importPackageObject"
            @click="runImport"
          >
            {{ importBusy ? 'Importing...' : 'Import And Replace' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { currentUser, logout } from '@/lib/auth'
import { errorMessage, request, snackbar } from '@/lib/api'

const router = useRouter()
const exportDialogOpen = ref(false)
const exportPassword = ref('')
const exportBusy = ref(false)

const importDialogOpen = ref(false)
const importPassword = ref('')
const importBusy = ref(false)
const importFileName = ref('')
const importPackageObject = ref<Record<string, unknown> | null>(null)
const importFileInput = ref<HTMLInputElement | null>(null)
const profileMenuRef = ref<HTMLElement | null>(null)
const profileMenuOpen = ref(false)

const avatarInitials = computed(() => {
  const username = (currentUser.value?.username || '').trim()
  if (!username) {
    return '?'
  }
  const parts = username.split(/[\s._-]+/).filter(Boolean)
  if (parts.length === 0) {
    return username.slice(0, 2).toUpperCase()
  }
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase()
  }
  return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
})

const signOut = async () => {
  await logout()
  await router.push('/')
}

const toggleProfileMenu = () => {
  profileMenuOpen.value = !profileMenuOpen.value
}

const closeProfileMenu = () => {
  profileMenuOpen.value = false
}

const onProfileExportClick = () => {
  closeProfileMenu()
  openExportDialog()
}

const onProfileImportClick = () => {
  closeProfileMenu()
  openImportDialog()
}

const onProfileLogoutClick = async () => {
  closeProfileMenu()
  await signOut()
}

const onWindowPointerDown = (event: Event) => {
  if (!profileMenuOpen.value) {
    return
  }
  const target = event.target as Node | null
  if (target && profileMenuRef.value?.contains(target)) {
    return
  }
  closeProfileMenu()
}

onMounted(() => {
  window.addEventListener('pointerdown', onWindowPointerDown)
})

onUnmounted(() => {
  window.removeEventListener('pointerdown', onWindowPointerDown)
})

const openExportDialog = () => {
  exportPassword.value = ''
  exportDialogOpen.value = true
}

const closeExportDialog = () => {
  if (exportBusy.value) {
    return
  }
  exportDialogOpen.value = false
}

const makeExportFilename = () => {
  const now = new Date()
  const parts = [
    now.getUTCFullYear().toString().padStart(4, '0'),
    (now.getUTCMonth() + 1).toString().padStart(2, '0'),
    now.getUTCDate().toString().padStart(2, '0'),
    now.getUTCHours().toString().padStart(2, '0'),
    now.getUTCMinutes().toString().padStart(2, '0'),
    now.getUTCSeconds().toString().padStart(2, '0'),
  ]
  return `money-planner-export-${parts.join('')}.json`
}

const triggerDownload = (payload: unknown, filename: string) => {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

const runExport = async () => {
  exportBusy.value = true
  try {
    const password = exportPassword.value.trim() || null
    const data = await request.post<Record<string, unknown>>('/data/export', { password })
    triggerDownload(data, makeExportFilename())
    exportDialogOpen.value = false
  } finally {
    exportBusy.value = false
  }
}

const openImportDialog = async () => {
  importPassword.value = ''
  importFileName.value = ''
  importPackageObject.value = null
  importDialogOpen.value = true
  await nextTick()
  if (importFileInput.value) {
    importFileInput.value.value = ''
  }
}

const closeImportDialog = () => {
  if (importBusy.value) {
    return
  }
  importDialogOpen.value = false
}

const openImportFilePicker = () => {
  importFileInput.value?.click()
}

const onImportFileSelected = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) {
    importFileName.value = ''
    importPackageObject.value = null
    return
  }
  try {
    const text = await file.text()
    const parsed = JSON.parse(text)
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error('Package file must contain a JSON object')
    }
    importPackageObject.value = parsed as Record<string, unknown>
    importFileName.value = file.name
  } catch (err: any) {
    importPackageObject.value = null
    importFileName.value = ''
    errorMessage.value = err?.message || 'Invalid package file'
    snackbar.value = true
  }
}

const runImport = async () => {
  if (!importPackageObject.value) {
    return
  }
  importBusy.value = true
  try {
    const password = importPassword.value.trim() || null
    await request.post('/data/import', {
      package: importPackageObject.value,
      password,
      replace_existing: true,
    })
    importDialogOpen.value = false
    window.location.reload()
  } finally {
    importBusy.value = false
  }
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
  position: sticky;
  top: 0;
  left: 0;
  right: 0;
  z-index: 50;
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
  flex-wrap: wrap;
  gap: 12px;
}

.profile-menu-wrap {
  position: relative;
}

.profile-trigger {
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  color: var(--cds-text-primary);
  border-radius: 999px;
  height: 36px;
  padding: 0 10px 0 6px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.profile-avatar {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--cds-support-info);
  color: #fff;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 0.72rem;
  font-weight: 700;
}

.shell-user {
  color: var(--cds-text-primary);
  font-size: 0.85rem;
  max-width: 14rem;
  white-space: nowrap;
  text-overflow: ellipsis;
  overflow: hidden;
}

.profile-caret {
  font-size: 0.8rem;
  color: var(--cds-text-secondary);
}

.profile-menu {
  position: absolute;
  right: 0;
  top: calc(100% + 8px);
  width: 220px;
  padding: 6px;
  display: grid;
  gap: 4px;
  z-index: 80;
}

.profile-menu-item {
  border: 0;
  text-align: left;
  padding: 10px 12px;
  border-radius: 6px;
  background: transparent;
  color: var(--cds-text-primary);
  cursor: pointer;
}

.profile-menu-item:hover {
  background: var(--cds-layer-hover);
}

.profile-menu-item--danger {
  color: var(--cds-support-error);
}

.shell-main {
  padding-top: 0.75rem;
  margin-left: 0 !important;
  width: 100%;
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

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgb(0 0 0 / 45%);
  display: grid;
  place-items: center;
  z-index: 1300;
  padding: 16px;
}

.modal-card {
  width: min(560px, 100%);
  display: grid;
  gap: 16px;
}

.modal-card h3 {
  margin: 0;
}

.modal-card p {
  margin: 0;
  color: var(--cds-text-secondary);
}

.modal-form-grid {
  display: grid;
  gap: 12px;
}

.bank-label {
  font-size: 0.875rem;
  color: var(--cds-text-secondary);
}

.import-file-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.import-file-input {
  display: none;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
