<script setup lang="ts">
import { RouterView } from "vue-router"
import CContextMenu from "./components/CContextMenu.vue"
import SiteFooter from "./components/SiteFooter.vue"
import SiteHeader from "./components/SiteHeader.vue"
import Toasts from "./components/Toasts.vue"
import WeChatHint from "./components/WeChatHint.vue"
</script>
<template>
  <a
    href="#main"
    class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-surface focus:px-4 focus:py-2"
  >
    跳到正文
  </a>
  <WeChatHint />
  <SiteHeader />
  <RouterView />
  <SiteFooter />
  <Toasts />
  <CContextMenu />
</template>
