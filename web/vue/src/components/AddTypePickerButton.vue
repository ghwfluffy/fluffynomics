<template>
  <div class="action-row" :data-inline="props.inline ? 'true' : 'false'">
    <button ref="trigger" class="cds--btn cds--btn--primary mp-add-btn" type="button" @click="open = !open">
      {{ props.buttonLabel }}
    </button>
    <div v-if="open" ref="picker" class="type-picker" :style="{ width: `${pickerWidth}px` }">
      <UnifiedDropdown
        auto-open
        :scrollable="false"
        menu-only
        :placeholder="props.placeholder"
        :options="props.options"
        @update:modelValue="onPick"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import UnifiedDropdown from '@/components/UnifiedDropdown.vue'

interface Option {
  label: string
  value: string
}

const props = withDefaults(
  defineProps<{
    buttonLabel: string
    placeholder?: string
    options: Option[]
    inline?: boolean
  }>(),
  {
    inline: false,
    placeholder: 'Select type',
  },
)

const emit = defineEmits<{
  (event: 'select', value: string): void
}>()

const trigger = ref<HTMLElement | null>(null)
const picker = ref<HTMLElement | null>(null)
const open = ref(false)
const pickerWidth = ref(220)

const syncWidth = () => {
  pickerWidth.value = trigger.value?.offsetWidth || 220
}

const onPick = (value: string | undefined) => {
  if (!value) {
    return
  }
  emit('select', value)
  open.value = false
}

const onWindowClick = (event: MouseEvent) => {
  if (!open.value) {
    return
  }
  const target = event.target as Node
  if (trigger.value?.contains(target) || picker.value?.contains(target)) {
    return
  }
  open.value = false
}

onMounted(async () => {
  await nextTick()
  syncWidth()
  window.addEventListener('resize', syncWidth)
  window.addEventListener('click', onWindowClick)
})

onUnmounted(() => {
  window.removeEventListener('resize', syncWidth)
  window.removeEventListener('click', onWindowClick)
})
</script>

<style scoped>
.action-row {
  position: relative;
  margin-bottom: 1.25rem;
  display: flex;
  justify-content: flex-end;
}

.action-row[data-inline='true'] {
  margin-bottom: 0;
}

.type-picker {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  z-index: 20;
}

</style>
