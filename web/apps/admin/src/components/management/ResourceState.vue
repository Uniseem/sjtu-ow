<script setup lang="ts">
import AdminNotice from "../AdminNotice.vue"
defineProps<{ pending: boolean; message: string; status?: number; empty?: boolean; emptyText?: string }>()
defineEmits<{ retry: [] }>()
</script>
<template>
  <p v-if="pending" class="b-section__text" role="status" aria-live="polite" aria-busy="true">正在加载…</p>
  <template v-if="message">
    <AdminNotice :message="message" kind="error" :data-page-status="status ?? 0" />
    <button v-if="status !== 403 && status !== 404" class="c-btn c-btn--secondary c-btn--sm" type="button" :disabled="pending" @click="$emit('retry')">重新加载</button>
  </template>
  <div v-if="!pending && !message && empty" class="c-empty">
    <p>{{ emptyText || '暂无记录。' }}</p>
    <slot />
  </div>
</template>
