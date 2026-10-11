<script setup lang="ts">
defineProps<{ message: string; uncertain: boolean; pending: boolean }>()
defineEmits<{ retry: [] }>()
</script>
<template>
  <div v-if="message" class="c-notice c-notice--error" role="alert">
    <div class="c-notice__body">
      <p>{{ message }}</p>
      <button v-if="uncertain" type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="pending" @click="$emit('retry')">重试上次提交</button>
    </div>
  </div>
</template>
