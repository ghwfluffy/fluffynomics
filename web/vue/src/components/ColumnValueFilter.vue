<template>
  <div ref="root" class="col-filter">
    <button type="button" class="col-filter-btn" @click="open = !open" :title="label">
      ▾
    </button>
    <div v-if="open" class="col-filter-menu">
      <div class="col-filter-actions">
        <button type="button" class="col-filter-link" @click="selectAll">All</button>
        <button type="button" class="col-filter-link" @click="clearAll">None</button>
      </div>
      <label v-for="option in options" :key="option" class="col-filter-item">
        <input type="checkbox" :checked="selected.has(option)" @change="toggle(option)" />
        <span>{{ option }}</span>
      </label>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    label?: string
    options: string[]
    modelValue: string[]
  }>(),
  {
    label: 'Filter',
  },
)

const emit = defineEmits<{
  (event: 'update:modelValue', value: string[]): void
}>()

const root = ref<HTMLElement | null>(null)
const open = ref(false)
const selected = computed(() => new Set(props.modelValue))

const toggle = (value: string) => {
  const next = new Set(props.modelValue)
  if (next.has(value)) {
    next.delete(value)
  } else {
    next.add(value)
  }
  emit('update:modelValue', [...next])
}

const selectAll = () => emit('update:modelValue', [...props.options])
const clearAll = () => emit('update:modelValue', [])

const onWindowClick = (event: MouseEvent) => {
  if (!open.value) {
    return
  }
  const target = event.target as Node
  if (root.value?.contains(target)) {
    return
  }
  open.value = false
}

onMounted(() => window.addEventListener('click', onWindowClick))
onUnmounted(() => window.removeEventListener('click', onWindowClick))
</script>

<style scoped>
.col-filter {
  position: relative;
  display: inline-flex;
  margin-left: 6px;
}

.col-filter-btn {
  border: 0;
  background: transparent;
  color: #6b7280;
  cursor: pointer;
  padding: 0 2px;
  line-height: 1;
}

.col-filter-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 30;
  min-width: 180px;
  max-height: 260px;
  overflow: auto;
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  box-shadow: 0 8px 16px rgba(15, 23, 42, 0.16);
  padding: 8px;
}

.col-filter-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}

.col-filter-link {
  border: 0;
  background: transparent;
  color: #0f62fe;
  cursor: pointer;
  padding: 0;
  font-size: 0.78rem;
}

.col-filter-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  padding: 2px 0;
}
</style>
