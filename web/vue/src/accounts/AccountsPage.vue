<template>
  <v-container class="py-6">
    <v-row>
      <v-col cols="12" md="7">
        <v-card class="pa-4">
          <v-card-title class="px-0">
            {{ form.id ? 'Edit Account' : 'Create Account' }}
          </v-card-title>
          <v-form @submit.prevent="saveAccount">
            <v-row>
              <v-col cols="12" md="6">
                <v-text-field v-model="form.account_number" label="Account Number" required />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model="form.name" label="Name" required />
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="form.type"
                  :items="accountTypes"
                  item-title="label"
                  item-value="value"
                  label="Type"
                  required
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model="form.organization" label="Organization" />
              </v-col>
              <v-col cols="12">
                <v-text-field v-model="form.url" label="URL" />
              </v-col>
              <v-col cols="12">
                <v-textarea v-model="form.notes" label="Notes" rows="2" />
              </v-col>
            </v-row>

            <v-divider class="my-4" />

            <v-row v-if="needsBalance">
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="form.balance_cents"
                  label="Balance (cents)"
                  type="number"
                />
              </v-col>
            </v-row>

            <v-row v-if="needsFee">
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="form.fee_amount_cents"
                  label="Fee Amount (cents)"
                  type="number"
                />
              </v-col>
              <v-col cols="12" md="6">
                <v-text-field v-model="form.fee_period" label="Fee Period" />
              </v-col>
            </v-row>

            <v-row v-if="needsRouting">
              <v-col cols="12" md="6">
                <v-text-field v-model="form.routing_number" label="Routing Number" />
              </v-col>
            </v-row>

            <v-row v-if="needsApy">
              <v-col cols="12" md="6">
                <v-text-field v-model.number="form.apy_bps" label="APY (bps)" type="number" />
              </v-col>
              <v-col cols="12" md="6">
                <v-select
                  v-model="form.compound_period"
                  :items="compoundPeriods"
                  label="Compound Period"
                />
              </v-col>
            </v-row>

            <v-row v-if="needsApr">
              <v-col cols="12" md="4">
                <v-text-field v-model.number="form.apr_bps" label="APR (bps)" type="number" />
              </v-col>
              <v-col cols="12" md="4" v-if="needsCompoundPeriod">
                <v-select
                  v-model="form.compound_period"
                  :items="compoundPeriods"
                  label="Compound Period"
                />
              </v-col>
              <v-col cols="12" md="4" v-if="needsBillingDay">
                <v-text-field v-model.number="form.billing_day" label="Billing Day" type="number" />
              </v-col>
              <v-col cols="12" md="4" v-if="needsPaymentDay">
                <v-text-field v-model.number="form.payment_day" label="Payment Day" type="number" />
              </v-col>
            </v-row>

            <v-row v-if="needsExpiration">
              <v-col cols="12" md="6">
                <v-text-field
                  v-model="form.expiration_date"
                  label="Expiration Date"
                  type="date"
                />
              </v-col>
              <v-col cols="12" md="6" v-if="needsCvc">
                <v-text-field v-model="form.cvc" label="CVC" />
              </v-col>
            </v-row>

            <v-row v-if="form.type === 'crypto_exchange'">
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="form.usd_balance_cents"
                  label="USD Balance (cents)"
                  type="number"
                />
              </v-col>
            </v-row>

            <v-row v-if="form.type === 'retirement'">
              <v-col cols="12" md="6">
                <v-select
                  v-model="form.retirement_account_type"
                  :items="retirementTypes"
                  label="Retirement Type"
                />
              </v-col>
            </v-row>

            <v-row v-if="form.type === 'loan'">
              <v-col cols="12" md="6">
                <v-text-field
                  v-model.number="form.payment_amount_cents"
                  label="Payment Amount (cents)"
                  type="number"
                />
              </v-col>
            </v-row>

            <v-card variant="tonal" class="pa-3 my-4" v-if="form.type === 'cash'">
              <div class="text-subtitle-1 mb-2">Cash Bills</div>
              <v-row>
                <v-col cols="6">
                  <v-text-field
                    v-model.number="cashDraft.denomination_cents"
                    label="Denomination (cents)"
                    type="number"
                  />
                </v-col>
                <v-col cols="4">
                  <v-text-field v-model.number="cashDraft.quantity" label="Quantity" type="number" />
                </v-col>
                <v-col cols="2" class="d-flex align-center">
                  <v-btn @click="addCashBill">Add</v-btn>
                </v-col>
              </v-row>
              <v-chip
                v-for="(item, idx) in form.cash_bills"
                :key="`cash-${idx}`"
                class="ma-1"
                closable
                @click:close="removeCashBill(idx)"
              >
                {{ item.quantity }} x {{ item.denomination_cents }}
              </v-chip>
            </v-card>

            <v-card variant="tonal" class="pa-3 my-4" v-if="needsCryptoPositions">
              <div class="text-subtitle-1 mb-2">Crypto Positions</div>
              <v-row>
                <v-col cols="5">
                  <v-text-field v-model="cryptoDraft.ticker" label="Ticker" />
                </v-col>
                <v-col cols="5">
                  <v-text-field v-model="cryptoDraft.quantity" label="Quantity" type="number" />
                </v-col>
                <v-col cols="2" class="d-flex align-center">
                  <v-btn @click="addCryptoPosition">Add</v-btn>
                </v-col>
              </v-row>
              <v-chip
                v-for="(item, idx) in form.crypto_positions"
                :key="`crypto-${idx}`"
                class="ma-1"
                closable
                @click:close="removeCryptoPosition(idx)"
              >
                {{ item.ticker }}: {{ item.quantity }}
              </v-chip>
            </v-card>

            <v-card variant="tonal" class="pa-3 my-4" v-if="form.type === 'stocks_account'">
              <div class="text-subtitle-1 mb-2">Stock Positions</div>
              <v-row>
                <v-col cols="5">
                  <v-select
                    v-model="stockDraft.stock_id"
                    :items="stocks"
                    item-title="ticker"
                    item-value="id"
                    label="Stock"
                  />
                </v-col>
                <v-col cols="5">
                  <v-text-field v-model="stockDraft.quantity" label="Quantity" type="number" />
                </v-col>
                <v-col cols="2" class="d-flex align-center">
                  <v-btn @click="addStockPosition">Add</v-btn>
                </v-col>
              </v-row>
              <v-chip
                v-for="(item, idx) in form.stock_positions"
                :key="`stock-${idx}`"
                class="ma-1"
                closable
                @click:close="removeStockPosition(idx)"
              >
                {{ stockTicker(item.stock_id) }}: {{ item.quantity }}
              </v-chip>
            </v-card>

            <v-btn type="submit" color="primary" class="mr-2">
              {{ form.id ? 'Update' : 'Create' }}
            </v-btn>
            <v-btn v-if="form.id" @click="resetForm">Cancel</v-btn>
          </v-form>
        </v-card>
      </v-col>

      <v-col cols="12" md="5">
        <v-card class="pa-4 mb-4">
          <v-card-title class="px-0">Quick Add Stock</v-card-title>
          <v-form @submit.prevent="createStock">
            <v-text-field v-model="stockForm.name" label="Name" required />
            <v-text-field v-model="stockForm.ticker" label="Ticker" required />
            <v-text-field v-model="stockForm.exchange" label="Exchange" />
            <v-btn type="submit" color="secondary">Add Stock</v-btn>
          </v-form>
        </v-card>

        <v-card class="pa-4">
          <v-card-title class="px-0">Accounts</v-card-title>
          <v-table density="comfortable">
            <thead>
              <tr>
                <th>Name</th>
                <th>Type</th>
                <th>Org</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="account in accounts" :key="account.id">
                <td>{{ account.name }}</td>
                <td>{{ account.type }}</td>
                <td>{{ account.organization || '-' }}</td>
                <td>
                  <v-btn size="small" variant="text" @click="editAccount(account)">Edit</v-btn>
                  <v-btn size="small" variant="text" color="error" @click="deleteAccount(account.id)">
                    Delete
                  </v-btn>
                </td>
              </tr>
            </tbody>
          </v-table>
        </v-card>
      </v-col>
    </v-row>
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

