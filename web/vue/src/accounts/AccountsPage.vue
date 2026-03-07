<template>
  <v-container>
    <v-card class="pa-4 mb-4">
      <v-form @submit.prevent="saveAccount">
        <v-text-field v-model="form.name" label="Name" required />
        <v-text-field v-model="form.type" label="Type" required />
        <v-text-field v-model="form.balance" label="Balance (cents)" type="number" required />
        <v-text-field v-model="form.apr" label="APR (%)" type="number" />
        <v-text-field v-model="form.url" label="URL" />
        <v-textarea v-model="form.notes" label="Notes" />
        <v-btn type="submit" color="primary" class="mt-2">{{ form.id ? 'Update' : 'Create' }}</v-btn>
        <v-btn v-if="form.id" @click="resetForm" class="mt-2 ml-2">Cancel</v-btn>
      </v-form>
    </v-card>

    <v-data-table :items="accounts" :headers="headers" class="elevation-1">
      <template #item.actions="{ item }">
        <v-btn icon @click="editAccount(item)"><v-icon>mdi-pencil</v-icon></v-btn>
        <v-btn icon @click="deleteAccount(item.id)"><v-icon>mdi-delete</v-icon></v-btn>
      </template>
    </v-data-table>
  </v-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { request } from '@/lib/api'

interface Account {
  id: number
  name: string
  type: string
  balance: number
  apr?: number
  url?: string
  notes?: string
}

const accounts = ref<Account[]>([])
const form = ref<Partial<Account>>({})

const snackbar = ref(false)
const errorMessage = ref('')

const headers = [
  { title: 'Name', value: 'name' },
  { title: 'Type', value: 'type' },
  { title: 'Balance', value: 'balance' },
  { title: 'APR', value: 'apr' },
  { title: 'Actions', value: 'actions', sortable: false }
]

const loadAccounts = async () => {
  const res = await request.get(`/accounts`)
  accounts.value = res.data
}

const saveAccount = async () => {
  if (form.value.id) {
    await request.put(`/accounts/${form.value.id}`, form.value)
  } else {
    await request.post(`/accounts`, form.value)
  }
  await loadAccounts()
  resetForm()
}

const editAccount = (acct: Account) => {
  form.value = { ...acct }
}

const deleteAccount = async (id: number) => {
  await request.delete(`${API_URL}/${id}`)
  await loadAccounts()
}

const resetForm = () => {
  form.value = {}
}

onMounted(loadAccounts)
</script>
