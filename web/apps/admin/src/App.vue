<script setup lang="ts">
import { computed, onErrorCaptured, ref, watch } from "vue"
import { useRoute } from "vue-router"
import AdminTop from "./components/AdminTop.vue"
import AdminError from "./components/AdminError.vue"
import AdminNotice from "./components/AdminNotice.vue"
import { useAdminSession } from "./core/session"
import { adminFailure, type AdminFailure } from "./core/error"
const route = useRoute()
const session = useAdminSession()
const failure = ref<AdminFailure | null>(null)
const reloadKey = ref(0)
const loginHref = computed(() => "/accounts/login/?next=" + encodeURIComponent(route.fullPath))
watch(() => route.fullPath, () => { failure.value = null })
onErrorCaptured(error => { failure.value = adminFailure(error); return false })
function retry(): void { failure.value = null; reloadKey.value++ }
</script>
<template>
  <a href="#main" class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:bg-surface focus:px-4 focus:py-2">跳到正文</a>
  <AdminTop />
  <AdminNotice v-if="session.message.value" :message="session.message.value" />
  <AdminError v-if="failure" :failure="failure" :login-href="loginHref" @retry="retry" />
  <RouterView v-else :key="route.fullPath + ':' + reloadKey" />
</template>
