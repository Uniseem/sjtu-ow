<script setup lang="ts">
withDefaults(defineProps<{ title?: string; message?: string; actionUrl?: string; actionLabel?: string }>(), { title: "暂无内容" })
</script>
<template>
  <div class="c-empty">
    <p class="c-empty__title">{{ title }}</p>
    <p v-if="message" class="c-empty__text">{{ message }}</p>
    <a v-if="actionUrl && actionLabel" :href="actionUrl" class="c-btn c-btn--secondary">{{ actionLabel }}</a>
  </div>
</template>
