<script setup lang="ts">
import AdminNotice from "../AdminNotice.vue"
defineProps<{ message: string; pending: boolean; uncertain: boolean }>()
defineEmits<{ retry: [] }>()
</script>
<template>
  <AdminNotice v-if="message" :message="message" kind="error" />
  <p v-if="pending" class="b-sub" role="status">正在提交…</p>
  <button v-if="uncertain" type="button" class="c-btn c-btn--secondary c-btn--sm" :disabled="pending" @click="$emit('retry')">重试上次提交</button>
</template>
