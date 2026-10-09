<script setup lang="ts">
import { computed } from "vue"
import { RouterView, useRoute } from "vue-router"
import AdminLayout from "./admin/AdminLayout.vue"
import CContextMenu from "./components/CContextMenu.vue"
import SiteFooter from "./components/SiteFooter.vue"
import SiteHeader from "./components/SiteHeader.vue"
import Toasts from "./components/Toasts.vue"
import WeChatHint from "./components/WeChatHint.vue"

const route = useRoute()
const isAdmin = computed(() => route.path.startsWith("/admin"))
</script>
<template>
  <a
    href="#main"
    class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-surface focus:px-4 focus:py-2"
  >
    跳到正文
  </a>
  <template v-if="!isAdmin">
    <WeChatHint />
    <SiteHeader />
    <RouterView />
    <SiteFooter />
  </template>
  <template v-else>
    <AdminLayout>
      <RouterView />
    </AdminLayout>
  </template>
  <Toasts />
  <CContextMenu />
</template>

