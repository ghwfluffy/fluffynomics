<template>
  <div class="app-shell">
    <header class="shell-header cds--header">
      <div class="shell-brand">
        <img :src="assetUrl('cat_small.png')" alt="Fluffynomics cat" class="brand-cat" />
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
            <img v-if="currentUser?.avatar_icon_id" :src="iconUrl(currentUser.avatar_icon_id)" class="profile-avatar" alt="Profile avatar" />
            <span v-else class="profile-avatar">{{ avatarInitials }}</span>
            <span class="shell-user">{{ currentUser?.username }}</span>
            <span class="profile-caret" aria-hidden="true">▾</span>
          </button>
          <div v-if="profileMenuOpen" class="profile-menu cds--tile" role="menu">
            <button class="profile-menu-item" type="button" role="menuitem" @click="onProfileManageClick">
              Profile
            </button>
            <button
              v-if="currentUser?.is_admin"
              class="profile-menu-item"
              type="button"
              role="menuitem"
              @click="onManageUsersClick"
            >
              Manage Users
            </button>
            <button
              v-if="currentUser?.is_admin"
              class="profile-menu-item"
              type="button"
              role="menuitem"
              @click="onAdministrationClick"
            >
              Administration
            </button>
            <button class="profile-menu-item" type="button" role="menuitem" @click="onProfileExportClick">
              Export Data
            </button>
            <button class="profile-menu-item" type="button" role="menuitem" @click="onProfileImportClick">
              Import Data
            </button>
            <button
              v-if="!maskedModeEnabled"
              class="profile-menu-item"
              type="button"
              role="menuitem"
              @click="onEnableMaskedModeClick"
            >
              Masked Mode
            </button>
            <div v-else class="profile-menu-item profile-menu-item--disabled" role="menuitem" aria-disabled="true">
              Masked Mode On
              <span class="profile-menu-item-note">Logout to exit</span>
            </div>
            <button class="profile-menu-item profile-menu-item--danger" type="button" role="menuitem" @click="onProfileLogoutClick">
              Logout
            </button>
          </div>
        </div>
      </div>
    </header>

    <main class="shell-main">
      <div v-if="maskedModeEnabled" class="masked-mode-banner">MASKED MODE ENABLED. VALUES ARE NOT REAL.</div>
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
            accept="application/json,.json,.yml,.yaml,text/yaml,text/x-yaml"
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
            :disabled="importBusy || importPackageData === null"
            @click="runImport"
          >
            {{ importBusy ? 'Importing...' : 'Import And Replace' }}
          </button>
        </div>
      </section>
    </div>

    <div v-if="profileDialogOpen" class="modal-backdrop">
      <section class="modal-card modal-card--wide cds--tile">
        <h3>Profile</h3>
        <div class="cds--tabs" role="navigation" aria-label="Profile sections">
          <ul class="cds--tabs__nav" role="tablist">
            <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': profileTab === 'info' }" role="presentation">
              <button
                id="tab-profile-info"
                class="cds--tabs__nav-link"
                role="tab"
                type="button"
                :aria-selected="profileTab === 'info'"
                aria-controls="panel-profile-info"
                @click="profileTab = 'info'"
              >
                Info
              </button>
            </li>
            <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': profileTab === 'password' }" role="presentation">
              <button
                id="tab-profile-password"
                class="cds--tabs__nav-link"
                role="tab"
                type="button"
                :aria-selected="profileTab === 'password'"
                aria-controls="panel-profile-password"
                @click="profileTab = 'password'"
              >
                Password
              </button>
            </li>
            <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': profileTab === 'wallets' }" role="presentation">
              <button
                id="tab-profile-wallets"
                class="cds--tabs__nav-link"
                role="tab"
                type="button"
                :aria-selected="profileTab === 'wallets'"
                aria-controls="panel-profile-wallets"
                @click="profileTab = 'wallets'"
              >
                Digital Wallets
              </button>
            </li>
            <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': profileTab === 'widget' }" role="presentation">
              <button
                id="tab-profile-widget"
                class="cds--tabs__nav-link"
                role="tab"
                type="button"
                :aria-selected="profileTab === 'widget'"
                aria-controls="panel-profile-widget"
                @click="profileTab = 'widget'"
              >
                Widget
              </button>
            </li>
            <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': profileTab === 'delete' }" role="presentation">
              <button
                id="tab-profile-delete"
                class="cds--tabs__nav-link"
                role="tab"
                type="button"
                :aria-selected="profileTab === 'delete'"
                aria-controls="panel-profile-delete"
                @click="profileTab = 'delete'"
              >
                Delete Account
              </button>
            </li>
          </ul>
        </div>

        <div v-if="profileTab === 'info'" id="panel-profile-info" role="tabpanel" aria-labelledby="tab-profile-info">
          <div class="profile-meta-grid">
            <div class="profile-avatar-section">
              <div class="profile-avatar-large-wrap">
                <img v-if="profileAvatarUrl" :src="profileAvatarUrl" class="profile-avatar-large" alt="Profile avatar" />
                <div v-else class="profile-avatar-large profile-avatar-large--fallback">{{ avatarInitials }}</div>
              </div>
              <div class="profile-avatar-actions">
                <button class="cds--btn cds--btn--ghost" type="button" @click="toggleProfileIconLibrary">
                  {{ showProfileIconLibrary ? 'Hide Icon Library' : 'Choose Avatar' }}
                </button>
                <input
                  ref="profileIconFileInput"
                  class="import-file-input"
                  type="file"
                  accept="image/*"
                  @change="onProfileAvatarUpload"
                />
                <button class="cds--btn cds--btn--ghost" type="button" @click="openProfileAvatarUploadPicker">Upload Avatar</button>
                <button class="cds--btn cds--btn--ghost" type="button" @click="clearProfileAvatar">Clear Avatar</button>
              </div>
              <div v-if="showProfileIconLibrary" class="profile-icon-grid">
                <button
                  v-for="icon in profileIconChoices"
                  :key="icon.id"
                  type="button"
                  class="profile-icon-choice"
                  :class="{ 'profile-icon-choice--selected': profileDraftAvatarIconId === icon.id }"
                  @click="profileDraftAvatarIconId = icon.id"
                >
                  <img :src="iconUrl(icon.id)" class="profile-icon-choice-image" alt="Avatar choice" />
                </button>
              </div>
            </div>
            <div class="profile-stats">
              <p><strong>Username:</strong> {{ currentUser?.username }}</p>
              <p><strong>Account Created:</strong> {{ formatDateTime(currentUser?.created_at) }}</p>
              <p><strong>Last Login:</strong> {{ formatDateTime(currentUser?.last_login_at) }}</p>
              <p><strong>Last Password Change:</strong> {{ formatDateTime(currentUser?.password_changed_at) }}</p>
            </div>
          </div>
        </div>

        <div
          v-if="profileTab === 'password'"
          id="panel-profile-password"
          class="password-section"
          role="tabpanel"
          aria-labelledby="tab-profile-password"
        >
          <h4>Change Password</h4>
          <div class="modal-form-grid">
            <label class="bank-label" for="profile-current-password">Current Password</label>
            <input
              id="profile-current-password"
              v-model="profileCurrentPassword"
              class="cds--text-input"
              type="password"
              autocomplete="current-password"
            />
            <label class="bank-label" for="profile-new-password">New Password</label>
            <input
              id="profile-new-password"
              v-model="profileNewPassword"
              class="cds--text-input"
              type="password"
              autocomplete="new-password"
            />
          </div>
        </div>

        <div
          v-if="profileTab === 'wallets'"
          id="panel-profile-wallets"
          class="modal-form-grid"
          role="tabpanel"
          aria-labelledby="tab-profile-wallets"
        >
          <p>Choose which real account backs each digital wallet alias for contracts and legacy imports.</p>
          <UnifiedDropdown
            v-model="profilePaypalAccountId"
            label="PayPal Linked Account"
            searchable
            :options="walletAccountDropdownOptions"
          />
          <UnifiedDropdown
            v-model="profileGooglePayAccountId"
            label="Google Pay Linked Account"
            searchable
            :options="walletAccountDropdownOptions"
          />
        </div>
        <div
          v-if="profileTab === 'widget'"
          id="panel-profile-widget"
          class="profile-widget-section"
          role="tabpanel"
          aria-labelledby="tab-profile-widget"
        >
          <h4>Widget URL</h4>
          <p>
            Generate a private PNG URL for your widget client. Regenerating the URL invalidates the old token and resets its hit history.
          </p>
          <div class="modal-form-grid">
            <label class="bank-label" for="profile-widget-url">Current Widget URL</label>
            <input
              id="profile-widget-url"
              class="cds--text-input"
              type="text"
              :value="profileWidgetUrl || 'No widget URL generated yet'"
              readonly
            />
          </div>
          <div class="profile-widget-actions">
            <button class="cds--btn cds--btn--secondary" type="button" :disabled="profileBusy" @click="regenerateProfileWidgetUrl">
              {{ profileBusy ? 'Generating...' : (profileWidgetUrl ? 'Generate New Widget URL' : 'Generate Widget URL') }}
            </button>
            <button
              class="cds--btn cds--btn--ghost"
              type="button"
              :disabled="profileBusy || !profileWidgetUrl"
              @click="copyProfileWidgetUrl"
            >
              {{ profileWidgetCopied ? 'Copied' : 'Copy URL' }}
            </button>
          </div>
        </div>
        <div
          v-if="profileTab === 'delete'"
          id="panel-profile-delete"
          class="profile-delete-section"
          role="tabpanel"
          aria-labelledby="tab-profile-delete"
        >
          <h4>Delete Account</h4>
          <p class="profile-delete-warning">
            This permanently deletes your user and all account data. This action cannot be undone.
          </p>
          <div class="modal-form-grid">
            <label class="bank-label" for="profile-delete-password">Current Password</label>
            <input
              id="profile-delete-password"
              v-model="profileDeletePassword"
              class="cds--text-input"
              type="password"
              autocomplete="current-password"
            />
            <label class="check-row-inline">
              <input v-model="profileDeleteConfirm" type="checkbox" />
              <span>I understand this will permanently delete my account.</span>
            </label>
          </div>
          <div class="profile-delete-actions">
            <button
              class="cds--btn cds--btn--danger"
              type="button"
              :disabled="profileBusy || !profileDeleteConfirm || !profileDeletePassword.trim()"
              @click="submitDeleteAccount"
            >
              {{ profileBusy ? 'Deleting...' : 'Delete My Account' }}
            </button>
          </div>
        </div>

        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" :disabled="profileBusy" @click="closeProfileDialog">
            Cancel
          </button>
          <button
            v-if="profileTab !== 'delete' && profileTab !== 'widget'"
            class="cds--btn cds--btn--primary"
            type="button"
            :disabled="profileBusy"
            @click="saveProfile"
          >
            {{ profileBusy ? 'Saving...' : 'Save Profile' }}
          </button>
        </div>
      </section>
    </div>

    <div v-if="adminDialogOpen" class="modal-backdrop">
      <section class="modal-card modal-card--wide cds--tile">
        <h3>Administration</h3>
        <div
          id="panel-admin-backups"
          class="modal-form-grid"
          role="tabpanel"
          aria-label="Backups"
        >
          <p>Administrative backup controls.</p>
          <button class="cds--btn cds--btn--secondary" type="button" :disabled="adminBusy" @click="triggerLocalBackupNow">
            {{ adminBusy ? 'Scheduling...' : 'Trigger Local Backup Now' }}
          </button>
          <button class="cds--btn cds--btn--secondary" type="button" :disabled="adminBusy" @click="downloadFullSiteBackup">
            Download Full Site Backup
          </button>
          <div class="import-file-row">
            <button class="cds--btn cds--btn--ghost" type="button" @click="openAdminRestorePicker">
              Choose Restore File
            </button>
            <span>{{ adminRestoreFileName || 'No restore file selected' }}</span>
          </div>
          <input
            ref="adminRestoreFileInput"
            class="import-file-input"
            type="file"
            accept=".gz,application/gzip"
            @change="onAdminRestoreFileSelected"
          />
          <button
            class="cds--btn cds--btn--danger"
            type="button"
            :disabled="adminRestoreBusy || !adminRestoreFile"
            @click="restoreFullSiteBackup"
          >
            {{ adminRestoreBusy ? 'Restoring...' : 'Restore Full Site Backup' }}
          </button>
        </div>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" :disabled="adminBusy || adminRestoreBusy" @click="closeAdminDialog">
            Close
          </button>
        </div>
      </section>
    </div>

    <div v-if="manageUsersDialogOpen" class="modal-backdrop">
      <section class="modal-card modal-card--wide cds--tile">
        <h3>Manage Users</h3>
        <div class="cds--tabs" role="navigation" aria-label="User management sections">
          <ul class="cds--tabs__nav" role="tablist">
            <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': manageUsersTab === 'users' }" role="presentation">
              <button
                id="tab-manage-users-users"
                class="cds--tabs__nav-link"
                role="tab"
                type="button"
                :aria-selected="manageUsersTab === 'users'"
                aria-controls="panel-manage-users-users"
                @click="manageUsersTab = 'users'"
              >
                Users
              </button>
            </li>
            <li class="cds--tabs__nav-item" :class="{ 'cds--tabs__nav-item--selected': manageUsersTab === 'registration' }" role="presentation">
              <button
                id="tab-manage-users-registration"
                class="cds--tabs__nav-link"
                role="tab"
                type="button"
                :aria-selected="manageUsersTab === 'registration'"
                aria-controls="panel-manage-users-registration"
                @click="manageUsersTab = 'registration'"
              >
                Registration
              </button>
            </li>
          </ul>
        </div>
        <div
          v-if="manageUsersTab === 'users'"
          id="panel-manage-users-users"
          class="modal-form-grid"
          role="tabpanel"
          aria-labelledby="tab-manage-users-users"
        >
          <p>Manage account access for all users.</p>
          <div class="manage-users-table-wrap">
            <table class="manage-users-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Last Login</th>
                  <th>Account Created</th>
                  <th>Role</th>
                  <th>Lock</th>
                  <th>Password</th>
                  <th>Delete</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="user in managedUsers" :key="user.id">
                  <td>{{ user.username }}</td>
                  <td>{{ formatDateTime(user.last_login_at) }}</td>
                  <td>{{ formatDateTime(user.created_at) }}</td>
                  <td>
                    <div class="cds--checkbox-wrapper manage-users-admin-check">
                      <input
                        :id="`managed-user-admin-${user.id}`"
                        class="cds--checkbox"
                        type="checkbox"
                        :checked="user.is_admin"
                        :disabled="manageUsersBusy || isManagedSelf(user)"
                        @change="onManagedUserAdminCheckboxChange(user, $event)"
                      />
                      <label :for="`managed-user-admin-${user.id}`" class="cds--checkbox-label">Admin</label>
                    </div>
                  </td>
                  <td>
                    <button
                      class="cds--btn cds--btn--ghost cds--btn--sm"
                      type="button"
                      :disabled="manageUsersBusy || isManagedSelf(user)"
                      @click="toggleManagedUserLock(user)"
                    >
                      {{ isManagedUserLocked(user) ? 'Unlock' : 'Lock' }}
                    </button>
                  </td>
                  <td>
                    <button
                      class="cds--btn cds--btn--secondary cds--btn--sm"
                      type="button"
                      :disabled="manageUsersBusy || isManagedSelf(user)"
                      @click="openManagedUserPasswordModal(user)"
                    >
                      Update Password
                    </button>
                  </td>
                  <td>
                    <button
                      class="cds--btn cds--btn--danger cds--btn--sm"
                      type="button"
                      :disabled="manageUsersBusy || isManagedSelf(user)"
                      @click="deleteManagedUser(user)"
                    >
                      Delete
                    </button>
                  </td>
                </tr>
                <tr v-if="managedUsers.length === 0">
                  <td colspan="7" class="registration-empty">No users found.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div
          v-else
          id="panel-manage-users-registration"
          class="modal-form-grid"
          role="tabpanel"
          aria-labelledby="tab-manage-users-registration"
        >
          <p>Create and manage registration codes for new accounts.</p>
          <div class="registration-create-grid">
            <div class="cds--form-item">
              <label for="registration-name" class="cds--label">Name</label>
              <input id="registration-name" v-model="registrationCreateName" class="cds--text-input" placeholder="Who is this code for?" />
            </div>
            <div class="cds--form-item">
              <label for="registration-expires-at" class="cds--label">Expires At (optional)</label>
              <input id="registration-expires-at" v-model="registrationCreateExpiresAt" class="cds--text-input" type="datetime-local" />
            </div>
            <button class="cds--btn cds--btn--primary" type="button" :disabled="registrationBusy" @click="createRegistrationCode">
              {{ registrationBusy ? 'Creating...' : 'Create Code' }}
            </button>
          </div>
          <div class="registration-table-wrap">
            <table class="registration-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Code</th>
                  <th>Expires</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in registrationCodes" :key="item.id">
                  <td>
                    <input
                      v-model="registrationEditById[item.id].name"
                      class="cds--text-input registration-inline-input"
                      type="text"
                    />
                  </td>
                  <td>
                    <div class="registration-code-cell">
                      <code>{{ maskRegistrationCode(item.code) }}</code>
                      <button
                        class="registration-copy-btn"
                        type="button"
                        :disabled="registrationBusy"
                        title="Copy code"
                        aria-label="Copy registration code"
                        @click="copyRegistrationCode(item.code)"
                      >
                        ⧉
                      </button>
                    </div>
                  </td>
                  <td>
                    <input
                      v-model="registrationEditById[item.id].expiresAtLocal"
                      class="cds--text-input registration-inline-input"
                      type="datetime-local"
                    />
                  </td>
                  <td class="registration-actions">
                    <button class="cds--btn cds--btn--ghost cds--btn--sm" type="button" :disabled="registrationBusy" @click="saveRegistrationCode(item.id)">
                      Save
                    </button>
                    <button class="cds--btn cds--btn--danger cds--btn--sm" type="button" :disabled="registrationBusy" @click="deleteRegistrationCode(item.id)">
                      Delete
                    </button>
                  </td>
                </tr>
                <tr v-if="registrationCodes.length === 0">
                  <td colspan="4" class="registration-empty">No registration codes yet.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" :disabled="manageUsersBusy || registrationBusy" @click="closeManageUsersDialog">
            Close
          </button>
        </div>
      </section>
    </div>

    <div v-if="manageUserPasswordDialogOpen" class="modal-backdrop">
      <section class="modal-card cds--tile">
        <h3>Update Password: {{ managePasswordTargetUsername }}</h3>
        <div class="modal-form-grid">
          <label class="bank-label" for="admin-user-password">New Password</label>
          <input
            id="admin-user-password"
            v-model="managePasswordDraft"
            class="cds--text-input"
            type="password"
            autocomplete="new-password"
          />
          <label class="bank-label" for="admin-user-password-verify">Verify Password</label>
          <input
            id="admin-user-password-verify"
            v-model="managePasswordVerifyDraft"
            class="cds--text-input"
            type="password"
            autocomplete="new-password"
          />
        </div>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" :disabled="manageUsersBusy" @click="closeManagedUserPasswordModal">
            Cancel
          </button>
          <button
            class="cds--btn cds--btn--primary"
            type="button"
            :disabled="manageUsersBusy || !managePasswordDraft.trim() || !managePasswordVerifyDraft.trim()"
            @click="submitManagedUserPasswordUpdate"
          >
            {{ manageUsersBusy ? 'Updating...' : 'Update Password' }}
          </button>
        </div>
      </section>
    </div>

    <div v-if="manageUserDeleteDialogOpen" class="modal-backdrop">
      <section class="modal-card cds--tile">
        <h3>Delete User</h3>
        <p>
          Delete user "{{ manageDeleteTargetUsername }}" and all of their data? This action cannot be undone.
        </p>
        <div class="modal-actions">
          <button class="cds--btn cds--btn--ghost" type="button" :disabled="manageUsersBusy" @click="closeManagedUserDeleteModal">
            Cancel
          </button>
          <button class="cds--btn cds--btn--danger" type="button" :disabled="manageUsersBusy" @click="confirmDeleteManagedUser">
            {{ manageUsersBusy ? 'Deleting...' : 'Delete User' }}
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { currentUser, deleteOwnAccount, logout, regenerateWidgetUrl, updateProfile } from '@/lib/auth'
import { errorMessage, request, snackbar } from '@/lib/api'
import { enableMaskedMode, maskedModeEnabled } from '@/lib/maskedMode'
import { absolutePublicUrl, apiUrl, assetUrl } from '@/lib/paths'
import UnifiedDropdown from '@/components/UnifiedDropdown.vue'

