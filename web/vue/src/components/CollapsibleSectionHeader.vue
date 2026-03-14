<template>
  <h2 class="section-title">
    <button
      v-if="collapsible"
      type="button"
      class="section-toggle"
      :aria-expanded="collapsed ? 'false' : 'true'"
      @click="emit('toggle')"
    >
      <span v-if="!collapsed" class="section-toggle-glyph section-toggle-glyph--text" aria-hidden="true">⌄</span>
      <svg v-else class="section-toggle-glyph" viewBox="0 0 12 12" aria-hidden="true">
        <path
          d="M4 2.5 8 6 4 9.5"
          fill="none"
          stroke="currentColor"
          stroke-linecap="round"
          stroke-linejoin="round"
          stroke-width="1.5"
        />
      </svg>
      <span>{{ title }}</span>
    </button>
    <span v-else>{{ title }}</span>
  </h2>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string
    collapsed?: boolean
    collapsible?: boolean
  }>(),
  {
    collapsed: false,
    collapsible: false,
  },
)

const emit = defineEmits<{
  (event: 'toggle'): void
}>()
</script>

<style scoped>
.section-toggle {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  font-weight: inherit;
  padding: 0;
  cursor: pointer;
}

.section-toggle-glyph {
  width: 0.8rem;
  height: 0.8rem;
  flex: 0 0 auto;
}

.section-toggle-glyph--text {
  width: auto;
  height: auto;
  font-size: 0.95rem;
  line-height: 1;
}
</style>
