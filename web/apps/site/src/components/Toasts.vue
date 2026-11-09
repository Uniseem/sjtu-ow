<script setup lang="ts">
import { beginToastLifetime, toasts, type ToastKind, type ToastPhase } from "../toasts"
import CIcon from "./CIcon.vue"
import { onMounted, onUnmounted, ref, watch, type WatchStopHandle } from "vue"
import { useViewer } from "../viewer"
const viewer = useViewer()
const flashPhase = ref<ToastPhase>("visible")
let cancelFlash: (() => void) | undefined
let stopFlash: WatchStopHandle | undefined
onMounted(() => {
  stopFlash = watch(() => viewer.flash, value => {
    cancelFlash?.()
    flashPhase.value = "visible"
    if (value) cancelFlash = beginToastLifetime(() => { flashPhase.value = "leaving" }, () => { delete viewer.flash })
  }, { immediate: true })
})
onUnmounted(() => { cancelFlash?.(); stopFlash?.() })

const ICON: Record<ToastKind, string> = {
  info: "info",
  success: "check-circle",
  error: "x-circle",
  warning: "alert",
}
</script>
<template>
  <div class="c-toasts" aria-live="polite">
    <div v-if="viewer.flash" class="c-toast" :class="{ 'is-leaving': flashPhase === 'leaving' }" role="status"><CIcon name="check-circle" /><span>{{ viewer.flash }}</span></div>
    <div v-for="item in toasts" :key="item.id" class="c-toast" :class="[`c-toast--${item.kind}`, { 'is-leaving': item.phase === 'leaving' }]" role="status">
      <CIcon :name="ICON[item.kind]" />
      <span>{{ item.text }}</span>
    </div>
  </div>
</template>