const router = useRouter()
const exportDialogOpen = ref(false)
const exportPassword = ref('')
const exportBusy = ref(false)

const importDialogOpen = ref(false)
const importPassword = ref('')
const importBusy = ref(false)
const importFileName = ref('')
const importPackageData = ref<Record<string, unknown> | string | null>(null)
const importFileInput = ref<HTMLInputElement | null>(null)
const profileMenuRef = ref<HTMLElement | null>(null)
const profileMenuOpen = ref(false)
const profileDialogOpen = ref(false)
const profileBusy = ref(false)
const profileTab = ref<'info' | 'password' | 'wallets' | 'widget' | 'delete'>('info')
const profileCurrentPassword = ref('')
const profileNewPassword = ref('')
const profileDraftAvatarIconId = ref<string | null>(null)
const profilePaypalAccountId = ref('')
const profileGooglePayAccountId = ref('')
const profileWidgetCopied = ref(false)
const profileDeletePassword = ref('')
const profileDeleteConfirm = ref(false)
const showProfileIconLibrary = ref(false)
const profileIconFileInput = ref<HTMLInputElement | null>(null)
const adminDialogOpen = ref(false)
const adminBusy = ref(false)
const adminRestoreBusy = ref(false)
const adminRestoreFileInput = ref<HTMLInputElement | null>(null)
const adminRestoreFile = ref<File | null>(null)
const adminRestoreFileName = ref('')

