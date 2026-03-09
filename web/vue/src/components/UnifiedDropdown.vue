<template>
  <div ref="root" class="dropdown" :class="{ 'dropdown--open': isOpen }">
    <label v-if="label" class="dropdown-label">{{ label }}</label>

    <button
      v-if="!menuOnly && !searchable"
      type="button"
      class="dropdown-trigger"
      :class="{ 'dropdown-trigger--placeholder': !selectedLabel }"
      @click="toggleOpen"
    >
      <span class="dropdown-text">{{ selectedLabel || placeholder }}</span>
      <span class="dropdown-caret" aria-hidden="true">▾</span>
    </button>

    <input
      v-else-if="!menuOnly"
      v-model="searchText"
      class="cds--text-input dropdown-input"
      :placeholder="placeholder"
      :required="required"
      @focus="isOpen = true"
      @input="isOpen = true"
      @keydown.enter.prevent="commitSearch"
      @keydown.esc="isOpen = false"
    />

    <div v-if="menuOnly || isOpen" class="dropdown-menu" :class="{ 'dropdown-menu--scrollable': scrollable }">
      <button
        v-for="option in filteredOptions"
        :key="option.value"
        type="button"
        class="dropdown-option"
        @mousedown.prevent="selectOption(option)"
      >
        {{ option.label }}
      </button>
      <button
        v-if="searchable && allowCustom && customCandidate"
        type="button"
        class="dropdown-option"
        @mousedown.prevent="selectCustom(customCandidate)"
      >
        Use "{{ customCandidate }}"
      </button>
      <div v-if="!filteredOptions.length && !(searchable && allowCustom && customCandidate)" class="dropdown-empty">
        No matches
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

interface Option {
  label: string
  value: string
}

const props = withDefaults(
  defineProps<{
    modelValue?: string
    options: Option[]
    label?: string
    placeholder?: string
    searchable?: boolean
    allowCustom?: boolean
    required?: boolean
    autoOpen?: boolean
    scrollable?: boolean
    menuOnly?: boolean
  }>(),
  {
    label: '',
    placeholder: 'Select an option',
    searchable: false,
    allowCustom: false,
    required: false,
    autoOpen: false,
    scrollable: true,
    menuOnly: false,
  },
)

const emit = defineEmits<{
  (event: 'update:modelValue', value: string | undefined): void
}>()

const root = ref<HTMLElement | null>(null)
const isOpen = ref(false)
const searchText = ref('')

const selectedOption = computed(() => props.options.find((option) => option.value === props.modelValue))
const selectedLabel = computed(() => selectedOption.value?.label || '')

watch(
  () => props.modelValue,
  (next) => {
    if (props.searchable) {
      if (!next) {
        searchText.value = ''
        return
      }
      const byValue = props.options.find((option) => option.value === next)
      searchText.value = byValue?.label || next
    }
  },
  { immediate: true },
)

const filteredOptions = computed(() => {
  if (!props.searchable) {
    return props.options
  }
  const query = searchText.value.trim().toLowerCase()
  if (!query) {
    return props.options
  }
  if (selectedLabel.value && query === selectedLabel.value.trim().toLowerCase()) {
    return props.options
  }
  return props.options.filter((option) => option.label.toLowerCase().includes(query))
})

const customCandidate = computed(() => {
  const query = searchText.value.trim()
  if (!query) {
    return ''
  }
  const duplicate = props.options.some((option) => option.label.toLowerCase() === query.toLowerCase())
  return duplicate ? '' : query
})

const selectOption = (option: Option) => {
  emit('update:modelValue', option.value)
  if (props.searchable) {
    searchText.value = option.label
  }
  isOpen.value = false
}

const selectCustom = (value: string) => {
  emit('update:modelValue', value)
  searchText.value = value
  isOpen.value = false
}

const commitSearch = () => {
  const first = filteredOptions.value[0]
  if (first) {
    selectOption(first)
    return
  }
  if (props.allowCustom && customCandidate.value) {
    selectCustom(customCandidate.value)
  }
}

const toggleOpen = () => {
  isOpen.value = !isOpen.value
}

const onWindowMouseDown = (event: MouseEvent) => {
  const target = event.target as Node
  if (root.value && !root.value.contains(target)) {
    isOpen.value = false
  }
}

onMounted(() => {
  if (props.autoOpen) {
    isOpen.value = true
  }
  window.addEventListener('mousedown', onWindowMouseDown)
})

onUnmounted(() => {
  window.removeEventListener('mousedown', onWindowMouseDown)
})
</script>

<style scoped>
.dropdown {
  position: relative;
  width: 100%;
}

.dropdown-label {
  display: block;
  margin-bottom: 6px;
  font-size: 0.75rem;
  color: var(--cds-text-secondary);
  font-weight: 600;
}

.dropdown-trigger {
  width: 100%;
  min-height: 2.5rem;
  border: 1px solid var(--cds-border-strong-01);
  background: var(--cds-field);
  padding: 0 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  text-align: left;
  color: var(--cds-text-primary);
  cursor: pointer;
}

.dropdown-trigger--placeholder {
  color: var(--cds-text-placeholder);
}

.dropdown-trigger:focus-visible,
.dropdown-input:focus-visible {
  outline: 2px solid #0f62fe;
  outline-offset: 0;
}

.dropdown-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dropdown-caret {
  flex: 0 0 auto;
}

.dropdown-input {
  min-height: 2.5rem;
}

.dropdown-menu {
  position: absolute;
  top: calc(100% + 2px);
  left: 0;
  right: 0;
  z-index: 50;
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.16);
  overflow: hidden;
  overflow-x: hidden;
}

.dropdown-menu--scrollable {
  max-height: 220px;
  overflow-y: auto;
}

.dropdown-option {
  display: block;
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--cds-text-primary);
  text-align: left;
  padding: 0.65rem 0.8rem;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-option:hover,
.dropdown-option:focus-visible {
  background: #e0f2fe;
  color: var(--cds-text-primary);
  outline: none;
}

.dropdown-empty {
  padding: 0.65rem 0.8rem;
  color: var(--cds-text-secondary);
  font-size: 0.86rem;
}
</style>
