<template>
  <div ref="root" class="cds--table-toolbar toolbar-shell">
    <div class="cds--table-toolbar-content toolbar-content">
      <div class="cds--search cds--search--sm toolbar-search">
        <label class="cds--label">Filter table</label>
        <input class="cds--search-input" type="text" :placeholder="placeholder" :value="modelValue" @input="onInput" />
      </div>
      <div class="toolbar-filter-wrap">
        <button type="button" class="toolbar-filter-trigger" title="Filter options" @click="open = !open">
          <span>Filter options</span>
          <span class="toolbar-filter-caret">▾</span>
        </button>
        <div v-if="open" class="toolbar-filter-menu">
          <section v-for="filter in filters" :key="filter.key" class="toolbar-filter-section">
            <div class="toolbar-filter-label">{{ filter.label }}</div>
            <div class="toolbar-filter-actions">
              <button type="button" class="toolbar-link" @click="setAll(filter.key, filter.options)">All</button>
              <button type="button" class="toolbar-link" @click="setAll(filter.key, [])">None</button>
            </div>
            <label v-for="option in filter.options" :key="option" class="toolbar-filter-item">
              <input
                type="checkbox"
                :checked="(filter.selected || []).includes(option)"
                @change="toggle(filter.key, filter.selected || [], option)"
              />
              <span>{{ option }}</span>
            </label>
          </section>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'

interface FilterSpec {
  key: string
  label: string
  options: string[]
  selected: string[]
}

withDefaults(
  defineProps<{
    modelValue: string
    placeholder?: string
    filters?: FilterSpec[]
  }>(),
  {
    placeholder: 'Filter table',
    filters: () => [],
  },
)

const emit = defineEmits<{
  (event: 'update:modelValue', value: string): void
  (event: 'update:filter', payload: { key: string; selected: string[] }): void
}>()

const root = ref<HTMLElement | null>(null)
const open = ref(false)

const onInput = (event: Event) => {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}

const toggle = (key: string, current: string[], option: string) => {
  const set = new Set(current)
  if (set.has(option)) {
    set.delete(option)
  } else {
    set.add(option)
  }
  emit('update:filter', { key, selected: [...set] })
}

const setAll = (key: string, selected: string[]) => {
  emit('update:filter', { key, selected })
}

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
.toolbar-shell {
  position: relative;
  min-width: 0;
}

.toolbar-content {
  display: flex;
  align-items: stretch;
  gap: 0;
  flex-wrap: nowrap;
}

.toolbar-search {
  flex: 1;
  min-width: 220px;
}

.toolbar-filter-wrap {
  position: relative;
  display: flex;
}

.toolbar-filter-trigger {
  border: 0;
  border-left: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  color: var(--cds-text-primary);
  min-height: 2.5rem;
  padding: 0 0.9rem;
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  cursor: pointer;
  white-space: nowrap;
}

.toolbar-filter-menu {
  position: absolute;
  top: calc(100% - 1px);
  right: 0;
  z-index: 25;
  width: min(360px, 92vw);
  max-height: 60vh;
  overflow: auto;
  border: 1px solid var(--cds-border-subtle-01);
  background: var(--cds-layer);
  box-shadow: 0 8px 20px rgba(15, 23, 42, 0.16);
  padding: 0.65rem;
}

.toolbar-filter-section + .toolbar-filter-section {
  margin-top: 0.65rem;
  padding-top: 0.65rem;
  border-top: 1px solid var(--cds-border-subtle-01);
}

.toolbar-filter-label {
  font-size: 0.78rem;
  font-weight: 600;
  margin-bottom: 0.3rem;
}

.toolbar-filter-actions {
  display: flex;
  gap: 8px;
  margin-bottom: 0.25rem;
}

.toolbar-link {
  border: 0;
  background: transparent;
  color: #0f62fe;
  font-size: 0.75rem;
  cursor: pointer;
  padding: 0;
}

.toolbar-filter-item {
  display: flex;
  gap: 6px;
  align-items: center;
  font-size: 0.82rem;
  padding: 2px 0;
}

@media (max-width: 720px) {
  .toolbar-content {
    flex-wrap: wrap;
  }

  .toolbar-search {
    min-width: 100%;
  }

  .toolbar-filter-trigger {
    border-left: 0;
    border-top: 1px solid var(--cds-border-subtle-01);
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
