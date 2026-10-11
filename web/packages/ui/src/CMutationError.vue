<script setup lang="ts">
import AuthError from "./AuthError.vue"

withDefaults(defineProps<{
  message: string
  uncertain?: boolean
  pending?: boolean
}>(), { uncertain: false, pending: false })

defineEmits<{ retry: [] }>()
</script>

<template>
  <div v-if="message || uncertain">
    <AuthError :message="message" />
    <p v-if="uncertain" class="text-sm text-fg-2" role="status">
      上次提交还没有确认，重试会继续处理同一次提交。
    </p>
    <button
      v-if="uncertain"
      type="button"
      class="c-btn c-btn--secondary c-btn--sm"
      :disabled="pending"
      @click="$emit('retry')"
    >重试上次提交</button>
  </div>
</template>
