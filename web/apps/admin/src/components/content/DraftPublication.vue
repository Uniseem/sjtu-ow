<script setup lang="ts">
withDefaults(defineProps<{ title: string; pending: boolean; missing?: string[] }>(), { missing: () => [] })
defineEmits<{ confirm: []; cancel: [] }>()
</script>
<template>
  <section class="c-notice c-notice--info" role="region" aria-label="发布确认">
    <div class="c-notice__body">
      <h2 class="b-section__title">发布{{ title }}</h2>
      <p v-if="missing.length">还缺：{{ missing.join('、') }}。补齐以后再发布。</p>
      <p v-else>发布后，网站上的内容会更新为这份草稿。</p>
      <div class="b-actions">
        <button type="button" class="c-btn c-btn--primary" :disabled="pending || missing.length > 0" @click="$emit('confirm')">{{ pending ? '正在发布…' : '确认发布' }}</button>
        <button type="button" class="c-btn c-btn--secondary" :disabled="pending" @click="$emit('cancel')">继续编辑</button>
      </div>
    </div>
  </section>
</template>