type IconChoice = {
  id: string
  is_default: boolean
}

type ManageUsersTab = 'users' | 'registration'

type RegistrationCodeItem = {
  id: string
  code: string
  name: string
  expires_at: string | null
  created_by_user_id: string
  created_at: string
  updated_at: string
}

type RegistrationCodeEdit = {
  name: string
  expiresAtLocal: string
}

type ManagedUser = {
  id: string
  username: string
  is_admin: boolean
  last_login_at: string | null
  password_changed_at: string | null
  created_at: string
  password_lockout_until: string | null
}

type WalletAccountSummary = {
  id: string
  name: string
  type: string
}

const profileIconChoices = ref<IconChoice[]>([])
const profileWalletAccounts = ref<WalletAccountSummary[]>([])
const registrationBusy = ref(false)
const registrationCodes = ref<RegistrationCodeItem[]>([])
const registrationEditById = ref<Record<string, RegistrationCodeEdit>>({})
const registrationCreateName = ref('')
const registrationCreateExpiresAt = ref('')
const manageUsersDialogOpen = ref(false)
const manageUsersTab = ref<ManageUsersTab>('users')
const manageUsersBusy = ref(false)
const managedUsers = ref<ManagedUser[]>([])
const manageUserPasswordDialogOpen = ref(false)
const managePasswordTargetUserId = ref('')
const managePasswordTargetUsername = ref('')
const managePasswordDraft = ref('')
const managePasswordVerifyDraft = ref('')
const manageUserDeleteDialogOpen = ref(false)
const manageDeleteTargetUserId = ref('')
const manageDeleteTargetUsername = ref('')

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