interface Stock {
  id: string
  name: string
  ticker: string
  exchange?: string | null
}

interface StockPosition {
  stock_id: string
  quantity: string
}

interface CryptoPosition {
  ticker: string
  quantity: string
}

interface CashBill {
  denomination_cents: number
  quantity: number
}

interface AccountPayload {
  id?: string
  account_number: string
  name: string
  type: AccountType
  organization?: string
  url?: string
  notes?: string
  balance_cents?: number
  fee_amount_cents?: number
  fee_period?: string
  routing_number?: string
  apy_bps?: number
  compound_period?: string
  apr_bps?: number
  billing_day?: number
  payment_day?: number
  expiration_date?: string
  cvc?: string
  usd_balance_cents?: number
  retirement_account_type?: string
  payment_amount_cents?: number
  stock_positions: StockPosition[]
  crypto_positions: CryptoPosition[]
  cash_bills: CashBill[]
}

const accountTypes = [
  { label: 'Checking', value: 'checking' },
  { label: 'Savings', value: 'savings' },
  { label: 'Cash', value: 'cash' },
  { label: 'Line of Credit', value: 'line_of_credit' },
  { label: 'Credit Card', value: 'credit_card' },
  { label: 'Stocks Account', value: 'stocks_account' },
  { label: 'Crypto Exchange', value: 'crypto_exchange' },
  { label: 'Crypto Wallet', value: 'crypto_wallet' },
  { label: 'Retirement', value: 'retirement' },
  { label: 'Loan', value: 'loan' },
  { label: 'Rewards Card', value: 'rewards_card' },
]

