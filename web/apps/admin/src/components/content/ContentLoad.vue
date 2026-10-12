<script setup lang="ts">
withDefaults(defineProps<{ pending: boolean; message: string; status?: number | null }>(), { status: null })
defineEmits<{ retry: [] }>()
</script>
<template>
  <p v-if="pending" class="b-sub" role="status" aria-live="polite">正在加载…</p>
  <div v-else-if="message" class="c-notice c-notice--error" role="alert" tabindex="-1" :data-page-status="status ?? 0">
    <div class="c-notice__body">
      <p v-if="status === 403">你没有使用这一页的权限。</p>
      <p v-else-if="status === 404">找不到这项内容。</p>
      <p v-else>{{ message }}</p>
      <button v-if="status !== 403 && status !== 404" class="c-btn c-btn--secondary c-btn--sm" @click="$emit('retry')">重新加载</button>
    </div>
  </div>
</template>