const iconUrl = (iconId: string) => apiUrl(`icons/${iconId}`)

const profileAvatarUrl = computed(() => {
  const iconId = profileDialogOpen.value
    ? profileDraftAvatarIconId.value
    : (currentUser.value?.avatar_icon_id || null)
  return iconId ? iconUrl(iconId) : ''
})

const profileWidgetUrl = computed(() => {
  const token = currentUser.value?.widget_token
  if (!token) {
    return ''
  }
  return absolutePublicUrl(apiUrl(`widgets/net-worth.png?token=${encodeURIComponent(token)}`))
})

const formatDateTime = (value?: string | null) => {
  if (!value) {
    return 'Never'
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return value
  }
  return parsed.toLocaleString()
}

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

const onProfileManageClick = async () => {
  closeProfileMenu()
  profileTab.value = 'info'
  profileCurrentPassword.value = ''
  profileNewPassword.value = ''
  profileDraftAvatarIconId.value = currentUser.value?.avatar_icon_id || null
  profilePaypalAccountId.value = currentUser.value?.paypal_account_id || ''
  profileGooglePayAccountId.value = currentUser.value?.google_pay_account_id || ''
  profileWidgetCopied.value = false
  profileDeletePassword.value = ''
  profileDeleteConfirm.value = false
  showProfileIconLibrary.value = false
  profileDialogOpen.value = true
  await Promise.all([loadProfileIcons(), loadProfileWalletAccounts()])
}

