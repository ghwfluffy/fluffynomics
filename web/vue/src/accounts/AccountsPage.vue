<template>
  <v-container class="dashboard py-6">
    <v-card class="widgets pa-5 mb-6" elevation="2">
      <div class="text-h6 mb-2">Insights Widgets</div>
      <div class="text-body-2 text-medium-emphasis mb-4">
        Placeholder area for trend charts, cashflow graphs, and forecasting widgets.
      </div>
      <div class="widget-grid">
        <div class="widget-slot">Net Worth Trend</div>
        <div class="widget-slot">Budget vs Actual</div>
        <div class="widget-slot">Debt Burn Down</div>
      </div>
    </v-card>

    <section v-for="section in sections" :key="section.key" class="mb-6">
      <div class="section-header mb-3">
        <h2 class="text-h6">{{ section.title }}</h2>
      </div>

      <div v-if="section.accounts.length" class="section-grid">
        <div v-for="account in section.accounts" :key="account.id">
          <v-card class="account-tile" variant="outlined">
            <v-card-text>
              <div class="tile-title">{{ account.name }}</div>
              <div class="tile-sub">{{ account.organization || 'Unknown organization' }}</div>
              <div class="tile-sub">•••• {{ last4(account.account_number) }}</div>
              <div class="tile-balance" :class="balanceTone(section.key)">
                {{ balanceLabel(account) }}
              </div>
              <div class="tile-type">{{ account.type.replaceAll('_', ' ') }}</div>
            </v-card-text>
          </v-card>
        </div>
      </div>

      <v-card v-else variant="tonal" class="pa-3 empty-state">
        No accounts yet.
      </v-card>
    </section>
  </v-container>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { request } from '@/lib/api'

type AccountType =
  | 'checking'
  | 'savings'
  | 'cash'
  | 'line_of_credit'
  | 'credit_card'
  | 'stocks_account'
  | 'crypto_exchange'
  | 'crypto_wallet'
  | 'retirement'
  | 'loan'
  | 'rewards_card'

interface AccountPayload {
  id: string
  account_number: string
  name: string
  type: AccountType
  organization?: string
  balance_cents?: number
  usd_balance_cents?: number
  stock_positions?: Array<{ stock_id: string; quantity: string }>
  crypto_positions?: Array<{ ticker: string; quantity: string }>
}

interface Section {
  key: string
  title: string
  types: AccountType[]
  accounts: AccountPayload[]
}

const accounts = ref<AccountPayload[]>([])

const sectionDefinitions: Array<Omit<Section, 'accounts'>> = [
  { key: 'cash', title: 'Cash Accounts', types: ['checking', 'savings', 'cash'] },
  {
    key: 'securities',
    title: 'Marketable Securities',
    types: ['stocks_account', 'crypto_exchange', 'crypto_wallet'],
  },
  { key: 'hard_assets', title: 'Hard Assets', types: ['retirement'] },
  { key: 'credit_cards', title: 'Credit Cards', types: ['credit_card'] },
  { key: 'payables', title: 'Payables', types: ['loan', 'line_of_credit'] },
  { key: 'rewards', title: 'Rewards', types: ['rewards_card'] },
]

const sections = computed<Section[]>(() =>
  sectionDefinitions.map((section) => ({
    ...section,
    accounts: accounts.value.filter((account) => section.types.includes(account.type)),
  })),
)

const last4 = (value: string) => value.slice(-4)

const cents = (value?: number) =>
  new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
  }).format((value || 0) / 100)

const balanceLabel = (account: AccountPayload) => {
  if (account.type === 'stocks_account') {
    return `${account.stock_positions?.length || 0} stock positions`
  }
  if (account.type === 'crypto_wallet') {
    return `${account.crypto_positions?.length || 0} crypto positions`
  }
  if (account.type === 'crypto_exchange') {
    return `USD ${cents(account.usd_balance_cents)}`
  }
  return `Balance ${cents(account.balance_cents)}`
}

const balanceTone = (sectionKey: string) =>
  ['credit_cards', 'payables'].includes(sectionKey) ? 'balance-liability' : 'balance-asset'

const loadAccounts = async () => {
  accounts.value = await request.get<AccountPayload[]>('/accounts')
}

onMounted(loadAccounts)
</script>

<style scoped>
.dashboard {
  max-width: 1320px;
}

.widgets {
  background: linear-gradient(140deg, #ffffff, #f8fafc);
}

.widget-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.widget-slot {
  border: 1px dashed #94a3b8;
  border-radius: 12px;
  min-height: 96px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: #475569;
  background: #ffffffcc;
}

.section-header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
}

.account-tile {
  border-radius: 14px;
  height: 100%;
}

.section-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.tile-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 2px;
}

.tile-sub {
  font-size: 0.87rem;
  color: #64748b;
}

.tile-balance {
  margin-top: 10px;
  font-size: 1rem;
  font-weight: 700;
}

.balance-asset {
  color: #047857;
}

.balance-liability {
  color: #b91c1c;
}

.tile-type {
  margin-top: 6px;
  font-size: 0.78rem;
  color: #475569;
  text-transform: capitalize;
}

.empty-state {
  color: #475569;
}

@media (max-width: 1200px) {
  .section-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .section-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .section-grid {
    grid-template-columns: 1fr;
  }
}
</style>
