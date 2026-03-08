<template>
  <div class="dollar-field">
    <label class="dollar-label">{{ label }}</label>
    <div class="dollar-input-wrap">
      <span class="currency">$</span>
      <input
        ref="inputRef"
        class="cds--text-input dollar-input"
        type="text"
        inputmode="numeric"
        :value="displayValue"
        @keydown="onKeyDown"
        @input="onInput"
        @paste.prevent="onPaste"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'

const props = defineProps<{
  modelValue?: number
  label: string
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: number): void
}>()

const formatCents = (cents: number) => (cents / 100).toFixed(2)

const toCentsFromDigits = (raw: string): number => {
  const cleaned = raw.replace(/\D/g, '')
  if (!cleaned) {
    return 0
  }
  return Number.parseInt(cleaned, 10)
}

const toCentsFromDisplay = (raw: string): number => {
  const cleaned = raw.replace(/[^0-9.]/g, '')
  const parsed = Number.parseFloat(cleaned)
  if (Number.isNaN(parsed) || !Number.isFinite(parsed)) {
    return 0
  }
  return Math.round(parsed * 100)
}

const replaceRange = (value: string, start: number, end: number, replacement: string) =>
  `${value.slice(0, start)}${replacement}${value.slice(end)}`

const centsValue = computed(() => props.modelValue ?? 0)
const cents = ref(centsValue.value)
const displayValue = computed(() => formatCents(cents.value))
const inputRef = ref<HTMLInputElement | null>(null)
const selectionEditMode = ref(false)

watch(
  centsValue,
  (next) => {
    cents.value = next
  },
  { immediate: true },
)

const emitCents = (value: number) => {
  cents.value = Math.max(0, value)
  emit('update:modelValue', cents.value)
}

const applyDisplayEdit = (nextDisplay: string, caretIndex: number) => {
  emitCents(toCentsFromDisplay(nextDisplay))
  nextTick(() => {
    inputRef.value?.setSelectionRange(caretIndex, caretIndex)
  })
}

const onKeyDown = (event: KeyboardEvent) => {
  const input = event.target as HTMLInputElement
  const start = input.selectionStart
  const end = input.selectionEnd
  const caretStart = start ?? displayValue.value.length
  const caretEnd = end ?? displayValue.value.length
  const hasSelection = start !== null && end !== null && start !== end

  if (/^[0-9]$/.test(event.key)) {
    if (hasSelection) {
      event.preventDefault()
      selectionEditMode.value = true
      const nextDisplay = replaceRange(displayValue.value, caretStart, caretEnd, event.key)
      applyDisplayEdit(nextDisplay, caretStart + 1)
      return
    }
    if (selectionEditMode.value) {
      event.preventDefault()
      const nextDisplay = replaceRange(displayValue.value, caretStart, caretEnd, event.key)
      applyDisplayEdit(nextDisplay, caretStart + 1)
      return
    }
    selectionEditMode.value = false
    event.preventDefault()
    emitCents(cents.value * 10 + Number.parseInt(event.key, 10))
    return
  }
  if (event.key === 'Backspace' || event.key === 'Delete') {
    if (hasSelection || selectionEditMode.value) {
      event.preventDefault()
      if (hasSelection) {
        const nextDisplay = replaceRange(displayValue.value, caretStart, caretEnd, '')
        applyDisplayEdit(nextDisplay, caretStart)
      } else if (event.key === 'Backspace' && caretStart > 0) {
        const nextDisplay = replaceRange(displayValue.value, caretStart - 1, caretStart, '')
        applyDisplayEdit(nextDisplay, caretStart - 1)
      } else if (event.key === 'Delete') {
        const nextDisplay = replaceRange(displayValue.value, caretStart, caretStart + 1, '')
        applyDisplayEdit(nextDisplay, caretStart)
      }
      return
    }
    selectionEditMode.value = false
    event.preventDefault()
    emitCents(Math.floor(cents.value / 10))
    return
  }
  if (['Tab', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) {
    return
  }
  if (event.ctrlKey || event.metaKey) {
    return
  }
  selectionEditMode.value = false
  event.preventDefault()
}

const onInput = (event: Event) => {
  // Keep terminal-style behavior even if browser dispatches plain input events.
  const raw = (event.target as HTMLInputElement).value
  emitCents(toCentsFromDigits(raw))
}

const onPaste = (event: ClipboardEvent) => {
  selectionEditMode.value = false
  const pasted = event.clipboardData?.getData('text') || ''
  emitCents(toCentsFromDigits(pasted))
}
</script>

<style scoped>
.dollar-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.dollar-label {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #475569;
  font-weight: 700;
}

.dollar-input-wrap {
  display: flex;
  align-items: center;
  border: 1px solid var(--cds-border-strong-01);
  background: var(--cds-field);
  padding: 0 10px;
  min-height: 2.5rem;
}

.currency {
  color: #64748b;
  font-weight: 700;
  margin-right: 6px;
}

.dollar-input {
  border: 0 !important;
  outline: none;
  width: 100%;
  min-height: 2.5rem;
  font-size: 0.94rem;
  color: #0f172a;
  background: transparent;
  text-align: left;
  font-variant-numeric: tabular-nums;
}

.dollar-input:focus {
  outline: none !important;
  box-shadow: none !important;
}

.dollar-input-wrap:focus-within {
  outline: 2px solid #0f62fe;
  outline-offset: 0;
}
</style>