const onAdministrationClick = () => {
  closeProfileMenu()
  adminRestoreFile.value = null
  adminRestoreFileName.value = ''
  adminDialogOpen.value = true
}

const onManageUsersClick = async () => {
  closeProfileMenu()
  manageUsersTab.value = 'users'
  manageUsersDialogOpen.value = true
  await loadManagedUsers()
}

const onProfileExportClick = () => {
  closeProfileMenu()
  openExportDialog()
}

const onProfileImportClick = () => {
  closeProfileMenu()
  openImportDialog()
}

const onEnableMaskedModeClick = () => {
  enableMaskedMode(currentUser.value?.id)
  closeProfileMenu()
}

const onProfileLogoutClick = async () => {
  closeProfileMenu()
  await signOut()
}

const closeAdminDialog = () => {
  if (adminBusy.value || adminRestoreBusy.value) {
    return
  }
  adminDialogOpen.value = false
}

const closeManageUsersDialog = () => {
  if (manageUsersBusy.value || registrationBusy.value) {
    return
  }
  manageUserPasswordDialogOpen.value = false
  manageUserDeleteDialogOpen.value = false
  manageUsersDialogOpen.value = false
}

const loadManagedUsers = async () => {
  manageUsersBusy.value = true
  try {
    managedUsers.value = await request.get<ManagedUser[]>('/admin/users')
  } finally {
    manageUsersBusy.value = false
  }
}

const isManagedSelf = (user: ManagedUser) => currentUser.value?.id === user.id

const isManagedUserLocked = (user: ManagedUser) => {
  if (!user.password_lockout_until) {
    return false
  }
  const lockUntil = new Date(user.password_lockout_until)
  if (Number.isNaN(lockUntil.getTime())) {
    return false
  }
  return lockUntil.getTime() > Date.now()
}

const openManagedUserPasswordModal = (user: ManagedUser) => {
  if (isManagedSelf(user)) {
    return
  }
  managePasswordTargetUserId.value = user.id
  managePasswordTargetUsername.value = user.username
  managePasswordDraft.value = ''
  managePasswordVerifyDraft.value = ''
  manageUserPasswordDialogOpen.value = true
}

