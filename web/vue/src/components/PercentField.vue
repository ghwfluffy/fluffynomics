<template>
  <div class="percent-field">
    <label class="percent-label">{{ label }}</label>
    <div class="percent-input-wrap">
      <input
        ref="inputRef"
        class="cds--text-input percent-input"
        type="text"
        inputmode="numeric"
        :value="displayValue"
        @keydown="onKeyDown"
        @input="onInput"
        @paste.prevent="onPaste"
      />
      <span class="suffix">%</span>
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

const formatBps = (bps: number) => (bps / 100).toFixed(2)

const toBpsFromDigits = (raw: string): number => {
  const cleaned = raw.replace(/\D/g, '')
  if (!cleaned) {
    return 0
  }
  return Number.parseInt(cleaned, 10)
}

const toBpsFromDisplay = (raw: string): number => {
  const cleaned = raw.replace(/[^0-9.]/g, '')
  const parsed = Number.parseFloat(cleaned)
  if (Number.isNaN(parsed) || !Number.isFinite(parsed)) {
    return 0
  }
  return Math.round(parsed * 100)
}

const replaceRange = (value: string, start: number, end: number, replacement: string) =>
  `${value.slice(0, start)}${replacement}${value.slice(end)}`

const bpsValue = computed(() => props.modelValue ?? 0)
const bps = ref(bpsValue.value)
const displayValue = computed(() => formatBps(bps.value))
const inputRef = ref<HTMLInputElement | null>(null)
const selectionEditMode = ref(false)

watch(
  bpsValue,
  (next) => {
    bps.value = next
  },
  { immediate: true },
)

const emitBps = (value: number) => {
  bps.value = Math.max(0, value)
  emit('update:modelValue', bps.value)
}

const applyDisplayEdit = (nextDisplay: string, caretIndex: number) => {
  emitBps(toBpsFromDisplay(nextDisplay))
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
    emitBps(bps.value * 10 + Number.parseInt(event.key, 10))
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
    emitBps(Math.floor(bps.value / 10))
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
  const raw = (event.target as HTMLInputElement).value
  emitBps(toBpsFromDigits(raw))
}

const onPaste = (event: ClipboardEvent) => {
  selectionEditMode.value = false
  const pasted = event.clipboardData?.getData('text') || ''
  emitBps(toBpsFromDigits(pasted))
}
</script>

<style scoped>
.percent-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.percent-label {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #475569;
  font-weight: 700;
}

.percent-input-wrap {
  display: flex;
  align-items: center;
  border: 1px solid var(--cds-border-strong-01);
  background: var(--cds-field);
  padding: 0 10px;
  min-height: 2.5rem;
}

.suffix {
  color: #64748b;
  font-weight: 700;
  margin-left: 6px;
}

.percent-input {
  border: 0 !important;
  outline: none;
  width: 100%;
  min-height: 2.5rem;
  font-size: 0.94rem;
  color: #0f172a;
  background: transparent;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.percent-input-wrap:focus-within {
  outline: 2px solid #0f62fe;
  outline-offset: 0;
}
</style>
