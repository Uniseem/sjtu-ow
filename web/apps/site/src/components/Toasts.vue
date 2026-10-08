<script setup lang="ts">
import { toasts, type ToastKind } from "../toasts"
import CIcon from "./CIcon.vue"

const ICON: Record<ToastKind, string> = {
  info: "info",
  success: "check-circle",
  error: "x-circle",
  warning: "alert",
}
</script>
<template>
  <div class="c-toasts" aria-live="polite">
    <div v-for="item in toasts" :key="item.id" class="c-toast" :class="`c-toast--${item.kind}`" role="status">
      <CIcon :name="ICON[item.kind]" />
      <span>{{ item.text }}</span>
    </div>
  </div>
</template>