const closeManagedUserPasswordModal = () => {
  if (manageUsersBusy.value) {
    return
  }
  manageUserPasswordDialogOpen.value = false
}

const closeManagedUserDeleteModal = () => {
  if (manageUsersBusy.value) {
    return
  }
  manageUserDeleteDialogOpen.value = false
}

const submitManagedUserPasswordUpdate = async () => {
  if (!managePasswordTargetUserId.value) {
    return
  }
  const draft = managePasswordDraft.value.trim()
  const verify = managePasswordVerifyDraft.value.trim()
  if (!draft || !verify) {
    return
  }
  if (draft !== verify) {
    errorMessage.value = 'Password and verify password must match'
    snackbar.value = true
    return
  }
  manageUsersBusy.value = true
  try {
    await request.put(`/admin/users/${managePasswordTargetUserId.value}/password`, { new_password: draft })
    manageUserPasswordDialogOpen.value = false
    await loadManagedUsers()
  } finally {
    manageUsersBusy.value = false
  }
}

const toggleManagedUserLock = async (user: ManagedUser) => {
  if (isManagedSelf(user)) {
    return
  }
  manageUsersBusy.value = true
  try {
    await request.put(`/admin/users/${user.id}/lock`, { locked: !isManagedUserLocked(user) })
    await loadManagedUsers()
  } finally {
    manageUsersBusy.value = false
  }
}

const onManagedUserAdminCheckboxChange = async (user: ManagedUser, event: Event) => {
  if (isManagedSelf(user)) {
    return
  }
  const target = event.target as HTMLInputElement
  const isAdmin = !!target.checked
  manageUsersBusy.value = true
  try {
    await request.put(`/admin/users/${user.id}/admin`, { is_admin: isAdmin })
    await loadManagedUsers()
  } finally {
    manageUsersBusy.value = false
  }
}

const deleteManagedUser = async (user: ManagedUser) => {
  if (isManagedSelf(user)) {
    return
  }
  manageDeleteTargetUserId.value = user.id
  manageDeleteTargetUsername.value = user.username
  manageUserDeleteDialogOpen.value = true
}

const confirmDeleteManagedUser = async () => {
  if (!manageDeleteTargetUserId.value) {
    return
  }
  manageUsersBusy.value = true
  try {
    await request.delete(`/admin/users/${manageDeleteTargetUserId.value}`)
    manageUserDeleteDialogOpen.value = false
    manageDeleteTargetUserId.value = ''
    manageDeleteTargetUsername.value = ''
    await loadManagedUsers()
  } finally {
    manageUsersBusy.value = false
  }
}

const isoToDateTimeLocal = (value: string | null) => {
  if (!value) {
    return ''
  }
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime())) {
    return ''
  }
  const pad = (n: number) => n.toString().padStart(2, '0')
  const year = parsed.getFullYear()
  const month = pad(parsed.getMonth() + 1)
  const day = pad(parsed.getDate())
  const hours = pad(parsed.getHours())
  const minutes = pad(parsed.getMinutes())
  return `${year}-${month}-${day}T${hours}:${minutes}`
}

const dateTimeLocalToIso = (value: string) => {
  const trimmed = value.trim()
  if (!trimmed) {
    return null
  }
  const parsed = new Date(trimmed)
  if (Number.isNaN(parsed.getTime())) {
    return null
  }
  return parsed.toISOString()
}

const rebuildRegistrationEditDrafts = () => {
  const drafts: Record<string, RegistrationCodeEdit> = {}
  for (const item of registrationCodes.value) {
    drafts[item.id] = {
      name: item.name,
      expiresAtLocal: isoToDateTimeLocal(item.expires_at),
    }
  }
  registrationEditById.value = drafts
}

const loadRegistrationCodes = async () => {
  registrationBusy.value = true
  try {
    registrationCodes.value = await request.get<RegistrationCodeItem[]>('/admin/registration-codes')
    rebuildRegistrationEditDrafts()
  } finally {
    registrationBusy.value = false
  }
}

const createRegistrationCode = async () => {
  const name = registrationCreateName.value.trim()
  if (!name) {
    errorMessage.value = 'Name is required'
    snackbar.value = true
    return
  }
  registrationBusy.value = true
  try {
    await request.post<RegistrationCodeItem>('/admin/registration-codes', {
      name,
      expires_at: dateTimeLocalToIso(registrationCreateExpiresAt.value),
    })
    registrationCreateName.value = ''
    registrationCreateExpiresAt.value = ''
    await loadRegistrationCodes()
  } finally {
    registrationBusy.value = false
  }
}

const saveRegistrationCode = async (id: string) => {
  const draft = registrationEditById.value[id]
  if (!draft) {
    return
  }
  registrationBusy.value = true
  try {
    await request.put<RegistrationCodeItem>(`/admin/registration-codes/${id}`, {
      name: draft.name.trim(),
      expires_at: dateTimeLocalToIso(draft.expiresAtLocal),
    })
    await loadRegistrationCodes()
  } finally {
    registrationBusy.value = false
  }
}

const maskRegistrationCode = (code: string) => {
  const trimmed = (code || '').trim()
  if (!trimmed) {
    return '...'
  }
  return `${trimmed.slice(0, 2)}...`
}

const copyRegistrationCode = async (code: string) => {
  await navigator.clipboard.writeText(code)
}

const deleteRegistrationCode = async (id: string) => {
  registrationBusy.value = true
  try {
    await request.delete(`/admin/registration-codes/${id}`)
    await loadRegistrationCodes()
  } finally {
    registrationBusy.value = false
  }
}