const compoundPeriods = ['daily', 'monthly']
const retirementTypes = ['roth', 'simple', '401k']

const makeEmptyForm = (): AccountPayload => ({
  account_number: '',
  name: '',
  type: 'checking',
  organization: '',
  url: '',
  notes: '',
  stock_positions: [],
  crypto_positions: [],
  cash_bills: [],
})

const accounts = ref<AccountPayload[]>([])
const stocks = ref<Stock[]>([])
const form = ref<AccountPayload>(makeEmptyForm())

const stockForm = ref({ name: '', ticker: '', exchange: '' })
const stockDraft = ref<{ stock_id: string; quantity: string }>({ stock_id: '', quantity: '' })
const cryptoDraft = ref<CryptoPosition>({ ticker: '', quantity: '' })
const cashDraft = ref<CashBill>({ denomination_cents: 100, quantity: 1 })

const needsBalance = computed(() =>
  [
    'checking',
    'savings',
    'line_of_credit',
    'credit_card',
    'retirement',
    'loan',
    'rewards_card',
  ].includes(form.value.type),
)
const needsFee = computed(() =>
  ['checking', 'savings', 'line_of_credit', 'credit_card'].includes(form.value.type),
)
const needsRouting = computed(() => ['checking', 'savings'].includes(form.value.type))
const needsApy = computed(() => form.value.type === 'savings')
const needsApr = computed(() =>
  ['line_of_credit', 'credit_card', 'loan'].includes(form.value.type),
)
const needsCompoundPeriod = computed(() =>
  ['line_of_credit', 'credit_card', 'loan'].includes(form.value.type),
)
const needsBillingDay = computed(() =>
  ['line_of_credit', 'credit_card'].includes(form.value.type),
)
const needsPaymentDay = computed(() =>
  ['line_of_credit', 'credit_card', 'loan'].includes(form.value.type),
)
const needsExpiration = computed(() =>
  ['credit_card', 'rewards_card'].includes(form.value.type),
)
const needsCvc = computed(() => form.value.type === 'credit_card')
const needsCryptoPositions = computed(() =>
  ['crypto_exchange', 'crypto_wallet'].includes(form.value.type),
)

