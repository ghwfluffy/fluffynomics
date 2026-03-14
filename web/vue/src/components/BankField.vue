<template>
  <div class="bank-field">
    <label v-if="!hideLabel" class="bank-label">{{ label }}</label>

    <textarea
      v-if="multiline"
      class="cds--text-area bank-input bank-textarea"
      :value="displayValue"
      :required="required"
      :placeholder="placeholder"
      :aria-label="hideLabel ? label : undefined"
      @input="onInput"
    />

    <select
      v-else-if="options.length"
      class="cds--select-input bank-input"
      :value="displayValue"
      :required="required"
      :aria-label="hideLabel ? label : undefined"
      @change="onInput"
    >
      <option value="" disabled>Select</option>
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>

    <input
      v-else
      class="cds--text-input bank-input"
      :type="type"
      :value="displayValue"
      :required="required"
      :placeholder="placeholder"
      :aria-label="hideLabel ? label : undefined"
      @input="onInput"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Option {
  label: string
  value: string
}

const props = withDefaults(
  defineProps<{
    modelValue?: string | number
    label: string
    type?: string
    required?: boolean
    multiline?: boolean
    hideLabel?: boolean
    placeholder?: string
    options?: Option[]
  }>(),
  {
    type: 'text',
    required: false,
    multiline: false,
    hideLabel: false,
    placeholder: '',
    options: () => [],
  },
)

const emit = defineEmits<{
  (event: 'update:modelValue', value: string | number | undefined): void
}>()

const displayValue = computed(() => (props.modelValue ?? '').toString())

const onInput = (event: Event) => {
  const rawValue = (event.target as HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement).value
  if (props.type === 'number') {
    emit('update:modelValue', rawValue === '' ? undefined : Number(rawValue))
    return
  }
  emit('update:modelValue', rawValue === '' ? undefined : rawValue)
}
</script>

<style scoped>
.bank-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.bank-label {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #475569;
  font-weight: 700;
}

.bank-input {
  width: 100%;
  min-height: 2.5rem;
  border-radius: 0;
  font-size: 0.94rem;
}

.bank-input:focus {
  outline: 2px solid #0f62fe;
  outline-offset: 0;
}

.bank-textarea {
  min-height: 82px;
  resize: vertical;
}
</style>