const triggerLocalBackupNow = async () => {
  adminBusy.value = true
  try {
    await request.post('/backups/run-now')
  } finally {
    adminBusy.value = false
  }
}

const downloadFullSiteBackup = async () => {
  adminBusy.value = true
  try {
    const blob = await request.post<Blob>(
      '/backups/site/export',
      {},
      { responseType: 'blob' },
    )
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'site-backup.sql.gz'
    document.body.appendChild(anchor)
    anchor.click()
    anchor.remove()
    URL.revokeObjectURL(url)
  } finally {
    adminBusy.value = false
  }
}

const openAdminRestorePicker = () => {
  adminRestoreFileInput.value?.click()
}

const onAdminRestoreFileSelected = (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  adminRestoreFile.value = file || null
  adminRestoreFileName.value = file?.name || ''
}

const restoreFullSiteBackup = async () => {
  if (!adminRestoreFile.value) {
    return
  }
  adminRestoreBusy.value = true
  try {
    const form = new FormData()
    form.append('file', adminRestoreFile.value)
    await request.post('/backups/site/restore', form)
    adminDialogOpen.value = false
    window.location.reload()
  } finally {
    adminRestoreBusy.value = false
  }
}

const closeProfileDialog = () => {
  if (profileBusy.value) {
    return
  }
  profileDialogOpen.value = false
}

const loadProfileIcons = async () => {
  const icons = await request.get<IconChoice[]>('/icons')
  profileIconChoices.value = icons
}

const loadProfileWalletAccounts = async () => {
  profileWalletAccounts.value = await request.get<WalletAccountSummary[]>('/accounts')
}

const walletAccountDropdownOptions = computed(() => [
  { label: 'Not linked', value: '' },
  ...profileWalletAccounts.value.map((account) => ({
    label: `${account.name} (${account.type.replaceAll('_', ' ')})`,
    value: account.id,
  })),
])

const toggleProfileIconLibrary = async () => {
  showProfileIconLibrary.value = !showProfileIconLibrary.value
  if (showProfileIconLibrary.value && profileIconChoices.value.length === 0) {
    await loadProfileIcons()
  }
}

const openProfileAvatarUploadPicker = () => {
  profileIconFileInput.value?.click()
}

const onProfileAvatarUpload = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) {
    return
  }
  const form = new FormData()
  form.append('file', file)
  const uploaded = await request.post<{ id: string; hash: string }>('/icons', form)
  profileDraftAvatarIconId.value = uploaded.id
  if (showProfileIconLibrary.value) {
    await loadProfileIcons()
  }
  input.value = ''
}

const clearProfileAvatar = () => {
  profileDraftAvatarIconId.value = null
}

const copyProfileWidgetUrl = async () => {
  if (!profileWidgetUrl.value) {
    return
  }
  try {
    await navigator.clipboard.writeText(profileWidgetUrl.value)
    profileWidgetCopied.value = true
    window.setTimeout(() => {
      profileWidgetCopied.value = false
    }, 1600)
  } catch {
    errorMessage.value = 'Unable to copy the widget URL'
    snackbar.value = true
  }
}

const regenerateProfileWidgetUrl = async () => {
  profileBusy.value = true
  try {
    await regenerateWidgetUrl()
    profileWidgetCopied.value = false
  } finally {
    profileBusy.value = false
  }
}

const saveProfile = async () => {
  profileBusy.value = true
  try {
    const payload: {
      avatar_icon_id?: string | null
      paypal_account_id?: string | null
      google_pay_account_id?: string | null
      current_password?: string
      new_password?: string
    } = {}
    if ((currentUser.value?.avatar_icon_id || null) !== profileDraftAvatarIconId.value) {
      payload.avatar_icon_id = profileDraftAvatarIconId.value
    }
    if ((currentUser.value?.paypal_account_id || '') !== profilePaypalAccountId.value) {
      payload.paypal_account_id = profilePaypalAccountId.value || null
    }
    if ((currentUser.value?.google_pay_account_id || '') !== profileGooglePayAccountId.value) {
      payload.google_pay_account_id = profileGooglePayAccountId.value || null
    }
    if (profileNewPassword.value.trim()) {
      payload.current_password = profileCurrentPassword.value
      payload.new_password = profileNewPassword.value
    }
    if (Object.keys(payload).length === 0) {
      profileDialogOpen.value = false
      return
    }
    await updateProfile(payload)
    profileCurrentPassword.value = ''
    profileNewPassword.value = ''
    profileDialogOpen.value = false
  } finally {
    profileBusy.value = false
  }
}

