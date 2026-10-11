<script lang="ts">
import type { LoadCtx } from "../router"
import { PageRedirect, safeNext } from "@sjtu-ow/shared/navigation"
export async function load(ctx: LoadCtx) {
  const next = safeNext(ctx.query.next)
  if (!(await ctx.viewer()).user) throw new PageRedirect(next)
  return { title: "退出登录", next }
}
</script>
<script setup lang="ts">
import { useHead } from "@unhead/vue"
import { inject } from "vue"
import { postApiAuthLogout } from "@sjtu-ow/api"
import AuthLayout from "@sjtu-ow/ui/AuthLayout.vue"
import AuthError from "@sjtu-ow/ui/AuthError.vue"
import { useApi } from "../api"
import { useViewer } from "../viewer"
import { finishAccountAction, useAccountForm } from "../account-form"
const api = useApi()
const data = inject<{ next: string }>("page-data")
const viewer = useViewer()
const { pending, message, submit } = useAccountForm()
useHead({ title: "退出登录 · SJTU-OW" })
function logout() { return submit(async () => { if (viewer.user) await postApiAuthLogout(api); finishAccountAction(safeNext(data?.next)) }) }
</script>
<template>
  <AuthLayout><h1>退出登录</h1><p>确定要退出当前账号吗？</p>
    <form method="post" action="/accounts/logout/" :aria-busy="pending || undefined" @submit.prevent="logout"><AuthError :message="message" /><button type="submit" class="c-btn c-btn--primary" :disabled="pending">退出</button><a href="/" class="c-btn c-btn--quiet">取消</a></form>
  </AuthLayout>
</template>
