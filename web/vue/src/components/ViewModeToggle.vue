<template>
  <div class="view-toggle" role="group" aria-label="View mode">
    <button
      type="button"
      class="view-toggle-btn"
      :class="{ 'view-toggle-btn--active': modelValue === 'tiles' }"
      @click="emit('update:modelValue', 'tiles')"
    >
      Tiles
    </button>
    <button
      type="button"
      class="view-toggle-btn"
      :class="{ 'view-toggle-btn--active': modelValue === 'table' }"
      @click="emit('update:modelValue', 'table')"
    >
      Table
    </button>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  modelValue: 'tiles' | 'table'
}>()

const emit = defineEmits<{
  (event: 'update:modelValue', value: 'tiles' | 'table'): void
}>()
</script>

<style scoped>
.view-toggle {
  display: inline-flex;
  border: 1px solid var(--cds-border-subtle-01);
}

.view-toggle-btn {
  border: 0;
  background: var(--cds-layer);
  color: var(--cds-text-primary);
  padding: 0.45rem 0.75rem;
  cursor: pointer;
}

.view-toggle-btn + .view-toggle-btn {
  border-left: 1px solid var(--cds-border-subtle-01);
}

.view-toggle-btn--active {
  background: #0f62fe;
  color: #fff;
}
</style>