const submitDeleteAccount = async () => {
  if (!profileDeleteConfirm.value || !profileDeletePassword.value.trim()) {
    return
  }
  profileBusy.value = true
  try {
    await deleteOwnAccount(profileDeletePassword.value)
    profileDialogOpen.value = false
    await router.push('/')
  } finally {
    profileBusy.value = false
  }
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

const onWindowKeyDown = (event: KeyboardEvent) => {
  if (event.key !== 'Escape') {
    return
  }
  if (adminDialogOpen.value) {
    closeAdminDialog()
    return
  }
  if (manageUserPasswordDialogOpen.value) {
    closeManagedUserPasswordModal()
    return
  }
  if (manageUserDeleteDialogOpen.value) {
    closeManagedUserDeleteModal()
    return
  }
  if (manageUsersDialogOpen.value) {
    closeManageUsersDialog()
    return
  }
  if (profileDialogOpen.value) {
    closeProfileDialog()
    return
  }
  if (importDialogOpen.value) {
    closeImportDialog()
    return
  }
  if (exportDialogOpen.value) {
    closeExportDialog()
    return
  }
  if (profileMenuOpen.value) {
    closeProfileMenu()
  }
}

onMounted(() => {
  window.addEventListener('pointerdown', onWindowPointerDown)
  window.addEventListener('keydown', onWindowKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('pointerdown', onWindowPointerDown)
  window.removeEventListener('keydown', onWindowKeyDown)
})

watch(manageUsersTab, async (tab) => {
  if (!manageUsersDialogOpen.value || tab !== 'registration') {
    return
  }
  await loadRegistrationCodes()
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
  importPackageData.value = null
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
    importPackageData.value = null
    return
  }
  try {
    const text = await file.text()
    const normalized = text.trim()
    if (!normalized) {
      throw new Error('Package file is empty')
    }
    let parsed: unknown = null
    try {
      parsed = JSON.parse(normalized)
    } catch {
      parsed = null
    }
    if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
      importPackageData.value = parsed as Record<string, unknown>
    } else {
      importPackageData.value = normalized
    }
    importFileName.value = file.name
  } catch (err: any) {
    importPackageData.value = null
    importFileName.value = ''
    errorMessage.value = err?.message || 'Invalid package file'
    snackbar.value = true
  }
}

const runImport = async () => {
  if (importPackageData.value === null) {
    return
  }
  importBusy.value = true
  try {
    const password = importPassword.value.trim() || null
    await request.post('/data/import', {
      package: importPackageData.value,
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
  object-fit: cover;
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

.profile-menu-item--disabled {
  cursor: default;
  color: var(--cds-text-secondary);
  display: grid;
  gap: 2px;
}

.profile-menu-item--disabled:hover {
  background: transparent;
}

.profile-menu-item-note {
  font-size: 0.75rem;
}

.shell-main {
  padding-top: 0.75rem;
  margin-left: 0 !important;
  width: 100%;
}

.masked-mode-banner {
  margin: 0 0 0.9rem;
  padding: 0.7rem 1rem;
  border: 1px solid #f59e0b;
  background: #fff7ed;
  color: #9a3412;
  font-size: 0.82rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  text-align: center;
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

.modal-card--wide {
  width: min(760px, 100%);
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

.profile-meta-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.profile-avatar-section {
  display: grid;
  gap: 12px;
}

.profile-avatar-large-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.profile-avatar-large {
  width: 84px;
  height: 84px;
  border-radius: 50%;
  object-fit: cover;
}

.profile-avatar-large--fallback {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--cds-support-info);
  color: #fff;
  font-size: 1.6rem;
  font-weight: 700;
}

.profile-avatar-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.profile-icon-grid {
  max-height: 150px;
  overflow: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(44px, 1fr));
  gap: 8px;
  padding: 4px;
  border: 1px solid var(--cds-border-subtle-01);
}

.profile-icon-choice {
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  border-radius: 6px;
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.profile-icon-choice--selected {
  border-color: var(--cds-link-primary);
}

.profile-icon-choice-image {
  width: 30px;
  height: 30px;
  object-fit: cover;
}

.profile-stats p {
  margin: 0 0 8px;
}

.password-section {
  border-top: 1px solid var(--cds-border-subtle-01);
  padding-top: 12px;
}

.password-section h4 {
  margin: 0 0 10px;
}

.profile-widget-section {
  border-top: 1px solid var(--cds-border-subtle-01);
  padding-top: 12px;
  display: grid;
  gap: 12px;
}

.profile-widget-section h4,
.profile-widget-section p {
  margin: 0;
}

.profile-widget-section p {
  color: var(--cds-text-secondary);
}

.profile-widget-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.profile-delete-section {
  border-top: 1px solid var(--cds-border-subtle-01);
  padding-top: 12px;
  display: grid;
  gap: 12px;
}

.profile-delete-section h4 {
  margin: 0;
}

.profile-delete-warning {
  color: var(--cds-support-error);
}

.check-row-inline {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--cds-text-primary);
}

.profile-delete-actions {
  display: flex;
  justify-content: flex-start;
}

.manage-users-table-wrap {
  overflow-x: auto;
}

.manage-users-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.84rem;
}

.manage-users-table th,
.manage-users-table td {
  border-bottom: 1px solid var(--cds-border-subtle-01);
  padding: 8px 6px;
  vertical-align: top;
}

.manage-users-admin-check {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  white-space: nowrap;
}

.registration-create-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: 1fr 1fr auto;
  align-items: end;
}

.registration-table-wrap {
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--cds-border-subtle-01);
}

.registration-table {
  width: 100%;
  border-collapse: collapse;
  table-layout: fixed;
}

.registration-table th,
.registration-table td {
  padding: 8px 10px;
  border-bottom: 1px solid var(--cds-border-subtle-01);
  text-align: left;
  vertical-align: middle;
}

.registration-inline-input {
  width: 100%;
  min-width: 0;
}

.registration-actions {
  display: flex;
  gap: 8px;
}

.registration-code-cell {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.registration-copy-btn {
  border: 1px solid var(--cds-border-subtle-01);
  border-radius: 4px;
  background: var(--cds-layer);
  color: var(--cds-text-primary);
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}

.registration-copy-btn:hover {
  background: var(--cds-layer-hover);
}

.registration-empty {
  color: var(--cds-text-secondary);
}

@media (max-width: 760px) {
  .profile-meta-grid {
    grid-template-columns: 1fr;
  }

  .registration-create-grid {
    grid-template-columns: 1fr;
  }
}
</style>
