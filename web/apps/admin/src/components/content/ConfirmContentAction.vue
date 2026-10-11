<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue"
withDefaults(defineProps<{ title: string; description: string; pending?: boolean; danger?: boolean }>(), { pending: false, danger: false })
defineEmits<{ confirm: []; cancel: [] }>()
const root = ref<HTMLElement | null>(null)
onMounted(async () => { await nextTick(); root.value?.focus() })
function key(event: KeyboardEvent): void {
  if (event.key !== "Tab" || !root.value) return
  const nodes = [...root.value.querySelectorAll<HTMLButtonElement>("button:not(:disabled)")]
  if (!nodes.length) { event.preventDefault(); return }
  const first = nodes[0]
  const last = nodes[nodes.length - 1]
  if (event.shiftKey && (document.activeElement === first || document.activeElement === root.value)) {
    event.preventDefault(); last?.focus()
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault(); first?.focus()
  }
}
</script>
<template>
  <section ref="root" class="c-notice c-notice--warn" role="alertdialog" aria-modal="false" aria-labelledby="content-confirm-title" aria-describedby="content-confirm-description" tabindex="-1" @keydown="key">
    <div class="c-notice__body">
      <h2 id="content-confirm-title" class="b-section__title">{{ title }}</h2>
      <p id="content-confirm-description">{{ description }}</p>
      <div class="b-actions">
        <button type="button" class="c-btn" :class="danger ? 'c-btn--danger' : 'c-btn--primary'" :disabled="pending" @click="$emit('confirm')">{{ pending ? '正在提交…' : '确认' }}</button>
        <button type="button" class="c-btn c-btn--secondary" :disabled="pending" @click="$emit('cancel')">取消</button>
      </div>
    </div>
  </section>
</template>