const loadAccounts = async () => {
  accounts.value = await request.get<AccountPayload[]>('/accounts')
}

const loadStocks = async () => {
  stocks.value = await request.get<Stock[]>('/stocks')
}

const normalizePayload = (input: AccountPayload): Omit<AccountPayload, 'id'> => ({
  account_number: input.account_number,
  name: input.name,
  type: input.type,
  organization: input.organization || undefined,
  url: input.url || undefined,
  notes: input.notes || undefined,
  balance_cents: input.balance_cents,
  fee_amount_cents: input.fee_amount_cents,
  fee_period: input.fee_period || undefined,
  routing_number: input.routing_number || undefined,
  apy_bps: input.apy_bps,
  compound_period: input.compound_period || undefined,
  apr_bps: input.apr_bps,
  billing_day: input.billing_day,
  payment_day: input.payment_day,
  expiration_date: input.expiration_date || undefined,
  cvc: input.cvc || undefined,
  usd_balance_cents: input.usd_balance_cents,
  retirement_account_type: input.retirement_account_type || undefined,
  payment_amount_cents: input.payment_amount_cents,
  stock_positions: input.stock_positions,
  crypto_positions: input.crypto_positions.map((item) => ({
    ticker: item.ticker.toUpperCase(),
    quantity: item.quantity,
  })),
  cash_bills: input.cash_bills,
})

const saveAccount = async () => {
  const payload = normalizePayload(form.value)
  if (form.value.id) {
    await request.put(`/accounts/${form.value.id}`, payload)
  } else {
    await request.post('/accounts', payload)
  }
  await loadAccounts()
  resetForm()
}

const editAccount = (account: AccountPayload) => {
  form.value = {
    ...account,
    stock_positions: account.stock_positions || [],
    crypto_positions: account.crypto_positions || [],
    cash_bills: account.cash_bills || [],
  }
}

const deleteAccount = async (id: string) => {
  await request.delete(`/accounts/${id}`)
  await loadAccounts()
  if (form.value.id === id) {
    resetForm()
  }
}

const resetForm = () => {
  form.value = makeEmptyForm()
}

const stockTicker = (stockId: string) => {
  const found = stocks.value.find((item) => item.id === stockId)
  return found ? found.ticker : stockId
}

const addStockPosition = () => {
  if (!stockDraft.value.stock_id || !stockDraft.value.quantity) {
    return
  }
  form.value.stock_positions.push({ ...stockDraft.value })
  stockDraft.value = { stock_id: '', quantity: '' }
}

const removeStockPosition = (index: number) => {
  form.value.stock_positions.splice(index, 1)
}

const addCryptoPosition = () => {
  if (!cryptoDraft.value.ticker || !cryptoDraft.value.quantity) {
    return
  }
  form.value.crypto_positions.push({
    ticker: cryptoDraft.value.ticker.toUpperCase(),
    quantity: cryptoDraft.value.quantity,
  })
  cryptoDraft.value = { ticker: '', quantity: '' }
}

const removeCryptoPosition = (index: number) => {
  form.value.crypto_positions.splice(index, 1)
}

const addCashBill = () => {
  if (!cashDraft.value.denomination_cents || !cashDraft.value.quantity) {
    return
  }
  form.value.cash_bills.push({
    denomination_cents: cashDraft.value.denomination_cents,
    quantity: cashDraft.value.quantity,
  })
}

const removeCashBill = (index: number) => {
  form.value.cash_bills.splice(index, 1)
}

const createStock = async () => {
  await request.post('/stocks', {
    name: stockForm.value.name,
    ticker: stockForm.value.ticker,
    exchange: stockForm.value.exchange || undefined,
  })
  stockForm.value = { name: '', ticker: '', exchange: '' }
  await loadStocks()
}

onMounted(async () => {
  await Promise.all([loadAccounts(), loadStocks()])
})
</script>
