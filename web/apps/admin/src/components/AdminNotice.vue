<script setup lang="ts">
import CIcon from "@sjtu-ow/ui/CIcon.vue"

withDefaults(defineProps<{
  message?: string
  kind?: "ok" | "info" | "warn" | "error"
}>(), { message: "", kind: "info" })
</script>

<template>
  <div v-if="message" :class="'c-notice c-notice--' + kind" :role="kind === 'error' ? 'alert' : 'status'">
    <CIcon :name="kind === 'warn' || kind === 'error' ? 'alert' : 'info'" />
    <div class="c-notice__body"><p>{{ message }}</p><slot /></div>
  </div>
</template>
