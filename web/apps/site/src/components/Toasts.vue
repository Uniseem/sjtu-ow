<script setup lang="ts">
import { toasts, type ToastKind } from "../toasts"
import CIcon from "./CIcon.vue"
import { onMounted, onUnmounted } from "vue"
import { useViewer } from "../viewer"
const viewer = useViewer()
let noticeTimer: ReturnType<typeof setTimeout> | undefined
onMounted(() => { if (viewer.flash) noticeTimer = setTimeout(() => { delete viewer.flash }, 4500) })
onUnmounted(() => { if (noticeTimer) clearTimeout(noticeTimer) })

const ICON: Record<ToastKind, string> = {
  info: "info",
  success: "check-circle",
  error: "x-circle",
  warning: "alert",
}
</script>
<template>
  <div class="c-toasts" aria-live="polite">
    <div v-if="viewer.flash" class="c-toast" role="status"><CIcon name="check-circle" /><span>{{ viewer.flash }}</span></div>
    <div v-for="item in toasts" :key="item.id" class="c-toast" :class="`c-toast--${item.kind}`" role="status">
      <CIcon :name="ICON[item.kind]" />
      <span>{{ item.text }}</span>
    </div>
  </div>
</template>
