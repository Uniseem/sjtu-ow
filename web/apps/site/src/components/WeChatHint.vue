<script setup lang="ts">
import { onMounted, ref } from "vue"

// WeChat may block or warn on this unregistered overseas domain (design
// 16.9). Only the browser knows it is WeChat, so the banner appears after
// hydration; SSR paints it hidden, matching the client's first render.
const root = ref<HTMLElement | null>(null)
onMounted(() => {
  if (/MicroMessenger/i.test(navigator.userAgent)) root.value?.removeAttribute("hidden")
})
</script>
<template>
  <div ref="root" class="c-banner c-banner--hint" role="note" hidden>点右上角菜单，在浏览器中打开</div>
</template>
