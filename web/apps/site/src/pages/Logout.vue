<script lang="ts">
export function load() { return { title: "退出登录" } }
</script>
<script setup lang="ts">
import { useHead } from "@unhead/vue"
import { postApiAuthLogout } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import { useApi } from "../api"
import { useViewer } from "../viewer"
import { finishAccountAction, useAccountForm } from "../account-form"
const api = useApi()
const viewer = useViewer()
const { pending, message, submit } = useAccountForm()
useHead({ title: "退出登录 · SJTU-OW" })
function logout() { return submit(async () => { if (viewer.user) await postApiAuthLogout(api); finishAccountAction("/") }) }
</script>
<template>
  <AuthLayout><h1>退出登录</h1><p>确定要退出当前账号吗？</p>
    <form method="post" action="/accounts/logout/" :aria-busy="pending || undefined" @submit.prevent="logout"><AuthError :message="message" /><button type="submit" class="c-btn c-btn--primary" :disabled="pending">退出</button><a href="/" class="c-btn c-btn--quiet">取消</a></form>
  </AuthLayout>
</template>
